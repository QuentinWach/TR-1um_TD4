# hdl/ — RTL 記述

```
hdl/
├── rtl/   Verilog RTL（td4 コア / SoC 2種）
└── tb/    テストベンチ
```

| ファイル | 内容 |
|---|---|
| `rtl/td4_core.v` | TD4 コア。A/B/OUT 4bit + PC 4bit + Cフラグ + 4bit加算器。命令メモリは外付け I/F |
| `rtl/td4_soc_rom.v` | コア + **16×8 マスクROM**（組合せ論理、プログラム固定）。最小構成 |
| `rtl/td4_soc_ff.v` | コア + **16×8 書換可能メモリ**（ニブル書込・メモリもリセット付き）。tt-td4 と同方式 |
| `rtl/td4_mem.v` | **16×8 命令メモリ（差し替え点）**。非同期リード / 8bit一括ライト / リセット無し |
| `rtl/td4_soc_arr.v` | **★本命**。コア + `td4_mem`。実装時に `td4_mem` をカスタム RFCELL アレイへ差し替える |
| `tb/tb_td4_core.v` | 全12命令 + キャリー + JNC 分岐 + PC ラップの 19項目チェック |
| `tb/tb_td4_soc_arr.v` | Load モードで5命令書込 → Exec モードで OUT 列を確認 |

`td4_soc_ff` と `td4_soc_arr` の違い（詳細は `../reference/07_memory_array.md` §3）:
`td4_soc_arr` は **下位ニブルをステージングして 8bit 一括ライト**するので
書込ワードラインが行あたり1本で済み、**メモリにリセットを持たせない**。
合成後の組合せセルが **536 → 291** に減り、アレイ化の下地になる。

**記述ルール・トップ I/F・検証フローは `../reference/06_design_policy.md` §2–§4 に集約。**

要点だけ:
1. `always @(posedge CLK or negedge RSTN)` のみ（単相・CPI=1・ステートマシン無し）
2. **`inout` を使わない**（TD4 は入力ポートと出力ポートが別なので双方向バス不要）
3. 命令メモリはブラックボックス化し、FF実装 ⇔ RFCELL アレイを差し替えられるようにする
4. 出力は必ずレジスタ出力（`OUT[3:0]` / `CF`）

## 実行

```sh
# 機能検証
iverilog -g2012 -o tb.vvp hdl/tb/tb_td4_core.v hdl/rtl/td4_core.v && vvp tb.vvp
# → === ALL TD4 INSTRUCTION TESTS PASSED ===
iverilog -g2012 -o tb2.vvp hdl/tb/tb_td4_soc_arr.v \
         hdl/rtl/td4_soc_arr.v hdl/rtl/td4_mem.v hdl/rtl/td4_core.v && vvp tb2.vvp
# → === td4_soc_arr LOAD+EXEC TEST PASSED ===

# 機能検証 + 面積見積り 一括
sh scripts/syn.sh
```

## REG4x16 — メモリアレイのスイッチレベル検証

`rtl/reg4x16.v` は RTL ではなく、**LVS ソースネットリスト
`spice/REG4x16_src.spi`（LVS クリーン）をトランジスタ 1 個ずつ 1:1 で
書き起こしたスイッチレベル記述**。動作モデルではないので、
これが通ることは「その配線でちゃんと動く」ことの確認になる。

| SPICE | Verilog |
|---|---|
| `MP <d> <g> <s> <b> PMOS` | `pmos (<d>, <s>, <g>)` |
| `MN <d> <g> <s> <b> NMOS` | `nmos (<d>, <s>, <g>)` |
| トランスファゲート | `tranif0`(PMOS側) + `tranif1`(NMOS側) — **双方向** |

トランスファゲートを双方向で書いてあるので、ビット線のハイインピーダンス・
多重駆動・向きの誤りはそのまま `x` として現れる。階層とポート順も SPICE と同じ
（`TLAT` / `DEC2` / `REGBUF` / `ADDBUF` / `REG4x16`、1,076 Tr）。

```sh
sh hdl/run_reg4x16.sh        # 実行
sh hdl/run_reg4x16.sh -w     # VCD も出す (reg4x16.vcd)
```

### 検証項目（`tb/tb_reg4x16.v`）

| | 内容 |
|---|---|
| T1 | 全ワード書込 → 順・逆順で読出（値と番地を違えてある） |
| T2 | ウォーキング 1 / 0 — 4 本のビット線が独立か |
| T3 | **デコーダ一意性** — 全語を `0101` で埋めて 1 語だけ `1010` に書換、他 15 語が不変か。16 通り全部 |
| T4 | WEB 極性 — `WEB=1` では書けない／落とせば書ける |
| T5 | 保持 — 全書込後にアドレス順でない順序で読み直す |
| 毎回 | 読出値に `x`/`z` が無いこと（`===` 比較）と **RD がちょうど 1 本**だけ立っていること |
| 常時 | **WR が同時に 2 本以上立たないこと**（多重書込の検出） |

**結果: PASS 1024 / FAIL 0 / WR 多重アサート 0。**

### タイミングについて分かったこと（I1 参考出力）

- **アドレスと WEB を同時に動かすのは安全。** WE バッファが INV 2 段、
  アドレス補が INV 1 段なので、`WEB` が効く頃にはアドレスが確定している。
- **`WEB=0` のままアドレスを動かすと 2 ワードが書き換わる。** レベル書込なので、
  開いている間に通過したワードは全部書かれる。
  **アドレス確定 → `WEB` 立下げ → `WEB` 立上げ → 次のアドレス**の順を守ること。

> 次段: 同じベクタを IRSIM（`../irsim/`）に移して、レイアウト抽出ネットリストで
> 遅延つきの検証を行う。Verilog 版は論理と接続、IRSIM 版は速度とマージンを見る。


## オペコード

`op[3:2]` = 書込先（00:A / 01:B / 10:OUT / 11:PC）、
`op[1:0]` = セレクタ（00:A / 01:B / 10:IN / 11:0、ジャンプ群では強制 0）。
一覧は `../reference/01_TD4_spec.md` §2。

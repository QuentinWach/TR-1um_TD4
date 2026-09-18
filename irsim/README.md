# irsim/ — スイッチレベルシミュレーション

## REG4x16 / REG8x16（Nbit x 16word レジスタファイル）

**LVS がクリーンになったソースネットリスト `spice/REG4x16_src.spi` をそのまま
IRSIM に持ち込んで、実 R/C モデルで全レジスタアクセスを検証する。**

```sh
sh irsim/run_regx16.sh      # 4bit 全レジスタアクセス検証（合否まで表示）
sh irsim/run_regx16.sh 8    # 8bit
sh irsim/run_timing.sh      # 読出アクセス時間 / 書込レイテンシ / 最小 WEB パルス幅（4bit）
```

| ファイル | 内容 |
|---|---|
| `TR-1um.prm` | TR-1um 実モデルから校正したパラメータ（TR-1um_Async_I2C と共通） |
| `reg4x16.sim` / `reg8x16.sim` | `$APRTOOLS/apr/spi2sim.py` が LVS ソースから生成（1,076 Tr / 426 ノード、1,876 Tr / 705 ノード） |
| `reg4x16.cmd` / `reg8x16.cmd` | `$APRTOOLS/apr/gen_irsim_cmd.py --bits N` が生成。**`hdl/tb/tb_regx16.v` と同じベクタ・同じ期待値** |
| `reg4x16_timing.cmd` | `scripts/gen_irsim_timing.py` が生成。タイミング測定用 |
| `run_regx16.sh` / `run_timing.sh` | 実行 → 判定まで一発 |

### 時間分解能

```
stepsize 1     -> 1ns。以降の `s <n>` の n はすべて ns
settle 10      -> TLAT の帰還ノード(n2/n3)が背中合わせインバータなので、
                  一瞬の競合で X 判定されないよう落ち着く時間を与える
```

### 合否の出し方

IRSIM の `.cmd` 言語には条件分岐も算術も無いので、テストベンチのように
自前で pass/fail を数えられない。読出のたびに

```
print CHECK tag=T3_unique add=0101 exp=1010   ← 何を期待しているか
assert QV 1010                                 ← IRSIM 自身の判定（外れたらログに出る）
d AV QV                                        ← 実際の番地と値
```

の 3 行を出すので、**ログだけで完結して集計できる**（期待値ファイルは不要）。
`$APRTOOLS/apr/check_irsim_log.py` がタグ別に集計する。

### 結果

```
  T1_readback     PASS   16   FAIL    0     全ワード書込/読出
  T1_reverse      PASS   16   FAIL    0     逆順読出
  T2_walk1        PASS   64   FAIL    0     ウォーキング1
  T2_walk0        PASS   64   FAIL    0     ウォーキング0
  T3_unique       PASS  256   FAIL    0     デコーダ一意性（16通り全部）
  T4_no-write     PASS   16   FAIL    0     WEB=1 では書けない
  T4_write-ok     PASS   16   FAIL    0     WEB=0 なら書ける
  T5_hold         PASS   64   FAIL    0     保持
  合計  PASS 512 / FAIL 0    assertion failed 0 件
```

REG8x16（`sh irsim/run_regx16.sh 8`）は T2 が倍になるので **PASS 640 / FAIL 0**。

**どちらも Verilog 版（`hdl/run_regx16.sh [4|8]`）と完全に一致。** 読出に X は 1 回も出ていない。

### タイミング実測（TR-1um.prm, 1ns 分解能）

| | 値 |
|---|---:|
| 読出アクセス時間 `ADD` 変化 → `Q` 確定（0→1） | **14 ns** |
| 同（1→0） | 12 ns |
| 書込レイテンシ `WEB`↓ → `Q` 反映 | **12 ns** |
| 最小 `WEB` パルス幅 | 3 ns |

> **この数字は配線容量を含まない。** `.sim` に配線形状を持たせていないので、
> ビット線（M2 878 µm）やワードラインの容量は入っていない。実物はこれより遅い。
> ここで見ているのは「素子の R/C での論理と接続」であって、最終的な速度は
> レイアウト抽出（寄生込み）か SPICE で確認すること。
> TD4 は CPI=1 でクロックも遅いので、14 ns 程度なら余裕は十分ある。

### 分かったこと（タイミング制約）

- **アドレスと `WEB` を同時に動かしても安全。** WE バッファが INV 2 段、
  アドレス補が INV 1 段なので、`WEB` が効く頃にはアドレスが確定している。
- **`WEB`=0 のままアドレスを動かすと、通過したワードが全部書き換わる。**
  レベル書込なので当然。**アドレス確定 → `WEB` 立下げ → `WEB` 立上げ → 次のアドレス**
  の順を守ること。Verilog 版と IRSIM 版で同じ結果になった。

### 既知の警告

```
There are too many transistors in parallel (> 30)
      XT14_0.n3 / XT14_0.n2
```

IRSIM の `MAX_PARALLEL`（`base/globals.h`、既定 30）にぶつかっている。
**電源投入直後、ワードラインがまだ X で全 16 行のパスゲートが「導通かもしれない」
状態のときに、ビット線経由でアレイ全体が 1 つのステージになるため。**
アドレスが確定すれば 1 行しか導通しないので実害は無く、実際 512 項目すべてが
Verilog 版と一致している。気になる場合は `MAX_PARALLEL` を 64 にして
IRSIM をビルドし直せば消える。

---

## TD4 コア — 全 12 命令トレース（U14）

```sh
export APRTOOLS=<PDK と道具を置いた場所>/TR-1um_APRtools
sh irsim/run_td4.sh        # 実行 -> 合否まで一発
sh irsim/run_td4.sh -v     # 全サイクルを 1 行ずつ
```

| ファイル | 内容 |
|---|---|
| `td4_soc_arr.sim` | `$APRTOOLS/apr/spi2sim.py` が `layout/chip/simulation/td4_soc_arr_nrow_fm.spice`（LVS ソース）から生成。**3,597 Tr / 1,386 ノード** |
| `td4_soc_arr.cmd` | `scripts/gen_irsim_td4.py` が生成 |
| `TR-1um.prm` | REG4x16 と共通 |
| `run_td4.sh` | `.sim` / `.cmd` の作り直し → 実行 → 判定 |

### 何を流すか

`hdl/tb/tb_td4_core.v` は `rom_data` を**直接叩いて** 12 命令を出すので、
**そのままでは実装に持ち込めない** — `td4_soc_arr_nrow_fm` に `rom_data` の
ピンは無く、命令は Load モードで書いたメモリから出てくる。そこで
「PC が進む順に並んだプログラム」に書き直した。

- **P1**（16 命令 / 16 サイクル）— 12 命令のうち 11 種、キャリー発生、
  JNC の**飛ぶ/飛ばない両方**、PC の 15 → 0 ラップ。
  14 番地に `OUT Im 15` を置いてあり、**通ってはいけない**（通れば OUT=15 で落ちる）
- **P2**（4 命令 / 5 サイクル）— `JMP` と飛び先の確認、自己ループで停止

期待値は手計算ではなく `gen_irsim_td4.py` の参照モデル（`Sim`）が解く。
**同じ表から Verilog TB `hdl/tb/tb_td4_soc_arr_isa.v` も生成する**ので、
論理（Verilog）とスイッチレベル（IRSIM）が食い違うことがない。

### ★ 入力の BUFTH は IRSIM では解けない（迂回している）

このライブラリは外部入力を**全部 `BUFTH`（シュミットトリガ）で受ける**
（`insert_bufth.py`。立上り 3.43 V / 立下り 1.44 V、ヒステリシス 2.00 V —
`$APRTOOLS/docs/10_pdk_facts.md` §2）。**IRSIM はこれを解けない。**

ヒステリシスの帰還 MOS が**自分の出力ノード `n2` でゲートされている**ので、
初期値 X から抜けられない:

```
n2=X -> 帰還 MP0/MP1 が「導通するかも」-> n3 が vdd と vss の両方に
        引かれて X -> n2=X -> …
```

しかも帰還（5.1 µm × 2 並列）の方が入力側（5.1 µm の直列 2 段）より太いので、
強さでも決まらない。2026-09-17 に実際に踏んだ — 入力 9 本が全部 X になり、
**21 サイクル全部 FAIL / assertion failed 84 件**。

→ `.cmd` はピンと**その BUFTH の出口**（`clk_buf` / `d_buf0` …）を
**同じ値で駆動する**。`run_td4.sh` は毎回 `probe_bufth.cmd`（BUFTH 1 個だけ）を
先に走らせて、`Y` が X のままであることを**その場で測る**。
もし解けるようになっていたら迂回は要らないので、この節ごと見直すこと。

**BUFTH 9 個（90 Tr）は検査の外に出る。** 残り 3,507 Tr — コアと
メモリアレイ全部 — は実物の接続で走る。BUFTH 自体の閾値は ngspice で
測ってある。

### 見える信号

`out_port[3:0]` と `cflag_o` はトップピン。**`u_core_reg_a[3:0]` と
`u_core_reg_b[3:0]` は内部だが LVS ソースに名前が残っている**ので
IRSIM から直接見られる（角括弧は `spi2sim.py` が潰すので `u_core_reg_a0`）。
`pc` と `ld_addr[3:1]` は合成で番号に化けていて見えないが、
どの命令が実行されたかは OUT / A / B の並びで決まるので足りる。

### 時間分解能

半周期 100 ns（5 MHz）。`syn/sta` の実測 `reg->reg` 60.307 ns に対し 3 倍以上。
`.sim` は配線容量を持たないので IRSIM は実物より速く出る — **速度の根拠には
使わない**（速度は STA と ngspice で見る）。

### 合否の出し方

1 サイクルごとに `print TD4CHECK tag=... expA=... expB=... expO=... expC=...` を
刻み、`assert` でその場で判定し、`d AV BV OV CV` で実際の値を残す。
`scripts/check_irsim_td4_log.py` が集計し、**12 命令ぜんぶ通ったか**も数える
（通っていなければ「PASS だが検査していない」なので落とす）。

### 残っているもの

- 命令メモリ（RFCELL アレイ版）の読み書きマージン確認
- レイアウトの寄生を入れるなら Magic の `extract` → `ext2sim` 経由にする
  （いまの `.sim` は LVS ソースからで、**配線容量が入らない**）

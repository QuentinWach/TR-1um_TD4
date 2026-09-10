# lef/ — 抽象化ライブラリ（LEF / Liberty）

TR-1um PDK には LEF も Liberty (.lib) も含まれていないので、ここで整備する。

| ファイル | 内容 |
|---|---|
| `TR-1um_STDCELL.gds` | セルライブラリ本体（レイアウト） |
| `TR-1um_tech.lef` | LAYER / VIA / SITE 定義 — `scripts/mklef.py` で生成 |
| `TR-1um_cells.lef` | 全 MACRO（標準セル + アレイセル + `REG4x16`）— 同上 |

## 生成

```sh
python3 scripts/mklef.py lef/TR-1um_STDCELL.gds -o lef
```

GDS を更新したら毎回これを流す。最後に「ピンの入っていないセル」が一覧で出る。

## レイヤ / 規約（GDS 実測）

| GDS | 意味 | LEF |
|---|---|---|
| (13,0) | M1（横配線・電源レール） | `METAL1` W 1.8 / S 1.4 / pitch 3.2 |
| (19,0) | V1 | `VIA1` |
| (20,0) | M2（縦配線・ピンパッド） | `METAL2` W 3.0 / S 2.0 / pitch 5.0 |
| (49,1) | 信号ピン形状 | `PIN ... PORT` |
| (48,1) | 電源レール / 貫通ワードラインのラベル | `USE POWER/GROUND SHAPE ABUTMENT` |
| (235,0) | セル境界 | `SIZE` |
| (140,0) | N-well（境界を ±6.3 / +4.0 はみ出す） | — |

- **SITE `TR1UM` = 5.4 × 64.8 µm**（ポリピッチ × 標準セル行高）。
  標準セルの幅はすべて `10.8 + n × 5.4` なのでこのサイトに乗る。
- **`TLAT` / `TAP2S` / `REGBUF` / `DEC0` は行高 59.4 µm** でサイトに乗らないため
  `CLASS BLOCK` として出している（アレイ専用セル。P&R では使わない）。
- `REG4x16` は `CLASS BLOCK`、**SIZE 248.400 × 933.000 µm**。
  ハードマクロなので `OBS` で M1/M2 とも全面をふさいである。

## 現状と TODO

- [x] 標準セル 26 種の MACRO（ピン・OBS 付き）
- [x] `REG4x16` の外形と OBS
- [ ] **`REG4x16` のピン** — GDS のトップにまだラベル / (49,1) 形状が無い。
      入れてから `mklef.py` を流し直すと `PIN` が入る
- [ ] `TLAT` の `WR/WRB/RD/RDB` を (48,1) → (49,1) へ（現在は貫通 M1 として拾っている）
- [ ] `DEC0` / `ADDBUF` の信号ラベル（(49,1) の形状はあるがテキストが無い）
- [ ] Liberty (`.lib`) — タイミングは SPICE 特性化が要るので後回し。
      Yosys 見積り用の簡易 genlib は `../scripts/tr1um.genlib` にある

## Liberty を作るかどうか

`td4_soc_rom`（マスクROM版）は 76 セル / 3 行なので**手配置で十分**で、
LEF/Liberty は「TD4 を作るため」ではなく **C4004 に向けた投資**という位置づけ。
`td4_soc_arr` の論理部（FF 25 / 組合せ 83、約 108 セル）で P&R フローを通しておくと、
そのまま C4004（2,000 ゲート超）に使える。

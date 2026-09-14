# layout/chip/simulation/ — チップレベルの LVS

```
tr_1um_TD4.spice       ソース（設計意図）。scripts/pnr/mkchipnet.py が生成
tr_1um_TD4_lay.spice   レイアウトからの抽出。scripts/pnr/lvs_pnr.py -o
lvs_report.txt         比較の結果
```

## 流し方

```sh
python3 scripts/pnr/add_top_pins.py          # step2 -> step3（ボンドパッドにピン）
python3 scripts/pnr/mkchipnet.py             # ソースを作る
python3 scripts/pnr/lvs_pnr.py \
    layout/chip/step3_top_pins.gds tr_1um_TD4 \
    layout/chip/simulation/tr_1um_TD4.spice \
    -o layout/chip/simulation/tr_1um_TD4_lay.spice
```

現状（2026-09-14）:

```
レイアウト: circuit 1 / top pin 16 / device 4225 / net 1503
ソース    : circuit 1 / top pin 16 / device 4225 / net 1503
=== LVS: **一致**
```

## ソースの作り

サブサーキット 2 個とポート表だけ。

```
.subckt tr_1um_TD4 P1 P2 P3 P4 P5 P6 P7 VSS P9 P10 P11 P12 P13 P14 P15 VDD
x1 … OSS_FRAME_GIO
x2 … td4_soc_arr_nrow_fm
.ends
```

* コア `layout/portrait/simulation/td4_soc_arr_nrow_fm.spice`（単体で LVS 済み）
* フレーム `lef/simulation/OSS_FRAME_GIO_nocombine.spice`
* 網の張り方 `layout/chip/gio_connections.json`

両インスタンスのポート順は**それぞれの `.subckt` 行から読む**。決め打ちしない。

## 踏んだ穴

* **フレームは `combine_devices()` を掛けていない方を使う。** `lvs_pnr.py` は
  DFFRB で KLayout が内部エラーを出すため両側とも combine しない方針なので、
  combine 済みの `lef/simulation/OSS_FRAME_GIO.spice`（ngspice 用。こちらは
  触らない）を混ぜると素子数が **316 個**ずれる（レイアウト 4225 /
  ソース 3909）。`scripts/mkframespice.py --no-combine` で作り直したのが
  `OSS_FRAME_GIO_nocombine.spice`。
* **トップのポートは 16 本ちょうど。** レイアウト側は
  `scripts/pnr/add_top_pins.py` がボンドパッドに M2PIN (49,1) 3 µm 角 +
  TXM2 (49,0) のラベルを打つ。本数が合わないと KLayout はグラフマッチに
  入らず、全ピンが将棋倒しで不一致になる。
* フレームのグランドは `VSS`、コアは `GND`。同じ 1 本で、チップでの名前は
  ボンドパッドのラベルに合わせて `VSS`。
* 入力パッドの `OUT` は浮くので `VSS` に落としてある
  （`route_chip.py` が実際に落としているのと同じ）。

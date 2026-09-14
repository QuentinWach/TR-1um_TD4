# layout/chip/simulation/ — チップレベルの LVS

```
tr_1um_jun1okamura.spice       ソース（設計意図）。scripts/pnr/mkchipnet.py が生成
tr_1um_jun1okamura_lay.spice   レイアウトからの抽出。scripts/pnr/lvs_pnr.py -o
lvs_report.txt         比較の結果
```

## 流し方

```sh
python3 scripts/pnr/add_top_pins.py          # step2 -> step3（ボンドパッドにピン）
python3 scripts/pnr/place_logo.py            # step3 -> step4（ロゴ）
python3 scripts/pnr/mkchipnet.py             # ソースを作る
python3 scripts/pnr/lvs_pnr.py \
    layout/chip/step4_final.gds tr_1um_jun1okamura \
    layout/chip/simulation/tr_1um_jun1okamura.spice \
    -o layout/chip/simulation/tr_1um_jun1okamura_lay.spice
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
.subckt tr_1um_jun1okamura P1 P2 P3 P4 P5 P6 P7 VSS P9 P10 P11 P12 P13 P14 P15 VDD
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
* **ラベルだけではサブサーキットのピンが生えない。** パッドの金属は
  `OSS_FRAME_GIO` の中にあるので、トップにラベル（と M2PIN）しか置かないと、
  抽出器によっては「トップから物理的に触っていない」と見なされる。PDK の
  LVS ランセットで 2026-09-14:

      No equivalent pin P10 from reference netlist found in netlist.
      This is an indication that a physical connection is not made to the
      subcircuit.

  P10/P11/P12/P13/P15 -- **出力パッド 5 本ちょうど**。入力パッドは `P<n>`
  端子までコアから配線が来ているので触れているが、出力パッドはコアが
  `OUT<n>` を駆動するだけで、ボンドパッドの網にはトップから何も触れて
  いなかった。`scripts/klayout_extract.py` はラベル層を M2 に繋ぐので
  44 ピン全部見えていて、こちらの LVS では気づけなかった。
  `add_top_pins.py` が**同じ 3 µm 角を M2 (20,0) にも置く**ようにして解決
  （素の抽出でフレームのピンが 39 -> 44 に増えるのを確認）。
* フレームのグランドは `VSS`、コアは `GND`。同じ 1 本で、チップでの名前は
  ボンドパッドのラベルに合わせて `VSS`。
* 入力パッドの `OUT` は浮くので `VSS` に落としてある
  （`route_chip.py` が実際に落としているのと同じ）。

## ngspice（抽出ネットリストでの動作確認）

```
tr_1um_jun1okamura_ext.spice   抽出（scripts/klayout_extract.py、combine 済み・ネット名付き）
tr_1um_jun1okamura_sim.spice   それを ngspice 用に直したもの（scripts/frame2sim.py）
tb_tr_1um_jun1okamura.spi      テストベンチ（scripts/pnr/gen_chip_tb.py）
chip_tb.log            ngspice の出力
chip_tb.png            波形（scripts/pnr/check_chip_sim.py）
```

### 流し方

```sh
python3 scripts/klayout_extract.py layout/chip/step4_final.gds tr_1um_jun1okamura \
    -o layout/chip/simulation/tr_1um_jun1okamura_ext.spice
python3 scripts/frame2sim.py layout/chip/simulation/tr_1um_jun1okamura_ext.spice \
    -o layout/chip/simulation/tr_1um_jun1okamura_sim.spice
python3 scripts/pnr/gen_chip_tb.py --period 100 --cycles 12
cd layout/chip/simulation && ngspice -b tb_tr_1um_jun1okamura.spi > chip_tb.log
cd - && python3 scripts/pnr/check_chip_sim.py --t-exec 1800
```

**LVS 用の `tr_1um_jun1okamura_lay.spice` は ngspice には使えない。** あれは
`lvs_pnr.py -o` の出力で、トップに `.SUBCKT` のポートが無く、ネット名が
番号で、素子が `M...`（PDK の PMOS/NMOS は `.model` ではなく**サブサーキット**
なので `XM` でないといけない）。`klayout_extract.py` はそのどれもやってくれる。

`frame2sim.py` が要るのは 2 つの理由:

* **ESD 素子はモデルが別物。** `OSS_PCH_DRV` / `OSS_PCH_ESD` は `MPE`、
  `OSS_NCH_DRV` / `OSS_NCH_ESD` は `MNE`（抽出では PMOS 側が ESD でも
  `PMOS` と書かれるので、囲っているサブサーキット名で判定する）。
* ネット名の `\$8` や `GND|gnd`、ダイオードの `A=`/`P=` 表記を直す。

### テストベンチ

`hdl/tb/tb_td4_soc_arr.v` と同じ手順を**ボンドパッドに対して**流す。

    リセット -> Load モードで 5 命令書込 -> Exec モードで走らせる

    0: 1011_0011  OUT 3
    1: 1011_0110  OUT 6
    2: 1011_1100  OUT 12
    3: 1011_1000  OUT 8
    4: 1111_0000  JMP 0

1 命令 = 下位ニブル（即値）-> 上位ニブル（オペコード）の 2 回書込。値は
negedge で置いて posedge で取り込む。出力パッドには 10 pF を付けている。

### 結果（2026-09-14）

クロック 100 ns（10 MHz、STA の `reg->reg` 63.09 ns = 15.85 MHz に対して余裕）、
3,150 ns を 0.5 ns 刻み。**12 サイクルすべて期待どおり**:

    OUT = 3, 6, 12, 8, 8, 3, 6, 12, 8, 8, 3, 6   CF は終始 0

JMP のサイクルは OUT が動かないので 1 周 5 サイクルで `[3, 6, 12, 8, 8]`
になる（Verilog の TB は `i%4==3` で 1 サイクル読み飛ばしていて、同じことを
別の書き方で見ている）。実行時間は 4,225 素子で約 1 分 52 秒。

`chip_tb.raw.csv`（2.5 MB）は波形の生データ。git には入れていない。

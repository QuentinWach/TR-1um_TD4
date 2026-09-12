# scripts/pnr/ — 配置配線

`TR-1um_SCLK_SPI/scripts/`（さらにその元は `TR-1um_Async_I2C/script/`）の
フローを TD4 に移したもの。**アルゴリズムは触らない**方針も同じで、
設計固有の値は `td4_config.py` 1 本に集めてある。

## 動かす場所

`gdstk` と `klayout` の Python バインディングが要る。
**Mac には両方とも入っていない**ので、配置配線そのものはクラウド側で回し、
成果物の GDS を Mac に置いて KLayout GUI で見る、という分担になる。
Mac で動くのは GDS を読まないもの（`td4_config.py` の整合チェックなど）だけ。

| | Mac | device_bash の Linux VM | クラウド |
|---|---|---|---|
| `gdstk` | ✗ | ✗ | ✓ |
| `klayout` (python) | ✗（GUI はある） | ✗ | ✓ |
| `ngspice` / `yosys` | ✓ | ✗ | ✓ |

## STEP と成果物

**STEP ごとに GDS を残す。** 途中で何が起きたかを GDS で追えるようにするため。

| STEP | 内容 | 成果物 |
|---|---|---|
| — | セル寸法表 | `layout/cell_info.json` |
| step1 | 行割当（FM 風分割） | `layout/step1/place_step1_rows.gds` |
| step2 | 行内順序（バリセンタ反復） | `layout/step2/place_step2_ordered.gds` |
| step3 | TAP 挿入 | `layout/step3/place_step3_tap.gds` |
| step4 | FILL 挿入（配置の最終） | `layout/step4/place_step4_fill.gds` |
| step5 | 配置 JSON 変換 + 配置 GDS | `layout/step5/route_step_1_placement.gds` |
| step6 | チャネル配線 | `layout/step6/route_step_2_*.gds` |
| step7 | 短絡のリップアップ/再配線 | `layout/step7/route_step_3_ripup_reroute.gds` |
| step8 | トップピンのコア端引き出し | `layout/step8/route_step_4_top_pins.gds` |
| step9 | VDD/VSS チップレベルピン | `layout/step9/route_step_5_power_pins.gds` |
| step10 | チャネル圧縮 | `layout/step10/route_step_6_squeezed.gds` |

```sh
python3 scripts/insert_bufth.py out/td4_soc_arr_mw.v out/td4_soc_arr_pnr.v
python3 scripts/pnr/mkcellinfo.py        # セル寸法表
python3 scripts/pnr/place.py             # step1..step4
python3 scripts/pnr/verify_placement.py  # 配置の検証
python3 scripts/pnr/plot_placement.py    # layout/placement_steps.png
```

## フロアプラン

`td4_config.py` が単一ソース。import のたびに `check()` が内部矛盾を潰す。

| | 値 |
|---|---|
| コア | **1598.4 × 1597.0 µm** |
| 行 | 5 行 × 1177.2 µm（218 サイト）、行高 59.4 |
| 行の実効幅 | 1101.6 µm/行（TAP 4 + 優先コリドー 3 を引いた残り） |
| セル | 140 個 / 幅合計 4,303.8 µm（`BUFTH` 9 個を含む）→ 充填率 79% |
| チャネル | `[280, 250, 290, 220, 130, 130]` µm（下から） |
| マクロ | `REG8x16` 399.6 × 933.0 @ (1198.8, 280.0) |
| 開口 | 1840 µm（余裕 243 µm） |

### 旧案から変えた 2 点（どちらも実測で決まった）

**1. マクロを ch[0] ぶん持ち上げた。**
`REG8x16` の信号ピン 21 本（`ADD[3:0]` `WEB` `D[7:0]` `Q[7:0]`）は
**全部 M2 で下辺 1 列** (y 1.1…4.5)、しかも OBS が M1/M2 とも全面。
旧案はマクロ底面 = コア底面だったので、**ピンの真下に配線空間が無く到達
できなかった**（左から入ろうとすると最大 369 µm ぶん OBS の上を走ることになる）。
マクロを ch[0] だけ持ち上げて**底面を row0 の底面と面一**にすると、
マクロのピン列と row0 のセルのピン列が同じ ch[0] を向く。
チャネルルータから見ると「マクロは 933 µm 高い row0 のセル」になる。

**2. コア幅を 1620 → 1598.4 µm に削った。**
フレーム開口は幅 1600 µm を 0.1 µm でも超えると四隅の `OSS_FRAME_CNR` に
当たって **1840 → 1600 µm に縮む**（`td4_config.frame_opening()` が
`OSS_FRAME_GIO` の OBS から毎回実測する）。旧案の 1620 はこの崖の向こう側。
行幅を 21.6 µm（4 サイト）削るだけで**チャネル予算が 240 µm 増える**。
行の実効幅は 1123.2 → 1101.6 µm で、必要な 4,012 µm に対し 5 行で 5,508 µm あるので
損は無い。

> **ダイは 2500 × 2500 µm で固定**なので、コアが開口に収まる限り
> コアを大きくしても面積の損は無い。チャネルは詰めずに余らせる方が得。
> 実際いまはマクロの上（y 1213…1597、x 1198.8…1598.4）が空いている。

### 入力は `BUFTH` で受ける

`scripts/insert_bufth.py` が合成の最後（`syn.sh` 6.5）で、トップの入力
9 本（`clk` `rst_n` `exec` `wr` `nibsel` `d[3:0]`）に `BUFTH` を 1 段ずつ挿す。
`OSS_ESD_5V_DIO` に入力バッファが無く、`PAD` の 4.8 pF を外部ドライバが
直接振るため。`BUFTH` はシュミット（立上り 3.71 V / 立下り 1.20 V）。
P&R から見ると 9 セル 291.6 µm が増えるだけで、扱いは普通の標準セル。

## ファイル

| ファイル | 役割 |
|---|---|
| `td4_config.py` | パスと幾何定数の単一ソース。**設定を触るのはここだけ** |
| `spi_config.py` | 薄皮。移植した配線スクリプトが `import spi_config` と書いているため |
| `mkcellinfo.py` | `layout/cell_info.json`。LEF の SIZE と GDS の prBoundary を突き合わせる |
| `place.py` | 配置本体。step1〜step4 |
| `verify_placement.py` | 配置の検証（被覆・アバット・グリッド・TAP 位置・マクロ・GDS 実体） |
| `plot_placement.py` | 4 STEP の PNG（目視確認用、フロー外） |
| `../insert_bufth.py` | 外部入力を `BUFTH` で受ける（合成側。`syn.sh` 6.5 から呼ぶ） |
| `../normalize_prboundary.py` | セルの prBoundary 左下を原点に合わせる |
| `netlist_util.py` | Yosys ネットリストの最小パーサ。SCLK_SPI から無改変 |
| `lef_parser.py` / `netlist_parser.py` | 同上（`spi_config` 経由でパスを取る） |

## 注意

セル原点と prBoundary の左下は**一致している**。`REG4x16` / `REG8x16` は
元は (-86.4, -54.6) から始まっていて、「(x, y) に置けば prBoundary が
(x, y) に来る」が成り立たなかったので、`scripts/normalize_prboundary.py` で
中身ごと平行移動して揃えた。`place.py` はそれでも決め打ちせず
`cell_info.json` の `origin` を見る（`verify_placement.py` が GDS 上の実位置で
毎回確認する）。

まだ原点が (0,0) でないのは `ADDBUF` (-48.6, 0) と `DEC0` (-2.4, 0) の 2 つ。
どちらも `REG8x16` / `DEC2` の中でしか使わない子セルで、**親から参照されて
いるセルは中身をずらせない**（親の中で位置が動く）ため、そのままにしてある。
行には置かないので配置には関係しない。

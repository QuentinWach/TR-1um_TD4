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
python3 scripts/pnr/mkcellinfo.py        # セル寸法表
python3 scripts/pnr/place.py             # step1..step4
python3 scripts/pnr/verify_placement.py  # 配置の検証
python3 scripts/pnr/plot_placement.py    # layout/placement_steps.png
```

## フロアプラン

`td4_config.py` が単一ソース。import のたびに `check()` が内部矛盾を潰す。

| | 値 |
|---|---|
| コア | **1598.4 × 1437.0 µm** |
| 行 | 5 行 × 1177.2 µm（218 サイト）、行高 59.4 |
| 行の実効幅 | 1101.6 µm/行（TAP 4 + 優先コリドー 3 を引いた残り） |
| チャネル | `[260, 220, 220, 200, 120, 120]` µm（下から） |
| マクロ | `REG8x16` 399.6 × 933.0 @ (1198.8, 260.0) |
| 開口 | 1840 µm（余裕 403 µm） |

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
> 実際いまはマクロの上（y 1193…1437、x 1198.8…1598.4）が空いている。

## ファイル

| ファイル | 役割 |
|---|---|
| `td4_config.py` | パスと幾何定数の単一ソース。**設定を触るのはここだけ** |
| `spi_config.py` | 薄皮。移植した配線スクリプトが `import spi_config` と書いているため |
| `mkcellinfo.py` | `layout/cell_info.json`。LEF の SIZE と GDS の prBoundary を突き合わせる |
| `place.py` | 配置本体。step1〜step4 |
| `verify_placement.py` | 配置の検証（被覆・アバット・グリッド・TAP 位置・マクロ・GDS 実体） |
| `plot_placement.py` | 4 STEP の PNG（目視確認用、フロー外） |
| `netlist_util.py` | Yosys ネットリストの最小パーサ。SCLK_SPI から無改変 |
| `lef_parser.py` / `netlist_parser.py` | 同上（`spi_config` 経由でパスを取る） |

## 注意

`REG8x16` の prBoundary 原点は **(-86.4, -54.6)** で (0,0) ではない
（`ADDBUF` は (-48.6, 0)、`DEC0` は (-2.4, 0)）。GDS に配置するときは
この分を足し戻さないと 86 µm ずれる。`mkcellinfo.py` が `origin` として
記録し、`place.py` が使う。`verify_placement.py` が GDS 上の実位置で確認する。

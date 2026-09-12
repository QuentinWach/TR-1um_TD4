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

export TR1UM_PDK=<PDK>/libs.tech/klayout/tech   # via_1 PCell（必須）
python3 scripts/pnr/route.py             # step5..step10 + DRC/接続性
python3 scripts/pnr/route.py --from 6 --to 6    # 配線だけやり直す
python3 scripts/pnr/plot_layout.py layout/step10/route_step_6_squeezed.gds \
        -o layout/routed.png
```

## 移植でルータに入れた変更（9 箇所）

原本（`TR-1um_SCLK_SPI` 経由で `TR-1um_Async_I2C`）は**アルゴリズムを触らない**
方針。入れた変更は全部「TD4 移植 (n)」のコメント付き。

| # | 場所 | 内容 |
|---|---|---|
| 1 | `route_channels_nrow_fm.py` | 行幅の直書きを `cfg.ROW_WIDTH_UM` に |
| 2 | 同上 | 行の右端の照合からハードマクロを除く |
| 3 | 同上 | **片側にしかピンが無いマクロのネットを ch[0] に固定**。既定の分類は「ピンのある行」しか見ないので、マクロと row1 を繋ぐネットが ch[1] へ割り振られて詰まる |
| 4 | 同上 | 優先コリドーのセル種を `FILL2` 限定から `FILL*` に |
| 5 | `highlight_top_pins_nrow_fm.py` | `assign out_port = \u_core.reg_out ;` の**エスケープ識別子**を別名として拾う。拾えないと step8 が out_port[0..3] と cflag_o を見失う |
| 6 | `squeeze_channels_nrow_fm.py` | ハードマクロの y 範囲を identity 写像で保護 |
| 6b | 同上 | **保護区間を 2 トラックぶん膨らませる**。保護区間の外側は詰まるので、隣のトラックが区間の脇まで寄って M1 間隔違反が出る（実測 11 件） |
| 7 | `ripup_reroute_shorts.py` | `SIMPLE_PIN_MAX` を環境変数で振れるように |
| 8 | `route_top_pins_nrow_fm.py` | **トップピンを下辺に出さない** (`NO_BOTTOM_PORTS`)。コアの下は `MEMPORT` の帯なので、BBOX 下辺はチップから見るとコアの内側 |
| 9 | `verify_port_connectivity.py` | ハードマクロの帯を「セル行」と数えない |

## メモリを横倒しにした経緯（重要）

縦置き（`REG8x16` をそのまま行の横に）では短絡が 31 件から下がらなかった。
原因は**行の配置率 79%** で、行またぎに使える「M2 の無い x」が 1 行 216 トラック
中 48 本しか無く、158 回の行またぎのうち 63 回が clear な x を見つけられずに
遠くへ逃げていた。

さらに**縦置きはチャネルの圧縮も止めていた**。マクロが 933 µm の剛体で
y 200…1133 を塞ぐため、step10 が削れたのは 507.6 µm のうち 249.8 µm だけ。
実使用 891 µm に対して 1398.6 µm を背負ったままだった。
（KLayout で見ると ch1/ch2 が明らかに空いている、というのがこの症状。）

`scripts/pnr/mkmemport.py` で **R90 + M1/M2 の直交変換**を行い、
上辺にパッド列を持つ `MEMPORT` にまとめた。

| | 縦置き | 横倒し (`MEMPORT`) |
|---|---|---|
| 行幅 | 1177.2 | **1598.4** |
| 行数 | 5 | 4 |
| 配置率 | 79% | **70〜74%** |
| 行またぎの clear x 失敗 | 63 | **4** |
| step10 の圧縮 | 249.8 µm | **1790.1 µm (-62%)** |
| 短絡 | 31 | **20** |
| チップ側コア高 | 1457.2 | 1659.1（帯 561.6 込み） |

## フロアプラン

`td4_config.py` が単一ソース。import のたびに `check()` が内部矛盾を潰す。

| | 値 |
|---|---|
| コア幅 | 1598.4 µm |
| 行 | **4 行 × 1598.4 µm**、行高 59.4 |
| 行の実効幅 | 1490.4 µm/行（TAP 4 + 優先コリドー 6 を引いた残り） |
| セル | 140 個 / 幅合計 4,303.8 µm（`BUFTH` 9 個を含む）→ 充填率 70〜74% |
| チャネル（配線時） | `[600, 600, 600, 600, 250]` µm — **多めに積んで step10 で潰す** |
| `MEMPORT` の帯 | 1598.4 × 550.8 µm @ y −561.6 … −10.8（ルータ座標の下） |
| 圧縮後のコア | 1598.4 × **1659.1** µm（開口 1840 に対し上下 90 µm ずつ） |

### 帯はルータ座標の「下」に置く

`MEMPORT` は y < 0 に置く。こうするとルータの ch[0] は帯の上から始まり、
トラック割当が帯に食い込まない。パッドはルータから見て負の y にあり、
「row0 のセルのピンが下に飛び出している」ように扱われる（ストラブは
min/max で描かれるので向きは問題にならない）。

帯の上端と y=0 の間は **`MACRO_GAP_UM = 10.8` 空ける**。0 にすると
ch[0] の最初のトラック (y=2.0) と TAP の M2 メッシュ (y=0 から) が
帯の上辺の金属と 1.4/2.0 µm を割る（実測 M1 17 件 / M2 13 件）。

### FILL の詰め方

**右端に固めない。** 区画ごとの目標量を「残りのセル幅 : 残りの容量」の比で
決め（quota）、区画内では `alternate`（偶数区画は右寄せ、奇数区画は左寄せ、
**全行で同じ振り方**）にする。区画の境目に幅の広い空き列が縦一直線に揃い、
行を跨ぐ配線がそこを通る。各行 FILL の塊 3 個 × 約 140 µm。

幅 10.8 の隙間からは via パッド 3.4 + 間隔 2.0 が両側に要るので**行またぎ用の
x が 1 本しか取れない**。140 µm の塊なら 25 本取れる。だから `distributed`
（セル間に散らす）より `alternate` の方が良い。

TAP の左右に置いた優先コリドー（`PRI_MODE="both"`、6 本/行）は区画に含めない。
**グローバル配線用の予約**なので通常の FILL では埋めない。

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

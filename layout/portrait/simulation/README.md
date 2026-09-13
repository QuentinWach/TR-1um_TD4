# 縦置きコアの LVS 用ネットリスト

対象レイアウト: **`layout/portrait/portrait_5row_bus8_pwr_step11.gds`**
（縦置き 5 行 / 縦 M2 バス 8 本 / **マクロ電源接続済み（step11）**、
1598.4 × 1347.4 µm、短絡 0 / DRC 0）

| ファイル | 中身 | 出どころ |
|---|---|---|
| `td4_soc_arr_nrow_fm.spice` | **設計意図側**（LVS のソース） | `out/td4_soc_arr_pnr.v` + `layout/placement_nrow_fm.json` + `lef/simulation/*.spice`。**レイアウトは一切見ていない** |
| `td4_soc_arr_nrow_fm_lay.spice` | **レイアウト抽出側** | `scripts/klayout_extract.py`（PDK のランセットと同じ層の導出） |
| `lvs_report.txt` | 照合結果 | `scripts/pnr/lvs_pnr.py` |

## 結果: **一致**

```
レイアウト: circuit 1 / top pin 16 / device 3597 / net 1386
ソース    : circuit 1 / top pin 16 / device 3597 / net 1386

=== LVS: **一致**
```

デバイス 3597 個・網 1386 本・トップピン 16 本がすべて一致。
`--tie-floating-power` のような仮の細工は要らない。

## 作り直し方

```sh
export TD4_MACRO_MODE=portrait TD4_MACRO_ROW=1 TD4_PRI_CELL=FILL3
export TD4_SIDE_BUS=8 TD4_SIDE_BUS_PINS="Q["
export TD4_CH_HEIGHTS="250,450,230,190,190,85.4"

# 1) 配置 + 配線（step11 まで。step11 がマクロ電源を繋ぐ）
python3 scripts/pnr/place.py --seed 1
python3 scripts/pnr/route.py --from 5

# 2) ソースネットリスト（配置 JSON を読むので 1) の後）
#    -o 省略で layout/<mode>/simulation/<トップセル名>.spice に出る
python3 scripts/pnr/mklvsnet.py

# 3) 抽出 + 照合
python3 scripts/pnr/lvs_pnr.py \
  layout/step11/route_step_7_macro_power.gds td4_soc_arr_nrow_fm \
  layout/portrait/simulation/td4_soc_arr_nrow_fm.spice \
  -o layout/portrait/simulation/td4_soc_arr_nrow_fm_lay.spice
```

## マクロ電源（step11）の中身

`REG8x16` の電源ポートは **上辺と下辺の M2 だけ**で、行の電源レールは
x ≤ 1150.2 で終わり、その右の帯は縦 M2 バス 8 本が占めている。放っておくと
マクロの vdd も vss も**金属では何にも繋がらない**（`lvs_pnr.py` が
「電源の島 `$3.vdd` 端子 1476 本」として検出していた）。

`scripts/pnr/connect_macro_power.py` が圧縮後の実座標に対して:

```
ストラップ帯 y 311.0..333.0（M1 幅 10 µm × 2 本、隙間 2 µm）
  vdd  ストラップ y 311.0..321.0  x 1145.8..1597.4 / ライザ x 1594.0..1597.4
  vss  ストラップ y 323.0..333.0  x 1140.4..1592.0 / ライザ x 1588.6..1592.0
```

右端 TAP の M2 柱（GND x 1140.4–1143.8 / VDD x 1145.8–1149.2）から
マクロ**右下**の電源ポートへ立ち上げる。給電点は**まず 1 組**。

### なぜこの経路か

* マクロの下（x 1198.8–1598.4, y 0–414.4）にはマクロの信号エスケープの
  横 M1 トランクが 21 本あるが、**y 209 より下と y 273–334 は M1 が空いている**。
* **x 1594 の列は y 0–415 が完全に空き**なので、右下のポート対へまっすぐ立てられる。
* M1 のストラップは信号エスケープの縦 M2 と交差するが、**別層なので問題ない**
  （via を打たない限り）。

### 落とし穴（必ず読むこと）

**マクロ下辺の長い M1（y 415.5–418.1, x 1198.8 から右）は `vdd`。**
同じ高さにある右端 TAP の M1 レール（x 1139.4–1150.2, y 415.5–420.7）は **`GND`**。
**同じ高さで別ネットが向かい合っている**ので、「行のレールを右へ伸ばす」は
VDD/GND 短絡になる。この高さは使わない。

もう 1 つ: via_1 の PCell は `x`/`y` を大きくするとカットを配列にする
（3.4 → 1 個 / 6.8 → 4 個 / 10.0 → 9 個）。ただし **`x` は 3.4 のまま**にすること。
TAP の柱も M2 ポートも幅 3.4 で隣との間隔が 2.0 しかないため、横に太らせると
隣のネットに当たる。ストラップの幅ぶんは `y` で稼ぐ。

## 残っていること

* **マクロ上辺のポート（y 1342.9–1346.3）はコア上辺と面一**でコア内からは届かない。
  933 µm のマクロを両端給電にするなら、**チップ組み立てで上から**メッシュを落とす。
* 給電点を増やすなら x 1200.0（vss）/ 1275.4（vdd）にもライザを立てられる
  （下は空いている）。

## 名前の約束

ソースは **`<トップセル名>.spice`**（= `td4_soc_arr_nrow_fm.spice`）。
KLayout の LVS は「セル名と同じ名前の .spice」を探す流儀で、
`lef/simulation/*.spice` も `REG8x16.spice` のようにセル名そのもの。
`mklvsnet.py` は `-o` 省略でこの名前に出す。

ユーザ側の KLayout LVS が出す抽出網は `layout/portrait/<トップセル名>.extracted`。
これは `XM<name> … <MODEL> L=… W=… AS=… PS=…` 形式（KLayout の
`NetlistSpiceWriter` + デバイス委譲）なので、**素の `NetlistSpiceReader` で
読むとデバイスではなく subckt 呼び出しに見える**（実測: circuit 94 / device 0）。
読み戻して比較するならデリゲートが要る。`scripts/pnr/lvs_pnr.py` は GDS から
自前で抽出するのでこの問題に触れない。

## 注意

* **`scripts/lvs_check.py` はこのコアでは使えない。** `combine_devices()` が
  KLayout の内部エラー（`Terminal still connected after removing device …
  circuit=DFFRB, terminal=D`）で落ちる。`scripts/pnr/lvs_pnr.py` は
  `combine_devices()` を掛けない（この設計のセルは全部シングルフィンガで、
  直列/並列のまとめが要る形が無いので、両側とも掛けなければ意味は変わらない）。
* ソース側には**フィラーも入れてある**（`FILL2` × 12 / `FILL3` × 68 = 2T の
  デキャップ）。入れないとレイアウト側の余剰デバイスとして落ちる。
  `TAP2` × 20 はデバイスを持たないので出していない。
* トップピン名はレイアウトのラベルに合わせてある（`out_port[3]` … / `VDD` / `GND`）。
  Yosys の `assign out_port = \u_core.reg_out ;` のようなバス別名を解かないと
  出力がどこにも繋がらない網になるので、`mklvsnet.py` は独自の別名解決を持つ。

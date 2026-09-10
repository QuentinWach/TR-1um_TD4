# spice/ — 回路ネットリストと SPICE 検証

| ファイル | 内容 |
|---|---|
| `REG4x16_src.spi` | **LVS ソースネットリスト（設計意図側）**。`scripts/mkspice.py` で生成 |
| `TLAT_extracted.spi` | TLAT を GDS から簡易抽出したもの（回路確認用、LVS 品質ではない） |

同じ内容を **`lef/simulation/REG4x16.spice`**（= `~/.xschem/simulations/`）に置いてある。
このパスとファイル名は PDK のランセットが決め打ちで参照する:

```ruby
# libs.tech/klayout/tech/lvs/05_Compare.lvs
Sch_file = "simulation/" + source.cell_name + ".spice"
```

つまり **`lef/` を作業ディレクトリにして top cell `REG4x16` で LVS を回すと、
`lef/simulation/REG4x16.spice` が自動で参照ネットリストになる**。
`$circuit` を指定すれば別パスも使える。

> 後で xschem で回路図を描いて netlist を書き出すと、同じパスに上書きされる。
> その時点では xschem 版が正となるので、それで構わない。

## LVS の考え方

`REG4x16_src.spi` は**レイアウトから抽出したものではなく、設計意図を書き下したもの**。
LVS はこれとレイアウト抽出ネットリストを突き合わせる。
抽出結果をソースにしてしまうと LVS が同語反復になり、何も検証できない。

素子数はレイアウト実測と一致している（**1,076 Tr**）:

| | 個数 | Tr/個 | 計 |
|---|---:|---:|---:|
| TLAT | 64 | 12 | 768 |
| **DEC2** | **8** | **32** | 256 |
| REGBUF | 4 | 8 | 32 |
| ADDBUF | 1 | 20 | 20 |
| **計** | | | **1,076** |

> デコーダは **`DEC2`（2行ぶん 32Tr）を最小単位**にしてある。レイアウトの `DEC0` は
> 隣（ミラー）と拡散を共有していて自己完結しないため、階層 LVS の単位にできない。
> 詳細は `LVS_analysis.md`。

## 回路構成

```
TLAT  (12T)   D --[TG-W:WR]-- n3 --INV1--> n1 --INV2--> n2 --[TG-F:WRB]-- n3
                                  n1 --INV3--> n4 --[TG-R:RD]-- Q
              W(P)=7.2 / W(N)=3.4    ★ GDS 抽出で確認済み

DEC2  (32T/16pin)  デコーダ2行ぶん。1行は:
                RDB = NAND4(A0,A1,A2,A3)   ← アクティブロー選択がそのまま RDB
                RD  = INV(RDB)
                WR  = NOR2(RDB, WEB)       ← 選択行 かつ WEB=L で書込
                WRB = INV(WR)
              E = 偶数行 2k（bit0=0 → AB0）/ O = 奇数行 2k+1（bit0=1 → A0）
              ★ bit1..3 のアドレスは2行で共有 → アドレスピンは 5本（A0 AB0 A1 A2 A3）
              ★ DEC2 に N-well タップ / 基板タップを内蔵（2026-09-10 追加）
                 → バルク = レール。電源ピンは 2本（vdd vss）。TLAT / REGBUF と同じ
              W(P)=12.2 / W(N)=4.6   ★ GDS 抽出で確認済み

REGBUF (8T)   DD --INV--INV--> D    書込（外部 → ビット線）
              Q  --INV--INV--> QQ   読出（ビット線 → 外部、Q は入力）
              W(P)=10.2 / W(N)=3.4

ADDBUF (20T)  ABk = INV(Ak_PIN) / Ak = INV(ABk)  (k=0..3)  平衡型 true/complement
              WEB = INV(INV(WEB_PIN))                       バッファ2段
              W(P)=10.2 / W(N)=3.4   ※ 意図
```

行 i のデコーダ入力は、i の bit k が 1 なら `a{k}`、0 なら `ab{k}`。

## トップのポート（GDS のピンラベル実測に一致）

```
.subckt REG4x16 ADD[0] ADD[1] ADD[2] ADD[3] WEB
                D[0] D[1] D[2] D[3] Q[0] Q[1] Q[2] Q[3] vdd vss
```

| ピン | 意味 |
|---|---|
| `ADD[3:0]` | アドレス（ブロック内の ADDBUF で相補を作る） |
| `WEB` | 書込イネーブル（**アクティブロー**）。`WR = NOR2(RDB, WEB)` |
| `D[3:0]` | **外部書込データ入力** → `REGBUF.DD` |
| `Q[3:0]` | **外部読出データ出力** ← `REGBUF.QQ` |
| `vdd` / `vss` | 電源（各4箇所、上下端の四隅） |

> セル内部（TLAT / REGBUF / ADDBUF）のレイアウトラベルは `gnd` だが、
> トップのピンは `vss`。物理的には abut した同一ネットなので LVS 上は問題ない。
> 気になるなら将来どちらかに統一する。

## 実行前に合わせること

1. ~~モデル名~~ **対応済み** — `01_Extract.lvs` の
   `extract_devices(mos4("PMOS"))` / `mos4("NMOS")` に合わせて **`PMOS` / `NMOS`**（大文字）、
   4端子 `M<name> D G S B <model> W=..u L=..u` 形式で書いてある。
2. **W/L の許容差** — ランセットは `tolerance W = 1%` / **`L = 0%`**。
   L はぴったり `1.0u` でなければ不一致になる。W は実測値
   （TLAT 7.2/3.4、DEC0 12.2/4.6、REGBUF・ADDBUF 10.2/3.4）をそのまま入れてある。
3. **バルク端子** — PMOS は `vdd`、NMOS は `vss`。`mos4` なので4端子で比較される。
4. **バス表記** — `ADD[0]` のように角括弧を使っている。嫌う場合は
   `scripts/mkspice.py` 冒頭の `P_ADDR` / `P_DIN` / `P_DOUT` を `"ADD{k}"` 形式に変えて再生成。
5. **`DEC0` に vdd/gnd のラベルが無い** — 電源ネットは abut したレールから拾われる。
   ラベルで電源を識別する設定なら足しておくと確実（`LVS_analysis.md` §4 参照）。
6. **中間階層** — レイアウトの `TLAT4` / `TLAT8` / `TLAT64` / `DEC16` / `REGBUF4` / `DEC0` は
   ソース側に無いので、`05_Compare.lvs` の `align` が自動でフラット化する。
   **`DEC2` だけは両側にある**ので保持されて比較される（`DEC0` は DEC2 に溶ける）。
   `flatten_circuit` を書き足す必要はない。

## ★ run.lvs の `%include` が全部コメントアウトされている

`libs.tech/klayout/tech/lvs/run.lvs` の末尾:

```ruby
# %include ../drc/00_Layers.drc
# %include ../drc/02_Device.drc
# %include 01_Extract.lvs
# %include 03_Combiner.lvs
# %include 02_Extract.lvs
# %include 04_Custom.lvs
# %include 05_Compare.lvs
```

`lvs.lylvs` 側の `# %include run.lvs` も同様。このままでは何も実行されないので、
走らせる前にコメントを外す必要がある。

## ビット線の向き（確定）

**TLAT の `D` も `Q` も TG の端子＝拡散**なので、どちらもゲート負荷を持たない。
したがってビット線を駆動するのは必ず反対側:

| ビット線 | 駆動する側 | 受ける側 | 負荷 |
|---|---|---|---|
| `dl[j]`（書込） | **REGBUF.D（出力）** | TLAT.D ×16（TG 拡散） | M2 878 µm + TG 拡散 32個 |
| `ql[j]`（読出） | 選択行の TLAT.Q（INV3 → TG-R） | **REGBUF.Q（入力）** | M2 878 µm + TG 拡散 30個 + INV 1個 |

配置もこれと一致している（REGBUF.D の x = 2.6/40.4/78.2/116.0 = TLAT.D 列、
REGBUF.Q = TLAT.Q 列、`DD`/`QQ` は外周側 y = −51.8）。

> どちらのビット線も**ゲートではなく拡散でぶら下がる**ので、
> 878 µm の M2 を引いてもアンテナ的に安全（放電経路が常にある）。

## `scripts/gds_extract.py` の限界

簡易抽出器は REGBUF で **vdd と gnd を1つのネットに併合してしまい**、
その巻き添えで `D` がゲートに見えるという誤った結果を出した。
そのため電源分離のセルフチェックを入れてある:

| セル | 判定 |
|---|---|
| `TLAT` | クリーン（結果は信頼できる） |
| `DEC0` | vdd/gnd のラベルが無いため判定不能。ただし 4直列 NMOS + 4並列 PMOS という**構造そのもの**は明確に読めるので、NAND4 系の構成は確か |
| `REGBUF` | **誤併合の警告あり — 結果を信用しないこと** |

いずれにせよ**正式な確認は PDK の LVS ランセット**で行う。

## SPICE 検証の優先順位

1. **リードパス（クリティカルパス）** — 選択セルの INV3 が TG-R 経由で
   「M2 878 µm + 非選択15セルの TG ドレイン容量」を駆動し、REGBUF が受ける。
   ワースト（非選択15セルが全部逆データ）で測る。
2. **書込パス** — REGBUF の出力 INV が `dl[j]`（M2 878 µm + TG 拡散 32個）を駆動し、
   選択行の TG-W を通って保持ノード n3 に届くまで。ratioless なので競合は無いが、
   「線路 → TG → 保持ノード」の直列 RC を確認する。
3. **D のホールド時間** — `WRB = INV(WR)` のスキューで、WR 立ち下がりに
   TG-F が TG-W より先に導通し始める。D が同時に変わると一瞬競合する。
4. **`ADDR` 変化 → `WEB` 立ち下がりの最小間隔** — ADDRB が INV 1段（約1.2 ns）遅れる間、
   2行が同時選択され得る。書込は必ずアドレス確定後に。
5. **保持リーク**

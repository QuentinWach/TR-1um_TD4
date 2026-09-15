"""config.py -- TR-1um_TD4 を APRtools で回すための設定（**縦置き・提出版**）。

    cd ~/Dropbox/98_LSI_Design/TR-1um_TD4
    export TR1UM_PDK=~/Dropbox/91_OpenPDK/TR-1um
    export APRTOOLS=~/Dropbox/91_OpenPDK/TR-1um_APRtools
    export PYTHONPATH=$APRTOOLS/apr
    python3 $APRTOOLS/apr/selfcheck.py
    python3 $APRTOOLS/apr/place.py        # 引数なし
    python3 $APRTOOLS/apr/route.py

旧 `scripts/pnr/td4_config.py` は**環境変数 6 個と `--seed 1`** を毎回
手で並べる作りだった（`scripts/pnr/README.md`）:

    TD4_MACRO_MODE=portrait TD4_MACRO_ROW=1 TD4_PRI_CELL=FILL3 \\
    TD4_SIDE_BUS=8 TD4_SIDE_BUS_PINS="Q[" \\
    TD4_CH_HEIGHTS="250,450,230,190,190,85.4" \\
      python3 scripts/pnr/place.py --seed 1

**手で打つ値は、いつか打ち忘れる値**（`docs/40_gotchas.md` §4-0）。
全部ここに書いて、引数も環境変数も無しで提出物が再現するようにする。
掃引したいときだけ `APR_SIDE_BUS` / `APR_PLACE_SEED` … で上書きする。

## 横倒し（landscape）は入れていない

提出したのは縦置き（`MEMPORT` の帯を使わない方）。横倒しは
`td4_config.py` が残っているのでそちらで回せる
（`scripts/pnr/README.md`「縦置き再訪」の比較表）。
"""
import os

from config_base import *          # noqa: F401,F403

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---- 設計の同定 ----------------------------------------------------------
TOP_CELL_NAME = "td4_soc_arr_nrow_fm"         # 提出済み。改名しない
CHIP_TOP_CELL = "tr_1um_jun1okamura"
NET_PATH = os.path.join(ROOT, "out", "td4_soc_arr_pnr.v")

# ---- フロアプラン --------------------------------------------------------
N_ROWS = 5
CORE_WIDTH_TRACKS = 296                       # x 5.4 = 1598.4
# 縦置きでは**多めにしてはいけない**。マクロは参照なので step10 の圧縮が
# その y 範囲を貫通できず、余りがそのままコア高に乗る。
CH_HEIGHTS = [250.0, 450.0, 230.0, 190.0, 190.0, 85.4]
# 上下端（250.0 / 85.4）は 5.4 の倍数ではない。APR_2026 ではそれで M1 間隔
# 違反が出たが、**TD4 のこの値では DRC 0**（提出済み）。承知のうえで通す。
CH_END_OFF_GRID_OK = True
PRI_CELL = "FILL3"
NO_BOTTOM_PORTS = False                       # 縦置きはコアの下辺が素通し

# ---- ハードマクロ（レジスタファイル）------------------------------------
# `REG8x16` を回さずそのまま行スタックの右に置く。信号ピンは下辺 1 列。
MACRO_MODE = "portrait"
MACRO_NET_CELL = "REG8x16"                    # ネットリストに出てくる名前
MACRO_CELL = "REG8x16"                        # 実際に置く物理セル
MACRO_W, MACRO_H = 399.6, 933.0
MACRO_POWER = True                            # step11 でレールへ繋ぐ
# マクロの**底面をどの行の底面に合わせるか**。0 だと 21 本が全部 row0 を
# 越えて上へ抜けて row0 の行またぎが詰まる。1 なら row0 へは下り、
# row1…row4 へは上りに分かれる。
MACRO_ALIGN_ROW = 1

# コア右の縦 M2 バス。マクロの `Q[*]`（`rom_data`）が ch[1] から row0…row4 へ
# 散るのを逃がす。**本数は実測で決めた**（span>=2 が 13 本）。
# 帯の予算式: 3.1 + (N-1)x5.4 + 3.1 <= 1198.8 - 行幅
#   N=9 なら行幅 1144.8 / N=8 なら 1150.2 が上限 → 提出は 8 本。
SIDE_BUS_TRACKS = 8
SIDE_BUS_SLACK = 5.4
# ROW_WIDTH_UM / MACRO_SIDE_GAP / TAP_X は `config_base.finalize()` が出す
#   MACRO_SIDE_GAP = 5.4 + 8 x 5.4 = 48.6
#   ROW_WIDTH_UM   = 1598.4 - 399.6 - 48.6 = 1150.2
#   TAP_X          = [0.0, 378.0, 756.0, 1139.4]（等間隔に振り直し）

# 信号ピンが 1 辺にしか出ていないインスタンス。ルータが行だけ見て上の ch に
# 割り振らないよう名指しする。
DOWN_FACING_INSTS = {"u_mem"}

# ---- フレーム ------------------------------------------------------------
# **GDS は指定しない。** `config_base.pdk_frame_gds()` が解決する
# （`APR_FRAME_GDS` -> `pdk/pending-upstream/` -> PDK。`docs/07_frame_issue.md`）。
FRAME_LEF = os.path.join(ROOT, "lef", "TR-1um_frame.lef")

# ---- 成果物の名前 --------------------------------------------------------
LAYOUT = os.path.join(ROOT, "layout")

# ---- チップ組み立ての連鎖（★ ロゴが最後）--------------------------------
# APR_2026 は配線の前にロゴを置くが、TD4 は
#   assemble -> route_chip -> add_top_pins -> place_logo
# の順。`config_base` の既定（ロゴが先）を組み替える。
# チップ床は**コアだけ**（RING_OSC もロゴの帯も下に無い）。上下のチャネルが
# 両方空いているので、VDD は上辺のタップから上のバスへ、GND は下辺のタップから
# 下のバスへまっすぐ取れる（U30。APR_2026 は下が塞がっていて上辺からしか
# 取れないので別方式）。
CHIP_POWER = "top_bottom"
CHIP_LANE_R0 = 810.0          # 下に帯が無いので 810 から始められる
CHIP_VDD_BUS_Y = 690.0        # コア上端 678.5 から 6.5
CHIP_GND_BUS_Y = -690.0
CHIP_VDD_CROSS_Y = 916.0      # M2 の上端。壁 920 から 4.0

CHIP_ROUTE_IN_GDS = os.path.join(ROOT, "layout", "chip", "step1_assembled.gds")
CHIP_LOGO_IN_GDS = os.path.join(ROOT, "layout", "chip", "step3_top_pins.gds")
CHIP_LOGO_OUT_GDS = os.path.join(ROOT, "layout", "chip", "step4_final.gds")
CHIP_FINAL_GDS = CHIP_LOGO_OUT_GDS          # 提出に載せるのはロゴ入り
# ロゴはコア右下の空き地（実測）。APR_2026 は RING_OSC の上に帯で置く。
LOGO_BOX = (410.0, -680.0, 790.0, -470.0)
LOGO_SCALE = 2                              # 1/2 に縮約
LOGO_COLS = "0:64"                          # 紋章だけ（全幅は 0:316）

# ---- 配置の再現（★ 提出した配置を作った値）------------------------------
PLACE_SEED = 1
# TD4 の提出はパッド近接（`docs/21_flow_place.md` §6）が**入る前**の世代。
# 0 にすると当時と同じ評価関数になる（`place.py` の `PAD_WEIGHT <= 0`）。
PAD_WEIGHT = 0.0


# ---- ボンドパッドの表（設計固有。U20 で config.py へ移した）--------------
# TD4 は 14 本すべて**方向が固定**なので `HIZ` はレール直結でよい
#   in  -> HIZ=VDD（パッドのドライバを切って入力にする）
#   out -> HIZ=GND（ドライバを有効にする）
# P8 = VSS / P16 = VDD はフレーム固定。
PAD_MAP = {
    1:  {"role": "CLK",    "dir": "in",  "P": "clk",           "HIZ": "VDD"},
    2:  {"role": "WR",     "dir": "in",  "P": "wr",            "HIZ": "VDD"},
    3:  {"role": "NIBSEL", "dir": "in",  "P": "nibsel",        "HIZ": "VDD"},
    4:  {"role": "D[3]",   "dir": "in",  "P": "d[3]",          "HIZ": "VDD"},
    5:  {"role": "D[2]",   "dir": "in",  "P": "d[2]",          "HIZ": "VDD"},
    6:  {"role": "D[1]",   "dir": "in",  "P": "d[1]",          "HIZ": "VDD"},
    7:  {"role": "D[0]",   "dir": "in",  "P": "d[0]",          "HIZ": "VDD"},
    9:  {"role": "RSTN",   "dir": "in",  "P": "rst_n",         "HIZ": "VDD"},
    10: {"role": "OUT[0]", "dir": "out", "OUT": "out_port[0]", "HIZ": "GND"},
    11: {"role": "OUT[1]", "dir": "out", "OUT": "out_port[1]", "HIZ": "GND"},
    12: {"role": "OUT[2]", "dir": "out", "OUT": "out_port[2]", "HIZ": "GND"},
    13: {"role": "OUT[3]", "dir": "out", "OUT": "out_port[3]", "HIZ": "GND"},
    14: {"role": "EXEC",   "dir": "in",  "P": "exec",          "HIZ": "VDD"},
    15: {"role": "CF",     "dir": "out", "OUT": "cflag_o",     "HIZ": "GND"},
}
UNBONDED = set()          # 14 本すべてボンドする

# ---- 幾何（マクロがあるので設計側で持つ）--------------------------------
def macro_box():
    """マクロの prBoundary (x0, y0, x1, y1)（コアローカル）。

    行スタックの右。**底面を `MACRO_ALIGN_ROW` の行の底面と面一**にするので、
    下辺のピン列がその行と同じチャネルを向く。"""
    x0 = ROW_WIDTH_UM + MACRO_SIDE_GAP
    y0 = row_y()[0][MACRO_ALIGN_ROW]
    return (x0, y0, round(x0 + MACRO_W, 3), round(y0 + MACRO_H, 3))


def side_bus_x():
    """コア右の縦 M2 バスのトラック中心 x。

    行のセルは `ROW_WIDTH_UM` で終わり、マクロの金属は左端 +2.8 から
    始まるので、ここは**上下に素通し**。行を跨がない。"""
    if SIDE_BUS_TRACKS <= 0:
        return []
    return [round(ROW_WIDTH_UM + SITE_UM + k * SITE_UM, 3)
            for k in range(SIDE_BUS_TRACKS)]


def core_size():
    """ルータが扱う領域の幅・高さ。マクロが行スタックより高くなりうる。"""
    _, stack_h = row_y()
    return CORE_WIDTH_UM, round(max(stack_h, macro_box()[3]), 3)


def chip_core_box():
    """チップに落とすときのコア外形。縦置きは帯が無いので下端 0。"""
    w, h = core_size()
    return (0.0, 0.0, w, h)


finalize(globals())

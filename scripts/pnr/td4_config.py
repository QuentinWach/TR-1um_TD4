"""td4_config.py -- P&R のパス・幾何定数の単一ソース。

`TR-1um_SCLK_SPI/scripts/spi_config.py` と同じ役割。配線スクリプトは
`TR-1um_Async_I2C/script/` → `TR-1um_SCLK_SPI/scripts/` と渡ってきた移植物で、
中で `import spi_config as _cfg` と書いてある。**原本を書き換えないため**、
同じディレクトリに `spi_config.py`（このモジュールを再輸出するだけの薄皮）を
置いてある。触るのはこのファイルだけ。

環境変数:
  TR1UM_PDK   PDK チェックアウト（via_1 PCell ライブラリ用）
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---- 設計の同定 ----------------------------------------------------------
TOP_CELL_NAME = "td4_soc_arr_nrow_fm"        # 配置配線したコアセル
CHIP_TOP_CELL = "tr_1um_TD4"                 # info.yaml の gds.top_cell

# ---- 入力 ----------------------------------------------------------------
LEF_PATH = os.path.join(ROOT, "lef", "TR-1um_cells.lef")
CELL_GDS = os.path.join(ROOT, "lef", "TR-1um_STDCELL.gds")
NET_PATH = os.path.join(ROOT, "out", "td4_soc_arr_pnr.v")
FRAME_GDS = os.path.join(ROOT, "lef", "TR-1um_frame_25x25.gds")
FRAME_LEF = os.path.join(ROOT, "lef", "TR-1um_frame.lef")
FRAME_CELL = "OSS_FRAME_GIO"                 # 16 パッドの GIO リング

# ---- 成果物 --------------------------------------------------------------
LAYOUT = os.path.join(ROOT, "layout")
CELL_INFO = os.path.join(LAYOUT, "cell_info.json")      # mkcellinfo.py が生成

PLACEMENT_JSON = os.path.join(LAYOUT, "placement_nrow_fm.json")
PLACEMENT_GDS = os.path.join(LAYOUT, "step5", "route_step_1_placement.gds")
ROUTED_RAW_GDS = os.path.join(LAYOUT, "step6", "route_step_2_routed_raw.gds")
RIPUP_GDS = os.path.join(LAYOUT, "step7", "route_step_3_ripup_reroute.gds")
TOPPINS_GDS = os.path.join(LAYOUT, "step8", "route_step_4_top_pins.gds")
POWERPINS_GDS = os.path.join(LAYOUT, "step9", "route_step_5_power_pins.gds")
SQUEEZED_GDS = os.path.join(LAYOUT, "step10", "route_step_6_squeezed.gds")

PIN_MAP_JSON = os.path.join(LAYOUT, "pin_map_nrow_fm.json")
NET_SHAPES_JSON = os.path.join(LAYOUT, "net_shapes_nrow_fm.json")
CHANNEL_USAGE_JSON = os.path.join(LAYOUT, "channel_usage_nrow_fm.json")
FORCE_JOG_EVENTS_JSON = os.path.join(LAYOUT, "force_jog_events_nrow_fm.json")
PIN_MAP_RR_JSON = os.path.join(LAYOUT, "pin_map_nrow_fm_rr.json")
PIN_MAP_SQ_JSON = os.path.join(LAYOUT, "pin_map_nrow_fm_sq.json")
NET_SHAPES_SQ_JSON = os.path.join(LAYOUT, "net_shapes_nrow_fm_sq.json")
NET_SHAPES_RR_JSON = os.path.join(LAYOUT, "net_shapes_nrow_fm_rr.json")
COMPACTION_INFO_JSON = os.path.join(LAYOUT, "compaction_info_nrow_fm.json")

# ---- セルライブラリの幾何 ------------------------------------------------
# **SCLK_SPI と行高が違う。** あちらは 64.8、TR-1um_TD4 の STDCELL は 59.4。
# prBoundary の実測値（lef/TR-1um_STDCELL.gds、35 セルすべて 59.4）。
ROW_HEIGHT_UM = 59.4
SITE_UM = 5.4
TRACK_PITCH = 5.4
TAP_CELL = "TAP2"
TAP_W = 10.8
TAP_PITCH = 534.6              # I2C 実チップ実測。SCLK_SPI から踏襲
FILLS = [("FILL3", 16.2), ("FILL2", 10.8)]
PRI_CELL = "FILL2"             # 優先 M2 コリドーに使うセル
PRI_W = 10.8                   # = 2 トラック
# 優先 M2 コリドーのピッチ。TAP 直後の 1 枠だけでは行またぎの空き列が足りない
# （実測: 155 回の行またぎのうち 63 回が clear な x を見つけられず遠くへ逃げ、
#  短絡の主因になっていた）。全行同じ x に 2 トラック分を等間隔で予約する。
# 実測（5 行・配置率 79%）:
#   ピッチ 108 (コリドー 11 本/行)  行またぎの clear x 失敗 63 -> 63、短絡 32 -> 40
#   TAP 直後のみ (3 本/行)          短絡 32   <- いまはこちら
# コリドーを増やしても**同じ x に集まりすぎて互いに衝突する**ので効かなかった。
# 効くのは配置率そのもの。1e9 にすると「TAP 直後の 1 枠だけ」= 移植元と同じ。
PRI_PITCH = 1e9

# ---- フロアプラン --------------------------------------------------------
# `reference/05_pin_io_plan.md` と `claude/TD4_floorplan.md` の案を、
# **マクロのピンが全部下辺にある**という実測に合わせて直したもの。
#
#   REG8x16 の信号ピン 21 本 (ADD/WEB/D/Q) は全部 M2、y 1.1…4.5 の下辺 1 列。
#   OBS は M1/M2 とも全面。したがって**ピンの真下に配線チャネルが要る**。
#   旧案はマクロ底面 = コア底面だったのでピンに到達できなかった。
#
# 直し方: マクロを ch[0] ぶん持ち上げ、**マクロの底面を row0 の底面と面一**に
# する。マクロのピン列と row0 のセルのピン列が同じ ch[0] を向くので、
# チャネルルータから見ると「マクロは 933 µm 高い row0 のセル」に見える。
# **コア幅は 1600 µm 以下に収める。** フレーム開口は幅 1600 を 0.1 µm でも
# 超えると四隅セルに当たって 1840 → 1600 µm に縮む（`frame_opening()` で実測）。
# 旧案の 1620 はこの崖の向こう側だった。行幅を 1198.8 → 1177.2（222 → 218
# サイト）に 21.6 µm 削るだけで**チャネル予算が 240 µm 増える**。
# 行の実効幅は 1123.2 → 1101.6 で、必要な 4,012 µm に対し 5 行で 5,508 µm。
N_ROWS = 5
ROW_WIDTH_UM = 1177.2          # 218 サイト。コア幅とは独立（マクロが右に来る）
CORE_WIDTH_UM = 1598.4         # = ROW_WIDTH_UM + MACRO_GAP + MACRO_W

MACRO_CELL = "REG8x16"
MACRO_W, MACRO_H = 399.6, 933.0
MACRO_GAP = 21.6               # 行スタックとマクロの隙間（M2 4 トラック）
# セル原点と prBoundary 左下は一致している（`scripts/normalize_prboundary.py`
# で揃えた）。place.py は決め打ちせず cell_info.json の `origin` を見る。

# チャネル高（下から）。ch[0] がマクロのピン面で、**ch[0] = マクロの y0**。
# 拘束はこれ 1 本だけ。行スタックがマクロより高くなってもよい（マクロの上に
# 空きができるが、**ダイは 2500 x 2500 で固定**なのでコアが開口に収まる限り
# 面積の損は無い）。
#
# place.py の見積り（ネット交差数 x 5.4 µm）は [146, 189, 221, 151, 70, 16]。
# ルータのジョグは行またぎ 1 本ごとに新しいトラックを取るので見積りでは足りない
# （SCLK_SPI は見積りの数倍を積んで最後に圧縮した）。ここでは約 1.3 倍 + 余白。
# 開口 1840 − 行 297 = 1543 µm がチャネルに使える上限で、下の合計は 1300。
# **足りなければここを増やす**（243 µm 残してある）。
CH_HEIGHTS = [200.0, 290.0, 330.0, 250.0, 250.0, 90.0]

TAP_X = [0.0, 534.6, 1069.2, 1166.4]         # 行ローカル。tap_positions() と一致

# 配線で使うチャネル予算。**配置と同じでなければならない。**
# マクロの y0 = ch[0] なので、ここがずれるとルータの中でマクロが浮く
# （SCLK_SPI は配置の見積りと配線の予算を別にできたが、TD4 は繋がっている）。
ROUTE_CH_HEIGHTS = list(CH_HEIGHTS)

# 信号ピンが 1 辺（下辺）にしか出ていないインスタンス。ここにピンを持つネットは
# ch[0] からしか出られないので、ルータが行だけ見て上の ch に割り振らないよう
# 名指しする（`route_channels_nrow_fm.py` の「TD4 移植 (3)」）。
DOWN_FACING_INSTS = {"u_mem"}

# ---- 派生値 --------------------------------------------------------------
def row_y():
    """各行の prBoundary 下端 y（コアローカル）と、行スタックの総高。"""
    ys, y = [], 0.0
    for i in range(N_ROWS):
        y += CH_HEIGHTS[i]
        ys.append(round(y, 3))
        y += ROW_HEIGHT_UM
    return ys, round(y + CH_HEIGHTS[-1], 3)


def macro_box():
    """マクロ prBoundary の (x0, y0, x1, y1)（コアローカル）。"""
    x0 = ROW_WIDTH_UM + MACRO_GAP
    y0 = CH_HEIGHTS[0]
    return (x0, y0, round(x0 + MACRO_W, 3), round(y0 + MACRO_H, 3))


def core_size():
    _, stack_h = row_y()
    mx0, my0, mx1, my1 = macro_box()
    return CORE_WIDTH_UM, round(max(stack_h, my1), 3)


def check():
    """フロアプランの内部矛盾を潰す。import 時に毎回回す。"""
    msg = []
    if len(CH_HEIGHTS) != N_ROWS + 1:
        msg.append(f"CH_HEIGHTS は {N_ROWS+1} 本要る（今 {len(CH_HEIGHTS)}）")
    if sum(CH_HEIGHTS[1:]) < MACRO_H - N_ROWS * ROW_HEIGHT_UM - 1e-6:
        msg.append(f"sum(ch[1:]) = {sum(CH_HEIGHTS[1:])} だと行スタックが"
                   f"マクロより低くなり、マクロの上がコアの外に出る")
    mx0, _, mx1, _ = macro_box()
    if abs(mx1 - CORE_WIDTH_UM) > 1e-6:
        msg.append(f"マクロ右端 {mx1} とコア幅 {CORE_WIDTH_UM} が合わない")
    lo, hi = frame_opening(CORE_WIDTH_UM)
    _, ch = core_size()
    if ch > hi - lo + 1e-6:
        msg.append(f"コア高 {ch} がフレーム開口 {hi-lo} を超える")
    if any(abs(t / SITE_UM - round(t / SITE_UM)) > 1e-9 for t in TAP_X):
        msg.append("TAP_X がサイトグリッドに乗っていない")
    if msg:
        raise SystemExit("td4_config: フロアプランが矛盾している\n  - "
                         + "\n  - ".join(msg))


# ---- チップ統合（コアを GIO パッドリングに落とす） -----------------------
CHIP = os.path.join(LAYOUT, "chip")
GIO_PIN_RADIUS = 921.7         # P/HIZ/OUT 端子の半径（ダイ中心から）
PTECT_LAYER = (63, 1)


def core_bbox_um(gds=None, cell=None):
    import klayout.db as db
    ly = db.Layout()
    ly.read(gds or SQUEEZED_GDS)
    c = ly.cell(cell or TOP_CELL_NAME)
    if c is None:
        raise SystemExit(f"{cell or TOP_CELL_NAME} が {gds or SQUEEZED_GDS} に無い")
    b = c.bbox()
    return (b.left * ly.dbu, b.bottom * ly.dbu, b.right * ly.dbu, b.top * ly.dbu)


def frame_opening(width_um=CORE_WIDTH_UM, lef=None):
    """幅 width_um のコアが収まる最大の y 帯（ダイ中心基準）。

    `OSS_FRAME_GIO` の OBS 実測。**定数で持たない** — SCLK_SPI は
    `GIO_INNER_WALL = 920.0` を定数で持っていたが、TD4 のフレーム GDS では
    幅 1620 に対する壁は ±800 で、そのまま継承すると 120 µm 食い込む。
    """
    import re
    txt = open(lef or FRAME_LEF).read()
    body = re.search(rf"MACRO {FRAME_CELL}(.*?)END {FRAME_CELL}", txt, re.S).group(1)
    obs = re.search(r"OBS(.*?)END", body, re.S).group(1)
    die = float(re.search(r"SIZE\s+([\d.]+)\s+BY", body).group(1))
    c = die / 2
    rects = sorted({tuple(float(v) - c for v in q) for q in
                    re.findall(r"RECT\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)"
                               r"\s+(-?[\d.]+)\s*;", obs)})
    x0, x1 = -width_um / 2, width_um / 2
    ys = [(a, b) for (p, a, q, b) in rects if q > x0 + 1e-9 and p < x1 - 1e-9]
    pts = sorted({-c, c} | {v for p in ys for v in p})
    best = (0.0, 0.0)
    for a, b in zip(pts, pts[1:]):
        m = (a + b) / 2
        if not any(lo < m < hi for lo, hi in ys) and b - a > best[1] - best[0]:
            best = (a, b)
    return best


def pdk_tech_python():
    """PDK の KLayout PCell パッケージ（`from cells import tr_1um`）。
    ルータのビアは全部この PCell のインスタンスなので必須。"""
    env = os.environ.get("TR1UM_PDK")
    cands = []
    if env:
        cands.append(os.path.join(env, "libs.tech", "klayout", "tech", "python"))
        cands.append(os.path.join(env, "klayout", "tech", "python"))
        cands.append(env)
    cands += [
        os.path.expanduser("~/Dropbox/91_OpenPDK/TR-1um/libs.tech/klayout/tech/python"),
        os.path.join(os.path.dirname(ROOT), "TR-1um", "libs.tech", "klayout", "tech", "python"),
        os.path.expanduser("~/TR-1um/libs.tech/klayout/tech/python"),
    ]
    for c in cands:
        if os.path.isdir(os.path.join(c, "cells")):
            return c
    raise SystemExit("TR-1um PDK の KLayout PCell パッケージが見つからない。\n"
                     "  TR1UM_PDK を PDK チェックアウトに向けること。\n"
                     f"  試した場所: {cands}")


def artifact(basename):
    """移植元が絶対パスで持っていた中間ファイルは全部 layout/ に落とす。"""
    return os.path.join(LAYOUT, basename)


def channel_heights(placement_json=PLACEMENT_JSON):
    import json
    return json.load(open(placement_json))["ch_heights"]


# フロアプランの内部矛盾は import のたびに潰す。frame_opening() を使うので
# 定義が全部そろった最後に呼ぶ。
check()

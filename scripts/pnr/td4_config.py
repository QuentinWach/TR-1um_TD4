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
# ライブラリ本体（`scripts/mklef.py` が作る。P&R は直接読まない）
LIB_LEF = os.path.join(ROOT, "lef", "TR-1um_cells.lef")
LIB_GDS = os.path.join(ROOT, "lef", "TR-1um_STDCELL.gds")
# P&R が読むもの = ライブラリ + `MEMPORT`。`scripts/pnr/mkmemport.py` が作る。
LEF_PATH = os.path.join(ROOT, "lef", "TR-1um_PNR.lef")
CELL_GDS = os.path.join(ROOT, "lef", "TR-1um_PNR.gds")
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
TRACK_PITCH = float(os.environ.get("TD4_TRACK_PITCH", "5.4"))   # チャネルの M1 トラック間隔（x のサイトとは別物）
TAP_CELL = "TAP2"
TAP_W = 10.8
TAP_PITCH = 534.6              # I2C 実チップ実測。SCLK_SPI から踏襲
# 隙間埋めに使う FILL（広い順）。**FILL1 (5.4) を入れておく。**
# FILL2/FILL3 だけだと隙間が 10.8 の倍数系に限られ、優先コリドーを増やして
# 区画が細かくなると詰め切れずに step3 が落ちる。FILL1 は容量ゼロの純フィラー
# なので、デキャップとしては FILL2/FILL3 が先に使われるこの順で問題ない。
# `TD4_USE_FILL1=1` で FILL1 (5.4) も使う。既定は入れない（入れると隙間の
# 刻みが変わって**配置が丸ごと変わる**ので、確定した横倒しの結果を壊さない）。
FILLS = [("FILL3", 16.2), ("FILL2", 10.8)]
if os.environ.get("TD4_USE_FILL1") == "1":
    FILLS = FILLS + [("FILL1", 5.4)]
# 優先 M2 コリドーに使うセル。`TD4_PRI_CELL` で振れる。
# FILL2 (10.8 = 2 トラック) だと上側トラックの via パッド（半幅 1.7 + 隙間 2.0）
# が隣のセルへ 1.0 µm はみ出すので、隣に M2 があると実質 1 本しか使えない。
# **FILL3 (16.2 = 3 トラック) なら真ん中の 1 本が必ず両側とも空く。**
_PRI_W = {"FILL1": 5.4, "FILL2": 10.8, "FILL3": 16.2}
# 実測（横倒し・seed 1、step10 の実 BBOX / 短絡 / DRC）:
#   FILL2  1655.8 / 0 / 0   行またぎジョグ 28、コリドー 12 track
#   FILL3  1645.0 / 0 / 0   行またぎジョグ 26、コリドー 18 track   <- 既定
PRI_CELL = os.environ.get("TD4_PRI_CELL", "FILL3")
if PRI_CELL not in _PRI_W:
    raise SystemExit(f"TD4_PRI_CELL は {sorted(_PRI_W)} のどれか（今 {PRI_CELL}）")
PRI_W = _PRI_W[PRI_CELL]
# 優先 M2 コリドーのピッチ。TAP 直後の 1 枠だけでは行またぎの空き列が足りない
# （実測: 155 回の行またぎのうち 63 回が clear な x を見つけられず遠くへ逃げ、
#  短絡の主因になっていた）。全行同じ x に 2 トラック分を等間隔で予約する。
# 実測（5 行・配置率 79%）:
#   ピッチ 108 (コリドー 11 本/行)  行またぎの clear x 失敗 63 -> 63、短絡 32 -> 40
#   TAP 直後のみ (3 本/行)          短絡 32   <- いまはこちら
# コリドーを増やしても**同じ x に集まりすぎて互いに衝突する**ので効かなかった。
# 効くのは配置率そのもの。1e9 にすると「TAP 直後の 1 枠だけ」= 移植元と同じ。
PRI_PITCH = float(os.environ.get("TD4_PRI_PITCH", "1e9"))
# コリドーの置き方。"after" = TAP 直後だけ（移植元と同じ）、
# "both" = **TAP の両側**。行末の TAP の手前にも 1 枠できるので、
# 行の右端にも縦に抜ける列ができる（ユーザ指摘）。
PRI_MODE = "both"

# ---- フロアプラン --------------------------------------------------------
# **メモリは横倒しにして行スタックの下に敷く。**
#
# `REG8x16` は 399.6 x 933.0 で信号ピン 21 本が下辺の水平 1 列。縦置きで行の
# 横に並べるとコア幅 1598.4 のうち 421.2 µm を食い、行幅が 1177.2 にしかならず
# **配置率が 79% まで上がって行またぎの空き x が枯れる**（M2 の無い x が
# 216 トラック中 48 本しかない）。これが短絡 31 件の直接の原因だった。
#
# R90 して 933.0 x 399.6 にすると行はコア幅いっぱい使える。回すとピン列は
# 垂直になってチャネルルータが扱えないので、`scripts/pnr/mkmemport.py` が
# マクロ右の空き地で M1/M2 に振り替え、**上辺に水平なパッド列を持つ
# ハードマクロ `MEMPORT` (1598.4 x 399.6)** にまとめる。中継はマクロの横に
# 置くので高さの持ち出しはゼロ。
#
# 帯は**ルータの座標系の下**（y -399.6 … 0）に置く。こうするとルータの ch[0]
# はマクロの上から始まり、トラック割当が帯の中に食い込まない。パッドは
# y -4.5 … -1.1 にあり、ルータからは「row0 のセルのピンが下に飛び出している」
# ように見える（ストラブは min/max で描かれるので向きは問題にならない）。
#
# **チャネル予算は多めでよい。** 帯がチャネルの y 範囲にかからないので、
# step10 の圧縮が全チャネルに効く（縦置きのときはマクロが y 200…1133 を
# 塞いで 507.6 µm のうち 249.8 µm しか削れなかった）。実測の必要量は 891 µm。
# ---- マクロの置き方 ------------------------------------------------------
# `TD4_MACRO_MODE`:
#   "landscape"（既定）  R90 して行スタックの**下に帯として敷く**（= `MEMPORT`）
#   "portrait"           そのまま行スタックの**右に縦置き**（= `REG8x16`）
#
# 縦置きは最初に試して短絡 31 件で行き詰まった案。その後ルータを直したので
# もう一度測れるように残してある（`scripts/pnr/README.md`「縦置き再訪」）。
# 縦置きの得失:
#   + 帯（502.2 + 隙間 27.0 = 529.2 µm）が丸ごと要らない
#   − 行幅が 1598.4 → 1177.2 に縮み、配置率が 71% → 78% に上がる
#   − マクロ（933 µm）は参照なので **step10 の圧縮がそこを貫通できない**
MACRO_MODE = os.environ.get("TD4_MACRO_MODE", "landscape")
if MACRO_MODE not in ("landscape", "portrait"):
    raise SystemExit(f"TD4_MACRO_MODE は landscape か portrait（今 {MACRO_MODE}）")
_PORTRAIT = MACRO_MODE == "portrait"

# 実験用の上書き。`TD4_N_ROWS=5 python3 scripts/pnr/place.py` のように使う。
N_ROWS = int(os.environ.get("TD4_N_ROWS", "5" if _PORTRAIT else "4"))
CORE_WIDTH_UM = 1598.4

MACRO_NET_CELL = "REG8x16"     # ネットリストに出てくる名前
if _PORTRAIT:
    MACRO_CELL = "REG8x16"     # 回さずそのまま置く
    MACRO_W, MACRO_H = 399.6, 933.0
    MACRO_SIDE_GAP = 21.6      # 行スタックとマクロの隙間（M2 4 トラック）
    # 218 サイト。**コア幅 1600 を超えるとフレーム開口が 1840 → 1600 に落ちる**
    # ので、行幅はここまで（`frame_opening()` で実測した崖）。
    ROW_WIDTH_UM = 1177.2
    # 等間隔にする。534.6 刻み（[0, 534.6, 1069.2, 1166.4]）だと最後の区間が
    # 86.4 µm しか無く、優先コリドー 2 本を引くと 64.8 µm。そこへ回された
    # セルが入らず step3 で落ちる（実測: 「1 個が行に入りきらない」）。
    # 388.8 刻みなら 3 区間とも 378 µm で、TAP ピッチの上限 534.6 も満たす。
    TAP_X_DEFAULT = [0.0, 388.8, 777.6, 1166.4]
else:
    MACRO_CELL = "MEMPORT"     # 実際に置く物理セル（R90 + 中継）
    MACRO_W, MACRO_H = 1598.4, 502.2   # mkmemport.py の出力と一致させること
    MACRO_SIDE_GAP = 0.0
    ROW_WIDTH_UM = CORE_WIDTH_UM   # 行はコア幅いっぱい（マクロが横に無いので）
    TAP_X_DEFAULT = [0.0, 534.6, 1069.2, 1587.6]
# 帯の上端と ch[0] の下端 (y=0) の間に空ける隙間。
# **0 にしてはいけない。** ルータは ch[0] の最初のトラックを y=2.0 に置き、
# TAP の M2 電源メッシュを y=0 から立てるので、帯の上辺の金属と 1.4/2.0 µm を
# 割る（実測: M1 間隔違反 17 件・M2 間隔違反 13 件が全部 y≈0、x<933 に出た）。
#
# ここには **VDD/VSS の電源バスバー 2 本（M1・幅 10 µm）** を通す
# （ユーザ指示）。帯の上辺と ch[0] の間は M2 のライザが縦に抜けるだけで
# M1 は 1 本も無いので、横向きの M1 バーを通すのに都合がよい。
# 必要量: 1.4 + 10 + 1.4 + 10 + 1.4 = 24.2 µm → サイト grid に丸めて 27.0。
POWER_BAR_W = 10.0             # バー 1 本の M1 幅
POWER_BAR_GAP = 2.0            # バー間 / 帯とバーの間（M1 最小 1.4 に余裕）
MACRO_GAP_UM = 0.0 if _PORTRAIT else 27.0
# ルータ座標での帯の下端。縦置きでは帯が無いので使わない（macro_box() 参照）。
MACRO_Y0 = 0.0 if _PORTRAIT else -(MACRO_H + MACRO_GAP_UM)

# チャネル予算。横倒しでは**圧縮で使わないトラックは丸ごと消える**ので多めで
# よい。最後だけ 250 なのは上端マージン（トップピンの引き出しにしか使わない）。
#
# **縦置きでは多めにしてはいけない。** マクロは参照なので圧縮がその y 範囲を
# 貫通できず、マクロが跨ぐチャネルの余りはそのままコア高に乗る。
# `TD4_CH_HEIGHTS="200,290,330,250,250,90"` のようにカンマ区切りで渡せる。
_ch_env = os.environ.get("TD4_CH_HEIGHTS")
if _ch_env:
    CH_HEIGHTS = [float(v) for v in _ch_env.split(",")]
elif _PORTRAIT:
    CH_HEIGHTS = [200.0] + [400.0] * (N_ROWS - 1) + [250.0]
else:
    CH_HEIGHTS = [600.0] * N_ROWS + [250.0]

TAP_X = TAP_X_DEFAULT                        # 行ローカル。tap_positions() と一致

# 配線で使うチャネル予算。配置と同じでなければならない（行の y が変わるため）。
ROUTE_CH_HEIGHTS = list(CH_HEIGHTS)

# 信号ピンが 1 辺にしか出ていないインスタンス。`MEMPORT` のパッドは帯の上辺
# （ルータ座標では row0 の下）にしか無いので、**ch[0] からしか出られない**。
# ルータが行だけ見て上の ch に割り振らないよう名指しする
# （`route_channels_nrow_fm.py` の「TD4 移植 (3)」）。
DOWN_FACING_INSTS = {"u_mem"}

# コアの下に `MEMPORT` の帯を敷くので、**BBOX の下辺はチップから見るとコアの
# 内側**になる。トップピンを下辺に出さない（`route_top_pins_nrow_fm.py` の
# 「TD4 移植 (8)」）。下辺のパッド 3 本 (D[0]/RSTN/OUT[0]) はチップ側で回り込む。
# 縦置きではコアの下辺は素通しなので下辺にもポートを出せる。
NO_BOTTOM_PORTS = not _PORTRAIT

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
    """マクロの prBoundary (x0, y0, x1, y1)（コアローカル）。

    横倒し: 行スタックの**下**の帯。y は負で、上端は -MACRO_GAP_UM。
    縦置き: 行スタックの**右**。**底面を row0 の底面と面一**にする
            （y0 = CH_HEIGHTS[0]）ので、マクロの下辺ピン列が row0 の
            セルのピン列と同じ ch[0] を向く。
    """
    if _PORTRAIT:
        x0 = ROW_WIDTH_UM + MACRO_SIDE_GAP
        y0 = CH_HEIGHTS[0]
        return (x0, y0, round(x0 + MACRO_W, 3), round(y0 + MACRO_H, 3))
    return (0.0, MACRO_Y0, MACRO_W, round(MACRO_Y0 + MACRO_H, 3))


def power_bars():
    """帯の上辺と ch[0] の間に確保した **M1 電源バスバー 2 本**の
    (name, y0, y1)。下が VSS、上が VDD（帯側が GND なのはマクロの
    電源が帯の右端から出るため。チップ側で受けるときに合わせること）。

    ルータはここに何も描かない（ch[0] は y>=0 から始まる）。実際の
    バーはチップ組み立てで TAP の M2 柱とマクロ右端の電源に繋ぐ。
    """
    if _PORTRAIT:
        return []                             # 帯が無いので隙間も無い
    top_of_band = MACRO_Y0 + MACRO_H          # = -MACRO_GAP_UM
    y = top_of_band + POWER_BAR_GAP
    out = []
    for name in ("GND", "VDD"):
        out.append((name, round(y, 3), round(y + POWER_BAR_W, 3)))
        y += POWER_BAR_W + POWER_BAR_GAP
    return out


def core_size():
    """ルータが扱う領域の幅・高さ。横倒しの帯は含まない（y<0 なので）。
    縦置きではマクロが行スタックより高くなりうるので max を取る。"""
    _, stack_h = row_y()
    if _PORTRAIT:
        return CORE_WIDTH_UM, round(max(stack_h, macro_box()[3]), 3)
    return CORE_WIDTH_UM, stack_h


def chip_core_box():
    """チップに落とすときのコア外形。横倒しは**帯を含む**ので下端が負。"""
    w, h = core_size()
    return (0.0, 0.0 if _PORTRAIT else MACRO_Y0, w, h)


def chip_core_height():
    _, b, _, t = chip_core_box()
    return round(t - b, 3)


def check():
    """フロアプランの内部矛盾を潰す。import 時に毎回回す。"""
    msg = []
    if len(CH_HEIGHTS) != N_ROWS + 1:
        msg.append(f"CH_HEIGHTS は {N_ROWS+1} 本要る（今 {len(CH_HEIGHTS)}）")
    if MACRO_W > CORE_WIDTH_UM + 1e-6:
        msg.append(f"マクロ幅 {MACRO_W} がコア幅 {CORE_WIDTH_UM} を超える")
    if not _PORTRAIT and MACRO_Y0 >= 0:
        msg.append(f"マクロ帯はルータ座標の下（y<0）に置くこと（今 {MACRO_Y0}）")
    if _PORTRAIT:
        mx0, my0, mx1, my1 = macro_box()
        if mx1 > CORE_WIDTH_UM + 1e-6:
            msg.append(f"縦置きのマクロ右端 {mx1} がコア幅 {CORE_WIDTH_UM} を超える")
        if abs(my0 - CH_HEIGHTS[0]) > 1e-6:
            msg.append(f"縦置きのマクロ底面 {my0} が row0 の底面 {CH_HEIGHTS[0]} と面一でない"
                       f"（下辺のピン列が ch[0] を向かなくなる）")
    # 電源バスバーが帯の上辺と ch[0] の間に収まるか（横倒しだけ）
    _need = 2 * POWER_BAR_W + 3 * POWER_BAR_GAP
    if not _PORTRAIT and MACRO_GAP_UM + 1e-9 < _need:
        msg.append(f"MACRO_GAP_UM {MACRO_GAP_UM} では M1 電源バー 2 本 "
                   f"({POWER_BAR_W} µm x2 + 間隔 {POWER_BAR_GAP} x3 = {_need}) が入らない")
    if power_bars() and power_bars()[-1][2] > -1.4:
        msg.append(f"電源バーの上端 {power_bars()[-1][2]} が ch[0] (y=0) に近すぎる"
                   f"（M1 最小間隔 1.4 µm）")
    if not _PORTRAIT and abs(MACRO_GAP_UM / SITE_UM - round(MACRO_GAP_UM / SITE_UM)) > 1e-9:
        msg.append(f"MACRO_GAP_UM {MACRO_GAP_UM} がサイトグリッド {SITE_UM} に乗っていない")
    if any(abs(t / SITE_UM - round(t / SITE_UM)) > 1e-9 for t in TAP_X):
        msg.append("TAP_X がサイトグリッドに乗っていない")
    if msg:
        raise SystemExit("td4_config: フロアプランが矛盾している\n  - "
                         + "\n  - ".join(msg))


def check_opening():
    """圧縮後のコア高がフレーム開口に収まるか。**配線が終わってから**使う
    （配線中は予算を多めに積むので、この時点では超えていて当たり前）。"""
    lo, hi = frame_opening(CORE_WIDTH_UM)
    h = chip_core_height()
    return h, hi - lo, (hi - lo) - h


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

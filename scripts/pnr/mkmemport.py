#!/usr/bin/env python3
"""mkmemport.py -- `REG8x16` を 90° 回し、垂直なピン列を**水平なパッド列**に
変換したハードマクロ `MEMPORT` を作る。

  usage: python3 scripts/pnr/mkmemport.py
         python3 scripts/pnr/mkmemport.py --plot layout/memport.png

## なぜ要るか

`REG8x16` は 399.6 × 933.0 で、信号ピン 21 本は `y 1.1…4.5` の**水平 1 列**。
縦置きのまま行の横に並べると、コア幅 1598.4 のうち 421.2 µm を食うので
行幅が 1177.2 にしかならず、配置率が 79% まで上がって**行またぎの空き x が
枯れる**（M2 の無い x が 216 トラック中 48 本）。これが短絡 31 件の原因。

横倒し（R90）にすれば 933.0 × 399.6 になり、行はコア幅いっぱい使えて
配置率が 71%（4 行）/ 57%（5 行）まで下がる。**ただし 90° 回すと水平な
ピン列は垂直なピン列になる**（右辺、x 928.5…931.9、y 6.4…377.0 に 21 本）。
水平チャネルのルータはこれを扱えない。

そこで**マクロの右の空き地**（x 933…1598.4、y 0…399.6）で M1/M2 に振り替え、
帯の上辺に水平なパッド列を作る。

    ピン(M2) ─V1─ M1 を右へ（各ピン自身の y。21 本とも別の y）
                 └─V1─ M2 を上へ（21 本とも別の x、5.4 ピッチ）
                        └─ 上辺の M2 パッド + ラベル

M1 は水平・M2 は垂直で、`lef/TR-1um_tech.lef` の方向規則どおり。
中継はマクロの**上**ではなく**横**に置くので、**帯の高さは 399.6 µm ちょうど**、
高さの持ち出しはゼロ。

## 出力

  `lef/TR-1um_PNR.gds`   標準セル + `MEMPORT`（1598.4 × 399.6）を 1 ファイルに
  `lef/TR-1um_PNR.lef`   同じく MACRO を 1 ファイルに

**配置配線はこの 2 つだけを読む**（`td4_config.CELL_GDS` / `LEF_PATH`）。
ライブラリ本体（`TR-1um_STDCELL.gds` / `TR-1um_cells.lef`）は汚さない。

以降のフローから見ると「上辺 1 列にピンがあるハードマクロ 1 個」になるので、
配置・配線は縦置きのときと同じ扱いで通る。

## 電源

マクロの `vdd`/`vss` は元の上辺と下辺に 2 本ずつ出ている。R90 すると
**左辺と右辺**に移る。左辺 (x≈2.8) はマクロの真上を通らないと外へ出せない
（OBS 全面）ので、**右辺の 2 本ずつだけ**を上辺へ引き出す。マクロ内部で
左右の電源は繋がっているので電気的には足りるが、**電流経路は片側だけ**に
なる。チップの電源メッシュ側で太く受けること。
"""
from __future__ import annotations
import argparse, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import td4_config as cfg                                    # noqa: E402
import lef_parser                                           # noqa: E402

SRC_CELL = "REG8x16"
CELL = "MEMPORT"
M1, M2, V1 = (13, 0), (20, 0), (19, 0)
M1LBL, M1PIN = (48, 0), (48, 1)
M2LBL, M2PIN = (49, 0), (49, 1)
BOUND = (235, 0)

PAD = 3.4                  # via_1 の既定パッド（M1/M2 とも）
HALF = PAD / 2.0
GRID = 5.4                 # サイト／トラックピッチ
M2_GAP = 2.0

# --- 中継の配置 ------------------------------------------------------------
VIA_X = 938.3              # マクロ右のピン引き出し V1 列（全ピン共通の x）
SIG_X0 = 945.0             # 信号 M2 ライザの左端
SIG_DX = 32.4              # 同ピッチ（6 サイト）。945.0…1593.0 に 21 本を最大限散らす
# 電源ライザは信号の隙間へ挟む（信号を右端まで使い切るため）。
PWR_X = [SIG_X0 + SIG_DX * k + SIG_DX / 2 for k in range(4)]
PAD_Y0, PAD_Y1 = 395.1, 398.5   # 上辺のパッド（元セルの 1.1…4.5 と同じ作法）


def r90(x, y, w_src, h_src):
    """R90 + 平行移動。(x, y) -> (h_src - y, x)。外形は h_src × w_src になる。"""
    return (h_src - y, x)


def build(plot=None):
    import gdstk
    lib = gdstk.read_gds(cfg.LIB_GDS)
    cells = {c.name: c for c in lib.cells}
    if SRC_CELL not in cells:
        raise SystemExit(f"{SRC_CELL} が {cfg.LIB_GDS} に無い")
    src = cells[SRC_CELL]
    prb = [p for p in src.polygons if (p.layer, p.datatype) == BOUND]
    b = prb[0].bounding_box()
    w_src, h_src = round(b[1][0] - b[0][0], 3), round(b[1][1] - b[0][1], 3)
    if abs(b[0][0]) > 1e-6 or abs(b[0][1]) > 1e-6:
        raise SystemExit(f"{SRC_CELL} の prBoundary 原点が (0,0) でない。"
                         f"先に scripts/normalize_prboundary.py")

    W, H = cfg.CORE_WIDTH_UM, w_src          # 回転後の高さ = 元の幅
    if h_src > W:
        raise SystemExit(f"回転後の幅 {h_src} がコア幅 {W} を超える")

    lefpins = lef_parser.parse_lef(cfg.LIB_LEF)[SRC_CELL]["pins"]
    sig, pwr = [], []
    for name, info in lefpins.items():
        for lay, x0, y0, x1, y1 in info["rects"]:
            nx0, ny0 = r90(x0, y1, w_src, h_src)
            nx1, ny1 = r90(x1, y0, w_src, h_src)
            rec = (name, info["use"], round(nx0, 3), round(ny0, 3),
                   round(nx1, 3), round(ny1, 3))
            (sig if info["use"] not in ("POWER", "GROUND") else pwr).append(rec)
    sig.sort(key=lambda r: r[3])
    # 右辺（x が大きい方）に来た電源ピンだけ引き出せる
    pwr_r = sorted([p for p in pwr if p[2] > h_src / 2], key=lambda r: r[3])
    if len(sig) != 21:
        raise SystemExit(f"信号ピンが {len(sig)} 本（21 本のはず）")

    out = gdstk.Library(name=CELL, unit=1e-6, precision=1e-9)
    seen = set()

    def add_deep(c):
        if c.name in seen:
            return
        seen.add(c.name)
        out.add(c)
        for r in c.references:
            add_deep(r.cell)

    add_deep(src)
    top = out.new_cell(CELL)
    top.add(gdstk.Reference(src, (h_src, 0.0), rotation=math.pi / 2))
    top.add(gdstk.rectangle((0, 0), (W, H), layer=BOUND[0], datatype=BOUND[1]))

    def box(ld, x0, y0, x1, y1):
        top.add(gdstk.rectangle((x0, y0), (x1, y1), layer=ld[0], datatype=ld[1]))

    def via(cx, cy):
        # ルータの via_1 PCell と同じ寸法の生ボックスで描く（このセルは
        # ライブラリセル扱いなので PCell 依存を持ち込まない）。
        box(V1, cx - 0.7, cy - 0.7, cx + 0.7, cy + 0.7)
        box(M1, cx - HALF, cy - HALF, cx + HALF, cy + HALF)
        box(M2, cx - HALF, cy - HALF, cx + HALF, cy + HALF)

    def fanout(name, use, px0, py0, px1, py1, rx):
        """1 本ぶんの中継。ピン(M2) → M1 で右 → M2 で上 → 上辺パッド。"""
        cy = round((py0 + py1) / 2.0, 3)
        # ピンから V1 列まで M2 を伸ばす（マクロの外へ出すぶんだけ）
        box(M2, px0, cy - HALF, VIA_X + HALF, cy + HALF)
        via(VIA_X, cy)
        # M1 を右へ
        box(M1, VIA_X - HALF, cy - HALF, rx + HALF, cy + HALF)
        via(rx, cy)
        # M2 を上辺まで
        box(M2, rx - HALF, cy - HALF, rx + HALF, PAD_Y1)
        # パッド本体 + ピンマーカ + ラベル
        box(M2PIN, rx - HALF, PAD_Y0, rx + HALF, PAD_Y1)
        top.add(gdstk.Label(name, (rx, (PAD_Y0 + PAD_Y1) / 2.0),
                            layer=M2LBL[0], texttype=M2LBL[1], magnification=2.0))
        return dict(name=name, use=use, x0=round(rx - HALF, 3), y0=PAD_Y0,
                    x1=round(rx + HALF, 3), y1=PAD_Y1)

    pins = []
    for k, (name, use, x0, y0, x1, y1) in enumerate(sig):
        rx = round(SIG_X0 + k * SIG_DX, 3)
        if rx + HALF > W - 1e-6:
            raise SystemExit(f"信号パッド {name} の x={rx} がコア幅を超える")
        pins.append(fanout(name, use, x0, y0, x1, y1, rx))
    for k, (name, use, x0, y0, x1, y1) in enumerate(pwr_r):
        pins.append(fanout(name, use, x0, y0, x1, y1, PWR_X[k]))

    # 干渉チェック: 同一レイヤの M2 ライザ同士が 2.0 µm 以上離れているか
    xs = sorted(p["x0"] + HALF for p in pins)
    tight = [(a, b) for a, b in zip(xs, xs[1:]) if b - a < PAD + M2_GAP - 1e-6]
    if tight:
        raise SystemExit(f"M2 ライザの間隔が足りない: {tight[:3]}")
    ys = sorted(round((r[3] + r[5]) / 2.0, 3) for r in sig + pwr_r)
    tighty = [(a, b) for a, b in zip(ys, ys[1:]) if b - a < PAD + 1.4 - 1e-6]
    if tighty:
        raise SystemExit(f"M1 引き出しの y 間隔が足りない: {tighty[:3]}")

    # 標準セルも同じライブラリに入れて、P&R が読むファイルを 1 つにする
    for c in lib.cells:
        if c.name not in seen:
            seen.add(c.name)
            out.add(c)
    gds = os.path.join(cfg.ROOT, "lef", "TR-1um_PNR.gds")
    out.write_gds(gds, timestamp=__import__("datetime").datetime(2026, 1, 1))

    # --- LEF ---------------------------------------------------------------
    L = [f"MACRO {CELL}", "  CLASS BLOCK ;", f"  FOREIGN {CELL} 0.000 0.000 ;",
         "  ORIGIN 0.000 0.000 ;", f"  SIZE {W:.3f} BY {H:.3f} ;",
         "  SYMMETRY X Y ;"]
    for p in pins:
        L += [f"  PIN {p['name']}", "    DIRECTION INOUT ;",
              f"    USE {p['use']} ;", "    PORT", "      LAYER METAL2 ;",
              f"        RECT {p['x0']:.3f} {p['y0']:.3f} {p['x1']:.3f} {p['y1']:.3f} ;",
              "    END", f"  END {p['name']}"]
    L += ["  OBS", "    LAYER METAL1 ;",
          f"      RECT 0.000 0.000 {W:.3f} {H:.3f} ;",
          "    LAYER METAL2 ;",
          f"      RECT 0.000 0.000 {W:.3f} {H:.3f} ;",
          "  END", f"END {CELL}", ""]
    leff = os.path.join(cfg.ROOT, "lef", "TR-1um_PNR.lef")
    open(leff, "w").write(open(cfg.LIB_LEF).read()
                          + "\n" + "\n".join(L))

    print(f"wrote {os.path.relpath(gds, cfg.ROOT)}")
    print(f"wrote {os.path.relpath(leff, cfg.ROOT)}")
    print(f"  {CELL} {W} x {H} um   （{SRC_CELL} を R90 して {h_src} x {w_src}、"
          f"右の空き地 {W - h_src:.1f} um に中継）")
    print(f"  上辺パッド: 信号 {len(sig)} 本 x {SIG_X0}…"
          f"{SIG_X0 + (len(sig)-1)*SIG_DX:.1f}（{SIG_DX} µm ピッチ）")
    print(f"              電源 {len(pwr_r)} 本 x {PWR_X[:len(pwr_r)]}")
    print(f"  ** 電源はマクロ右辺の 2 本ずつだけを引き出している"
          f"（左辺はマクロの真上を通れない）。チップ側で太く受けること")
    if plot:
        draw(plot, W, H, h_src, sig, pwr_r, pins)
    return gds, leff


def draw(path, W, H, mw, sig, pwr, pins):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(15, 5))
    ax.add_patch(Rectangle((0, 0), W, H, fc="#fcfcfc", ec="#2c3e50", lw=1.4))
    ax.add_patch(Rectangle((0, 0), mw, H, fc="#f8c471", ec="#ca6f1e", lw=1.0))
    ax.text(mw / 2, H / 2, f"{SRC_CELL} (R90)  {mw} x {H}", ha="center",
            va="center", fontsize=9)
    for name, use, x0, y0, x1, y1 in sig + pwr:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#8e44ad", ec="none"))
    for p, (name, use, x0, y0, x1, y1) in zip(pins, sig + pwr):
        cy = (y0 + y1) / 2
        rx = p["x0"] + 1.7
        ax.plot([x0, rx], [cy, cy], color="#2980b9", lw=0.8)
        ax.plot([rx, rx], [cy, p["y1"]], color="#e67e22", lw=0.8)
        ax.add_patch(Rectangle((p["x0"], p["y0"]), 3.4, 3.4, fc="#8e44ad", ec="none"))
    ax.set_xlim(-20, W + 20)
    ax.set_ylim(-20, H + 20)
    ax.set_aspect("equal")
    ax.set_title(f"{CELL}  {W} x {H} um   blue = M1 (horizontal), "
                 f"orange = M2 (vertical), purple = pins/pads", fontsize=9)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print(f"wrote {os.path.relpath(path, cfg.ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plot", default=None)
    a = ap.parse_args()
    build(a.plot)

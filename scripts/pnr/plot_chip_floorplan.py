#!/usr/bin/env python3
"""plot_chip_floorplan.py -- チップ組み立ての確認図。

  usage: python3 scripts/pnr/plot_chip_floorplan.py [-o layout/chip/floorplan.png]

`assemble_top.py` が置いたものを俯瞰する:

  * ダイ枠（2500 x 2500）と `OSS_FRAME_GIO` の OBS（= パッドとコーナー）
  * 端子リング（`GIO_PIN_RADIUS` = 921.7）
  * コアの bbox と、**コアのトップピン 14 本 + VDD/GND の実位置**

チップ配線はこのピンからパッドの端子まで引くので、どの辺に何本出ているかを
先に見ておく。ラベルは ASCII のみ（クラウド側に日本語フォントが無い）。
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                             # noqa: E402
from matplotlib.patches import Rectangle                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import td4_config as cfg                                    # noqa: E402
import klayout.db as db                                     # noqa: E402


def core_port_pins(gds, dx, dy):
    """[(name, x, y)] -- コアのピンラベル（M1PIN/M2PIN のテキスト）をチップ座標で。"""
    ly = db.Layout()
    ly.read(gds)
    top = ly.cell(cfg.TOP_CELL_NAME)
    out = []
    for lay, dt in ((49, 0), (48, 0)):
        for s in top.shapes(ly.layer(lay, dt)).each():
            if s.is_text():
                out.append((s.text.string, s.text.x * ly.dbu + dx, s.text.y * ly.dbu + dy))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default=os.path.join(cfg.CHIP, "floorplan.png"))
    ap.add_argument("--core-gds", default=None)
    a = ap.parse_args()

    core_gds = a.core_gds or cfg.FINAL_GDS
    geom = cfg.chip_geometry(core_gds)
    die, rects = cfg.frame_obs_rects()
    h = die / 2
    x0, y0, x1, y1 = geom["core_chip_bbox"]
    dx, dy = geom["core_offset"]

    fig, ax = plt.subplots(figsize=(9.5, 9.5))
    ax.add_patch(Rectangle((-h, -h), die, die, facecolor="none",
                           edgecolor="#333", lw=1.4))
    for p in rects:
        ax.add_patch(Rectangle((p[0], p[1]), p[2] - p[0], p[3] - p[1],
                               facecolor="#dedede", edgecolor="#b5b5b5",
                               lw=0.4, alpha=0.8, hatch="////"))
    # 実ジオメトリの内壁（= 本当の開口）。OBS の四隅の宣言は粗いので、
    # そちらはハッチだけにして、こちらを実線で出す。
    lo, hi = cfg.frame_opening()
    ax.add_patch(Rectangle((lo, lo), hi - lo, hi - lo, facecolor="none",
                           edgecolor="#2e7d32", lw=1.6))
    r = cfg.GIO_PIN_RADIUS
    ax.add_patch(Rectangle((-r, -r), 2 * r, 2 * r, facecolor="none",
                           edgecolor="#00838f", lw=0.9, ls="--"))
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="#2e6fb7",
                           alpha=0.18, edgecolor="#2e6fb7", lw=1.2))

    pins = core_port_pins(core_gds, dx, dy)
    seen = {}
    for name, px, py in pins:
        seen.setdefault(name, []).append((px, py))
    for name, pts in seen.items():
        for px, py in pts:
            ax.plot([px], [py], marker="o", ms=2.6,
                    color="#c0392b" if name not in ("VDD", "GND") else "#e67e22")
        px, py = pts[0]
        if name not in ("VDD", "GND"):
            ax.annotate(name, (px, py), fontsize=6.5, color="#c0392b",
                        xytext=(0, 6 if py > 0 else -10), textcoords="offset points",
                        ha="center")

    ax.set_xlim(-h - 60, h + 60)
    ax.set_ylim(-h - 60, h + 60)
    ax.set_aspect("equal")
    ax.set_title(
        f"{cfg.CHIP_TOP_CELL}   die {die:.0f} x {die:.0f} um\n"
        f"core {cfg.TOP_CELL_NAME} @ ({dx}, {dy})  "
        f"[{x1-x0:.1f} x {y1-y0:.1f}]   "
        f"opening {hi-lo:.0f} x {hi-lo:.0f} (measured)   "
        f"channel T/B {geom['channel_top'][0]:.1f}  L/R {geom['channel_left'][0]:.1f} um",
        fontsize=10, loc="left")
    ax.tick_params(labelsize=7)
    fig.text(0.5, 0.015,
             "hatched grey = LEF OBS (coarse, corners over-declared)   "
             "green = measured opening 1840x1840   dashed cyan = pin ring 921.7   "
             "blue = core bbox   red = core port pins   orange = VDD/GND pins",
             ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fig.savefig(a.out, dpi=140)
    print(f"wrote {os.path.relpath(a.out, cfg.ROOT)}  "
          f"({len(seen)} 個のピン名、{len(pins)} 個のマーカ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

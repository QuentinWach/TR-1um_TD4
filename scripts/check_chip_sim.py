#!/usr/bin/env python3
"""check_chip_sim.py -- チップの ngspice 結果を判定して波形も描く。

  usage: python3 scripts/check_chip_sim.py [LOG] [--csv CSV] [--png PNG]

`gen_chip_tb.py` が仕込んだ `.meas` の値（`o0_<i>` … `o3_<i>` と `cf_<i>`）を
ログから拾い、VDD/2 で 0/1 に落として `out_port` の並びを復元する。

期待する並びは `hdl/tb/tb_td4_soc_arr.v` と同じ LED フラッシャ:

    0: OUT 3 / 1: OUT 6 / 2: OUT 12 / 3: OUT 8 / 4: JMP 0

**JMP のサイクルは OUT が動かない**ので、1 周は 5 サイクルで
`[3, 6, 12, 8, 8]` になる（Verilog の TB は `i%4==3` のときに 1 サイクル
読み飛ばしていて、同じことを別の書き方で見ている）。

`--csv` があれば `wrdata` の波形も読んで PNG にする。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

# （TD4 版はここで APR_MACRO_MODE=portrait を固定していた。I2C の
#   i2c_config はマクロを持たないので不要。）
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apr_path  # noqa: F401  設計ルートを sys.path へ
import config as cfg                                    # noqa: E402

SIM = os.path.join(cfg.CHIP, "simulation")
VDD = 5.0
LOOP = [3, 6, 12, 8, 8]        # OUT 3 / 6 / 12 / 8 / JMP（OUT は保持）


def read_meas(path):
    """{(kind, i): 値}。`o0_3 = 4.99e+00` の形。"""
    out = {}
    pat = re.compile(r"^\s*(o[0-3]|cf)_(\d+)\s*=\s*([-\d.eE+]+)")
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = pat.match(ln)
        if m:
            out[(m.group(1), int(m.group(2)))] = float(m.group(3))
    return out


def plot(csv, png, t_exec=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    d = np.loadtxt(csv)
    # wrdata は「列ごとに (t, v)」を並べる
    names = ["OUT[0]", "OUT[1]", "OUT[2]", "OUT[3]", "CF", "CLK", "WR", "EXEC"]
    n = min(len(names), d.shape[1] // 2)
    fig, ax = plt.subplots(n, 1, figsize=(11, 1.05 * n), sharex=True)
    for i in range(n):
        t, v = d[:, 2 * i] * 1e9, d[:, 2 * i + 1]
        ax[i].plot(t, v, lw=0.8, color="#1f6fb4")
        ax[i].set_ylabel(names[i], fontsize=7, rotation=0, ha="right", va="center")
        ax[i].set_ylim(-0.5, VDD + 0.5)
        ax[i].tick_params(labelsize=6)
        ax[i].grid(alpha=0.25, lw=0.4)
        if t_exec:
            ax[i].axvline(t_exec, color="#c0392b", lw=0.8, ls="--")
    ax[-1].set_xlabel("time [ns]   (red dashed = exec goes high)", fontsize=8)
    ax[0].set_title(f"{cfg.CHIP_TOP_CELL}  extracted netlist, ngspice "
                    f"(program load then run)", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(png, dpi=140)
    print(f"wrote {cfg.show(png)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", nargs="?", default=os.path.join(SIM, "chip_tb.log"))
    ap.add_argument("--csv", default=os.path.join(SIM, "chip_tb.raw.csv"))
    ap.add_argument("--png", default=os.path.join(SIM, "chip_tb.png"))
    ap.add_argument("--t-exec", type=float, default=None)
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args()

    m = read_meas(a.log)
    if not m:
        raise SystemExit(f"{a.log} に .meas の結果が無い")
    n = max(i for _, i in m) + 1

    bad = []
    print("  cycle   OUT  期待   CF   o3 o2 o1 o0 [V]")
    for i in range(n):
        bits = [1 if m[(f"o{b}", i)] > VDD / 2 else 0 for b in range(4)]
        val = sum(b << k for k, b in enumerate(bits))
        cf = 1 if m[("cf", i)] > VDD / 2 else 0
        exp = LOOP[i % len(LOOP)]
        ok = val == exp and cf == 0
        if not ok:
            bad.append((i, val, exp, cf))
        print(f"  {i:>5}  {val:>4}  {exp:>4}  {cf:>4}   "
              + " ".join(f"{m[(f'o{b}', i)]:5.2f}" for b in (3, 2, 1, 0))
              + ("" if ok else "   <-- NG"))

    # ★ **合否を先に出す。** 作図はおまけなので、そこで落ちても判定は返す。
    #   2026-09-16: `matplotlib` が入っていない環境で、**全 12 サイクル
    #   期待どおりなのに作図の ImportError で落ちて、判定が 1 行も出ず
    #   終了コードも 1** になった。**任意の依存を、必須の判定より前に
    #   置かない。**
    print()
    if bad:
        for i, val, exp, cf in bad:
            print(f"PROBLEM: cycle {i}: OUT={val} 期待 {exp} / CF={cf}")
        rc = 1
    else:
        print(f"{n} サイクルすべて期待どおり（OUT = "
              + ", ".join(str(LOOP[i % len(LOOP)]) for i in range(min(n, 10)))
              + (" …" if n > 10 else "") + "、CF は終始 0）")
        rc = 0

    if not a.no_plot and os.path.exists(a.csv):
        try:
            plot(a.csv, a.png, a.t_exec)
        except ImportError as e:
            print(f"  （波形の図は描かない: {e}。"
                  "pip install matplotlib で描けるようになる）")
        except Exception as e:                      # 図で判定を落とさない
            print(f"  （波形の図を描けなかった: {type(e).__name__} {e}）")
    return rc


if __name__ == "__main__":
    sys.exit(main())

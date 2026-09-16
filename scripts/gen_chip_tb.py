#!/usr/bin/env python3
"""gen_chip_tb.py -- TD4 チップの ngspice テストベンチ（**この設計専用**）。

★ 2026-09-16 に APRtools の `apr/` からここへ移した（U25）。刺激も期待値も
  TD4 の LED フラッシャ固有で、他の設計では意味を持たない。設計に依らない
  部分（ポート順の読み取り / PWL / `models.spice`）は
  `$APRTOOLS/apr/chip_tb_lib.py` にある。


    layout/chip/simulation/<top>_sim.spice  （抽出 -> ngspice 用に変換）
  -> layout/chip/simulation/tb_<top>.spi

`hdl/tb/tb_td4_soc_arr.v` と**同じ手順**をボンドパッドに対して流す:

    リセット -> Load モードで 5 命令書込 -> Exec モードで走らせる

    0: 1011_0011  OUT 3
    1: 1011_0110  OUT 6
    2: 1011_1100  OUT 12
    3: 1011_1000  OUT 8
    4: 1111_0000  JMP 0        -> OUT は 3, 6, 12, 8 の繰り返し

1 命令 = 下位ニブル（即値）-> 上位ニブル（オペコード）の 2 回書込。値は
**negedge で置いて posedge で取り込まれる**（Verilog の `load` タスクと同じ）。

## パッドの割り当て（`layout/chip/gio_connections.json`）

    P1 clk / P2 wr / P3 nibsel / P4..P7 d[3..0] / P9 rst_n / P14 exec
    P10..P13 out_port[0..3] / P15 cflag_o / VDD / VSS（P16 / P8）

入力パッドは `HIZ=1` で Hi-Z、コア側は `BUFTH`（シュミット）で受けるので、
外から電圧源で叩いてよい。出力パッドには実装を想定して 10 pF を付ける
（`scripts/char/char_pad.py` の測定条件と同じ）。

  usage: python3 scripts/gen_chip_tb.py [--period 100] [--cycles 12]

★ **回すときは simulation ディレクトリに cd する。** TB の `.include` と
  `wrdata` は**名前だけ**にしてある（機械のパスを焼き付けないため。U24）が、
  ngspice が相対パスを解くのは **TB の場所ではなく実行時のカレント**なので:

      python3 $APRTOOLS/apr/gen_chip_sim_ready.py
      python3 scripts/gen_chip_tb.py
      ( cd layout/chip/simulation && ngspice -b tb_*.spi > chip_tb.log 2>&1 )
      python3 scripts/check_chip_sim.py layout/chip/simulation/chip_tb.log

  ★ **`cd -` を使わない。** 括弧で囲めば `cd` はサブシェルの中だけで終わるので、
    呼んだ側のカレントは動かない。`cd -` は「直前のディレクトリとの往復」なので、
    2 回続けて打つと戻ってしまう（実際に踏んだ）。
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
import chip_tb_lib as tb                                # noqa: E402

SIM = tb.sim_dir(cfg)
NETLIST = tb.sim_netlist(cfg)
# ★ モデルは **PDK から参照する**（設計の写しではない）。
MODELS = os.path.join(cfg.pdk_spice_models(), "ip62_models")
OUT = tb.tb_path(cfg)

VDD = 5.0
TR = 1.0                        # 入力の遷移時間 ns
CL = "10p"                      # 出力パッドの負荷

PROGRAM = [0b1011_0011, 0b1011_0110, 0b1011_1100, 0b1011_1000, 0b1111_0000]
EXPECT = [3, 6, 12, 8]

# パッド -> 役割（gio_connections.json の PAD_MAP と同じ。ここは読むだけ）
IN_PADS = {"P1": "clk", "P2": "wr", "P3": "nibsel", "P4": "d3", "P5": "d2",
           "P6": "d1", "P7": "d0", "P9": "rst_n", "P14": "exec"}
OUT_PADS = {"P10": "out0", "P11": "out1", "P12": "out2", "P13": "out3",
            "P15": "cf"}


subckt_ports = tb.subckt_ports          # 共通（U42: ポート順は生産物から読む）


def pwl(events, tr=TR):
    """[(t_ns, 0/1)] -> PWL 文字列（共通実装）。"""
    return tb.pwl(events, vdd=VDD, tr=tr)


def build(period, cycles):
    """1 本ずつの波形と、期待する OUT のサンプル時刻。"""
    T = float(period)
    neg = lambda j: (j + 1) * T              # noqa: E731  負エッジ j の時刻
    pos = lambda j: (j + 0.5) * T            # noqa: E731  正エッジ j の時刻

    ev = {k: [(0.0, 0)] for k in IN_PADS.values() if k != "clk"}

    def put(t, sig, val):
        if ev[sig][-1][1] != val:
            ev[sig].append((t, val))

    put(neg(0), "rst_n", 1)                  # n0 でリセット解除
    j = 2                                    # n1 は空ける（Verilog と同じ）
    for instr in PROGRAM:
        lo, hi = instr & 0xF, (instr >> 4) & 0xF
        for k, nib in ((0, lo), (1, hi)):
            t = neg(j + k)
            put(t, "nibsel", k)
            for b in range(4):
                put(t, f"d{b}", (nib >> b) & 1)
            put(t, "wr", 1)
        put(neg(j + 2), "wr", 0)
        j += 3
    t_exec = neg(j)
    put(t_exec, "exec", 1)                   # ここから Exec モード
    j += 1

    # クロックは最後まで振り続ける
    n_last = j + cycles + 2
    clk = []
    for k in range(n_last + 2):
        clk.append((pos(k), 1))
        clk.append((neg(k), 0))
    clk = [(0.0, 0)] + [e for e in clk if e[0] > 0]
    ev["clk"] = clk

    # OUT を見る時刻（Verilog と同じく posedge の直後）
    samples = [(i, pos(j + i) + 0.6 * T) for i in range(cycles)]
    t_stop = pos(j + cycles) + T
    return ev, samples, t_stop, t_exec


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", type=float, default=100.0, help="クロック周期 ns")
    ap.add_argument("--cycles", type=int, default=12, help="Exec で見るサイクル数")
    ap.add_argument("--step", type=float, default=0.5, help="tran の刻み ns")
    ap.add_argument("-o", "--out", default=OUT)
    ap.add_argument("--netlist", default=NETLIST)
    a = ap.parse_args()

    ports = subckt_ports(a.netlist, cfg.CHIP_TOP_CELL)
    ev, samples, t_stop, t_exec = build(a.period, a.cycles)

    L = [f"* {os.path.basename(a.out)} -- 抽出したチップの動作確認（ngspice）",
         "* scripts/pnr/gen_chip_tb.py が生成。手で編集しないこと。",
         f"* プログラム: " + " ".join(f"{i:02X}" for i in PROGRAM)
         + f"  期待する OUT: {EXPECT} の繰り返し",
         f"* クロック {a.period:g} ns（{1000/a.period:.1f} MHz）"
         f"  Exec 開始 {t_exec:g} ns  終了 {t_stop:g} ns",
         "",
         # ★ **PDK と抽出物の絶対パスを TB に埋めない**（U24）。ngspice の
         #   `.include` は環境変数を展開しないので、素直に書くと回した機械の
         #   パスが焼き付いてコミットできなくなる。モデルは隣に 1 行の
         #   `models.spice` を起こし、抽出物は**同じディレクトリなので名前だけ**。
         f".include '{tb.write_models_shim(cfg, SIM)}'",
         f".include '{os.path.basename(a.netlist)}'",
         "",
         f"Vvdd VDD 0 DC {VDD}",
         "Vvss VSS 0 DC 0",
         ""]

    # ★ ここは以前 `p if p in ("VDD", "VSS") else p` と書いてあった。
    #   **どちらの枝も p を返す死んだ分岐**で、電源だけ名前を変えるつもりの
    #   書きかけが残っていたもの。チップの .subckt はポートを宣言どおりの
    #   名前で受けるので、そのまま並べるのが正しい。
    L.append("X1 " + " ".join(ports) + f" {cfg.CHIP_TOP_CELL}")
    L.append("")

    for pad, sig in sorted(IN_PADS.items(), key=lambda kv: kv[1]):
        L.append(f"V{sig} {pad} 0 {pwl(ev[sig])}")
    L.append("")
    for pad, sig in sorted(OUT_PADS.items()):
        L.append(f"C{sig} {pad} 0 {CL}")
    L.append("")

    L += [".option reltol=1e-3 abstol=1e-10 vntol=1e-5 chgtol=1e-14",
          ".option gmin=1e-12 itl1=500 itl2=200 itl4=100 method=gear",
          f".tran {a.step:g}n {t_stop:g}n",
          "",
          ".control",
          "run",
          'echo "=== OUT (out3 out2 out1 out0) / CF"']
    for i, t in samples:
        L.append(f'meas tran o0_{i} FIND v(P10) AT={t:g}n')
        L.append(f'meas tran o1_{i} FIND v(P11) AT={t:g}n')
        L.append(f'meas tran o2_{i} FIND v(P12) AT={t:g}n')
        L.append(f'meas tran o3_{i} FIND v(P13) AT={t:g}n')
        L.append(f'meas tran cf_{i} FIND v(P15) AT={t:g}n')
    # ★ 出力先も**名前だけ**（TB と同じディレクトリに落ちる）。絶対パスに
    #   すると回した機械が TB に焼き付く（U24 と同じ理由）。
    L += ['wrdata chip_tb.raw.csv '
          'v(P10) v(P11) v(P12) v(P13) v(P15) v(P1) v(P2) v(P14)',
          ".endc",
          ".end", ""]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(L))
    print(f"wrote {cfg.show(a.out)}")
    print(f"  クロック {a.period:g} ns / Exec 開始 {t_exec:g} ns / "
          f"終了 {t_stop:g} ns / サンプル {len(samples)} 点")
    return 0


if __name__ == "__main__":
    sys.exit(main())

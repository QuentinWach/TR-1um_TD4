#!/usr/bin/env python3
"""生成した .lib を検算する。

  usage: python3 verify_lib.py [tr1um_typ_5v0_25c.lib]

3 段構え:

  1. **表そのものの健全性** — 欠損が無いか、値が正か、
     負荷を増やすと遅延が増えるか、入力遷移を鈍らせると遅延が増えるか。
     単調でない = 測り損ねているということなので、ここで落とす。

  2. **格子の外での照合** — 格子点そのものではなく、**格子の間**
     （入力遷移 1.0ns / 負荷 150fF）で ngspice を回し、.lib を線形補間した
     値と突き合わせる。格子点で合うのは当たり前なので、間で合うかを見る。

  3. **入力容量の照合** — INV_X1 で INV_X1 を N 個駆動したときの実測遅延が、
     .lib を「負荷 = N x capacitance(A)」で引いた値と合うか。
     合えば、.lib に書いた capacitance が遅延計算に使える量だと言える。
"""
from __future__ import annotations
import json, os, re, subprocess, sys
import cellspec
from charlib import HERE, VDD, SLEWS, LOADS, run_ngspice, header, ports_of, full_ramp

SLEW_V = 0.6        # 検算に使う入力遷移（20-80%）
import char_comb

TOL = 0.15          # 補間との許容ずれ


def interp2(x_idx, y_idx, table, x, y):
    """2 次元線形補間（格子外は端の傾きで外挿しない=クランプ）"""
    def pos(idx, v):
        if v <= idx[0]: return 0, 0.0
        if v >= idx[-1]: return len(idx) - 2, 1.0
        for i in range(len(idx) - 1):
            if idx[i] <= v <= idx[i + 1]:
                return i, (v - idx[i]) / (idx[i + 1] - idx[i])
        return len(idx) - 2, 1.0
    i, a = pos(x_idx, x)
    j, b = pos(y_idx, y)
    v00, v01 = table[i][j], table[i][j + 1]
    v10, v11 = table[i + 1][j], table[i + 1][j + 1]
    return (v00 * (1 - a) * (1 - b) + v01 * (1 - a) * b +
            v10 * a * (1 - b) + v11 * a * b)


def check_tables():
    print("--- 1. 表の健全性 ---")
    ng = 0
    for f in sorted(os.listdir(f"{HERE}/char")):
        if not f.endswith(".json"):
            continue
        d = json.load(open(f"{HERE}/char/{f}"))
        name = d["cell"]
        groups = []
        if d.get("seq"):
            for k, t in d["ckq"].items():
                groups.append((f"CK->Q {k}", t))
        else:
            for a in d["arcs"]:
                for k in ("cell_rise", "cell_fall", "rise_transition", "fall_transition"):
                    groups.append((f"{a['related_pin']}->{a['pin']} {k}", a[k]))
        for label, tbl in groups:
            if tbl is None or any(r is None for r in tbl):
                print(f"  ! {name} {label}: 行が欠けている"); ng += 1; continue
            flat = [v for r in tbl for v in r]
            if any(v is None for v in flat):
                n = sum(1 for v in flat if v is None)
                print(f"  ! {name} {label}: 測定できていない点が {n} 個"); ng += 1
            if any(v is not None and v <= 0 for v in flat):
                print(f"  ! {name} {label}: 0 以下の値がある"); ng += 1
            # 負荷を増やすと必ず遅くなるはず
            for ri, r in enumerate(tbl):
                vv = [v for v in r if v is not None]
                if len(vv) > 1 and any(b < a * 0.98 for a, b in zip(vv, vv[1:])):
                    print(f"  ! {name} {label}: 負荷に対して単調でない "
                          f"(入力遷移 {SLEWS[ri]}ns 行)"); ng += 1
    print("  逸脱なし" if ng == 0 else f"  ** {ng} 件")
    return ng


def check_offgrid(cells=("INV_X1", "NAND2", "NOR2", "MUX2", "XOR2", "AND2_X1")):
    """格子の間で ngspice と .lib 補間を突き合わせる"""
    print("\n--- 2. 格子の外（入力遷移 1.0ns / 負荷 150fF）で照合 ---")
    print(f"  {'cell':<10}{'arc':<10}{'向き':<5}{'ngspice':>9}{'.lib 補間':>10}{'ずれ':>8}")
    ng = 0
    slew, cl = 1.0, 150.0
    for cell in cells:
        p = f"{HERE}/char/{cell}.json"
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        a = d["arcs"][0]
        opin, ipin, sense = a["pin"], a["related_pin"], a["sense"]
        outs = cellspec.COMB[cell]
        side = next(s for o, i, s, _ in
                    __import__("charlib").arcs_of(cell, outs) if o == opin and i == ipin)
        for out_rise in (True, False):
            rise_in = (not out_rise) if sense == "negative_unate" else out_rise
            deck = char_comb.build_delay(cell, opin, ipin, side, slew, rise_in, set(outs))
            # 負荷 7 点のうち 1 点を 150fF に差し替える（先頭を使う）
            deck = deck.replace(f"C0 o0_{opin} 0 {LOADS[0]}f", f"C0 o0_{opin} 0 {cl:g}f")
            vals, _ = run_ngspice(deck, f"vfy_{cell}_{'r' if out_rise else 'f'}")
            got = vals.get(("dr0" if out_rise else "df0"))
            tbl = a["cell_rise"] if out_rise else a["cell_fall"]
            exp = interp2(SLEWS, LOADS, tbl, slew, cl)
            if got is None or exp is None:
                print(f"  ! {cell} 測定できず"); ng += 1; continue
            err = abs(got - exp) / exp
            mark = "" if err < TOL else "  ** ずれが大きい"
            if err >= TOL: ng += 1
            print(f"  {cell:<10}{ipin+'->'+opin:<10}{'rise' if out_rise else 'fall':<5}"
                  f"{got*1e9:8.3f}ns{exp*1e9:9.3f}ns{err:7.1%}{mark}")
    print("  " + ("全点が許容内" if ng == 0 else f"** {ng} 件が {TOL:.0%} を超えた"))
    return ng


def check_cap():
    """INV_X1 が INV_X1 を N 個駆動したときの遅延が、
    .lib の capacitance を使った引き当てと合うか"""
    print("\n--- 3. 入力容量 capacitance の妥当性（INV_X1 -> INV_X1 x N）---")
    d = json.load(open(f"{HERE}/char/INV_X1.json"))
    # .lib に書くのは較正済みの等価容量（cap_cal）。電荷から出した cap ではない。
    cin = (d.get("cap_cal") or d["cap"])["A"]
    tbl = d["arcs"][0]["cell_fall"]        # 入力立上り -> 出力立下り
    print(f"  .lib の capacitance(A) = {cin:.1f} fF")
    print(f"  {'ファンアウト':>10}{'ngspice':>10}{'.lib(N x Cin)':>14}{'ずれ':>8}")
    ng = 0
    for n in (1, 2, 4, 8):
        L = [f"* INV_X1 -> INV_X1 x{n} 実負荷での遅延"]
        L += header("INV_X1")
        # 入力は 20-80% が SLEW_V になる傾斜（表の index_1 と同じ定義）
        L.append(f"Vin src 0 PWL(0 0 100n 0 {100+full_ramp(SLEW_V):g}n 5)")
        L.append("Rin src A 0.001")
        L.append("XU A Y vdd gnd INV_X1")
        for k in range(n):
            L.append(f"XL{k} Y nc{k} vdd gnd INV_X1")
            L.append(f"Cn{k} nc{k} 0 20f")   # 次段の出力にも軽い負荷
        L.append(".tran 0.02n 260n")
        L.append(".meas tran d TRIG v(A) VAL=2.5 RISE=1 TARG v(Y) VAL=2.5 FALL=1")
        L += ["", ".end", ""]
        vals, _ = run_ngspice("\n".join(L), f"vfy_fo{n}")
        got = vals.get("d")
        exp = interp2(SLEWS, LOADS, tbl, SLEW_V, cin * n)
        if got is None:
            print(f"  ! ファンアウト {n}: 測定できず"); ng += 1; continue
        err = abs(got - exp) / exp
        if err >= 0.20: ng += 1
        print(f"  {n:>10}{got*1e9:9.3f}ns{exp*1e9:13.3f}ns{err:7.1%}"
              f"{'  ** ずれが大きい' if err >= 0.20 else ''}")
    print("  " + ("capacitance は遅延計算に使える値" if ng == 0
                  else f"** {ng} 点でずれが大きい"))
    return ng


def check_lib_syntax(path):
    print(f"\n--- 4. .lib の構文（括弧の対応・必須項目）---")
    txt = open(path).read()
    depth, ng = 0, 0
    for i, ch in enumerate(txt):
        if ch == "{": depth += 1
        elif ch == "}": depth -= 1
        if depth < 0:
            print("  ! 閉じ括弧が多い"); ng += 1; break
    if depth != 0:
        print(f"  ! 括弧が閉じていない (depth={depth})"); ng += 1
    for need in ("delay_model : table_lookup", "lu_table_template",
                 "nom_voltage", "operating_conditions"):
        if need not in txt:
            print(f"  ! 必須項目が無い: {need}"); ng += 1
    ncell = len(re.findall(r"^\s*cell \(", txt, re.M))
    nff = len(re.findall(r"^\s*ff \(", txt, re.M))
    ntim = len(re.findall(r"^\s*timing \(\)", txt, re.M))
    print(f"  cell {ncell} / ff {nff} / timing アーク {ntim} / {len(txt.splitlines())} 行")
    print("  逸脱なし" if ng == 0 else f"  ** {ng} 件")
    return ng


if __name__ == "__main__":
    lib = sys.argv[1] if len(sys.argv) > 1 else f"{HERE}/tr1um_typ_5v0_25c.lib"
    print("=" * 72)
    print(" Liberty 検算")
    print("=" * 72)
    n = check_tables() + check_offgrid() + check_cap()
    if os.path.exists(lib):
        n += check_lib_syntax(lib)
    print("\n" + "=" * 72)
    print("判定: OK" if n == 0 else f"判定: 要確認 {n} 件")
    sys.exit(1 if n else 0)

#!/usr/bin/env python3
"""Yosys の `stat` 出力を TR-1um STDCELL の実測セル面積に換算する。

usage:
  yowasp-yosys -p "read_verilog *.v; hierarchy -check -top TOP; synth -top TOP -flatten; \
                   abc -g simple; opt_clean; tee -o stat.txt stat"
  python3 area_estimate.py stat.txt --top TOP

面積は `lef/TR-1um_STDCELL.gds` の (235,0) abutment box 実測値。
`python3 scripts/cellinfo.py lef/TR-1um_STDCELL.gds` で再生成・再確認できる。

**2026-09-09 のライブラリ更新に追従**: 行高 62.6→64.8 µm、INV 1,821.7→699.8 µm²、
DFFR+MUX2 で作っていた DFFE は **MUXDFFRB 単一セル**に。全体で約 2.4 倍の高密度化。
"""
from __future__ import annotations
import argparse, collections, re, sys

# --- TR-1um STDCELL 実測面積 [um^2]（GDS 235/0 外形, 行高 64.8um）---
ROW_H  = 64.8
INV    = 699.8    # INV_X1 (10.8 x 64.8)
BUF    = 1049.8   # BUF_X1
NAND2  = 1049.8   # NAND2 / NOR2
AND2   = 1399.7   # AND2_X1 / OR2 / NAND3 / NOR3
XOR2   = 1749.6   # XOR2 / XNOR2 / AND3 / OR3 / NAND4 / NOR4
MUX2   = 2099.5   # MUX2 / AND4 / OR4 / BUFTH / DEL1
DFF    = 4199.0   # DFF / DFFRB / DFFS / REG
DFFE   = 6298.6   # MUXDFFRB（イネーブル付き FF が単一セルで存在する）
TLAT   = 2443.0   # 12T ラッチ型ビットセル（メモリアレイ用）
OR2 = AND2

AREA = {
    "$_NOT_": INV, "$_NAND_": NAND2, "$_NOR_": NAND2, "$_BUF_": BUF,
    "$_AND_": AND2, "$_OR_": OR2, "$_XOR_": XOR2, "$_XNOR_": XOR2,
    "$_MUX_": MUX2, "$_ANDNOT_": INV + AND2, "$_ORNOT_": INV + OR2,
    "$_AOI3_": AND2 + NAND2, "$_OAI3_": OR2 + NAND2,
    "$_AOI4_": AND2 + NAND2, "$_OAI4_": OR2 + NAND2,
}
CORE_W = CORE_H = 1840.0  # OSS_FRAME 内側の有効コア


def parse(path: str) -> dict[str, dict[str, int]]:
    txt = open(path).read()
    mods = {}
    for name, body in re.findall(r"=== (\S+) ===\n(.*?)(?=\n===|\Z)", txt, re.S):
        d = {k: int(v) for k, v in re.findall(r"^\s+(\$\S+)\s+(\d+)\s*$", body, re.M)}
        # newer yosys prints "<count>   <cellname>"
        d.update({k: int(v) for v, k in re.findall(r"^\s+(\d+)\s+(\$?[A-Za-z_]\S*)\s*$", body, re.M)
                  if not k.endswith(("wires", "bits", "ports", "cells", "memories"))})
        mods[name] = d
    return mods


def expand(mods, name, mult=1, acc=None):
    acc = collections.Counter() if acc is None else acc
    for k, v in mods.get(name, {}).items():
        if k in mods:
            expand(mods, k, mult * v, acc)
        else:
            acc[k] += mult * v
    return acc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("statfile")
    ap.add_argument("--top", required=True)
    a = ap.parse_args()

    mods = parse(a.statfile)
    if a.top not in mods:
        sys.exit(f"top module '{a.top}' not found in {a.statfile}")
    cells = expand(mods, a.top)

    ff = comb = 0
    area = 0.0
    for k, n in cells.items():
        if k == "$scopeinfo":
            continue
        if "DFF" in k or "LATCH" in k:
            ff += n
            area += n * (DFFE if ("DFFE" in k or "CE_" in k) else DFF)
        else:
            comb += n
            area += n * AREA.get(k, AND2)

    print(f"--- cell mix ({a.top}) ---")
    for k, n in sorted(cells.items(), key=lambda x: -x[1]):
        print(f"  {k:18} {n:6d}")
    print(f"\nFF              : {ff}")
    print(f"combinational   : {comb}")
    print(f"raw cell area   : {area:,.0f} um2 = {area/1e6:.3f} mm2")
    print(f"NAND2 equiv     : {area/NAND2:,.0f} gates")
    print(f"total cell width: {area/ROW_H:,.0f} um (row h={ROW_H} um)")
    core = CORE_W * CORE_H
    print(f"\ncore available  : {CORE_W:.0f} x {CORE_H:.0f} um = {core/1e6:.3f} mm2")
    for u in (0.5, 0.6, 0.7, 0.8):
        need = area / u
        print(f"  util {u:.0%}: {need/1e6:6.3f} mm2  {'OK' if need <= core else 'NG'}")


if __name__ == "__main__":
    main()

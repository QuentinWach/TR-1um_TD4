#!/usr/bin/env python3
"""TR-1um_STDCELL.gds から1セルを簡易抽出して SPICE サブサーキットを起こす。

  usage: python3 scripts/gds_extract.py lef/TR-1um_STDCELL.gds TLAT [-o tlat.spi]

正規の LVS 抽出器ではない（PDK の KLayout ランセットを置き換えるものではない）。
セルの回路構成を確認し、SPICE 検証の出発点を作るための道具。

レイヤ: (3,1)=P+ (3,2)=N+ (8,1)=poly (11,0)=contact (13,0)=M1 (19,0)=V1 (20,0)=M2
        (48,1)/(49,1)=ラベル (140,0)=Nwell (235,0)=セル境界
"""
from __future__ import annotations
import argparse, sys
from collections import defaultdict

try:
    import gdstk
except ImportError:
    sys.exit("pip install gdstk --break-system-packages")

EPS = 1e-3
L = dict(PIMP=(3, 1), NIMP=(3, 2), POLY=(8, 1), CONT=(11, 0), M1=(13, 0),
         V1=(19, 0), M2=(20, 0), NWELL=(140, 0), BOUND=(235, 0))


class UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.p[ra] = rb


def sel(cell, key):
    ld = L[key]
    return [p for p in cell.polygons if (p.layer, p.datatype) == ld]


def merge(polys):
    """重なり／接触するポリゴンを連結成分ごとにまとめる"""
    return gdstk.boolean(polys, [], "or", precision=EPS) if polys else []


def hits(shape, targets):
    """shape と面積を持って重なる targets のインデックス"""
    out = []
    for i, t in enumerate(targets):
        if gdstk.boolean([shape], [t], "and", precision=EPS):
            out.append(i)
    return out


def extract(cell):
    nwell = sel(cell, "NWELL")
    poly = merge(sel(cell, "POLY"))
    m1 = merge(sel(cell, "M1"))
    m2 = merge(sel(cell, "M2"))

    pact = gdstk.boolean(sel(cell, "PIMP"), nwell, "and", precision=EPS)
    nact = gdstk.boolean(sel(cell, "NIMP"), nwell, "not", precision=EPS)

    # ゲート = poly ∩ active、拡散島 = active ∖ poly
    devs = []          # (type, gate_poly, W)
    diff = {}          # ('P'|'N', idx) -> polygon
    for tag, act in (("P", pact), ("N", nact)):
        for g in gdstk.boolean(sel(cell, "POLY"), act, "and", precision=EPS):
            pts = g.points
            devs.append((tag, g, round(float(pts[:, 1].max() - pts[:, 1].min()), 2)))
        for i, d in enumerate(merge(gdstk.boolean(act, sel(cell, "POLY"), "not", precision=EPS))):
            diff[(tag, i)] = d

    uf = UF()
    nodes = ([("poly", i) for i in range(len(poly))] + [("m1", i) for i in range(len(m1))] +
             [("m2", i) for i in range(len(m2))] + list(diff))
    for n in nodes: uf.find(n)

    # コンタクト: M1 <-> poly / 拡散
    for c in sel(cell, "CONT"):
        for i in hits(c, m1):
            for j in hits(c, poly): uf.union(("m1", i), ("poly", j))
            for k, d in diff.items():
                if gdstk.boolean([c], [d], "and", precision=EPS): uf.union(("m1", i), k)
    # ビア: M1 <-> M2
    for v in sel(cell, "V1"):
        for i in hits(v, m1):
            for j in hits(v, m2): uf.union(("m1", i), ("m2", j))

    # ラベル → ネット名
    names = {}
    for lab in cell.labels:
        pt = gdstk.rectangle((lab.origin[0] - .2, lab.origin[1] - .2),
                             (lab.origin[0] + .2, lab.origin[1] + .2))
        for kind, arr in (("m2", m2), ("m1", m1), ("poly", poly)):
            for i in hits(pt, arr):
                names.setdefault(uf.find((kind, i)), lab.text)
                break
            else:
                continue
            break

    # 無名ネットには決定的な番号を振る（実行ごとに変わらないように）
    anon = {}
    for node in sorted(nodes, key=lambda n: (str(n[0]), n[1])):
        r = uf.find(node)
        if r not in names and r not in anon:
            anon[r] = f"n{len(anon) + 1}"

    def netname(node):
        r = uf.find(node)
        return names.get(r, anon.get(r, "n?"))

    # 各ゲートの端子
    out = []
    for tag, g, w in devs:
        gate = next((netname(("poly", i)) for i in hits(g, poly)), "?")
        sd = []
        for k, d in diff.items():
            if k[0] != tag: continue
            if gdstk.boolean([g.copy().scale(1.02, 1.0, g.bounding_box()[0])], [d], "and", precision=EPS):
                sd.append(netname(k))
        # 接触判定は膨張で拾う（ゲート左右の拡散）
        if len(sd) < 2:
            bb = g.bounding_box()
            grow = gdstk.rectangle((bb[0][0] - 0.6, bb[0][1]), (bb[1][0] + 0.6, bb[1][1]))
            sd = [netname(k) for k, d in diff.items()
                  if k[0] == tag and gdstk.boolean([grow], [d], "and", precision=EPS)]
        out.append((tag, gate, sorted(set(sd)), w))
    return out, names, uf


def cell_pins(cell):
    """(49,1) のピンラベル + セル左右端に接する (48,1) ラベル（= 貫通するワードライン）。
    TLAT の WR/WRB/RD/RDB は現状 (48,1) にあるので後者で拾う。"""
    b = sel(cell, "BOUND")
    x0, x1 = (b[0].points[:, 0].min(), b[0].points[:, 0].max()) if b else (None, None)
    pins, seen = [], set()
    for lab in cell.labels:
        t = lab.text
        if t in ("vdd", "gnd") or t in seen:
            continue
        edge = x0 is not None and (abs(lab.origin[0] - x0) < 2.0 or abs(lab.origin[0] - x1) < 2.0)
        if lab.layer == 49 or (lab.layer == 48 and edge):
            seen.add(t); pins.append(t)
    return pins


def spice(cell, devs, name):
    pins = cell_pins(cell)
    lines = [f".subckt {name} {' '.join(pins)} vdd gnd",
             "* auto-extracted by scripts/gds_extract.py -- NOT an LVS-grade netlist"]
    for i, (tag, gate, sd, w) in enumerate(devs):
        s, d = (sd + ["?", "?"])[:2]
        mtype = "pmos" if tag == "P" else "nmos"
        bulk = "vdd" if tag == "P" else "gnd"
        lines.append(f"M{i} {d} {gate} {s} {bulk} {mtype} W={w}u L=1.0u")
    lines.append(".ends")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("gds"); ap.add_argument("cell"); ap.add_argument("-o", "--out")
    a = ap.parse_args()
    lib = gdstk.read_gds(a.gds)
    cells = {c.name: c for c in lib.cells}
    if a.cell not in cells:
        sys.exit(f"cell {a.cell} not found. have: {', '.join(sorted(cells))}")
    c = cells[a.cell]
    devs, names, uf = extract(c)
    print(f"=== {a.cell}: {len(devs)} transistors ===")
    by = defaultdict(list)
    for tag, gate, sd, w in devs:
        by[gate].append((tag, sd, w))
    for tag, gate, sd, w in devs:
        print(f"  {tag}MOS W={w:5.1f}  gate={gate:<6} s/d={','.join(sd)}")
    print("\nnamed nets:", sorted(set(names.values())))
    txt = spice(c, devs, a.cell)
    if a.out:
        open(a.out, "w").write(txt); print(f"\nwrote {a.out}")
    else:
        print("\n" + txt)

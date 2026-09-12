#!/usr/bin/env python3
"""gen_placement_json.py -- ルータが読む配置 JSON へ変換する。

  usage: python3 scripts/pnr/gen_placement_json.py [-o layout/placement_nrow_fm.json]

`place.py` が配置そのものを持ち、ここではそれを移植元のルータ
（`route_channels_nrow_fm.py` 以下）が期待するスキーマに直すだけ:

  {"row_height", "row_width", "ch_heights",
   "rows": [[{"type", "name", "x", "width",
              "pins": {PIN: {"net", "use", "direction",
                             "rects": [[layer, x0, y0, x1, y1], ...]}}}]]}

ピン矩形は LEF から取り、x は**絶対座標**に直す（ルータは行の y だけ足す）。
ネットはゲートレベルネットリストから。Yosys の `assign` 別名は
`netlist_parser` の union-find が解決済み。

TAP / FILL には合成した名前を付ける。TAP 直後に予約した FILL2 は
`FILLPRI_*` という名前にする（ルータが優先 M2 コリドーとして自動検出する）。

SCLK_SPI 版との違いは 2 つ:

  1. **レイヤ名を M1 / M2 に正規化する。** TD4 の LEF は `METAL1` / `METAL2`
     と書く（`scripts/mklef.py` が LEF の慣習どおり技術ファイルのレイヤ名を
     使うため）が、ルータは `"M2"` と文字列比較している。ここで直さないと
     **ピンが 1 本も見つからないまま静かに通る**。

  2. **マクロ `REG8x16` を row0 の末尾に入れる。** 信号ピン 21 本は下辺 1 列
     (y 1.1…4.5) にあり、マクロの底面は row0 の底面と面一に置いてある
     （`td4_config.macro_box()`）。したがってピンの絶対 y は
     `row_y0[0] + 1.1` で正しく出て、ルータからは「933 µm 高い row0 のセル」
     に見える。行の右端の照合だけはマクロを除いて行う
     （`route_channels_nrow_fm.py` の「TD4 移植 (2)」）。
"""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import td4_config as cfg                                    # noqa: E402
import lef_parser                                           # noqa: E402
import netlist_parser                                       # noqa: E402
import netlist_util as nu                                   # noqa: E402
import place                                                # noqa: E402

PLACE = os.path.join(cfg.LAYOUT, "step4", "place_step4_fill.json")

# LEF のレイヤ名 -> ルータが使う名前
LAYER = {"METAL1": "M1", "METAL2": "M2", "M1": "M1", "M2": "M2"}


def conv_rects(rects, dx):
    out = []
    for lay, x0, y0, x1, y1 in rects:
        if lay not in LAYER:
            raise SystemExit(f"知らないレイヤ名 {lay!r}（LAYER に足すこと）")
        out.append([LAYER[lay], round(dx + x0, 4), y0, round(dx + x1, 4), y1])
    return out


def main(place_json=PLACE, out_json=None, net_path=None, lef_path=None):
    out_json = out_json or cfg.PLACEMENT_JSON
    net_path = net_path or cfg.NET_PATH
    lef_path = lef_path or cfg.LEF_PATH

    pl = json.load(open(place_json))
    macros = lef_parser.parse_lef(lef_path)
    net = netlist_parser.parse_netlist(net_path)
    pins_of = {name: pins for _t, name, pins in net["instances"]}
    type_of = {name: t for t, name, _p in net["instances"]}

    rows, npri, nsig = [], 0, 0
    for r, row in enumerate(pl["rows"]):
        out = []
        for k, e in enumerate(row):
            cell, inst = e["cell"], e["inst"]
            if inst:
                name = inst
                if type_of[inst] != cell:
                    raise SystemExit(f"{inst}: ネットリストは {type_of[inst]}、"
                                     f"配置は {cell}")
            elif e.get("pri"):
                name = f"FILLPRI_r{r}_{npri}"
                npri += 1
            elif cell.startswith("TAP"):
                name = f"TAP_r{r}_{k}"
            else:
                name = f"FILL_r{r}_{k}"

            pins = {}
            for pname, pinfo in macros[cell]["pins"].items():
                netname = None
                if pinfo["use"] not in ("POWER", "GROUND") and inst:
                    netname = pins_of.get(inst, {}).get(pname)
                    if netname:
                        nsig += 1
                pins[pname] = {"net": netname, "use": pinfo["use"],
                               "direction": pinfo["direction"],
                               "rects": conv_rects(pinfo["rects"], e["x"])}
            out.append({"type": cell, "name": name, "row": r, "x": e["x"],
                        "width": e["w"], "pins": pins})
        w = round(out[-1]["x"] + out[-1]["width"], 3)
        if abs(w - pl["row_width"]) > 1e-6:
            raise SystemExit(f"row {r} の右端が {w}（行幅 {pl['row_width']} のはず）")
        rows.append(out)

    # ---- マクロを row0 の末尾に ------------------------------------------
    mx0, my0, _, _ = cfg.macro_box()
    if abs(my0 - pl["ch_heights"][0]) > 1e-6:
        raise SystemExit(f"マクロの y0 {my0} が ch[0] {pl['ch_heights'][0]} と"
                         f"違う。ルータは行の y しか足さないので合わせること")
    mcell, minst = pl["macro"]["cell"], pl["macro"]["inst"]
    # **バス接続を開く。** `netlist_parser` はピンごとに 1 ネットしか持たず、
    # `.ADD({ _004_, _003_, _002_, _001_ })` を丸ごと 1 本として返す。
    # そのままだと LEF 側の `ADD[0]` … `ADD[3]` に 1 本も当たらず、
    # **マクロのピンが 1 本しか繋がらないまま静かに通る**。
    resolve = netlist_parser._build_alias_resolver(open(net_path).read())
    mconn = {}
    for i in nu.parse(open(net_path).read()):
        if i.name != minst:
            continue
        for pin, expr in i.conns.items():
            for pn, n in place.expand(pin, expr):
                mconn[pn] = resolve(n.strip())
    mpins, nmac = {}, 0
    for pname, pinfo in macros[mcell]["pins"].items():
        netname = None
        if pinfo["use"] not in ("POWER", "GROUND"):
            netname = mconn.get(pname)
            if netname:
                nmac += 1
        mpins[pname] = {"net": netname, "use": pinfo["use"],
                        "direction": pinfo["direction"],
                        "rects": conv_rects(pinfo["rects"], mx0)}
    rows[0].append({"type": mcell, "name": minst, "row": 0, "x": mx0,
                    "width": cfg.MACRO_W, "pins": mpins})

    data = {"row_height": pl["row_h"], "row_width": pl["row_width"],
            "core_w": pl["core_w"], "core_h": pl["core_h"],
            "ch_heights": pl["ch_heights"],
            "macro": {"cell": mcell, "inst": minst, "box": pl["macro"]["box"]},
            "top_cell": cfg.TOP_CELL_NAME, "rows": rows}
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(data, open(out_json, "w"), indent=1)
    print(f"wrote {os.path.relpath(out_json, cfg.ROOT)}")
    print(f"  行 {[len(r) for r in rows]}   行幅 {data['row_width']}   "
          f"コア {data['core_w']} x {data['core_h']}")
    print(f"  ch_heights {data['ch_heights']}")
    print(f"  優先コリドー {npri} 本 / ネットの付いた信号ピン {nsig} 本")
    print(f"  マクロ {mcell} {minst} @ x={mx0}（row0 の末尾）、信号ピン {nmac} 本")
    want = sum(1 for pn, pi in macros[mcell]["pins"].items()
               if pi["use"] not in ("POWER", "GROUND"))
    if nmac != want:
        raise SystemExit(f"マクロの信号ピン {want} 本のうち {nmac} 本しか"
                         f"ネットが付いていない: "
                         f"{sorted(set(macros[mcell]['pins']) - set(mconn))}")
    return out_json


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--placement", default=PLACE)
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--netlist", default=None)
    ap.add_argument("--lef", default=None)
    a = ap.parse_args()
    main(a.placement, a.output, a.netlist, a.lef)

#!/usr/bin/env python3
"""char/*.json から Liberty (.lib) を書き出す。

  usage: python3 mklib.py [-o out.lib]

単位: 時間 ns / 容量 fF / 電圧 V / 面積 µm²。
コーナーは typ 1 本（TR-1um の PDK に ss/ff のモデルが無いため）。

しきい値は特性化時と揃える必要がある（char_comb.py / charlib.py と同じ値を書く）:
  遅延 50%、遷移 20%-80%
"""
from __future__ import annotations
import argparse, json, os, sys
import cellspec
from charlib import HERE, VDD, TEMP, SLEWS, LOADS, SLEWS_C, TH_DELAY, TH_SLEW_LO, TH_SLEW_HI

AREAS = json.load(open(f"{HERE}/cell_area.json"))["cells"]
IND = "  "


def fmt_table(rows, scale=1e9, nan=None):
    """[[v,...],...] -> Liberty の values(...) 文字列。None は前後から埋める。"""
    out = []
    for r in rows:
        vals = []
        for v in r:
            vals.append(v * scale if v is not None else None)
        # 欠損は同じ行の直近の値で埋める（無ければ 0）
        last = None
        for i, v in enumerate(vals):
            if v is None:
                vals[i] = last if last is not None else 0.0
            else:
                last = vals[i]
        out.append(", ".join(f"{v:.5f}" for v in vals))
    return out


def values_block(rows, ind, scale=1e9):
    lines = fmt_table(rows, scale)
    body = ",\\\n".join(f'{ind}  "{l}"' for l in lines)
    return f"{ind}values(\\\n{body});"


def idx(vals):
    return ", ".join(f"{v:g}" for v in vals)


def emit_comb(cell, data, o):
    fns = cellspec.LIBFUNC.get(cell, {})
    # cap_cal（遅延が合うように較正した等価容量）があればそちらを使う。
    # 電荷から出した cap はミラー分を含むので遅延計算には過大。
    caps = data.get("cap_cal") or data.get("cap", {})
    area = AREAS[cell]["area"]
    o.append(f'{IND}cell ({cell}) {{')
    o.append(f'{IND*2}area : {area:.1f};')
    if cell in cellspec.BLOCK_ONLY:
        o.append(f'{IND*2}dont_use : true;   /* アレイ内部専用。LEF も CLASS BLOCK */')
        o.append(f'{IND*2}dont_touch : true;')
    ins = sorted({a["related_pin"] for a in data["arcs"]})
    outs = sorted({a["pin"] for a in data["arcs"]})
    for p in ins:
        c = caps.get(p)
        o.append(f'{IND*2}pin ({p}) {{')
        o.append(f'{IND*3}direction : input;')
        if c:
            o.append(f'{IND*3}capacitance : {c:.3f};')
        o.append(f'{IND*3}max_transition : {SLEWS[-1]:g};')
        o.append(f'{IND*2}}}')
    for p in outs:
        o.append(f'{IND*2}pin ({p}) {{')
        o.append(f'{IND*3}direction : output;')
        if p in fns:
            o.append(f'{IND*3}function : "{fns[p]}";')
        o.append(f'{IND*3}max_capacitance : {LOADS[-1]:g};')
        for a in data["arcs"]:
            if a["pin"] != p:
                continue
            o.append(f'{IND*3}timing () {{')
            o.append(f'{IND*4}related_pin : "{a["related_pin"]}";')
            o.append(f'{IND*4}timing_sense : {a["sense"]};')
            for key, tbl in (("cell_rise", a["cell_rise"]), ("rise_transition", a["rise_transition"]),
                             ("cell_fall", a["cell_fall"]), ("fall_transition", a["fall_transition"])):
                o.append(f'{IND*4}{key} (delay_template_7x7) {{')
                o.append(values_block(tbl, IND * 5))
                o.append(f'{IND*4}}}')
            o.append(f'{IND*3}}}')
        o.append(f'{IND*2}}}')
    o.append(f'{IND}}}')


def seqcap(data, pin, default=80.0):
    c = (data.get("cap_cal") or data.get("cap") or {}).get(pin)
    return c if c else default


def emit_seq(cell, data, o):
    spec = cellspec.FF[cell]
    area = AREAS[cell]["area"]
    q = data["q"]
    o.append(f'{IND}cell ({cell}) {{')
    o.append(f'{IND*2}area : {area:.1f};')
    o.append(f'{IND*2}ff (IQ, IQN) {{')
    o.append(f'{IND*3}next_state : "{spec["next_state"]}";')
    o.append(f'{IND*3}clocked_on : "{spec["clocked_on"]}";')
    if "clear" in spec:
        o.append(f'{IND*3}clear : "{spec["clear"]}";')
    if "preset" in spec:
        o.append(f'{IND*3}preset : "{spec["preset"]}";')
    o.append(f'{IND*2}}}')

    dpin = data["d"]
    # 入力ピン
    o.append(f'{IND*2}pin (CK) {{')
    o.append(f'{IND*3}direction : input;')
    o.append(f'{IND*3}clock : true;')
    o.append(f'{IND*3}capacitance : {seqcap(data, "CK"):.3f};')
    o.append(f'{IND*3}max_transition : {SLEWS[-1]:g};')
    o.append(f'{IND*2}}}')

    data_pins = [p for p in cellspec.SEQ_PINS[cell]["data"]]
    for p in data_pins:
        o.append(f'{IND*2}pin ({p}) {{')
        o.append(f'{IND*3}direction : input;')
        o.append(f'{IND*3}capacitance : {seqcap(data, p):.3f};')
        o.append(f'{IND*3}max_transition : {SLEWS[-1]:g};')
        if p == dpin:
            for tt, tbl in (("setup_rising", data["setup"]), ("hold_rising", data["hold"])):
                o.append(f'{IND*3}timing () {{')
                o.append(f'{IND*4}related_pin : "CK";')
                o.append(f'{IND*4}timing_type : {tt};')
                for k, key in (("rise", "rise_constraint"), ("fall", "fall_constraint")):
                    o.append(f'{IND*4}{key} (constraint_template_3x3) {{')
                    o.append(values_block(tbl[k], IND * 5, scale=1.0))
                    o.append(f'{IND*4}}}')
                o.append(f'{IND*3}}}')
        o.append(f'{IND*2}}}')
    for p in cellspec.SEQ_PINS[cell]["async"]:
        o.append(f'{IND*2}pin ({p}) {{')
        o.append(f'{IND*3}direction : input;')
        o.append(f'{IND*3}capacitance : {seqcap(data, p):.3f};')
        o.append(f'{IND*3}max_transition : {SLEWS[-1]:g};')
        o.append(f'{IND*2}}}')

    for p, fn in (("Q", "IQ"), ("QB", "IQN")):
        o.append(f'{IND*2}pin ({p}) {{')
        o.append(f'{IND*3}direction : output;')
        o.append(f'{IND*3}function : "{fn}";')
        o.append(f'{IND*3}max_capacitance : {LOADS[-1]:g};')
        o.append(f'{IND*3}timing () {{')
        o.append(f'{IND*4}related_pin : "CK";')
        o.append(f'{IND*4}timing_type : rising_edge;')
        ck = data["ckq"]
        # QB は Q の反転なので rise/fall を入れ替える
        swap = (p == "QB")
        pairs = (("cell_rise", "cell_fall" if swap else "cell_rise"),
                 ("rise_transition", "fall_transition" if swap else "rise_transition"),
                 ("cell_fall", "cell_rise" if swap else "cell_fall"),
                 ("fall_transition", "rise_transition" if swap else "fall_transition"))
        for key, src in pairs:
            o.append(f'{IND*4}{key} (delay_template_7x7) {{')
            o.append(values_block(ck[src], IND * 5))
            o.append(f'{IND*4}}}')
        o.append(f'{IND*3}}}')
        o.append(f'{IND*2}}}')
    o.append(f'{IND}}}')


def emit_plain(cell, o, kind):
    """論理も遅延も持たないセル（TAP / FILL）"""
    area = AREAS[cell]["area"]
    o.append(f'{IND}cell ({cell}) {{')
    o.append(f'{IND*2}area : {area:.1f};')
    o.append(f'{IND*2}dont_use : true;')
    o.append(f'{IND*2}dont_touch : true;')
    if kind == "fill":
        o.append(f'{IND*2}pad_cell : false;')
    o.append(f'{IND*2}pin (vdd) {{ direction : input; }}')
    o.append(f'{IND}}}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=f"{HERE}/tr1um_typ_5v0_25c.lib")
    a = ap.parse_args()

    o = []
    o.append("/* TR-1um (IP62) 標準セルライブラリ — Liberty")
    o.append(" *")
    o.append(" * scripts/char/mklib.py が char/*.json から自動生成。手で編集しないこと。")
    o.append(" * 元データは GDS から抽出したネットリストを ngspice (BSIM3 level49) で")
    o.append(" * 特性化したもの。回路の正しさは真理値表 436 点 / 順序 87 点で確認済み。")
    o.append(" *")
    o.append(f" * コーナー: typical / {VDD}V / {TEMP}degC （PDK に ss/ff のモデルが無いので 1 本のみ）")
    o.append(f" * 遅延の測定点: 入力 {TH_DELAY}% -> 出力 {TH_DELAY}%")
    o.append(f" * 遷移の測定点: {TH_SLEW_LO}% -> {TH_SLEW_HI}%")
    o.append(" * 単位: 時間 ns / 容量 fF / 面積 um^2")
    o.append(" *")
    o.append(" * 入っていないセル: ADDBUF / REGBUF / TLAT / DEC0 / DEC2 / DEC16 など")
    o.append(" *   アレイ内部で abut して使う CLASS BLOCK のセル。P&R の行に流さないので")
    o.append(" *   タイミングを持たせる意味がない（機能は ngspice で確認済み）。")
    o.append(" */")
    o.append("")
    o.append("library (tr1um_typ_5v0_25c) {")
    o.append(f"{IND}technology (cmos);")
    o.append(f"{IND}delay_model : table_lookup;")
    o.append(f'{IND}time_unit : "1ns";')
    o.append(f'{IND}voltage_unit : "1V";')
    o.append(f'{IND}current_unit : "1mA";')
    o.append(f'{IND}pulling_resistance_unit : "1kohm";')
    o.append(f'{IND}leakage_power_unit : "1nW";')
    o.append(f"{IND}capacitive_load_unit (1, ff);")
    o.append("")
    o.append(f"{IND}nom_process : 1.0;")
    o.append(f"{IND}nom_temperature : {TEMP};")
    o.append(f"{IND}nom_voltage : {VDD};")
    o.append(f"{IND}default_max_transition : {SLEWS[-1]:g};")
    o.append(f"{IND}default_max_fanout : 16;")
    o.append("")
    for e in ("rise", "fall"):
        o.append(f"{IND}slew_lower_threshold_pct_{e} : {TH_SLEW_LO};")
        o.append(f"{IND}slew_upper_threshold_pct_{e} : {TH_SLEW_HI};")
        o.append(f"{IND}input_threshold_pct_{e} : {TH_DELAY};")
        o.append(f"{IND}output_threshold_pct_{e} : {TH_DELAY};")
    o.append(f"{IND}slew_derate_from_library : 1.0;")
    o.append("")
    o.append(f"{IND}operating_conditions (typ) {{")
    o.append(f"{IND*2}process : 1.0;")
    o.append(f"{IND*2}temperature : {TEMP};")
    o.append(f"{IND*2}voltage : {VDD};")
    o.append(f"{IND*2}tree_type : balanced_tree;")
    o.append(f"{IND}}}")
    o.append(f"{IND}default_operating_conditions : typ;")
    o.append("")
    o.append(f"{IND}lu_table_template (delay_template_7x7) {{")
    o.append(f"{IND*2}variable_1 : input_net_transition;")
    o.append(f"{IND*2}variable_2 : total_output_net_capacitance;")
    o.append(f'{IND*2}index_1 ("{idx(SLEWS)}");')
    o.append(f'{IND*2}index_2 ("{idx(LOADS)}");')
    o.append(f"{IND}}}")
    o.append(f"{IND}lu_table_template (constraint_template_3x3) {{")
    o.append(f"{IND*2}variable_1 : constrained_pin_transition;")
    o.append(f"{IND*2}variable_2 : related_pin_transition;")
    o.append(f'{IND*2}index_1 ("{idx(SLEWS_C)}");')
    o.append(f'{IND*2}index_2 ("{idx(SLEWS_C)}");')
    o.append(f"{IND}}}")
    o.append("")

    ncell = 0
    for cell in sorted(os.listdir(f"{HERE}/char")):
        if not cell.endswith(".json"):
            continue
        name = cell[:-5]
        d = json.load(open(f"{HERE}/char/{cell}"))
        if d.get("seq"):
            emit_seq(name, d, o)
        else:
            emit_comb(name, d, o)
        ncell += 1
    for name in sorted(cellspec.PASS):
        emit_plain(name, o, "fill" if name.startswith("FILL") else "tap")
        ncell += 1
    o.append("}")
    open(a.out, "w").write("\n".join(o) + "\n")
    print(f"wrote {a.out}  ({ncell} cells, {len(o)} lines)")


if __name__ == "__main__":
    main()

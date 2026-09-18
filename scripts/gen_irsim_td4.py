#!/usr/bin/env python3
"""TD4 コアの全 12 命令トレース — IRSIM の .cmd と Verilog TB を**同じ表から**作る

  usage: python3 scripts/gen_irsim_td4.py --cmd irsim/td4_soc_arr.cmd
         python3 scripts/gen_irsim_td4.py --verilog hdl/tb/tb_td4_soc_arr_isa.v
         python3 scripts/gen_irsim_td4.py --cmd ... --verilog ...   （両方）

なぜ表から作るか（U14）:
  `hdl/tb/tb_td4_core.v` は `rom_data` を**直接叩いて** 12 命令を出すので、
  そのままでは実装（`td4_soc_arr_nrow_fm`）に持ち込めない。実装には
  `rom_data` のピンが無く、命令は Load モードで書き込んだメモリから出る。
  そこで「PC が進む順に並んだプログラム」に書き直した。書き直した以上、
  期待値は手計算ではなく**モデルに解かせる**（`Sim` クラス）。
  Verilog TB と IRSIM の .cmd を同じ表・同じ期待値から出すので、
  二つが食い違うことがない（`gen_irsim_cmd.py` と同じ流儀）。

観測できるもの（`layout/chip/simulation/td4_soc_arr_nrow_fm.spice` のネット名）:
  `out_port[3:0]` / `cflag_o` はトップピン。
  **`u_core_reg_a[3:0]` と `u_core_reg_b[3:0]` は内部だが名前が残っている**ので
  IRSIM から直接見られる（`pc` と `ld_addr[3:1]` は合成で番号に化けていて見えない）。
  `spi2sim.py` が角括弧を潰すので .cmd では `u_core_reg_a0` と書く。

TD4 の命令（op[3:2] = 書込先 00:A 01:B 10:OUT 11:PC、op[1:0] = セレクタ
00:A 01:B 10:IN 11:0。PC 群はセレクタが 0 に固定される）:

  0000 ADD A,Im   0001 MOV A,B   0010 IN A   0011 MOV A,Im
  0100 MOV B,A    0101 ADD B,Im  0110 IN B   0111 MOV B,Im
  1001 OUT B      1011 OUT Im    1110 JNC Im 1111 JMP Im
"""
from __future__ import annotations

import argparse

# --- タイミング（ns）--------------------------------------------------------
#   実測（`syn/sta`）: reg->reg の最小周期 60.307 ns（16.58 MHz）。
#   .sim は配線容量を持たない（`spi2sim.py`）ので IRSIM は速めに出る。
#   半周期 100 ns = 5 MHz と 3 倍以上の余裕をとってある。
THALF = 100

IN_VAL = 0b1010          # Exec 中ずっと `d` に置く入力ポートの値（= 10）

# ★ **入力の BUFTH（シュミットトリガ）を飛ばして駆動する。**
#   このライブラリは外部入力を全部 `BUFTH` で受ける（`insert_bufth.py`。
#   立上り 3.43 V / 立下り 1.44 V、ヒステリシス 2.00 V — docs/10_pdk_facts.md §2）。
#   **IRSIM はシュミットを解けない。** ヒステリシスの帰還 MOS が自分の出力
#   ノードでゲートされているので、初期値 X から抜けられない:
#       n2=X -> 帰還 MP0/MP1 が「導通するかも」-> n3 が vdd と vss の両方に
#       引かれて X -> n2=X …
#   しかも帰還の方が太い（5.1x2 対 5.1 の直列 2 段）ので、強さでも決まらない。
#   実際に踏んだ（2026-09-17）: 9 本の入力が全部 X になり、コアが丸ごと X。
#   → **バッファの出口も同じ値で駆動する**（`irsim/probe_bufth.cmd` が否定対照）。
#   こうすると BUFTH 9 個（90 Tr）は検査の外に出るが、残り 3,507 Tr —
#   コアとメモリアレイ全部 — は実物の接続で走る。
#   BUFTH 自体の閾値は ngspice で測ってある（docs/10_pdk_facts.md）。
BUF = {"clk": "clk_buf", "rst_n": "rst_n_buf", "exec": "exec_buf",
       "wr": "wr_buf", "nibsel": "nibsel_buf"}
BUF_BUS = {"d": "d_buf"}

# --- プログラム -------------------------------------------------------------
# (命令, 覚え書き)。**PC が進む順**に並んでいる。
P1 = [
    (0b0011_0101, "MOV A,Im 5"),      #  0  A=5
    (0b0000_0011, "ADD A,Im 3"),      #  1  A=8   C=0
    (0b0000_1001, "ADD A,Im 9"),      #  2  A=1   C=1   8+9=17
    (0b1110_0000, "JNC 0"),           #  3  C=1 -> 飛ばない
    (0b0100_0000, "MOV B,A"),         #  4  B=1
    (0b0111_1001, "MOV B,Im 9"),      #  5  B=9
    (0b0001_0000, "MOV A,B"),         #  6  A=9
    (0b0010_0000, "IN A"),            #  7  A=IN
    (0b0110_0000, "IN B"),            #  8  B=IN
    (0b1001_0000, "OUT B"),           #  9  OUT=IN
    (0b1011_0110, "OUT Im 6"),        # 10  OUT=6
    (0b0101_0110, "ADD B,Im 6"),      # 11  B=10+6=0  C=1
    (0b1110_1110, "JNC 14"),          # 12  C=1 -> 飛ばない
    (0b1110_1111, "JNC 15"),          # 13  C=0 -> 飛ぶ
    (0b1011_1111, "OUT Im 15"),       # 14  **通ってはいけない**（落ちたら OUT=15）
    (0b0011_0111, "MOV A,Im 7"),      # 15  A=7、PC は 15 -> 0 に回る
]
P1_CYCLES = 16                        # 15 を実行したところで PC が 0 に戻る

# JMP と「飛び先が正しいか」。P1 に入れる余地が無いので 2 本目にした。
P2 = [
    (0b1111_0010, "JMP 2"),           # 0  PC=2
    (0b1011_1111, "OUT Im 15"),       # 1  **通ってはいけない**
    (0b1011_0011, "OUT Im 3"),        # 2  OUT=3（飛び先が 2 だった証拠）
    (0b1111_0011, "JMP 3"),           # 3  自己ループ（停止）
]
P2_CYCLES = 5


class Sim:
    """td4_core の参照モデル。RTL（`hdl/rtl/td4_core.v`）の写し。

    ここは**独立した 2 つ目の実装**なので、Verilog TB がこの期待値で通れば
    「モデルと RTL が一致した」ことになる。手計算はしない。
    """

    def __init__(self):
        self.a = self.b = self.out = self.pc = 0
        self.c = 0

    def step(self, prog, in_port):
        instr = prog[self.pc][0]
        op, im = instr >> 4, instr & 0xF
        dst, src = op >> 2, op & 0b11
        sel = 0b11 if dst == 0b11 else src            # PC 群はセレクタ 0 固定
        sdat = (self.a, self.b, in_port, 0)[sel]
        total = sdat + im
        res, carry = total & 0xF, 1 if total > 0xF else 0
        jump = (dst == 0b11) and ((op & 1) or self.c == 0)
        pc0 = self.pc
        if dst == 0b00:
            self.a = res
        elif dst == 0b01:
            self.b = res
        elif dst == 0b10:
            self.out = res
        self.c = carry
        self.pc = res if jump else (pc0 + 1) & 0xF
        return {"pc": pc0, "instr": instr, "note": prog[pc0][1],
                "a": self.a, "b": self.b, "out": self.out, "c": self.c}


def trace(prog, ncycle, in_port=IN_VAL):
    s = Sim()
    return [s.step(prog, in_port) for _ in range(ncycle)]


PHASES = (("P1", P1, P1_CYCLES), ("P2", P2, P2_CYCLES))


# =============================== IRSIM .cmd =================================
class Cmd:
    def __init__(self):
        self.o: list[str] = []
        self.lvl: dict[str, int] = {}

    def c(self, s=""):
        self.o.append("| " + s if s else "|")

    def raw(self, s):
        self.o.append(s)

    def _one(self, node, v):
        """値が変わるときだけ書く（.cmd が短くなり、差分も読みやすい）。"""
        if self.lvl.get(node) != v:
            self.raw(f"{'h' if v else 'l'} {node}")
            self.lvl[node] = v

    def set(self, node, v):
        """ピンと、その BUFTH の出口を同じ値で駆動する（BUF の注記を参照）。"""
        self._one(node, v)
        if node in BUF:
            self._one(BUF[node], v)

    def bus(self, prefix, val, nbit=4):
        for i in range(nbit):
            self._one(f"{prefix}{i}", (val >> i) & 1)
            if prefix in BUF_BUS:
                self._one(f"{BUF_BUS[prefix]}{i}", (val >> i) & 1)

    def lo(self):                      # クロック立下り側（入力を動かす所）
        self.set("clk", 0)

    def tick(self):                    # 立上りで取り込ませて、落ち着かせる
        self.raw(f"s {THALF}")
        self.set("clk", 1)
        self.raw(f"s {THALF}")


def gen_cmd() -> str:
    g = Cmd()
    g.c("td4_soc_arr.cmd -- TD4 全 12 命令トレース（IRSIM 版）")
    g.c("scripts/gen_irsim_td4.py が生成。手で編集しないこと。")
    g.c("hdl/tb/tb_td4_soc_arr_isa.v と同じプログラム・同じ期待値。")
    g.c()
    g.c("合否判定: python3 scripts/check_irsim_td4_log.py irsim/td4_soc_arr_run.log")
    g.c("1 サイクルごとに print で期待値を刻み、assert でその場で判定し、")
    g.c("d で実際の値を残す。IRSIM の .cmd 言語には条件分岐も算術も無いので、")
    g.c("集計だけをログのオフライン突合せで行う。")
    g.c()
    g.c(f"stepsize 1 -> 1ns。半周期 {THALF} ns（reg->reg の実測 60.3 ns に対し 3 倍以上）")
    g.c()
    g.c("★ 入力ピンと**その BUFTH の出口**（*_buf）を同じ値で駆動している。")
    g.c("  BUFTH はシュミットトリガで、IRSIM は帰還が解けず X から抜けない")
    g.c("  （否定対照: irsim/probe_bufth.cmd）。BUFTH 9 個 90 Tr は検査の外。")
    g.raw("stepsize 1")
    g.raw("settle 10")
    g.c()
    g.raw("h Vdd")
    g.raw("l Gnd")
    g.lvl.update(Vdd=1, Gnd=0)
    for n in ("clk", "rst_n", "exec", "wr", "nibsel"):
        g.set(n, 0)
    g.bus("d", 0)
    g.raw("s 200")
    g.c()
    g.c("表示用ベクタ。d で 4 つ同時に出す。")
    g.raw("vector AV u_core_reg_a3 u_core_reg_a2 u_core_reg_a1 u_core_reg_a0")
    g.raw("vector BV u_core_reg_b3 u_core_reg_b2 u_core_reg_b1 u_core_reg_b0")
    g.raw("vector OV out_port3 out_port2 out_port1 out_port0")
    g.raw("vector CV cflag_o")

    for tag, prog, ncycle in PHASES:
        g.o.append("")
        g.c("=" * 66)
        g.c(f"{tag}  —  {len(prog)} 命令を Load して {ncycle} サイクル走らせる")
        g.c("=" * 66)

        g.c("リセット（PC と ld_addr を 0 に戻す）")
        g.lo()
        g.set("rst_n", 0)
        g.set("exec", 0)
        g.set("wr", 0)
        g.tick()
        g.lo()
        g.set("rst_n", 1)
        g.tick()

        g.c()
        g.c("Load モード: 1 命令 = 下位ニブル -> 上位ニブルの 2 回書込")
        for addr, (instr, note) in enumerate(prog):
            g.c(f"{addr:2d}: {instr:08b}  {note}")
            g.lo()
            g.set("nibsel", 0)
            g.bus("d", instr & 0xF)
            g.set("wr", 1)
            g.tick()
            g.lo()
            g.set("nibsel", 1)
            g.bus("d", instr >> 4)
            g.tick()
        g.lo()
        g.set("wr", 0)

        g.c()
        g.c(f"Exec モード（入力ポート d = {IN_VAL:04b}）")
        g.lo()
        g.bus("d", IN_VAL)
        g.set("exec", 1)
        for i, r in enumerate(trace(prog, ncycle)):
            g.tick()
            g.raw(f"print TD4CHECK tag={tag}_{i:02d} pc={r['pc']:04b} "
                  f"instr={r['instr']:08b} expA={r['a']:04b} expB={r['b']:04b} "
                  f"expO={r['out']:04b} expC={r['c']:01b} note={r['note'].replace(' ', '_')}")
            g.raw(f"assert AV {r['a']:04b}")
            g.raw(f"assert BV {r['b']:04b}")
            g.raw(f"assert OV {r['out']:04b}")
            g.raw(f"assert CV {r['c']:01b}")
            g.raw("d AV BV OV CV")
            g.lo()
        g.set("exec", 0)

    g.o.append("")
    g.c("end of td4_soc_arr.cmd")
    return "\n".join(g.o) + "\n"


# ============================== Verilog TB ==================================
def gen_verilog() -> str:
    o = ["`timescale 1ns/1ps",
         "// tb_td4_soc_arr_isa.v -- TD4 全 12 命令トレース（Verilog 版）",
         "// scripts/gen_irsim_td4.py が生成。手で編集しないこと。",
         "// irsim/td4_soc_arr.cmd と同じプログラム・同じ期待値（U14）。",
         "module tb_td4_soc_arr_isa;",
         "  reg clk=0, rst_n=0, exec=0, wr=0, nibsel=0;",
         "  reg [3:0] d=4'h0;",
         "  wire [3:0] out_port; wire cflag;",
         "  integer errors = 0;",
         "",
         "  td4_soc_arr dut(.clk(clk),.rst_n(rst_n),.exec(exec),.wr(wr),"
         ".nibsel(nibsel),",
         "                  .d(d),.out_port(out_port),.cflag_o(cflag));",
         "  always #5 clk = ~clk;",
         "",
         "  task load(input [7:0] instr);",
         "    begin",
         "      @(negedge clk); nibsel=1'b0; d=instr[3:0]; wr=1'b1; @(posedge clk);",
         "      @(negedge clk); nibsel=1'b1; d=instr[7:4];          @(posedge clk);",
         "    end",
         "  endtask",
         "",
         "  task chk(input [80*8-1:0] name, input [4:0] got, input [4:0] exp);",
         "    begin",
         "      if (got !== exp) begin",
         "        $display(\"FAIL %0s: got %0d exp %0d\", name, got, exp);",
         "        errors = errors + 1;",
         "      end",
         "    end",
         "  endtask",
         "",
         "  task cyc(input [80*8-1:0] tag, input [3:0] ea, input [3:0] eb,",
         "           input [3:0] eo, input ec);",
         "    begin",
         "      @(posedge clk); #1;",
         "      chk({tag,\"_A\"},   dut.u_core.reg_a, ea);",
         "      chk({tag,\"_B\"},   dut.u_core.reg_b, eb);",
         "      chk({tag,\"_OUT\"}, out_port,         eo);",
         "      chk({tag,\"_C\"},   cflag,            ec);",
         "    end",
         "  endtask",
         "",
         "  initial begin"]

    for tag, prog, ncycle in PHASES:
        o.append(f"    // ---------------- {tag} ----------------")
        o.append("    @(negedge clk); rst_n = 1'b0; exec = 1'b0; wr = 1'b0;")
        o.append("    @(posedge clk); @(negedge clk); rst_n = 1'b1;")
        for addr, (instr, note) in enumerate(prog):
            o.append(f"    load(8'b{instr >> 4:04b}_{instr & 0xF:04b});"
                     f"  // {addr:2d}: {note}")
        o.append("    @(negedge clk); wr = 1'b0;")
        o.append(f"    d = 4'b{IN_VAL:04b}; exec = 1'b1;")
        for i, r in enumerate(trace(prog, ncycle)):
            o.append(f"    cyc(\"{tag}_{i:02d}\", 4'b{r['a']:04b}, 4'b{r['b']:04b}, "
                     f"4'b{r['out']:04b}, 1'b{r['c']:01b});  // {r['note']}")
        o.append("    @(negedge clk); exec = 1'b0;")
        o.append("")

    ncyc = sum(n for _, _, n in PHASES)
    o += ["    if (errors == 0)",
          f'      $display("\\n=== TD4 ISA TRACE PASSED ({ncyc} cycles) ===");',
          '    else $display("\\n=== %0d FAILURES ===", errors);',
          "    $finish;",
          "  end",
          "endmodule"]
    return "\n".join(o) + "\n"


def check_sim(cmd_text, sim_path):
    """.cmd が触るノードが**全部 .sim にあるか**を先に見る。

    ★ 無いノードを `h`/`l`/`vector` に書いても IRSIM は黙って進むことがある。
    そうすると「走ったが何も駆動していない」トレースが出る。2026-09-17 に
    実際に踏んだ（設計側にあった `scripts/spi2sim.py` の写しが内部ノードの
    角括弧を潰さず、
    `u_core_reg_a[0]` のままだった。U94）。合否の前にここで止める。
    """
    nodes = set()
    for ln in open(sim_path, encoding="utf-8"):
        t = ln.split()
        if t and t[0] in ("n", "p") and len(t) >= 4:
            nodes.update(t[1:4])
    used = set()
    for ln in cmd_text.splitlines():
        t = ln.split()
        if not t or t[0] == "|":
            continue
        if t[0] in ("h", "l") and len(t) > 1:
            used.add(t[1])
        elif t[0] == "vector":
            used.update(t[2:])
    missing = sorted(used - nodes)
    if missing:
        raise SystemExit(
            f"** .cmd が触るノードが {sim_path} に無い: {', '.join(missing)}\n"
            f"   .sim を作り直すか、ネットの名前を確かめてください。")
    print(f"  ノードの突き合わせ ok（{len(used)} 個すべて {sim_path} にある）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", help="IRSIM の .cmd をここへ書く")
    ap.add_argument("--verilog", help="Verilog TB をここへ書く")
    ap.add_argument("--check-sim", metavar="SIM",
                    help=".cmd が触るノードがこの .sim にあるかを確かめる")
    a = ap.parse_args()
    if not (a.cmd or a.verilog or a.check_sim):
        ap.error("--cmd / --verilog / --check-sim のどれかは要る")
    if a.check_sim:
        check_sim(gen_cmd(), a.check_sim)
    if a.cmd:
        open(a.cmd, "w", encoding="utf-8").write(gen_cmd())
        print(f"wrote {a.cmd}")
    if a.verilog:
        open(a.verilog, "w", encoding="utf-8").write(gen_verilog())
        print(f"wrote {a.verilog}")


if __name__ == "__main__":
    main()

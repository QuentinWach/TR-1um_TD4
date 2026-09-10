#!/usr/bin/env python3
"""IRSIM コマンドファイル生成 — hdl/tb/tb_reg4x16.v と同じベクタを .cmd に落とす

  usage: python3 scripts/gen_irsim_cmd.py irsim/reg4x16.cmd

IRSIM の .cmd 言語には条件分岐も算術も無いので、テストベンチのループを
ここで展開して直線のコマンド列にする。合否判定は走らせたログを
scripts/check_irsim_log.py でオフラインに突き合わせて行う
（TR-1um_Async_I2C/irsim と同じやり方）。

Verilog 版（論理と接続の検証）と同じ順序・同じ期待値なので、
両者の結果を 1 対 1 で比較できる。
"""
from __future__ import annotations
import sys

# --- タイミング（すべて ns。stepsize 1 なので 1ns 分解能）-------------------
#   実測（TR-1um.prm, 1076Tr）: 書込 WEB↓ -> Q 反映 約 11ns
#                               読出 ADD 変化 -> Q 確定 約 14ns
#   3 倍以上の余裕をとって 50ns にしてある。
T_SETUP = 50   # アドレス／データ確定待ち
T_WRITE = 50   # WEB=0 のパルス幅
T_HOLD  = 50   # WEB=1 に戻してから次の操作まで
T_READ  = 50   # アドレスを変えてから読むまで

NW, NB = 16, 4


class Gen:
    def __init__(self):
        self.o: list[str] = []
        self.exp: list[dict] = []
        self.add = None          # 現在のアドレス（None = 不定）
        self.din = None          # 現在のデータ
        self.web = None

    # -- 低レベル ----------------------------------------------------------
    def c(self, s=""):
        self.o.append("| " + s if s else "|")

    def raw(self, s):
        self.o.append(s)

    def set_add(self, a):
        for b in range(4):
            v = (a >> b) & 1
            if self.add is None or ((self.add >> b) & 1) != v:
                self.raw(f"{'h' if v else 'l'} ADD{b}")
        self.add = a

    def set_din(self, d):
        for b in range(NB):
            v = (d >> b) & 1
            if self.din is None or ((self.din >> b) & 1) != v:
                self.raw(f"{'h' if v else 'l'} D{b}")
        self.din = d

    def set_web(self, v):
        if self.web != v:
            self.raw(f"{'h' if v else 'l'} WEB")
            self.web = v

    # -- 操作 --------------------------------------------------------------
    def wr(self, a, d):
        """書込: アドレスとデータを確定させてから WEB を落とす（順序厳守）"""
        self.set_add(a)
        self.set_din(d)
        self.raw(f"s {T_SETUP}")
        self.set_web(0)
        self.raw(f"s {T_WRITE}")
        self.set_web(1)
        self.raw(f"s {T_HOLD}")

    def rd(self, a, expect, tag):
        """読出 1 回。ログだけで合否が追えるように
             print  … 何を期待しているかを刻む（後段の集計用）
             assert … その場で IRSIM に判定させる（外れたらログに残る）
             d      … 実際の番地と値を残す
           の 3 行を出す。"""
        self.set_add(a)
        self.raw(f"s {T_READ}")
        t = tag.replace(" ", "_")
        self.raw(f"print CHECK tag={t} add={a:04b} exp={expect:04b}")
        self.raw(f"assert QV {expect:04b}")
        self.raw("d AV QV")
        self.exp.append({"tag": tag, "add": a, "expect": f"{expect:04b}"})

    def head(self, s):
        self.o.append("")
        self.c("=" * 64)
        self.c(s)
        self.c("=" * 64)


def build():
    g = Gen()
    g.c("reg4x16.cmd -- REG4x16 全レジスタアクセス検証（IRSIM 版）")
    g.c("scripts/gen_irsim_cmd.py が生成。手で編集しないこと。")
    g.c("hdl/tb/tb_reg4x16.v と同じベクタ・同じ順序・同じ期待値。")
    g.c()
    g.c("合否判定:  python3 scripts/check_irsim_log.py irsim/reg4x16_run.log")
    g.c("読出のたびに print で期待値を刻み、assert でその場で判定し、")
    g.c("d で実際の値を残す。IRSIM の .cmd 言語には条件分岐も算術も無いので、")
    g.c("pass/fail の集計だけをログのオフライン突合せで行う。")
    g.c()
    g.c("stepsize 1  -> 時間分解能 1ns。以降の `s <n>` の n はすべて ns。")
    g.c("settle 10   -> TLAT の帰還ノード（n2/n3）が背中合わせインバータに")
    g.c("               なっているので、一瞬の競合で X と判定されないよう")
    g.c("               落ち着く時間を与える。")
    g.raw("stepsize 1")
    g.raw("settle 10")

    g.c()
    g.c("電源と初期状態。TLAT は電源投入直後 n3 が X だが、ratioless なので")
    g.c("最初の書込で TG-W が強制的に上書きして解ける（forcing は不要）。")
    g.raw("h Vdd")
    g.raw("l Gnd")
    g.set_web(1)
    g.set_add(0)
    g.set_din(0)
    g.raw("s 200")

    g.c()
    g.c("表示用ベクタ。d AV QV で「読んだ番地」と「読めた値」が同時に出る。")
    g.raw("vector AV ADD3 ADD2 ADD1 ADD0")
    g.raw("vector QV Q3 Q2 Q1 Q0")

    #---- T1 -----------------------------------------------------------------
    g.head("T1  全ワード書込 / 読出（値と番地を違えてある）")
    shadow = [0] * NW
    for i in range(NW):
        v = i ^ 0b1010
        g.wr(i, v); shadow[i] = v
    for i in range(NW):
        g.rd(i, shadow[i], "T1 readback")
    g.c("逆順でもう一度（読出が直前の書込に依存していないこと）")
    for i in reversed(range(NW)):
        g.rd(i, shadow[i], "T1 reverse")

    #---- T2 -----------------------------------------------------------------
    g.head("T2  ウォーキング 1 / 0（4 本のビット線が独立か）")
    for i in range(NW):
        for j in range(NB):
            v = 1 << j
            g.wr(i, v); shadow[i] = v
            g.rd(i, v, "T2 walk1")
            v = (~(1 << j)) & 0xF
            g.wr(i, v); shadow[i] = v
            g.rd(i, v, "T2 walk0")

    #---- T3 -----------------------------------------------------------------
    g.head("T3  デコーダ一意性（全語 0101 -> 1 語だけ 1010、他 15 語が不変か）")
    for k in range(NW):
        for i in range(NW):
            g.wr(i, 0b0101)
        g.wr(k, 0b1010)
        for i in range(NW):
            g.rd(i, 0b1010 if i == k else 0b0101, "T3 unique")

    #---- T4 -----------------------------------------------------------------
    g.head("T4  WEB 極性（WEB=1 では書けない / 落とせば書ける）")
    for i in range(NW):
        g.wr(i, 0b1100)
    g.c("WEB を落とさずにアドレスとデータだけ動かす -> 何も書かれないはず")
    for i in range(NW):
        g.set_add(i)
        g.set_din(0b0011)
        g.raw(f"s {T_SETUP + T_WRITE + T_HOLD}")
    g.set_din(0)
    for i in range(NW):
        g.rd(i, 0b1100, "T4 no-write")
    g.c("WEB を落とせば書ける（そもそも書けていない、のではないことの証明）")
    for i in range(NW):
        g.wr(i, 0b0011)
    for i in range(NW):
        g.rd(i, 0b0011, "T4 write-ok")

    #---- T5 -----------------------------------------------------------------
    g.head("T5  保持（全書込後にアドレス順でない順序で読み直す）")
    for i in range(NW):
        v = (i * 7 + 3) & 0xF
        g.wr(i, v); shadow[i] = v
    n = 0
    for _ in range(4 * NW):
        n = (n * 5 + 11) % NW
        g.rd(n, shadow[n], "T5 hold")

    #---- I1 -----------------------------------------------------------------
    g.head("I1  [参考] アドレスと WEB のタイミング（合否には数えない）")
    g.c("(a) アドレスと WEB を同時に動かす")
    for i in range(NW):
        g.wr(i, 0)
    g.set_add(0)
    g.set_din(0b1111)
    g.raw(f"s {T_SETUP}")
    g.c("ここでアドレス変更と WEB 立下げを同じ時刻に置く")
    g.set_add(15)
    g.set_web(0)
    g.raw(f"s {T_WRITE}")
    g.set_web(1)
    g.raw(f"s {T_HOLD}")
    g.set_din(0)
    for i in range(NW):
        g.rd(i, 0b1111 if i == 15 else 0, "I1a timing")

    g.c()
    g.c("(b) WEB=0 のままアドレスを動かす（違反した使い方）")
    for i in range(NW):
        g.wr(i, 0)
    g.set_add(0)
    g.set_din(0b1111)
    g.raw(f"s {T_SETUP}")
    g.set_web(0)
    g.raw(f"s {T_WRITE}")
    g.c("書込を開いたままアドレスを動かす")
    g.set_add(15)
    g.raw(f"s {T_WRITE}")
    g.set_web(1)
    g.raw(f"s {T_HOLD}")
    g.set_din(0)
    for i in range(NW):
        g.rd(i, 0b1111 if i in (0, 15) else 0, "I1b timing")

    g.o.append("")
    g.c("end of reg4x16.cmd")
    return g


def main():
    out_cmd = sys.argv[1] if len(sys.argv) > 1 else "irsim/reg4x16.cmd"
    g = build()
    with open(out_cmd, "w", encoding="utf-8") as f:
        f.write("\n".join(g.o) + "\n")
    tags = {}
    for e in g.exp:
        tags[e["tag"]] = tags.get(e["tag"], 0) + 1
    print(f"{out_cmd}: {len(g.o)} 行 / {len(g.exp)} チェック", file=sys.stderr)
    for k, v in tags.items():
        print(f"    {k:14} {v}", file=sys.stderr)


if __name__ == "__main__":
    main()

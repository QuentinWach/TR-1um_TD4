#!/usr/bin/env python3
"""IRSIM の TD4 実行ログから合否を集計する（U14）

  usage: python3 scripts/check_irsim_td4_log.py irsim/td4_soc_arr_run.log [-v]

IRSIM の .cmd 言語には条件分岐も算術も無いので、テストベンチのように
自前で pass/fail を数えられない。`scripts/gen_irsim_td4.py` が出した .cmd は
1 サイクルごとに

    print TD4CHECK tag=P1_09 pc=1001 instr=10010000 expA=1010 expB=1010
                   expO=1010 expC=0 note=OUT_B      <- 何を期待しているか
    assert AV 1010 / assert BV 1010 / ...            <- IRSIM 自身の判定
    d AV BV OV CV                                    <- 実際の A / B / OUT / C

を出すので、ログだけで完結して集計できる（期待値ファイル不要）。

判定するもの:
  ・A / B / OUT / C が 1 サイクルずつ期待どおりか（`x` / `X` はその場で FAIL）
  ・IRSIM 自身の assertion failed が出ていないか
  ・**12 命令ぜんぶ通ったか**（op コードを数える。通っていなければ
    「PASS だが検査していない」なので落とす）
"""
from __future__ import annotations

import re
import sys

RE_CHECK = re.compile(
    r"TD4CHECK\s+tag=(\S+)\s+pc=([01]+)\s+instr=([01]+)\s+expA=([01]+)\s+"
    r"expB=([01]+)\s+expO=([01]+)\s+expC=([01]+)\s+note=(\S+)")
RE_VAL = re.compile(r"\b(AV|BV|OV|CV)=([01xX]+)")
RE_ASSERT = re.compile(r"assertion failed")

# 全 12 命令。ここに無い op が出てきたら「表に無い命令」として報告する。
ISA = {
    "0000": "ADD A,Im", "0001": "MOV A,B", "0010": "IN A", "0011": "MOV A,Im",
    "0100": "MOV B,A", "0101": "ADD B,Im", "0110": "IN B", "0111": "MOV B,Im",
    "1001": "OUT B", "1011": "OUT Im", "1110": "JNC Im", "1111": "JMP Im",
}
FIELDS = (("AV", 3, "A"), ("BV", 4, "B"), ("OV", 5, "OUT"), ("CV", 6, "C"))


def parse(path):
    """[(fields..., {AV/BV/OV/CV: 実測})] を出現順に返す。"""
    rows, cur, got = [], None, {}
    nassert = 0
    for ln in open(path, encoding="utf-8", errors="replace"):
        if RE_ASSERT.search(ln):
            nassert += 1
        m = RE_CHECK.search(ln)
        if m:
            if cur is not None:
                rows.append((cur, got))          # d が出ないまま次が来た
            cur, got = m.groups(), {}
            continue
        if cur is None:
            continue
        for name, val in RE_VAL.findall(ln):
            got[name] = val
        if len(got) == 4:
            rows.append((cur, got))
            cur, got = None, {}
    if cur is not None:
        rows.append((cur, got))
    return rows, nassert


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    verbose = "-v" in sys.argv[2:]

    rows, nassert = parse(path)

    print("=" * 66)
    print(f" TD4 全 12 命令トレース  IRSIM スイッチレベル検証   log = {path}")
    print("=" * 66)
    if not rows:
        print(" ** TD4CHECK マーカーが 1 つも見つからない。")
        print("    .cmd が古いか、IRSIM が起動していない。ログの先頭を見ること。")
        sys.exit(1)

    npass = nfail = 0
    seen_ops, per_phase = {}, {}
    for i, (f, got) in enumerate(rows):
        tag, pc, instr, note = f[0], f[1], f[2], f[7]
        op = instr[:4]
        seen_ops.setdefault(op, 0)
        seen_ops[op] += 1
        phase = tag.split("_")[0]
        cnt = per_phase.setdefault(phase, [0, 0])
        bad = []
        for key, idx, label in FIELDS:
            exp, act = f[idx], got.get(key)
            if act is None or act.lower().count("x") or act != exp:
                bad.append(f"{label} 期待 {exp} 実際 {act}")
        if bad:
            nfail += 1
            cnt[1] += 1
            print(f"  ** FAIL #{i} {tag} pc={int(pc, 2):2d} {instr} "
                  f"{note.replace('_', ' ')}: " + " / ".join(bad))
        else:
            npass += 1
            cnt[0] += 1
            if verbose:
                print(f"     ok  #{i} {tag} pc={int(pc, 2):2d} {instr} "
                      f"{note.replace('_', ' ')}  A={got['AV']} B={got['BV']} "
                      f"OUT={got['OV']} C={got['CV']}")

    print("-" * 66)
    for phase, (p, f) in per_phase.items():
        print(f"  {phase:6}  PASS {p:4d}   FAIL {f:4d}")
    print("-" * 66)
    print(f"  合計  PASS {npass} / FAIL {nfail}   （{len(rows)} サイクル）")
    print(f"  IRSIM 自身の assertion failed: {nassert} 件")

    missing = [f"{op} {name}" for op, name in ISA.items() if op not in seen_ops]
    extra = sorted(op for op in seen_ops if op not in ISA)
    print()
    print(f"  命令の網羅: {len(ISA) - len(missing)} / {len(ISA)}")
    if missing:
        print("  ** 通っていない命令: " + " , ".join(missing))
    if extra:
        print("  ** ISA 表に無い op が出た: " + " , ".join(extra))

    ok = not (nfail or nassert or missing or extra)
    print()
    print("  結果: 全項目 PASS — 12 命令ぜんぶがレイアウトのネットリストで走った"
          if ok else "  結果: 不一致あり")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

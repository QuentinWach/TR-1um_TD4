#!/usr/bin/env python3
"""KLayout の抽出ネットリスト `lef/extracted/<CELL>.extracted` を
ngspice でそのまま使える形に直す。

  usage: python3 loadext.py <extracted ディレクトリ> -o <出力ディレクトリ>

KLayout 版はこちらの簡易抽出器より**素性がよい**:

  ・DRC/LVS クリーンな状態の正規の抽出結果。
  ・**AS / AD / PS / PD（拡散の実面積と周長）が入っている。**
    PDK の PMOS/NMOS サブサーキットは既定で `AS='w*sdwidth'` と概算するが、
    実レイアウトの値で上書きできるので、接合容量が正確になる。
  ・すでに `XM...` 呼び出し形式（PDK のサブサーキットモデルに合う）。

直すのは 2 点だけ。回路は一切変えない。

  1. 無名ネットの `\\$6` → `n6`。`$` は ngspice で行末コメントの開始記号なので、
     そのまま食わせるとネット名が途中で切れる。
  2. インスタンス名の `XM$1` → `XM1`。同じ理由。
"""
from __future__ import annotations
import argparse, os, re, sys

RE_NET = re.compile(r"\\\$(\w+)")
RE_INST = re.compile(r"^(XM)\$(\w+)")


def convert(path):
    """[本文の行] を返す。コメントは落とさない（由来が追えるように）。"""
    out = []
    for ln in open(path, encoding="utf-8"):
        s = ln.rstrip("\n")
        s = RE_NET.sub(r"n\1", s)              # \$6 -> n6
        s = RE_INST.sub(r"\1\2", s)            # XM$1 -> XM1
        out.append(s)
    return out


def ports_of_lines(lines):
    for s in lines:
        t = s.split()
        if t and t[0].lower() == ".subckt":
            return t[2:]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    n = 0
    print(f"{'cell':<12}{'Tr':>4}  ports")
    for f in sorted(os.listdir(a.src)):
        if not f.endswith(".extracted"):
            continue
        cell = f[:-len(".extracted")]
        lines = convert(f"{a.src}/{f}")
        open(f"{a.out}/{cell}.spi", "w").write("\n".join(lines) + "\n")
        ntr = sum(1 for s in lines if re.match(r"^XM", s))
        print(f"{cell:<12}{ntr:>4}  {' '.join(ports_of_lines(lines))}")
        n += 1
    print(f"\n{n} セルを {a.out} に書いた")


if __name__ == "__main__":
    main()

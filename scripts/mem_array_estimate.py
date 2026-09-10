#!/usr/bin/env python3
"""td4_mem（16word x 8bit 命令メモリ）を FF 実装 / TLAT アレイで作った場合の面積比較。

FF 実装側は Yosys 合成の実測差分:
    td4_soc_arr（メモリも FF）      = 1.429 mm2   (scripts/stat_arr_ff.txt)
    td4_soc_arr（td4_mem をBB化）   = 0.277 mm2   (scripts/stat_arr_bb.txt)

アレイ側は **実在するセルの GDS 実測寸法**で積み上げる（推定値ではない）。
TLAT は行高 64.8 µm の標準セルで、セル内に基板/ウェルタップを持つので
アレイ内に TAP セル列は不要。ワードラインは M1 で左右端に出ており横 abut で繋がる。
"""
# --- lef/TR-1um_STDCELL.gds 実測（scripts/cellinfo.py）---
W_TLAT, W_INV, W_BUF, W_AND2, W_AND4 = 37.8, 10.8, 16.2, 21.6, 32.4   # µm
ROW_H = 64.8          # 標準セル行高
TLAT_H, TLAT_PITCH = 59.4, 54.6   # TLAT の 235 箱高さ / TLAT64 での実効行ピッチ
A_MUX2, A_DFFE = 2099.5, 6298.6
CORE = 1840.0 * 1840.0

WORDS, BITS = 16, 8
NBIT = WORDS * BITS
TILE = 4                                   # ビットセルタイルのビット幅

SOC_FF, SOC_BB = 1429429.0, 277488.0
MEM_FF = SOC_FF - SOC_BB

ARRAY_H = (WORDS - 1) * TLAT_PITCH + TLAT_H   # 878.4 (TLAT64 実測と一致)
W_ARRAY = BITS * W_TLAT                    # 302.4
# アドレスは R/W 共通・デコーダ1個。SEL[i] をそのまま RD[i] に使い、WR[i] = SEL[i] & WE。
#   AND4(SEL=RD) + INV(RDB) + AND2(WR) + INV(WRB) が1行ぶんの帯
W_DECDRV = W_AND4 + W_INV + W_AND2 + W_INV  # = 75.6
H_IO    = ROW_H                            # ライトドライバ + リード受け 1行

if __name__ == "__main__":
    print("=== FF 実装（Yosys 実測の差分） ===")
    print(f"  td4_soc_arr 全体   {SOC_FF/1e6:.3f} mm2 / うちメモリ以外 {SOC_BB/1e6:.3f} mm2")
    print(f"  命令メモリ {NBIT}bit  {MEM_FF/1e6:.3f} mm2  (全体の {MEM_FF/SOC_FF:.0%})")
    print(f"    = MUXDFFRB {NBIT}bit {NBIT*A_DFFE:,.0f} + 16:1リードMUX x8bit {BITS*(WORDS-1)*A_MUX2:,.0f} um2 ほか")
    print()

    print(f"=== TLAT アレイ（{TILE}bit タイル x {BITS//TILE} = {BITS}bit ワード）===")
    blocks = [
        (f"ビットセル {WORDS}行 x {BITS}列 (TLAT {W_TLAT}x{ROW_H})", W_ARRAY, ARRAY_H),
        ("デコーダ+WLドライバ帯 (AND4/INV/AND2/INV) x16行",          W_DECDRV, ARRAY_H),
        ("カラム I/O 帯 (ライトドライバ x8 + リード受け x16)",         W_ARRAY, H_IO),
    ]
    tot = 0.0
    for n, w, h in blocks:
        a = w * h; tot += a
        print(f"  {n:<44}{w:6.1f} x {h:6.1f} = {a:9,.0f} um2")
    print(f"  {'計':<44}{'':>15} {tot:9,.0f} um2 = {tot/1e6:.3f} mm2   ({MEM_FF/tot:.1f}x 圧縮)")
    mw, mh = W_ARRAY + W_DECDRV, ARRAY_H + H_IO
    print(f"  マクロ外形 {mw:.1f} x {mh:.1f} um = {mw*mh/1e6:.3f} mm2")
    print()

    print("=== ワードライン RC（M1 が途切れ、セルごとに poly を 9.2 µm 渡る）===")
    COX = 1.77e-3          # F/m2  (Tox 19.5nm, eps_ox 3.9)
    cg = lambda w: w * 1.0 * COX * 1e3   # fF: W[um]*L[um]*1e-12 m2 * COX[F/m2] * 1e15
    per_cell = {"WR": cg(3.4) + cg(7.2), "RD": cg(3.4)}   # TG-W(N)+TG-F(P) / TG-R(N)
    for n, c in per_cell.items():
        print(f"  {n}: ゲート容量 {c:.1f} fF/bit -> {TILE}bit {c*TILE:5.1f} fF / {BITS}bit {c*BITS:5.1f} fF")
    print("  poly 区間 9.2 µm/bit が直列 -> R も C も bit 数に比例 -> **RC は bit 数の 2乗**")
    print(f"  {BITS}bit を1本で引くと {TILE}bit タイルの {(BITS/TILE)**2:.0f} 倍。")
    print("  ※ poly のシート抵抗は PDK で要確認。20-40 ohm/sq なら TD4 の速度では問題にならない。")
    print()

    print("=== チップ全体（td4_soc_arr） ===")
    for tag, m, u in (("FF 実装", MEM_FF, 0.6), ("TLAT アレイ", mw * mh, 1.0)):
        total = SOC_BB / 0.6 + m / u
        print(f"  {tag:<12} ロジック {SOC_BB/1e6:.3f} + メモリ {m/1e6:.3f} "
              f"-> {total/1e6:.3f} mm2  (コアの {total/CORE:.0%})  {'OK' if total <= CORE else 'NG'}")

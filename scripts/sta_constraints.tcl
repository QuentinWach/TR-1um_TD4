# td4_soc_arr の設計固有の STA 制約。`config.STA_EXTRA_TCL` が指す。
# `$APRTOOLS/syn/sta/setup.tcl` の直後（クロックと駆動セルが決まってから）に連結される。
#
# ★ **false path は「ここは見なくてよい」という主張**なので、根拠を隣に書く。
#   根拠が無い指定は、検査を黙って減らすだけになる。
# ★ **当たったかどうかを必ず出す。** 名前が変わって 0 個に当たっても
#   SDC は無言で通る（U74 と同じ「回っていないのに OK」）。

proc fp {label objs {to_objs ""}} {
    # ★ `eval`/`concat` は使わない。OpenSTA のコレクションが複数語に
    #   ばらけて `-to` が壊れる。引数は 2 通りしか無いので素直に分ける。
    if {[llength $objs] == 0} {
        puts "  ** false path「$label」が **0 個**に当たった。名前が変わっていないか"
        return
    }
    if {$to_objs eq ""} {
        set_false_path -through $objs
        puts "  （false path: $label — 経由 [llength $objs] 個）"
    } elseif {[llength $to_objs] == 0} {
        puts "  ** false path「$label」の行き先が **0 個**に当たった"
    } else {
        set_false_path -through $objs -to $to_objs
        puts "  （false path: $label — 経由 [llength $objs] 個 -> 行き先 [llength $to_objs] 個）"
    }
}

# --- 1. 書込み中に Q が追従する経路（REG8x16 の WEB -> Q）------------------
# `WEB` は scripts/mem_wrap.py が置く `OR2(clk_buf, ~wr_hi)` なので、`clk` の
# クロックネットワークがそのまま伝播し、**clk の立下りを起点に**
#   WEB↓ -> WEB->Q -> 命令デコード -> pc[3]/D
# という半周期パスに見える。周期 100 ns で **-15.031 ns** 違反と出た。
#
# この経路は**論理的に成立しない**。RTL の 2 行が根拠:
#   hdl/rtl/td4_soc_arr.v : wire wr_hi = ~exec & wr & nibsel;  // 書込みは exec=0 のときだけ
#   hdl/rtl/td4_core.v    : end else if (en) ... pc <= ...     // en = exec。exec=0 では全 FF が止まる
# さらに exec=1 では wr_hi=0 なので `WEB = clk | 1` で動かない。
# → **書込みで動いた Q を捕まえる FF が 1 つも無い。**
#
# ★ 読出し `ADD -> Q` は外さない（実行中の本物のパスで、critical に乗っている）。
fp "WEB -> Q（書込み中の追従。exec=0 でしか動かず、そのときコアは止まっている）" \
   [get_pins -quiet u_mem/WEB]

# --- 2. nib_lo -> REG8x16 の D（データ保持 6.0 ns）-------------------------
# `nib_lo` の FF は clk↑ の 5.291 ns 後に値を変え、`REG8x16` が要求する保持は
# `WEB↑` から 6.0 ns（U7 実測・配線容量なし）なので **-0.709 ns** 違反と出る。
#
# これも**論理的に成立しない**。ネットリストの 2 行が根拠（out/td4_soc_arr_pnr.v）:
#   wr_hi = AND3_X1(_083_, wr_buf, nibsel_buf)
#       -> WEB が「書込みの終わり」として立ち上がるのは **nibsel_buf = 1** のときだけ
#   nib_lo[k] の D = MUX2(nib_lo[k], d_buf[k], _073_),  _073_ = NOR3(exec_buf, _072_, nibsel_buf)
#       -> 新しい値を取り込むのは **nibsel_buf = 0** のときだけ
# **同じ網が逆の極性で両方を選んでいる**ので、書込みを終える縁で nib_lo は動かない。
# チップの TB も 1 命令 3 サイクル（下位 / 上位 / 空け）で、この形になっている。
#
# ★ **前提**: `nibsel` は負エッジで置いて正エッジで取り込む（同期入力の約束）。
#   クロック縁の近くで `nibsel` を動かすと、この排他は崩れる。
# ★ **将来プロトコルを変えて、書込み中に nib_lo が動くようにしたら、この
#   false path は本物の違反を隠す。** そのときはここを消すこと。
# ★ `ADD` 側の保持は外していない（`raddr` の MUX を通るぶん遅く着いて
#   +3.4〜+6.5 ns で満たしている。**検査は残す**）。
fp "nib_lo -> u_mem/D（nibsel が排他に選ぶので、書込みを終える縁では動かない）" \
   [get_nets -quiet {nib_lo[0] nib_lo[1] nib_lo[2] nib_lo[3]}] \
   [get_pins -quiet u_mem/D*]

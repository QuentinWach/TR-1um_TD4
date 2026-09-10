#!/bin/sh
# TD4 / TR-1um: 機能検証 → Yosys 合成 → 実セル面積換算 をまとめて実行する。
# usage: sh scripts/syn.sh   (リポジトリルートで)
set -e
YS=${YOSYS:-yowasp-yosys}
RTL="hdl/rtl/td4_core.v hdl/rtl/td4_mem.v hdl/rtl/td4_soc_rom.v \
     hdl/rtl/td4_soc_ff.v hdl/rtl/td4_soc_arr.v"

# ---- 機能検証 ----
if command -v iverilog >/dev/null 2>&1; then
  iverilog -g2012 -o /tmp/td4_tb1.vvp hdl/tb/tb_td4_core.v hdl/rtl/td4_core.v
  vvp /tmp/td4_tb1.vvp | tail -2
  iverilog -g2012 -o /tmp/td4_tb2.vvp hdl/tb/tb_td4_soc_arr.v \
           hdl/rtl/td4_soc_arr.v hdl/rtl/td4_mem.v hdl/rtl/td4_core.v
  vvp /tmp/td4_tb2.vvp | tail -2
  echo
fi

# ---- 合成 + 面積見積り ----
for T in td4_core td4_soc_rom td4_soc_ff td4_soc_arr; do
  echo "##################### $T"
  $YS -q -p "read_verilog $RTL; hierarchy -check -top $T; synth -top $T -flatten; \
             abc -g simple; opt_clean; tee -o scripts/stat_$T.txt stat" >/dev/null 2>&1
  python3 scripts/area_estimate.py scripts/stat_$T.txt --top $T | tail -13
  echo
done

# ---- td4_mem をブラックボックス化して周辺ロジックだけ測る ----
echo "##################### td4_soc_arr (td4_mem = blackbox)"
$YS -q -p "read_verilog $RTL; blackbox td4_mem; hierarchy -check -top td4_soc_arr; \
           synth -top td4_soc_arr -flatten; abc -g simple; opt_clean; \
           tee -o scripts/stat_arr_bb.txt stat" >/dev/null 2>&1
python3 scripts/area_estimate.py scripts/stat_arr_bb.txt --top td4_soc_arr | tail -13
echo

echo "##################### 命令メモリ カスタムアレイ化の効果"
python3 scripts/mem_array_estimate.py
echo
echo "##################### カスタムセル適用後（全体）"
python3 scripts/area_custom.py

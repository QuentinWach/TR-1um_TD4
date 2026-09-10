#!/bin/sh
# REG4x16 スイッチレベル検証
#   ./hdl/run_reg4x16.sh          … 実行
#   ./hdl/run_reg4x16.sh -w       … VCD も出す (reg4x16.vcd)
set -e
cd "$(dirname "$0")/.."
OPT="-g2012"
[ "$1" = "-w" ] && OPT="$OPT -DDUMP"
iverilog $OPT -o hdl/sim_reg4x16 hdl/rtl/reg4x16.v hdl/tb/tb_reg4x16.v
vvp hdl/sim_reg4x16

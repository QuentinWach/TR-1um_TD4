#!/bin/sh
# REG4x16 / REG8x16 スイッチレベル検証
#   sh hdl/run_regx16.sh        … 4bit（既定）
#   sh hdl/run_regx16.sh 8      … 8bit
#   sh hdl/run_regx16.sh 8 -w   … VCD も出す (regx16.vcd)
set -e
cd "$(dirname "$0")/.."
BITS="${1:-4}"
OPT="-g2012 -DBITS=$BITS"
[ "$2" = "-w" ] && OPT="$OPT -DDUMP"
iverilog $OPT -o hdl/sim_reg${BITS}x16 hdl/rtl/regx16.v hdl/tb/tb_regx16.v
vvp hdl/sim_reg${BITS}x16

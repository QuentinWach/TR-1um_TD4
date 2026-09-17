#!/bin/sh
# TD4 全 12 命令トレース（IRSIM スイッチレベル）— U14
#
#   sh irsim/run_td4.sh        … 実行して合否まで表示
#   sh irsim/run_td4.sh -v     … 全サイクルを 1 行ずつ表示
#
# hdl/tb/tb_td4_soc_arr_isa.v（Verilog 版）と**同じプログラム・同じ期待値**。
# 両方 scripts/gen_irsim_td4.py が出すので食い違わない。
# Verilog 版は論理と接続、こちらは実 R/C モデルでの遅延を見る。
#
# ★ .sim は **LVS ソースネットリスト**（= 配置配線したコアと LVS が通った網）
#   から作る。配線容量は入らないが、トランジスタの接続と寸法は実物と一致する。
set -eu
cd "$(dirname "$0")/.."
VERBOSE="${1:-}"

# ★ `.sim` の変換器は **APRtools の正本**を使う（決定 25）。
#   `scripts/spi2sim.py` は移行前の写しで、内部ノードの角括弧を潰さない
#   古い版のまま残っている（U94）。写しを掴むと `.cmd` の `vector` に
#   `u_core_reg_a[0]` と書くはめになり、IRSIM がノードを見つけられない。
#   **黙って写しに落ちないよう、無ければここで止める。**
: "${APRTOOLS:?APRTOOLS を export してください（docs/30_verify_drc_lvs.md §0）}"
SPI2SIM="$APRTOOLS/apr/spi2sim.py"
[ -f "$SPI2SIM" ] || { echo "$SPI2SIM が無い。APRTOOLS を確かめること" >&2; exit 1; }
PRM=irsim/TR-1um.prm
TOP=td4_soc_arr_nrow_fm
SRC=layout/chip/simulation/${TOP}.spice
SIM=irsim/td4_soc_arr.sim
CMD=irsim/td4_soc_arr.cmd
TB=hdl/tb/tb_td4_soc_arr_isa.v
LOG=irsim/td4_soc_arr_run.log

[ -f "$SRC" ] || { echo "$SRC が無い。先に scripts/pnr/mklvsnet.py を回すこと" >&2; exit 1; }

# LVS ソースの方が新しければ .sim を作り直す
if [ ! -f "$SIM" ] || [ "$SRC" -nt "$SIM" ]; then
  echo "generating $SIM from $SRC" >&2
  python3 "$SPI2SIM" "$SRC" "$TOP" > "$SIM"
fi
# 生成器の方が新しければ .cmd と Verilog TB を作り直す（2 つは必ず同時に）
if [ ! -f "$CMD" ] || [ scripts/gen_irsim_td4.py -nt "$CMD" ]; then
  python3 scripts/gen_irsim_td4.py --cmd "$CMD" --verilog "$TB"
fi
# .cmd が触るノードが .sim にあるか（無いと「走ったが何も駆動していない」になる）
python3 scripts/gen_irsim_td4.py --check-sim "$SIM"

echo "irsim $PRM $SIM  ($CMD -> $LOG)" >&2
# NOTE: "-@ cmdfile" の CLI フラグは環境によって効かないので、
#       参照プロジェクト（TR-1um_Async_I2C）と同じく stdin の heredoc で渡す。
irsim "$PRM" "$SIM" > "$LOG" 2>&1 << EOT
@ $CMD
EOT

python3 scripts/check_irsim_td4_log.py "$LOG" $VERBOSE

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
# ★ .sim は **LVS ソースネットリスト**（= 配置配線したコアと LVS が通ったネット）
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

# --- 否定対照: BUFTH だけを叩く ------------------------------------------
# 入力は全部 BUFTH（シュミットトリガ）で受けている。**IRSIM はこれを解けない**
# ので、本体では BUFTH の出口（*_buf）も直接駆動している。その根拠をここで
# 毎回とる — Y が X のままなら「IRSIM が解けない」、解けていたら本体の
# 迂回はもう要らない（そのときはこの注記ごと見直すこと）。
PSIM=irsim/probe_bufth.sim
PCMD=irsim/probe_bufth.cmd
PLOG=irsim/probe_bufth_run.log
if [ ! -f "$PSIM" ] || [ "$SPI2SIM" -nt "$PSIM" ]; then
  python3 "$SPI2SIM" "$APRTOOLS/stdcell/v59_4/simulation/BUFTH.spice" BUFTH \
    | sed -e "s#$APRTOOLS#\$APRTOOLS#g" > "$PSIM"
fi
irsim "$PRM" "$PSIM" > "$PLOG" 2>&1 << EOT
@ $PCMD
EOT
echo "--- BUFTH 単体（否定対照）: A を 0 / 1 / 0 と振ったときの Y ---"
grep -E "\bA=" "$PLOG" || echo "  ** d の出力が無い。$PLOG を見ること"
echo

echo "irsim $PRM $SIM  ($CMD -> $LOG)" >&2
# NOTE: "-@ cmdfile" の CLI フラグは環境によって効かないので、
#       参照プロジェクト（TR-1um_Async_I2C）と同じく stdin の heredoc で渡す。
irsim "$PRM" "$SIM" > "$LOG" 2>&1 << EOT
@ $CMD
EOT

python3 scripts/check_irsim_td4_log.py "$LOG" $VERBOSE

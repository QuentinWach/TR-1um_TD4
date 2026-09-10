#!/bin/sh
# REG4x16 タイミング確認（ngspice, 実デバイスモデル, 0.1ns 刻み）
#
#   sh spice/run_tran.sh            … 配線容量 0/50/100/200 fF を掃引
#   sh spice/run_tran.sh 100        … 1 点だけ
#
# 配線容量はネットリストに入っていないので集中容量として外付けし、
# 遅延がどれだけ効くかを掃引で見る。CBL=0 が IRSIM と同じ条件。
set -eu
cd "$(dirname "$0")/.."
MODELS="${MODELS:-$HOME/Dropbox/91_OpenPDK/TR-1um/libs.tech/spice/models/ip62_models}"
NET=spice/REG4x16_ngspice.spi
LIST="${*:-0 50 100 200}"

# LVS ソースが新しければ ngspice 用ネットリストを作り直す
if [ ! -f "$NET" ] || [ spice/REG4x16_src.spi -nt "$NET" ]; then
  echo "generating $NET" >&2
  python3 scripts/spi2ngspice.py spice/REG4x16_src.spi > "$NET"
fi

LOGS=""
for c in $LIST; do
  DECK=spice/REG4x16_tran_$c.spi
  LOG=spice/REG4x16_tran_$c.log
  python3 scripts/gen_ngspice_tran.py "$c" "$DECK" "$MODELS" "$NET"
  echo "ngspice -b $DECK  -> $LOG" >&2
  ngspice -b "$DECK" > "$LOG" 2>&1
  LOGS="$LOGS $LOG"
done
python3 scripts/check_ngspice.py tran $LOGS

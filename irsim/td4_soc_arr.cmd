| td4_soc_arr.cmd -- TD4 全 12 命令トレース（IRSIM 版）
| scripts/gen_irsim_td4.py が生成。手で編集しないこと。
| hdl/tb/tb_td4_soc_arr_isa.v と同じプログラム・同じ期待値。
|
| 合否判定: python3 scripts/check_irsim_td4_log.py irsim/td4_soc_arr_run.log
| 1 サイクルごとに print で期待値を刻み、assert でその場で判定し、
| d で実際の値を残す。IRSIM の .cmd 言語には条件分岐も算術も無いので、
| 集計だけをログのオフライン突合せで行う。
|
| stepsize 1 -> 1ns。半周期 100 ns（reg->reg の実測 60.3 ns に対し 3 倍以上）
stepsize 1
settle 10
|
h Vdd
l Gnd
l clk
l rst_n
l exec
l wr
l nibsel
l d0
l d1
l d2
l d3
s 200
|
| 表示用ベクタ。d で 4 つ同時に出す。
vector AV u_core_reg_a3 u_core_reg_a2 u_core_reg_a1 u_core_reg_a0
vector BV u_core_reg_b3 u_core_reg_b2 u_core_reg_b1 u_core_reg_b0
vector OV out_port3 out_port2 out_port1 out_port0
vector CV cflag_o

| ==================================================================
| P1  —  16 命令を Load して 16 サイクル走らせる
| ==================================================================
| リセット（PC と ld_addr を 0 に戻す）
s 100
h clk
s 100
l clk
h rst_n
s 100
h clk
s 100
|
| Load モード: 1 命令 = 下位ニブル -> 上位ニブルの 2 回書込
|  0: 00110101  MOV A,Im 5
l clk
h d0
h d2
h wr
s 100
h clk
s 100
l clk
h nibsel
h d1
l d2
s 100
h clk
s 100
|  1: 00000011  ADD A,Im 3
l clk
l nibsel
s 100
h clk
s 100
l clk
h nibsel
l d0
l d1
s 100
h clk
s 100
|  2: 00001001  ADD A,Im 9
l clk
l nibsel
h d0
h d3
s 100
h clk
s 100
l clk
h nibsel
l d0
l d3
s 100
h clk
s 100
|  3: 11100000  JNC 0
l clk
l nibsel
s 100
h clk
s 100
l clk
h nibsel
h d1
h d2
h d3
s 100
h clk
s 100
|  4: 01000000  MOV B,A
l clk
l nibsel
l d1
l d2
l d3
s 100
h clk
s 100
l clk
h nibsel
h d2
s 100
h clk
s 100
|  5: 01111001  MOV B,Im 9
l clk
l nibsel
h d0
l d2
h d3
s 100
h clk
s 100
l clk
h nibsel
h d1
h d2
l d3
s 100
h clk
s 100
|  6: 00010000  MOV A,B
l clk
l nibsel
l d0
l d1
l d2
s 100
h clk
s 100
l clk
h nibsel
h d0
s 100
h clk
s 100
|  7: 00100000  IN A
l clk
l nibsel
l d0
s 100
h clk
s 100
l clk
h nibsel
h d1
s 100
h clk
s 100
|  8: 01100000  IN B
l clk
l nibsel
l d1
s 100
h clk
s 100
l clk
h nibsel
h d1
h d2
s 100
h clk
s 100
|  9: 10010000  OUT B
l clk
l nibsel
l d1
l d2
s 100
h clk
s 100
l clk
h nibsel
h d0
h d3
s 100
h clk
s 100
| 10: 10110110  OUT Im 6
l clk
l nibsel
l d0
h d1
h d2
l d3
s 100
h clk
s 100
l clk
h nibsel
h d0
l d2
h d3
s 100
h clk
s 100
| 11: 01010110  ADD B,Im 6
l clk
l nibsel
l d0
h d2
l d3
s 100
h clk
s 100
l clk
h nibsel
h d0
l d1
s 100
h clk
s 100
| 12: 11101110  JNC 14
l clk
l nibsel
l d0
h d1
h d3
s 100
h clk
s 100
l clk
h nibsel
s 100
h clk
s 100
| 13: 11101111  JNC 15
l clk
l nibsel
h d0
s 100
h clk
s 100
l clk
h nibsel
l d0
s 100
h clk
s 100
| 14: 10111111  OUT Im 15
l clk
l nibsel
h d0
s 100
h clk
s 100
l clk
h nibsel
l d2
s 100
h clk
s 100
| 15: 00110111  MOV A,Im 7
l clk
l nibsel
h d2
l d3
s 100
h clk
s 100
l clk
h nibsel
l d2
s 100
h clk
s 100
l clk
l wr
|
| Exec モード（入力ポート d = 1010）
l d0
h d3
h exec
s 100
h clk
s 100
print TD4CHECK tag=P1_00 pc=0000 instr=00110101 expA=0101 expB=0000 expO=0000 expC=0 note=MOV_A,Im_5
assert AV 0101
assert BV 0000
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_01 pc=0001 instr=00000011 expA=1000 expB=0000 expO=0000 expC=0 note=ADD_A,Im_3
assert AV 1000
assert BV 0000
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_02 pc=0010 instr=00001001 expA=0001 expB=0000 expO=0000 expC=1 note=ADD_A,Im_9
assert AV 0001
assert BV 0000
assert OV 0000
assert CV 1
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_03 pc=0011 instr=11100000 expA=0001 expB=0000 expO=0000 expC=0 note=JNC_0
assert AV 0001
assert BV 0000
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_04 pc=0100 instr=01000000 expA=0001 expB=0001 expO=0000 expC=0 note=MOV_B,A
assert AV 0001
assert BV 0001
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_05 pc=0101 instr=01111001 expA=0001 expB=1001 expO=0000 expC=0 note=MOV_B,Im_9
assert AV 0001
assert BV 1001
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_06 pc=0110 instr=00010000 expA=1001 expB=1001 expO=0000 expC=0 note=MOV_A,B
assert AV 1001
assert BV 1001
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_07 pc=0111 instr=00100000 expA=1010 expB=1001 expO=0000 expC=0 note=IN_A
assert AV 1010
assert BV 1001
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_08 pc=1000 instr=01100000 expA=1010 expB=1010 expO=0000 expC=0 note=IN_B
assert AV 1010
assert BV 1010
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_09 pc=1001 instr=10010000 expA=1010 expB=1010 expO=1010 expC=0 note=OUT_B
assert AV 1010
assert BV 1010
assert OV 1010
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_10 pc=1010 instr=10110110 expA=1010 expB=1010 expO=0110 expC=0 note=OUT_Im_6
assert AV 1010
assert BV 1010
assert OV 0110
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_11 pc=1011 instr=01010110 expA=1010 expB=0000 expO=0110 expC=1 note=ADD_B,Im_6
assert AV 1010
assert BV 0000
assert OV 0110
assert CV 1
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_12 pc=1100 instr=11101110 expA=1010 expB=0000 expO=0110 expC=0 note=JNC_14
assert AV 1010
assert BV 0000
assert OV 0110
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_13 pc=1101 instr=11101111 expA=1010 expB=0000 expO=0110 expC=0 note=JNC_15
assert AV 1010
assert BV 0000
assert OV 0110
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_14 pc=1111 instr=00110111 expA=0111 expB=0000 expO=0110 expC=0 note=MOV_A,Im_7
assert AV 0111
assert BV 0000
assert OV 0110
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P1_15 pc=0000 instr=00110101 expA=0101 expB=0000 expO=0110 expC=0 note=MOV_A,Im_5
assert AV 0101
assert BV 0000
assert OV 0110
assert CV 0
d AV BV OV CV
l clk
l exec

| ==================================================================
| P2  —  4 命令を Load して 5 サイクル走らせる
| ==================================================================
| リセット（PC と ld_addr を 0 に戻す）
l rst_n
s 100
h clk
s 100
l clk
h rst_n
s 100
h clk
s 100
|
| Load モード: 1 命令 = 下位ニブル -> 上位ニブルの 2 回書込
|  0: 11110010  JMP 2
l clk
l nibsel
l d3
h wr
s 100
h clk
s 100
l clk
h nibsel
h d0
h d2
h d3
s 100
h clk
s 100
|  1: 10111111  OUT Im 15
l clk
l nibsel
s 100
h clk
s 100
l clk
h nibsel
l d2
s 100
h clk
s 100
|  2: 10110011  OUT Im 3
l clk
l nibsel
l d3
s 100
h clk
s 100
l clk
h nibsel
h d3
s 100
h clk
s 100
|  3: 11110011  JMP 3
l clk
l nibsel
l d3
s 100
h clk
s 100
l clk
h nibsel
h d2
h d3
s 100
h clk
s 100
l clk
l wr
|
| Exec モード（入力ポート d = 1010）
l d0
l d2
h exec
s 100
h clk
s 100
print TD4CHECK tag=P2_00 pc=0000 instr=11110010 expA=0000 expB=0000 expO=0000 expC=0 note=JMP_2
assert AV 0000
assert BV 0000
assert OV 0000
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P2_01 pc=0010 instr=10110011 expA=0000 expB=0000 expO=0011 expC=0 note=OUT_Im_3
assert AV 0000
assert BV 0000
assert OV 0011
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P2_02 pc=0011 instr=11110011 expA=0000 expB=0000 expO=0011 expC=0 note=JMP_3
assert AV 0000
assert BV 0000
assert OV 0011
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P2_03 pc=0011 instr=11110011 expA=0000 expB=0000 expO=0011 expC=0 note=JMP_3
assert AV 0000
assert BV 0000
assert OV 0011
assert CV 0
d AV BV OV CV
l clk
s 100
h clk
s 100
print TD4CHECK tag=P2_04 pc=0011 instr=11110011 expA=0000 expB=0000 expO=0011 expC=0 note=JMP_3
assert AV 0000
assert BV 0000
assert OV 0011
assert CV 0
d AV BV OV CV
l clk
l exec

| end of td4_soc_arr.cmd

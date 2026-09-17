| probe_bufth.cmd -- BUFTH（シュミットトリガ入力バッファ）だけを IRSIM で叩く
|
| 何のための否定対照か:
|   TD4 のトレースで入力 9 本が全部 X になった（2026-09-17、U14）。
|   原因が「BUFTH を IRSIM が解けない」ことだと**測って**示すための最小例。
|   A を 0 / 1 / 0 と振って Y を見る。Y が X のままなら、原因は BUFTH。
|
| なぜ解けないか:
|   ヒステリシスの帰還 MOS が自分の出力ノード n2 でゲートされているので、
|   初期値 X から抜けられない（n2=X -> 帰還が「導通するかも」-> n3 が vdd と
|   vss の両方に引かれて X -> n2=X …）。しかも帰還の方が太いので強さでも決まらない。
stepsize 1
settle 10
h Vdd
l Gnd
l A
s 500
d A Y n2 n3 n1
h A
s 500
d A Y n2 n3 n1
l A
s 500
d A Y n2 n3 n1

| end of probe_bufth.cmd

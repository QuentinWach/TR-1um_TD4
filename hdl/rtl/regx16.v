//============================================================================
//  regx16.v — REG4x16 / REG8x16 (Nbit x 16word レジスタファイル)
//             スイッチレベル Verilog
//
//  spice/REG4x16_src.spi / REG8x16_src.spi（= LVS ソースネットリスト、
//  どちらも LVS クリーン）を
//  トランジスタ 1 個ずつ 1:1 で書き起こしたもの。
//  動作モデルではなく「ネットリストそのもの」を Verilog のスイッチ
//  プリミティブ（pmos / nmos / tranif0 / tranif1）で表現している。
//
//    MP/MN <d> <g> <s> <b> PMOS/NMOS   ->  pmos/nmos (<d>, <s>, <g>)
//    トランスファゲート                ->  tranif0(pmos側) + tranif1(nmos側)
//
//  トランスファゲートを双方向 tranif で書いてあるので、ビット線の
//  ハイインピーダンス・多重駆動・向きの誤りがそのまま X として現れる。
//
//  ビット幅だけが違う同じ構成なので、トップを REGX16 #(BITS) として
//  一般化し、REG4x16 / REG8x16 はその薄いラッパにしてある
//  （scripts/mkspice.py --bits と同じ関係）。
//
//  階層・ポート順は SPICE と同じ:
//    TLAT   WR WRB RD RDB D Q
//    DEC2   A0 AB0 A1 A2 A3 WEB WRE WRBE RDE RDBE WRO WRBO RDO RDBO
//    REGBUF DD D Q QQ
//    ADDBUF A0_PIN A1_PIN A2_PIN A3_PIN WEB_PIN A0 AB0 A1 AB1 A2 AB2 A3 AB3 WEB
//
//  TR-1um (IP62) / L = 1.0um
//    REG4x16 = 1,076 Tr / 248.4 x 933.0 um
//    REG8x16 = 1,876 Tr / 399.6 x 933.0 um
//============================================================================
`timescale 1ns / 1ps
`default_nettype none

// INV 1 段ぶんの遅延。0 にすると競合が見えなくなるので必ず 0 より大きく。
`ifndef TP_INV
 `define TP_INV 1
`endif

//----------------------------------------------------------------------------
// TLAT — 12T ratioless ラッチ ビットセル
//
//   D --[TG-W:WR]-- n3 --INV1--> n1 --INV2--> n2 --[TG-F:WRB]-- n3
//                                 n1 --INV3--> n4 --[TG-R:RD]-- Q
//
//   WR=1 で TG-W 導通・TG-F 遮断（ratioless: 書込中は帰還を切る）
//   RD=1 で TG-R 導通。INV3 は読出専用バッファなので読出ディスターブ無し
//----------------------------------------------------------------------------
module TLAT (input wire WR, input wire WRB, input wire RD, input wire RDB,
             inout wire D, inout wire Q);
  supply1 vdd;
  supply0 vss;
  wire n1, n2, n3, n4;

  // MP0 D WRB n3 / MN0 D WR n3 : TG-W（D <-> n3、WR=1 で導通）
  tranif0 MP0 (D, n3, WRB);
  tranif1 MN0 (D, n3, WR);

  // MP1/MN1 : INV1  n3 -> n1
  pmos #(`TP_INV) MP1 (n1, vdd, n3);
  nmos #(`TP_INV) MN1 (n1, vss, n3);

  // MP2/MN2 : INV2  n1 -> n2
  pmos #(`TP_INV) MP2 (n2, vdd, n1);
  nmos #(`TP_INV) MN2 (n2, vss, n1);

  // MP3 n2 WR n3 / MN3 n2 WRB n3 : TG-F（n2 <-> n3、WR=0 で導通＝保持）
  tranif0 MP3 (n2, n3, WR);
  tranif1 MN3 (n2, n3, WRB);

  // MP4/MN4 : INV3  n1 -> n4（読出バッファ）
  pmos #(`TP_INV) MP4 (n4, vdd, n1);
  nmos #(`TP_INV) MN4 (n4, vss, n1);

  // MP5 n4 RDB Q / MN5 n4 RD Q : TG-R（n4 <-> Q、RD=1 で導通）
  tranif0 MP5 (n4, Q, RDB);
  tranif1 MN5 (n4, Q, RD);
endmodule

//----------------------------------------------------------------------------
// DEC2 — 行デコーダ 2 行ぶん（32Tr）
//
//   1 行あたり  RDB = NAND4(A)          ← アクティブロー選択がそのまま RDB
//               RD  = INV(RDB)
//               WR  = NOR2(RDB, WEB)    ← 選択行 かつ WEB=L で書込
//               WRB = INV(WR)
//   E = 偶数行 2k（bit0=0 → AB0）/ O = 奇数行 2k+1（bit0=1 → A0）
//   NMOS 直列は vss 側から A3, A2, A1, A0 の順（レイアウト実測に一致）
//   NOR2 の PMOS 直列は vdd 側から WEB, RDB の順
//----------------------------------------------------------------------------
module DEC2 (input wire A0, input wire AB0, input wire A1, input wire A2,
             input wire A3, input wire WEB,
             output wire WRE, output wire WRBE, output wire RDE, output wire RDBE,
             output wire WRO, output wire WRBO, output wire RDO, output wire RDBO);
  supply1 vdd;
  supply0 vss;
  wire s1_E, s2_E, s3_E, p1_E;
  wire s1_O, s2_O, s3_O, p1_O;

  //---- 行 E（bit0 = 0 なので AB0 を使う）--------------------------------
  pmos #(`TP_INV) MPE0 (RDBE, vdd, AB0);
  pmos #(`TP_INV) MPE1 (RDBE, vdd, A1);
  pmos #(`TP_INV) MPE2 (RDBE, vdd, A2);
  pmos #(`TP_INV) MPE3 (RDBE, vdd, A3);
  nmos #(`TP_INV) MNE0 (s1_E, vss,  A3);
  nmos #(`TP_INV) MNE1 (s2_E, s1_E, A2);
  nmos #(`TP_INV) MNE2 (s3_E, s2_E, A1);
  nmos #(`TP_INV) MNE3 (RDBE, s3_E, AB0);

  pmos #(`TP_INV) MPEA (RDE, vdd, RDBE);
  nmos #(`TP_INV) MNEA (RDE, vss, RDBE);

  pmos #(`TP_INV) MPEB (p1_E, vdd,  WEB);
  pmos #(`TP_INV) MPEC (WRE,  p1_E, RDBE);
  nmos #(`TP_INV) MNEB (WRE,  vss,  RDBE);
  nmos #(`TP_INV) MNEC (WRE,  vss,  WEB);

  pmos #(`TP_INV) MPED (WRBE, vdd, WRE);
  nmos #(`TP_INV) MNED (WRBE, vss, WRE);

  //---- 行 O（bit0 = 1 なので A0 を使う）---------------------------------
  pmos #(`TP_INV) MPO0 (RDBO, vdd, A0);
  pmos #(`TP_INV) MPO1 (RDBO, vdd, A1);
  pmos #(`TP_INV) MPO2 (RDBO, vdd, A2);
  pmos #(`TP_INV) MPO3 (RDBO, vdd, A3);
  nmos #(`TP_INV) MNO0 (s1_O, vss,  A3);
  nmos #(`TP_INV) MNO1 (s2_O, s1_O, A2);
  nmos #(`TP_INV) MNO2 (s3_O, s2_O, A1);
  nmos #(`TP_INV) MNO3 (RDBO, s3_O, A0);

  pmos #(`TP_INV) MPOA (RDO, vdd, RDBO);
  nmos #(`TP_INV) MNOA (RDO, vss, RDBO);

  pmos #(`TP_INV) MPOB (p1_O, vdd,  WEB);
  pmos #(`TP_INV) MPOC (WRO,  p1_O, RDBO);
  nmos #(`TP_INV) MNOB (WRO,  vss,  RDBO);
  nmos #(`TP_INV) MNOC (WRO,  vss,  WEB);

  pmos #(`TP_INV) MPOD (WRBO, vdd, WRO);
  nmos #(`TP_INV) MNOD (WRBO, vss, WRO);
endmodule

//----------------------------------------------------------------------------
// REGBUF — 1bit ぶんのデータバッファ（8T）
//   DD -> D : 書込（外部 -> ビット線）   Q -> QQ : 読出（ビット線 -> 外部）
//   TLAT の D も Q も TG の拡散端子なので、ビット線を駆動するのは必ずこちら側
//----------------------------------------------------------------------------
module REGBUF (input wire DD, output wire D, input wire Q, output wire QQ);
  supply1 vdd;
  supply0 vss;
  wire w1, r1;

  pmos #(`TP_INV) MP0 (w1, vdd, DD);
  nmos #(`TP_INV) MN0 (w1, vss, DD);
  pmos #(`TP_INV) MP1 (D,  vdd, w1);
  nmos #(`TP_INV) MN1 (D,  vss, w1);

  pmos #(`TP_INV) MP2 (r1, vdd, Q);
  nmos #(`TP_INV) MN2 (r1, vss, Q);
  pmos #(`TP_INV) MP3 (QQ, vdd, r1);
  nmos #(`TP_INV) MN3 (QQ, vss, r1);
endmodule

//----------------------------------------------------------------------------
// ADDBUF — アドレス相補生成 + WE バッファ（20T）
//   ABk = INV(Ak_PIN) / Ak = INV(ABk)   -> 真・補のスキューを INV 1 段に固定
//   wt  = INV(WEB_PIN) / WEB = INV(wt)  -> バッファ 2 段
//----------------------------------------------------------------------------
module ADDBUF (input wire A0_PIN, input wire A1_PIN, input wire A2_PIN,
               input wire A3_PIN, input wire WEB_PIN,
               output wire A0, output wire AB0, output wire A1, output wire AB1,
               output wire A2, output wire AB2, output wire A3, output wire AB3,
               output wire WEB);
  supply1 vdd;
  supply0 vss;
  wire wt;

  pmos #(`TP_INV) MP0 (AB0, vdd, A0_PIN);  nmos #(`TP_INV) MN0 (AB0, vss, A0_PIN);
  pmos #(`TP_INV) MP1 (A0,  vdd, AB0);     nmos #(`TP_INV) MN1 (A0,  vss, AB0);
  pmos #(`TP_INV) MP2 (AB1, vdd, A1_PIN);  nmos #(`TP_INV) MN2 (AB1, vss, A1_PIN);
  pmos #(`TP_INV) MP3 (A1,  vdd, AB1);     nmos #(`TP_INV) MN3 (A1,  vss, AB1);
  pmos #(`TP_INV) MP4 (AB2, vdd, A2_PIN);  nmos #(`TP_INV) MN4 (AB2, vss, A2_PIN);
  pmos #(`TP_INV) MP5 (A2,  vdd, AB2);     nmos #(`TP_INV) MN5 (A2,  vss, AB2);
  pmos #(`TP_INV) MP6 (AB3, vdd, A3_PIN);  nmos #(`TP_INV) MN6 (AB3, vss, A3_PIN);
  pmos #(`TP_INV) MP7 (A3,  vdd, AB3);     nmos #(`TP_INV) MN7 (A3,  vss, AB3);
  pmos #(`TP_INV) MP8 (wt,  vdd, WEB_PIN); nmos #(`TP_INV) MN8 (wt,  vss, WEB_PIN);
  pmos #(`TP_INV) MP9 (WEB, vdd, wt);      nmos #(`TP_INV) MN9 (WEB, vss, wt);
endmodule

//----------------------------------------------------------------------------
// REGX16 — トップ（ビット幅 BITS でパラメータ化）
//   ADD[3:0]       アドレス（ブロック内で相補を作る）
//   WEB            書込イネーブル（アクティブロー）
//   D[BITS-1:0]    書込データ入力   Q[BITS-1:0] 読出データ出力
//
//   ADD で選んだ 1 行が常に読み出される（非同期読出）。
//   WEB=0 の間、その行に D が書き込まれる（レベル書込・ラッチ）。
//
//   デコーダ DEC2 x8 はビット幅に依存しない（4->16 なので 1 組で足りる）。
//   増えるのは TLAT の列と REGBUF だけ。レイアウトもこの関係のまま。
//----------------------------------------------------------------------------
module REGX16 #(parameter integer BITS = 4)
               (input wire [3:0] ADD, input wire WEB,
                input wire [BITS-1:0] D, output wire [BITS-1:0] Q);

  wire a0, ab0, a1, ab1, a2, ab2, a3, ab3, webi;

  ADDBUF U_ADDBUF (.A0_PIN(ADD[0]), .A1_PIN(ADD[1]), .A2_PIN(ADD[2]),
                   .A3_PIN(ADD[3]), .WEB_PIN(WEB),
                   .A0(a0), .AB0(ab0), .A1(a1), .AB1(ab1),
                   .A2(a2), .AB2(ab2), .A3(a3), .AB3(ab3), .WEB(webi));

  // {真, 補} を並べて、bit が 1 なら真・0 なら補を選ぶ（定数選択なので論理は増えない）
  wire [1:0] sel1 = {a1, ab1};
  wire [1:0] sel2 = {a2, ab2};
  wire [1:0] sel3 = {a3, ab3};

  wire [15:0] wr, wrb, rd, rdb;   // ワードライン
  wire [BITS-1:0] dl, ql;         // ビット線（dl=書込, ql=読出）

  genvar k, i, j;
  generate
    //---- 行デコーダ DEC2 x8（1 個で 2 行、bit1..3 は 2 行で共有）--------
    for (k = 0; k < 8; k = k + 1) begin : G_DEC
      DEC2 U (.A0(a0), .AB0(ab0),
              .A1(sel1[(k >> 0) & 1]),
              .A2(sel2[(k >> 1) & 1]),
              .A3(sel3[(k >> 2) & 1]),
              .WEB(webi),
              .WRE (wr [2*k  ]), .WRBE(wrb[2*k  ]),
              .RDE (rd [2*k  ]), .RDBE(rdb[2*k  ]),
              .WRO (wr [2*k+1]), .WRBO(wrb[2*k+1]),
              .RDO (rd [2*k+1]), .RDBO(rdb[2*k+1]));
    end

    //---- ビットセル 16 x BITS -------------------------------------------
    for (i = 0; i < 16; i = i + 1) begin : G_ROW
      for (j = 0; j < BITS; j = j + 1) begin : G_BIT
        TLAT U (.WR(wr[i]), .WRB(wrb[i]), .RD(rd[i]), .RDB(rdb[i]),
                .D(dl[j]), .Q(ql[j]));
      end
    end

    //---- データバッファ x BITS ------------------------------------------
    for (j = 0; j < BITS; j = j + 1) begin : G_BUF
      REGBUF U (.DD(D[j]), .D(dl[j]), .Q(ql[j]), .QQ(Q[j]));
    end
  endgenerate
endmodule

//----------------------------------------------------------------------------
// 実際のマクロ名のラッパ（LVS ソースの .subckt と 1:1）
//----------------------------------------------------------------------------
module REG4x16 (input wire [3:0] ADD, input wire WEB,
                input wire [3:0] D, output wire [3:0] Q);
  REGX16 #(.BITS(4)) U (.ADD(ADD), .WEB(WEB), .D(D), .Q(Q));
endmodule

module REG8x16 (input wire [3:0] ADD, input wire WEB,
                input wire [7:0] D, output wire [7:0] Q);
  REGX16 #(.BITS(8)) U (.ADD(ADD), .WEB(WEB), .D(D), .Q(Q));
endmodule

`default_nettype wire

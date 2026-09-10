//============================================================================
//  tb_reg4x16.v — REG4x16 の全レジスタアクセス検証テストベンチ
//
//  目的: hdl/rtl/reg4x16.v（= LVS ソースネットリストの 1:1 書き起こし）で
//        16 word x 4 bit の全ビットが正しく書けて読めることを確認する。
//
//  検証項目
//    T1 全ワード書込 → 全ワード読出          （アドレスごとに違う値・順/逆順）
//    T2 ウォーキング 1 / ウォーキング 0       （4 本のビット線が独立か）
//    T3 デコーダの一意性                      （1 ワード書換で他 15 語が不変か）
//    T4 WEB 極性                              （WEB=1 では書けない）
//    T5 保持                                  （全書込後にアドレス順でなく読み直す）
//    読出のたびに次も検査する:
//      ・Q に X/Z が無いこと（=== 比較）
//      ・RD ワードラインがちょうど 1 本だけ立っていること
//    さらに WR が同時に 2 本以上立たないことを常時監視する（多重書込の検出）
//
//    I1 参考情報: アドレス確定前に WEB を落とすとどうなるか（合否には数えない）
//
//  実行:  iverilog -g2012 -o sim_reg4x16 hdl/rtl/reg4x16.v hdl/tb/tb_reg4x16.v
//         vvp sim_reg4x16
//    波形: iverilog -g2012 -DDUMP ... ; vvp sim_reg4x16   -> reg4x16.vcd
//============================================================================
`timescale 1ns / 1ps

module tb_reg4x16;

  localparam integer T  = 20;   // 1 ステップ（INV 遅延 1ns に対して十分長く）
  localparam integer NW = 16;   // ワード数
  localparam integer NB = 4;    // ビット幅

  reg  [3:0] add = 4'd0;
  reg  [3:0] din = 4'd0;
  reg        web = 1'b1;        // アクティブロー。既定は書込禁止
  wire [3:0] q;

  integer pass = 0, fail = 0, wrmulti = 0;
  integer i, j, k, n, m, w, cnt;
  reg [3:0] shadow [0:NW-1];    // 期待値モデル
  reg [3:0] exp, got;
  reg       running = 1'b0;

  REG4x16 dut (.ADD(add), .WEB(web), .D(din), .Q(q));

  //--------------------------------------------------------------------------
  // 基本操作
  //   書込: アドレスとデータを確定させてから WEB を落とす。
  //         ADDB は INV 1 段ぶん遅れるので、アドレス変化中に WEB=0 だと
  //         2 行が同時選択され得る。必ずこの順序で。
  //--------------------------------------------------------------------------
  task wr (input [3:0] a, input [3:0] d);
    begin
      add = a;  din = d;  #T;      // アドレス・データ確定
      web = 1'b0;         #T;      // 書込（レベル）
      web = 1'b1;         #T;      // 閉じる
      shadow[a] = d;
    end
  endtask

  task rd_chk (input [3:0] a, input [3:0] e, input [8*16-1:0] tag);
    begin
      add = a;  #T;                // 落ち着かせてからサンプル
      got = q;
      if (got === e) pass = pass + 1;
      else begin
        fail = fail + 1;
        $display("  ** FAIL %0s : ADD=%0d  expect %b  got %b  (t=%0t)",
                 tag, a, e, got, $time);
      end
      // ワードラインがちょうど 1 本だけ立っているか
      cnt = 0;
      for (w = 0; w < NW; w = w + 1) if (dut.rd[w] === 1'b1) cnt = cnt + 1;
      if (cnt != 1) begin
        fail = fail + 1;
        $display("  ** FAIL %0s : RD が %0d 本 (期待 1) ADD=%0d rd=%b (t=%0t)",
                 tag, cnt, a, dut.rd, $time);
      end else pass = pass + 1;
    end
  endtask

  task chk_all (input [8*16-1:0] tag);
    begin
      for (m = 0; m < NW; m = m + 1) rd_chk(m[3:0], shadow[m], tag);
    end
  endtask

  //--------------------------------------------------------------------------
  initial begin
`ifdef DUMP
    $dumpfile("reg4x16.vcd");
    $dumpvars(0, tb_reg4x16);
`endif
    $display("========================================================");
    $display(" REG4x16  全レジスタアクセス検証  (%0d word x %0d bit)", NW, NB);
    $display("========================================================");

    #(2*T);
    running = 1'b1;

    //---- T1: 全ワードに異なる値を書いて全部読む --------------------------
    $display("--- T1 全ワード書込/読出");
    for (i = 0; i < NW; i = i + 1) wr(i[3:0], i[3:0] ^ 4'b1010);   // 値と番地を違える
    chk_all("T1 readback");
    for (i = NW-1; i >= 0; i = i - 1) rd_chk(i[3:0], shadow[i], "T1 reverse");

    //---- T2: ウォーキング 1 / 0（ビット線の独立性）------------------------
    $display("--- T2 ウォーキング1/0");
    for (i = 0; i < NW; i = i + 1) begin
      for (j = 0; j < NB; j = j + 1) begin
        wr(i[3:0], 4'b0001 << j);
        rd_chk(i[3:0], 4'b0001 << j, "T2 walk1");
        wr(i[3:0], ~(4'b0001 << j));
        rd_chk(i[3:0], ~(4'b0001 << j), "T2 walk0");
      end
    end

    //---- T3: デコーダの一意性 -------------------------------------------
    //   全ワードを 0101 で埋め、1 ワードだけ 1010 に書き換えて
    //   「そのワードだけ」が変わることを 16 通りすべてで確認する。
    //   多重選択・デコード漏れ・ワードライン短絡はここで落ちる。
    $display("--- T3 デコーダ一意性");
    for (k = 0; k < NW; k = k + 1) begin
      for (i = 0; i < NW; i = i + 1) wr(i[3:0], 4'b0101);
      wr(k[3:0], 4'b1010);
      for (i = 0; i < NW; i = i + 1) begin
        exp = (i == k) ? 4'b1010 : 4'b0101;
        rd_chk(i[3:0], exp, "T3 unique");
      end
    end

    //---- T4: WEB 極性（WEB=1 では書けない）------------------------------
    $display("--- T4 WEB 極性");
    for (i = 0; i < NW; i = i + 1) wr(i[3:0], 4'b1100);
    for (i = 0; i < NW; i = i + 1) begin
      add = i[3:0];  din = 4'b0011;  web = 1'b1;  #(3*T);   // WEB を落とさない
    end
    din = 4'b0000;
    for (i = 0; i < NW; i = i + 1) rd_chk(i[3:0], 4'b1100, "T4 no-write");
    for (i = 0; i < NW; i = i + 1) wr(i[3:0], 4'b0011);      // 落とせば書ける
    chk_all("T4 write-ok");

    //---- T5: 保持（全書込後にアドレス順でなく読み直す）--------------------
    $display("--- T5 保持");
    for (i = 0; i < NW; i = i + 1) wr(i[3:0], (i*7 + 3) & 4'hF);
    n = 0;
    for (k = 0; k < 4*NW; k = k + 1) begin
      n = (n * 5 + 11) % NW;
      rd_chk(n[3:0], shadow[n], "T5 hold");
    end

    //---- 合否 -----------------------------------------------------------
    running = 1'b0;
    $display("========================================================");
    $display(" PASS %0d / FAIL %0d      WR 多重アサート %0d 回", pass, fail, wrmulti);
    if (fail == 0 && wrmulti == 0)
      $display(" 結果: 全項目 PASS — 16 word x 4 bit すべて正しくアクセスできる");
    else
      $display(" 結果: 不一致あり");
    $display("========================================================");

    //---- I1: 参考情報（合否には数えない）--------------------------------
    //   アドレスを変えると同時に WEB を落とすと何が起きるか。
    //   ADDB は INV 1 段ぶん遅れるので、切替の瞬間に 2 行が選ばれ得る。
    $display("");
    $display("--- I1 [参考] アドレスと WEB のタイミング");

    // (a) アドレスと WEB を同時に動かす
    for (i = 0; i < NW; i = i + 1) wr(i[3:0], 4'b0000);
    add = 4'd0;  din = 4'b1111;  web = 1'b1;  #T;
    add = 4'd15; web = 1'b0;                  #T;   // 同時
    web = 1'b1;                               #T;
    cnt = 0;
    for (i = 0; i < NW; i = i + 1) begin
      add = i[3:0]; #T;
      if (q !== 4'b0000) begin cnt = cnt + 1; $display("    (a) ADD=%0d が %b に変化", i, q); end
    end
    $display("    (a) アドレスと WEB を同時に動かす -> 書き換わったのは %0d ワード", cnt);
    if (cnt == 1)
      $display("        WE バッファが INV 2 段、アドレス補が INV 1 段なので、"
             , "WEB が効く頃にはアドレスが確定している。構造的に安全。");

    // (b) WEB を落としたままアドレスを変える（違反した使い方）
    for (i = 0; i < NW; i = i + 1) wr(i[3:0], 4'b0000);
    add = 4'd0;  din = 4'b1111;  #T;
    web = 1'b0;  #T;              // 書込を開いたまま…
    add = 4'd15; #T;              // …アドレスを動かす
    web = 1'b1;  #T;
    cnt = 0;
    for (i = 0; i < NW; i = i + 1) begin
      add = i[3:0]; #T;
      if (q !== 4'b0000) begin cnt = cnt + 1; $display("    (b) ADD=%0d が %b に変化", i, q); end
    end
    $display("    (b) WEB=0 のままアドレスを動かす -> 書き換わったのは %0d ワード", cnt);
    $display("        レベル書込なので、開いている間に通過したワードは全部書かれる。");
    $display("        アドレスを確定させてから WEB を落とし、WEB を上げてから次のアドレスへ。");
    $display("       （設計上の制約であって不良ではない。spice/README.md の SPICE 検証項目 4 を参照）");

    if (fail != 0 || wrmulti != 0) $fatal(1);
    $finish;
  end

  //--------------------------------------------------------------------------
  // WR ワードラインの多重アサート監視
  //   WR が同時に 2 本以上立つと 2 行に同じデータが書かれる = 実害のある不良。
  //   （RD の一瞬の多重選択はアドレス切替中の過渡で、WEB=1 なら無害なので
  //     ここでは見ない。読出時の RD 本数は rd_chk で毎回チェックしている。）
  //--------------------------------------------------------------------------
  always @(dut.wr) begin
    if (running) begin
      cnt = 0;
      for (w = 0; w < NW; w = w + 1) if (dut.wr[w] === 1'b1) cnt = cnt + 1;
      if (cnt > 1) begin
        wrmulti = wrmulti + 1;
        if (wrmulti <= 5)
          $display("  ** WR 多重アサート %0d 本: wr=%b (t=%0t)", cnt, dut.wr, $time);
      end
    end
  end

  initial begin
    #(20_000_000);
    $display("** タイムアウト");
    $fatal(1);
  end

endmodule

`timescale 1ns/1ps
// Load モードでプログラムを書き込み、Exec モードで走らせる一連の流れを検証する。
module tb_td4_soc_arr;
  reg clk=0, rst_n=0, exec=0, wr=0, nibsel=0;
  reg [3:0] d=4'h0;
  wire [3:0] out_port; wire cflag;
  integer errors = 0, i;

  td4_soc_arr dut(.clk(clk),.rst_n(rst_n),.exec(exec),.wr(wr),.nibsel(nibsel),
                  .d(d),.out_port(out_port),.cflag_o(cflag));
  always #5 clk = ~clk;

  // 1命令 = 下位ニブル(即値) → 上位ニブル(オペコード) の2回書込
  task load(input [7:0] instr);
    begin
      @(negedge clk); nibsel=1'b0; d=instr[3:0]; wr=1'b1; @(posedge clk); #1;
      @(negedge clk); nibsel=1'b1; d=instr[7:4]; wr=1'b1; @(posedge clk); #1;
      @(negedge clk); wr=1'b0;
    end
  endtask

  task chk(input [4:0] got, input [4:0] exp);
    begin
      if (got !== exp) begin $display("FAIL OUT: got %0d exp %0d", got, exp); errors=errors+1; end
      else $display("ok   OUT = %0d", got);
    end
  endtask

  // 期待する OUT の並び（LED フラッシャ）
  reg [3:0] expect_seq [0:3];

  initial begin
    expect_seq[0]=4'd3; expect_seq[1]=4'd6; expect_seq[2]=4'd12; expect_seq[3]=4'd8;

    @(negedge clk); rst_n = 1'b1; @(negedge clk);

    // ---- Load モード ----
    load(8'b1011_0011); // 0: OUT 3
    load(8'b1011_0110); // 1: OUT 6
    load(8'b1011_1100); // 2: OUT 12
    load(8'b1011_1000); // 3: OUT 8
    load(8'b1111_0000); // 4: JMP 0
    $display("-- loaded 5 instructions, ld_addr = %0d", dut.ld_addr);
    if (dut.ld_addr !== 4'd5) begin $display("FAIL ld_addr"); errors=errors+1; end

    // ---- Exec モード ----
    @(negedge clk); exec = 1'b1;
    for (i = 0; i < 8; i = i + 1) begin
      @(posedge clk); #1;
      chk(out_port, expect_seq[i % 4]);   // OUT 4命令 + JMP で 4周期ごとに一巡…
      if (i % 4 == 3) @(posedge clk);     // JMP 0 の1サイクルを読み飛ばす
      #1;
    end

    if (errors == 0) $display("\n=== td4_soc_arr LOAD+EXEC TEST PASSED ===");
    else             $display("\n=== %0d FAILURES ===", errors);
    $finish;
  end
endmodule

`timescale 1ns/1ps
// tb_td4_soc_arr_isa.v -- TD4 全 12 命令トレース（Verilog 版）
// scripts/gen_irsim_td4.py が生成。手で編集しないこと。
// irsim/td4_soc_arr.cmd と同じプログラム・同じ期待値（U14）。
module tb_td4_soc_arr_isa;
  reg clk=0, rst_n=0, exec=0, wr=0, nibsel=0;
  reg [3:0] d=4'h0;
  wire [3:0] out_port; wire cflag;
  integer errors = 0;

  td4_soc_arr dut(.clk(clk),.rst_n(rst_n),.exec(exec),.wr(wr),.nibsel(nibsel),
                  .d(d),.out_port(out_port),.cflag_o(cflag));
  always #5 clk = ~clk;

  task load(input [7:0] instr);
    begin
      @(negedge clk); nibsel=1'b0; d=instr[3:0]; wr=1'b1; @(posedge clk);
      @(negedge clk); nibsel=1'b1; d=instr[7:4];          @(posedge clk);
    end
  endtask

  task chk(input [80*8-1:0] name, input [4:0] got, input [4:0] exp);
    begin
      if (got !== exp) begin
        $display("FAIL %0s: got %0d exp %0d", name, got, exp);
        errors = errors + 1;
      end
    end
  endtask

  task cyc(input [80*8-1:0] tag, input [3:0] ea, input [3:0] eb,
           input [3:0] eo, input ec);
    begin
      @(posedge clk); #1;
      chk({tag,"_A"},   dut.u_core.reg_a, ea);
      chk({tag,"_B"},   dut.u_core.reg_b, eb);
      chk({tag,"_OUT"}, out_port,         eo);
      chk({tag,"_C"},   cflag,            ec);
    end
  endtask

  initial begin
    // ---------------- P1 ----------------
    @(negedge clk); rst_n = 1'b0; exec = 1'b0; wr = 1'b0;
    @(posedge clk); @(negedge clk); rst_n = 1'b1;
    load(8'b0011_0101);  //  0: MOV A,Im 5
    load(8'b0000_0011);  //  1: ADD A,Im 3
    load(8'b0000_1001);  //  2: ADD A,Im 9
    load(8'b1110_0000);  //  3: JNC 0
    load(8'b0100_0000);  //  4: MOV B,A
    load(8'b0111_1001);  //  5: MOV B,Im 9
    load(8'b0001_0000);  //  6: MOV A,B
    load(8'b0010_0000);  //  7: IN A
    load(8'b0110_0000);  //  8: IN B
    load(8'b1001_0000);  //  9: OUT B
    load(8'b1011_0110);  // 10: OUT Im 6
    load(8'b0101_0110);  // 11: ADD B,Im 6
    load(8'b1110_1110);  // 12: JNC 14
    load(8'b1110_1111);  // 13: JNC 15
    load(8'b1011_1111);  // 14: OUT Im 15
    load(8'b0011_0111);  // 15: MOV A,Im 7
    @(negedge clk); wr = 1'b0;
    d = 4'b1010; exec = 1'b1;
    cyc("P1_00", 4'b0101, 4'b0000, 4'b0000, 1'b0);  // MOV A,Im 5
    cyc("P1_01", 4'b1000, 4'b0000, 4'b0000, 1'b0);  // ADD A,Im 3
    cyc("P1_02", 4'b0001, 4'b0000, 4'b0000, 1'b1);  // ADD A,Im 9
    cyc("P1_03", 4'b0001, 4'b0000, 4'b0000, 1'b0);  // JNC 0
    cyc("P1_04", 4'b0001, 4'b0001, 4'b0000, 1'b0);  // MOV B,A
    cyc("P1_05", 4'b0001, 4'b1001, 4'b0000, 1'b0);  // MOV B,Im 9
    cyc("P1_06", 4'b1001, 4'b1001, 4'b0000, 1'b0);  // MOV A,B
    cyc("P1_07", 4'b1010, 4'b1001, 4'b0000, 1'b0);  // IN A
    cyc("P1_08", 4'b1010, 4'b1010, 4'b0000, 1'b0);  // IN B
    cyc("P1_09", 4'b1010, 4'b1010, 4'b1010, 1'b0);  // OUT B
    cyc("P1_10", 4'b1010, 4'b1010, 4'b0110, 1'b0);  // OUT Im 6
    cyc("P1_11", 4'b1010, 4'b0000, 4'b0110, 1'b1);  // ADD B,Im 6
    cyc("P1_12", 4'b1010, 4'b0000, 4'b0110, 1'b0);  // JNC 14
    cyc("P1_13", 4'b1010, 4'b0000, 4'b0110, 1'b0);  // JNC 15
    cyc("P1_14", 4'b0111, 4'b0000, 4'b0110, 1'b0);  // MOV A,Im 7
    cyc("P1_15", 4'b0101, 4'b0000, 4'b0110, 1'b0);  // MOV A,Im 5
    @(negedge clk); exec = 1'b0;

    // ---------------- P2 ----------------
    @(negedge clk); rst_n = 1'b0; exec = 1'b0; wr = 1'b0;
    @(posedge clk); @(negedge clk); rst_n = 1'b1;
    load(8'b1111_0010);  //  0: JMP 2
    load(8'b1011_1111);  //  1: OUT Im 15
    load(8'b1011_0011);  //  2: OUT Im 3
    load(8'b1111_0011);  //  3: JMP 3
    @(negedge clk); wr = 1'b0;
    d = 4'b1010; exec = 1'b1;
    cyc("P2_00", 4'b0000, 4'b0000, 4'b0000, 1'b0);  // JMP 2
    cyc("P2_01", 4'b0000, 4'b0000, 4'b0011, 1'b0);  // OUT Im 3
    cyc("P2_02", 4'b0000, 4'b0000, 4'b0011, 1'b0);  // JMP 3
    cyc("P2_03", 4'b0000, 4'b0000, 4'b0011, 1'b0);  // JMP 3
    cyc("P2_04", 4'b0000, 4'b0000, 4'b0011, 1'b0);  // JMP 3
    @(negedge clk); exec = 1'b0;

    if (errors == 0)
      $display("\n=== TD4 ISA TRACE PASSED (21 cycles) ===");
    else $display("\n=== %0d FAILURES ===", errors);
    $finish;
  end
endmodule

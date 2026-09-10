`timescale 1ns/1ps
module tb_td4_core;
  reg clk=0, rst_n=0, en=1;
  reg [3:0] in_port=4'h0;
  reg [7:0] rom_data=8'h00;
  wire [3:0] rom_addr, out_port; wire cflag;
  integer errors = 0;

  td4_core dut(.clk(clk),.rst_n(rst_n),.en(en),.in_port(in_port),
               .rom_data(rom_data),.rom_addr(rom_addr),.out_port(out_port),.cflag_o(cflag));
  always #5 clk = ~clk;

  task step(input [7:0] instr);
    begin rom_data = instr; @(posedge clk); #1; end
  endtask
  task chk(input [63:0] name, input [4:0] got, input [4:0] exp);
    begin
      if (got !== exp) begin
        $display("FAIL %0s: got %0d exp %0d", name, got, exp); errors = errors + 1;
      end else $display("ok   %0s = %0d", name, got);
    end
  endtask

  initial begin
    @(negedge clk); rst_n = 1;
    // MOV A,Im (0011) : A <= 5
    step(8'b0011_0101); chk("MOV A,Im", dut.reg_a, 5);
    // ADD A,Im (0000) : A <= 5+3 = 8, C=0
    step(8'b0000_0011); chk("ADD A,Im", dut.reg_a, 8); chk("C after add", dut.cflag, 0);
    // ADD A,Im : 8+9 = 17 -> A=1, C=1
    step(8'b0000_1001); chk("ADD carry", dut.reg_a, 1); chk("C=1", dut.cflag, 1);
    // MOV B,A (0100) : B <= A = 1
    step(8'b0100_0000); chk("MOV B,A", dut.reg_b, 1);
    // MOV A,B (0001) : A <= B = 1  (first set B to 9)
    step(8'b0111_1001); chk("MOV B,Im", dut.reg_b, 9);
    step(8'b0001_0000); chk("MOV A,B", dut.reg_a, 9);
    // IN A (0010) / IN B (0110)
    in_port = 4'hA;
    step(8'b0010_0000); chk("IN A", dut.reg_a, 10);
    step(8'b0110_0000); chk("IN B", dut.reg_b, 10);
    // OUT B (1001) / OUT Im (1011)
    step(8'b1001_0000); chk("OUT B", out_port, 10);
    step(8'b1011_0110); chk("OUT Im", out_port, 6);
    // ADD B,Im (0101) : B = 10+6 = 16 -> 0, C=1
    step(8'b0101_0110); chk("ADD B,Im", dut.reg_b, 0); chk("C=1", dut.cflag, 1);
    // JNC with C=1 -> not taken
    begin : jnc_nt
      reg [3:0] pc0; pc0 = rom_addr;
      step(8'b1110_0000); chk("JNC not taken", rom_addr, pc0 + 1);
    end
    // clear carry via ADD A,0 then JNC taken
    step(8'b0000_0000);
    step(8'b1110_0011); chk("JNC taken", rom_addr, 3);
    // JMP
    step(8'b1111_1100); chk("JMP", rom_addr, 12);
    // PC wrap 15 -> 0
    step(8'b1111_1111); chk("JMP 15", rom_addr, 15);
    step(8'b0011_0000); chk("PC wrap", rom_addr, 0);

    if (errors == 0) $display("\n=== ALL TD4 INSTRUCTION TESTS PASSED ===");
    else             $display("\n=== %0d FAILURES ===", errors);
    $finish;
  end
endmodule

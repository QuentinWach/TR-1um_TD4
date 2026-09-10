// TD4 core (CPU only, external program memory) - for TR-1um area estimation
// Architecture per "CPUの創りかた" (渡波郁):
//   A/B/OUT 4bit regs, 4bit PC, 1bit C flag, one 4bit adder, one 4-input selector.
//   Single cycle (CPI = 1). op[3:2] = load destination, op[1:0] = selector source.
`default_nettype none

module td4_core (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       en,        // 1 = execute
    input  wire [3:0] in_port,
    input  wire [7:0] rom_data,  // {op[3:0], im[3:0]}
    output wire [3:0] rom_addr,  // = PC
    output wire [3:0] out_port,
    output wire       cflag_o
);
  reg [3:0] reg_a, reg_b, reg_out, pc;
  reg       cflag;

  wire [3:0] op = rom_data[7:4];
  wire [3:0] im = rom_data[3:0];

  // load destination decode: 00->A 01->B 10->OUT 11->PC
  wire dst_pc = (op[3:2] == 2'b11);
  wire ld_a   = (op[3:2] == 2'b00);
  wire ld_b   = (op[3:2] == 2'b01);
  wire ld_out = (op[3:2] == 2'b10);

  // selector: 00->A 01->B 10->IN 11->0 ; forced to 0 for the PC (jump) group
  wire [1:0] ssel = dst_pc ? 2'b11 : op[1:0];
  wire [3:0] sdat = (ssel == 2'b00) ? reg_a   :
                    (ssel == 2'b01) ? reg_b   :
                    (ssel == 2'b10) ? in_port : 4'b0000;

  // single 4bit adder (74HC283 equivalent)
  wire [4:0] sum = {1'b0, sdat} + {1'b0, im};

  // JMP = op[0]=1 unconditional, JNC = op[0]=0 taken when C = 0
  wire jump = dst_pc & (op[0] | ~cflag);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      reg_a <= 4'b0; reg_b <= 4'b0; reg_out <= 4'b0; pc <= 4'b0; cflag <= 1'b0;
    end else if (en) begin
      if (ld_a)   reg_a   <= sum[3:0];
      if (ld_b)   reg_b   <= sum[3:0];
      if (ld_out) reg_out <= sum[3:0];
      cflag <= sum[4];                       // C is reloaded every cycle
      pc    <= jump ? sum[3:0] : pc + 4'd1;
    end
  end

  assign rom_addr = pc;
  assign out_port = reg_out;
  assign cflag_o  = cflag;
endmodule

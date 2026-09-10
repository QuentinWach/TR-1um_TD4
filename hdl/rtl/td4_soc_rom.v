// TD4 SoC with a MASK ROM (fixed 16x8 program, combinational) - smallest variant.
// Program = the book's "ラーメンタイマー" style loop (placeholder pattern).
`default_nettype none

module td4_soc_rom (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] in_port,
    output wire [3:0] out_port,
    output wire [3:0] pc_o,
    output wire       cflag_o
);
  wire [3:0] pc;
  reg  [7:0] rom_data;

  always @* begin
    case (pc)
      4'h0: rom_data = 8'b1011_0111; // OUT 0111
      4'h1: rom_data = 8'b0000_0001; // ADD A,0001
      4'h2: rom_data = 8'b1110_0001; // JNC 0001
      4'h3: rom_data = 8'b0000_0001;
      4'h4: rom_data = 8'b1110_0011;
      4'h5: rom_data = 8'b1011_0110;
      4'h6: rom_data = 8'b0000_0001;
      4'h7: rom_data = 8'b1110_0110;
      4'h8: rom_data = 8'b0000_0001;
      4'h9: rom_data = 8'b1110_1000;
      4'hA: rom_data = 8'b1011_0000;
      4'hB: rom_data = 8'b1011_0100;
      4'hC: rom_data = 8'b0000_0001;
      4'hD: rom_data = 8'b1110_1100;
      4'hE: rom_data = 8'b1011_1000;
      4'hF: rom_data = 8'b1111_0000; // JMP 0000
    endcase
  end

  td4_core u_core (
      .clk(clk), .rst_n(rst_n), .en(1'b1), .in_port(in_port),
      .rom_data(rom_data), .rom_addr(pc), .out_port(out_port), .cflag_o(cflag_o)
  );
  assign pc_o = pc;
endmodule

// TD4 SoC: core + on-chip 16word x 8bit writable program memory built from FFs
// (this is what tt-td4 / TinyTapeout does). Pin-count friendly for a 14-signal frame.
`default_nettype none

module td4_soc_ff (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       exec,      // 0 = program load mode, 1 = run
    input  wire       wr,        // program write strobe (load mode)
    input  wire [3:0] din,       // load mode: instruction nibble / run mode: input port
    input  wire       nibsel,    // load mode: 0 = write low nibble, 1 = write high nibble
    output wire [3:0] out_port,
    output wire [3:0] pc_o,
    output wire       cflag_o
);
  reg [7:0] mem [0:15];
  reg [3:0] ld_addr;
  integer i;

  wire [3:0] pc;
  wire [7:0] rom_data = mem[exec ? pc : ld_addr];

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      ld_addr <= 4'b0;
      for (i = 0; i < 16; i = i + 1) mem[i] <= 8'b0;
    end else if (!exec && wr) begin
      if (nibsel) mem[ld_addr][7:4] <= din;
      else        mem[ld_addr][3:0] <= din;
      if (nibsel) ld_addr <= ld_addr + 4'd1;
    end
  end

  td4_core u_core (
      .clk      (clk),
      .rst_n    (rst_n),
      .en       (exec),
      .in_port  (din),
      .rom_data (rom_data),
      .rom_addr (pc),
      .out_port (out_port),
      .cflag_o  (cflag_o)
  );
  assign pc_o = pc;
endmodule

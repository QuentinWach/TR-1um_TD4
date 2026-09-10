// td4_soc_arr — TD4 コア + td4_mem（カスタム RFCELL アレイに差し替え可能な命令メモリ）
//
// プログラム書き込みは 4bit ずつ 2回で 1命令。下位ニブルはステージングレジスタに
// 溜め、上位ニブルが来たタイミングで **8bit 一括ライト**する。
// → メモリのワードライン制御がニブル単位でなくワード単位で済み、
//   アレイ周辺回路が半分になる（reference/07_memory_array.md §3）。
`default_nettype none

module td4_soc_arr (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       exec,    // 0 = Load モード, 1 = Exec モード
    input  wire       wr,      // Load モード: 書込ストローブ
    input  wire       nibsel,  // Load モード: 0 = 下位(即値) / 1 = 上位(オペコード)
    input  wire [3:0] d,       // Load: 命令ニブル / Exec: 入力ポート
    output wire [3:0] out_port,
    output wire       cflag_o
);
  wire [3:0] pc;
  wire [7:0] rom_data;

  // --- プログラム書き込み側 -------------------------------------------------
  reg [3:0] ld_addr;      // 書込アドレス（上位ニブル書込で +1）
  reg [3:0] nib_lo;       // 下位ニブルのステージング

  wire wr_lo = ~exec & wr & ~nibsel;
  wire wr_hi = ~exec & wr &  nibsel;   // このとき 8bit 一括ライト

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      ld_addr <= 4'b0;
      nib_lo  <= 4'b0;
    end else begin
      if (wr_lo) nib_lo  <= d;
      if (wr_hi) ld_addr <= ld_addr + 4'd1;
    end
  end

  // --- 命令メモリ -----------------------------------------------------------
  td4_mem u_mem (
      .clk   (clk),
      .raddr (exec ? pc : ld_addr),
      .rdata (rom_data),
      .waddr (ld_addr),
      .wdata ({d, nib_lo}),   // {オペコード, 即値}
      .we    (wr_hi)
  );

  // --- コア -----------------------------------------------------------------
  td4_core u_core (
      .clk(clk), .rst_n(rst_n), .en(exec), .in_port(d),
      .rom_data(rom_data), .rom_addr(pc), .out_port(out_port), .cflag_o(cflag_o)
  );
endmodule

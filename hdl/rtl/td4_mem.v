// td4_mem — 16 word x 8 bit 命令メモリ
//
//   * 非同期リード 1ポート（raddr -> rdata）: TD4 は CPI=1 なので PC から
//     組合せで命令が出ている必要がある。
//   * 同期ライト 1ポート（8bit 一括）。リードとライトは同時に起きない
//     （EXEC=1 のとき書かない）ので実体は 1ポート時分割でよい。
//   * **リセットを持たない。** プログラムは実行前に必ず書き込むので初期値不要。
//     カスタムアレイ化するときセルごとのクリアTrを省ける。
//
// 合成時はこのビヘイビア記述（FF 実装）、実装時はカスタム RFCELL アレイに差し替える。
// アレイ版の具体設計は reference/07_memory_array.md を参照。
`default_nettype none

(* td4_blackbox_candidate *)
module td4_mem (
    input  wire       clk,
    input  wire [3:0] raddr,
    output wire [7:0] rdata,
    input  wire [3:0] waddr,
    input  wire [7:0] wdata,
    input  wire       we
);
  reg [7:0] mem [0:15];

  always @(posedge clk)
    if (we) mem[waddr] <= wdata;

  assign rdata = mem[raddr];
endmodule

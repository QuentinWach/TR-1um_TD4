// REG8x16 — 16 word x 8 bit 命令メモリマクロの**振る舞いモデル**
//
// 実体は TLAT（12T ラッチ型ビットセル）を 16 行 x 8 列に並べたもの。
// レイアウトは lef/TR-1um_STDCELL.gds、LVS ソースは lef/simulation/REG8x16.spice。
// ここはゲートレベルシミュレーション用のモデルで、**遅延は持たない**
// （hdl/rtl/tr1um_cells.v と同じ方針。遅延は .lib / SDF 側で与える）。
//
//   * クロックを持たない。
//   * リードは組合せ（非同期）。ADD が変われば Q がついてくる。
//     TD4 は CPI=1 なので PC から組合せで命令が出ている必要がある。
//   * ライトは `WR = NOR2(RDB, WEB)` すなわち **WEB=0（アクティブロー）の間だけ
//     選択行が素通し**になり、WEB の立上りでラッチされる。レベルセンス。
//   * **リセットを持たない。** プログラムは実行前に必ず書き込む。
//     したがって電源投入直後の内容は不定（x）。
//
// 書込み中は選択ワードが D に追従するので Q も D に追従する（実物と同じ）。
`default_nettype none

module REG8x16 (
    input  wire [3:0] ADD,
    input  wire       WEB,
    input  wire [7:0] D,
    output wire [7:0] Q
);
  reg [7:0] mem [0:15];

  // WEB=0 の間だけ素通し。ADD が動けば書込み先も動く（行選択が ADD に従うため）。
  always @* if (!WEB) mem[ADD] = D;

  assign Q = mem[ADD];
endmodule

`default_nettype wire

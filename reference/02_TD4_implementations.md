# TD4 の HDL / ASIC 実装事例

## 1. Tiny Tapeout（実シリコン）

### ttsky25a #166 `tt_um_td4` — KATO, Jinnosuke ★最重要参考

- SKY130 / **1×1 タイル（約 167 × 108 µm ≒ 2,000 ゲート枠）**
- **CPU + 16word×8bit プログラムメモリを1チップに内蔵**
- 動作モードを `ui_in[7:6]` で切替: **Load（プログラム書込） / Read（読出確認） / Exec（実行）**
- Security Camp 2025 全国大会 開発コース L2 ゼミの成果
- リポジトリ: https://github.com/jinnosukeKato/tt-td4
  （手元にクローン済: `~/Dropbox/98_LSI_Design/tt-td4`）
- ページ: https://www.tinytapeout.com/chips/ttsky25a/tt_um_td4

> **C4004 の参考にした ttsky25a #39 "MCS-4 4004 CPU"（丸山宗智）と同じシャトル。**
> 4004 が 1タイルに収まるなら TD4 は当然収まる、という規模感の裏付けになる。

### tt07 `tt_um_TD4_Assy_KosugiSubaru` — Ko Kosugi

- SKY130 / 1×1 タイル / clock 10 Hz
- https://github.com/KosugiSubaru/tt07-td4cpu

## 2. FPGA / RTL 実装

| 実装 | 言語 | 特徴 |
|---|---|---|
| [asfdrwe/simpleTD4](https://github.com/asfdrwe/simpleTD4) | Verilog (MIT) | 単一ファイル・約60行。Tang Nano 向け。**もっとも簡潔** |
| [upaengineering/TD4_SV](https://github.com/upaengineering/TD4_SV) | SystemVerilog | 原典の IC 単位（`fulladd` / `dsel` / `pc` / `rom`）にモジュール分割 |
| [wallento/tt09-4bit-toycpu](https://github.com/wallento/tt09-4bit-toycpu) | Verilog | TT09 の 4bit toy CPU |
| [thata gist](https://gist.github.com/thata/ed0575c2871070ecc89d99bd7e357f5d) | Verilog | 解説付き |
| [wuxx/TD4-4BIT-CPU](https://github.com/wuxx/TD4-4BIT-CPU) | 回路図 | 74HC 版の基板データ |

## 3. 本リポジトリの RTL

`hdl/rtl/` に3種を用意（いずれも同じ `td4_core` を共有）。

| モジュール | 命令メモリ | 用途 |
|---|---|---|
| `td4_core.v` | 外付け（`rom_data[7:0]` / `rom_addr[3:0]`） | コア単体の規模測定・TEG |
| `td4_soc_rom.v` | **オンチップ マスクROM**（16×8 固定、組合せ論理） | 最小面積・最少ピン |
| `td4_soc_ff.v` | **オンチップ 書換可能メモリ**（16×8 = 128 FF） | tt-td4 と同方式。実用構成 |

`hdl/tb/tb_td4_core.v` で全12命令 + キャリー + PCラップの19項目を検証済（iverilog、全 PASS）。

## 4. C4004 との比較

| | C4004 (Intel 4004) | TD4 |
|---|---|---|
| FF | 231 | **17**（コア） / 149（128bitメモリ込み） |
| 組合せセル | 576 | **66**（コア） |
| NAND2換算 | 2,085 gates | **180 gates**（コア） |
| 素セル面積 (TR-1um STDLIB) | 3.80 mm² → **NG** | **0.33 mm² → 余裕でOK** |
| 必要信号ピン | 14（ちょうど一杯・双方向バス必須） | **10–14（双方向バス不要）** |
| 2相クロック | 必要（φ1/φ2） | **不要（単相そのまま）** |

# reference/ — 調査資料

TR-1um プロセスで TD4（『CPUの創りかた』の4bit CPU）を実装できるかの事前調査。

| ファイル | 内容 |
|---|---|
| `01_TD4_spec.md` | TD4 のアーキテクチャ・全12命令・原典の 74HCxx 構成・RTL規模 |
| `02_TD4_implementations.md` | HDL/ASIC 実装事例（Tiny Tapeout ttsky25a #166 ほか）と C4004 との比較 |
| `03_TR-1um_facts.md` | TR-1um(IP62) の実測制約：DR、フレーム/パッド、STDLIB セル面積（C4004 と共通） |
| `04_area_estimation.md` | Yosys 合成 + 実セル面積による面積見積り（3構成 × カスタムセル適用段階） |
| `05_pin_io_plan.md` | **ピン割当**: 14信号への収め方3案。**双方向バス不要**という TD4 の利点 |
| `06_design_policy.md` | **設計方針まとめ**: 構成選択 / 記述ルール / 検証フロー / 自作セル / C4004 への位置づけ |
| `07_memory_array.md` | **命令メモリのカスタム RFCELL アレイ化の具体設計**: 12Tセル回路 / アレイ構成 / 周辺回路 / 面積 / 検証項目 |

## 要旨

- TD4 は 4bit・**12命令**・レジスタ A/B/OUT + PC + Cフラグのみ・**加算器1個**・**CPI=1**。
  原典は 74HCxx 12個・150–200ゲート規模。
- 先行例あり: **Tiny Tapeout ttsky25a #166 `tt_um_td4`**（SKY130、1タイル、CPU+16×8メモリ内蔵）。
  **C4004 の参考にした #39 "MCS-4 4004 CPU" と同じシャトル**。
- TR-1um（コア 1,840×1,840 µm = 3.386 mm²）に対し、Yosys 合成 + 実セル面積換算で:

  | 構成 | FF | 組合せ | 素セル面積 | 判定 |
  |---|---:|---:|---:|---|
  | コアのみ（メモリ外付け） | 17 | 66 | **0.328 mm²** | **◎** |
  | コア + マスクROM | 13 | 63 | **0.259 mm²** | **◎** |
  | コア + 書換可能メモリ(128bit FF) | 149 | 536 | 2.691 mm² | ✕ |
  | `td4_soc_arr`（8bit一括ライト・メモリリセット無し） | 153 | 291 | 2.376 mm² | ✕ |
  | ↑ **命令メモリのみ 12T アレイ化** | 25 | 84 | **0.805 mm²** | **◎** |

  メモリ 128bit を FF で作ると **1.919 mm²（全体の 81%）**。
  12T ラッチセル + 周辺回路のアレイにすると **0.349 mm²（5.5倍圧縮）**。
  コア側 0.456 mm² は一切変更しない。→ `07_memory_array.md`

- **結論: 面積は全く問題ない**（C4004 は 2倍オーバーで NG だった）。
  さらに **双方向バスが無いので GIO の自作が不要**。速度も CPI=1 で 4004 より短いパス。
- → TD4 は **C4004 に進む前のテストベヒクル**として最適。
  空き領域（2 mm² 以上）に GIO / TG-DFFE / RFCELL の TEG を載せれば、
  **C4004 に必要なカスタムセルを TD4 チップ1個でほぼ全部実証できる**。

## 設計方針（要点）→ 詳細は `06_design_policy.md`

1. **本命は「コア + 書換可能メモリ（RFCELL アレイ）」**、保険に **マスクROM版を同居**
2. **単相クロック・ステートマシン無し**（TD4 は CPI=1）
3. **自作セルは IBUF / OBUF の2個だけ**（+ 案A″なら RFCELL アレイ）
4. 余った面積は **C4004 用セルの TEG** に充てる

## 主要リンク

- 渡波郁『CPUの創りかた』マイナビ出版
- https://www.tinytapeout.com/chips/ttsky25a/tt_um_td4
- https://github.com/jinnosukeKato/tt-td4
- https://github.com/asfdrwe/simpleTD4
- https://github.com/KosugiSubaru/tt07-td4cpu
- https://www.philipzucker.com/td4-4bit-cpu/
- https://github.com/OpenSUSI/TR-1um

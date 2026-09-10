# irsim/ — スイッチレベルシミュレーション

抽出ネットリストを IRSIM でスイッチレベル検証する。

```
irsim/
├── *.sim   ext2sim / 抽出結果から生成した .sim ネットリスト
├── *.prm   パラメータファイル（TR-1um 5V 用に調整）
└── *.cmd   IRSIM コマンドスクリプト（ベクタ）
```

## 手順（Magic 系フロー）

```sh
magic -dnull -noconsole <<'EOT'
load td4_soc_rom
extract all
ext2sim labels on
ext2sim
quit
EOT
irsim tr1um.prm td4_soc_rom.sim -td4_soc_rom.cmd
```

## 用途

- 全12命令の実行トレース（`hdl/tb/tb_td4_core.v` と同じベクタをそのまま移植する）
- 命令メモリ（RFCELL アレイ版）の読み書きマージン確認
- CPI=1 なので **1クロック内で「セレクタ→加算器→レジスタ」が閉じているか**の確認が主眼。
  C4004 と違って2相クロックのレース検証は不要。
- SPICE より桁違いに速いので、16命令のプログラムを丸ごと流せる。

> `.prm` は TR-1um（Tox 19.5 nm, Vth n=+0.763 / p=−0.678, 5 V）に合わせて作成すること。
> C4004 リポジトリと共通ファイルにするのが望ましい。

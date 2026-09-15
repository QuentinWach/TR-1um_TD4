# 提出版（トップセル `tr_1um_jun1okamura`）

MPW に提出したそのもの。動かさない。

## なぜ名前を変えたか

`info.yaml` の規則は

    - "tr_1um_" で始まる
    - GitHub 名を含む（一意にするため）

で、`tr_1um_jun1okamura` はこれを満たしてはいる。ただし**設計の識別子が
無い**ので、同じ人の別設計（`tr_1um_jun1okamura_i2c` など）と並べたときに
区別が付かない。2026-09-15 に **`tr_1um_jun1okamura_td4`** へ直した。

## 改名で幾何は 1 つも動いていない

新しい `src/tr_1um_jun1okamura_td4.gds` のトップセル名を旧名に戻して
`apr/cmp_gds.py` で突き合わせた結果:

    → **幾何は完全一致**（Region XOR が全層で空）
    → ラベルも一致。差はバイト列の書き方だけ
    666,410 B 同士

改名後の版でも **DRC 0 件 / LVS Netlists match**（KLayout 0.28 +
`--allow-old-klayout`。サインオフは 0.29 以上で取り直すこと）。

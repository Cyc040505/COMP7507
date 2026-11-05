# 数据准备说明

CEPII 原始数据体积大，而且每个人本地的存放路径不同，所以不提交到 Git。
每位组员自己准备一份本地数据，并用下面两种等价方式之一让项目找到它：

1. 把文件放进（或软链接到）约定的 `data/` 目录。
2. 设置 `COMP7507_*_DIR` 环境变量，指向自己的数据目录。

约定的目录结构如下：

```text
data/
  BACI/
  CHELEM/
  GEODIST/
  reference/
  processed/
```

## BACI

- 来源：https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37
- 文件：1995–2024 年的 `BACI_HS92_Y<年份>_V202601.csv`，以及
  `country_codes_V202601.csv`、`product_codes_HS92_V202601.csv`、`Readme.txt`。
- 放置位置：`data/BACI/`，或 `$COMP7507_BACI_DIR` 指向的目录。

## CHELEM GDP

- 来源：https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=17
- 文件：`gdp_v202502.csv`（在 `chelem_gdp_v202502.zip` 压缩包内）。
- 放置位置：`data/CHELEM/`，或 `$COMP7507_CHELEM_DIR` 指向的目录。

## GeoDist

- 来源：https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=6
- 文件：`geo_cepii.xls` 和 `dist_cepii.xls`（`dist_cepii.xls` 在 `dist_cepii.zip` 内）。
- 放置位置：`data/GEODIST/`，或 `$COMP7507_GEODIST_DIR` 指向的目录。

## 处理后的分析表

在项目根目录执行：

```bash
python scripts/build_analytics.py
```

这个脚本只扫描一次原始数据，然后把生成的 parquet 分析表写到
`data/processed/`。临时数据库和标记文件已被 Git 忽略；只有组里明确同意共享的
小型分析表才提交到仓库。

M1 的 `country_pair_hs2_year.parquet` 体积超过普通 Git 的单文件限制，
不随代码提交。组员可使用上述脚本在本地生成，或通过单独的数据共享渠道获取后
放入 `data/processed/`。该文件缺失时，M1 的单个 HS2 商品分析会使用演示数据。

## 环境变量覆盖

```bash
export COMP7507_BACI_DIR='/绝对路径/BACI'
export COMP7507_CHELEM_DIR='/绝对路径/CHELEM'
export COMP7507_GEODIST_DIR='/绝对路径/GeoDist'
```

未设置这些变量时，`src/config.py` 会回退到默认的 `data/` 目录。

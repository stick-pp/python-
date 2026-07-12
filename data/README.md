# 本地数据说明

本目录只记录复现所需的本地数据文件名与来源，不提交任何 WRDS/CRSP/CCM 原始数据。

正式入口 `python/replicate_skinner_2008.py` 会按顺序在以下位置查找数据：

- 项目根目录；
- Git 仓库根目录；
- `data/` 目录。

## 必需文件

| 文件名 | 来源 | 用途 |
| --- | --- | --- |
| `maindata.csv` | Compustat 年度公司数据，本项目已整理为主表 | 读取会计变量、股利、回购、收益、Table 1-3 和 Figure 1-3 所需字段 |
| `CCM Link Table.csv` | WRDS CRSP/Compustat Merged Link Table | 将 Compustat `gvkey` 与 CRSP `permno` 历史链接 |
| `crsp_dse_names.csv` | CRSP Stock Names / DSE 历史名称表 | 股票层普通股、交易所和历史有效区间筛选 |

## 不提交的数据

以下文件只允许本地保留，不能加入 Git：

- `xintopt_1995_2005.csv`
- `monthly.csv`
- `sale.csv`
- `Past stock return.csv`
- 任何 WRDS、CRSP、CCM 导出的 CSV/DTA/SAS 数据文件

生成结果应写入项目级 `shared_artifacts/python_out/`，该目录同样不纳入 Git。

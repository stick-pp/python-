# Skinner (2008) 复现样本清洗与进入口径说明：修订前宽松口径

本文档说明在执行两份 md 清洗规范之前，`replicate_skinner_2008.py` 使用的样本清洗、变量构建与进入 Table/Figure/Regression 的口径。该口径更接近“尽量复现原论文趋势”的宽松实现，但会把部分无法判断的支付状态处理为 0，因此严谨性弱于当前严格口径。

## 1. 数据来源

- 主数据：`2.csv`，来自 WRDS Compustat Fundamentals Annual。
- 调整因子：`ajex.csv`。
- 合并键：`gvkey + datadate`。
- 样本单位：公司-财政年度，即 firm-year。

## 2. 基础样本筛选

修订前基础筛选包括：

- 保留 `consol = C`。
- 保留 `indfmt = INDL`。
- 保留 `datafmt = STD`。
- 保留 `curcd = USD`。
- 保留 `fic = USA`。
- 剔除金融业和公用事业。

行业筛选在较早版本中主要使用 `sich`，缺失时使用 `sic`；后续已改为 `sic` 和 `sich` 任一字段命中金融或公用事业即剔除。

## 3. 变量构建口径

### 3.1 股利

修订前口径：

```text
dividend = dvc
dvc 缺失值填 0
```

含义是：若 Compustat 中 `dvc` 缺失，程序将其解释为没有支付普通股股利。

该处理有利于保持较大的样本量，但经济含义较强：它默认“缺失”就是“没有发生”。

### 3.2 特殊项目与收益

```text
special_items = spi，缺失填 0
earnings = ib - 0.6 * spi
```

该处理与 Skinner (2008) 中调整特殊项目税后影响的思路一致。

### 3.3 净回购

修订前口径：

```text
tstkc、prstkc、sstk 缺失值均先填 0
lag_tstkc 使用 groupby(gvkey).shift(1)
若 tstkc 和 lag_tstkc 均为 0，则使用 prstkc - sstk
否则使用 tstkc - lag_tstkc
负值设为 0
缺失或不可计算结果最终也填 0
```

这意味着：

- 公司第一条观测的上一年 `tstkc` 会被视为 0。
- 若公司年度不连续，上一行也可能被当作上一财政年度。
- 如果 `tstkc`、`prstkc` 或 `sstk` 缺失，程序仍可能生成 0 回购。

该口径可以得到较完整的公司支付历史，因此 Table 1、Table 2、Figure 2、Figure 3 和 Table 3 都能生成较完整结果。

### 3.4 总支付

```text
total_payout = dividend + repurchase
```

由于股利和回购已经被填 0，因此总支付几乎总是可计算。

### 3.5 Table 3 变量

修订前口径包括：

```text
roa = oibdp / lag(at)
cash = che / at
adjusted_price = abs(prcc_f) / ajex
past_stock_return = adjusted_price_t / adjusted_price_t-3 - 1
eso_dilution = xintopt / sale * past_stock_return
```

其中 `roa` 早期使用 `groupby(gvkey).shift(1)`，后来已改为精确匹配 `gvkey + fyear - 1`。三年收益后续也已改为精确匹配 `gvkey + fyear - 3`。

## 4. Table 1 进入口径

窗口：

```text
1980-1989
1985-1994
1990-1999
1995-2004
```

进入条件：

- 公司在窗口内有至少一个 Compustat firm-year 观测。
- 由于股利和回购缺失被填 0，公司均可计算股利年份数和回购年份数。

分组：

- 股利年份数：`0`、`1-4`、`5-9`、`10`。
- 回购年份数：`0`、`1-4`、`5-10`。

该口径下，无法判断支付状态的公司不会被排除，而是常被归入 0 年支付组。

## 5. Table 2 进入口径

期间：

```text
1980-2005
```

进入条件：

- 公司在 1980-2005 年内有至少一个 firm-year 观测。
- 股利和回购年份数均可由填 0 后的变量计算。

分组：

```text
0
1-5
6-10
11-15
16-20
>20
```

该口径下 Table 2 样本量较大，0 股利列也较大，原因是缺失支付信息会被解释为 0。

## 6. Group I-V 进入口径

基于 1980-2005 长期支付历史：

- Group I：股利年份数 = 0，回购年份数 = 0。
- Group II：股利年份数 >= 16，回购年份数 >= 11。
- Group III：股利年份数 = 0，回购年份数 1-5。
- Group IV：股利年份数 = 0，回购年份数 >= 6。
- Group V：回购年份数 = 0，股利年份数 >= 6。

由于支付缺失已被填 0，该口径可以得到非空的 Group I-V，并可绘制 Figure 2、Figure 3，Table 3 也有可估计样本。

## 7. Table 3 回归进入口径

Panel A：

- 样本为 Group II。
- 估计期间为 `1980-1994`、`1995-2005`、`1995-2005 + ESO`。

Panel B：

- 样本为 Group III 和 Group IV。
- `regular_dummy = 1` 表示 Group IV。
- `regular_dummy = 0` 表示 Group III。

缺失处理：

- 回归变量缺失时按模型变量集逐模型删除。
- 由于因变量 `repurchase_dummy` 基于填 0 后的回购变量构造，因此回归样本较大。

## 8. 该口径的优点

- 能得到接近原论文形式的完整 Figure 1-3 和 Table 1-3。
- Table 2 和 Group I-V 不会因为早期回购字段缺失而大面积清空。
- Table 3 可以运行 Stata logit 回归。
- 适合作为“论文复现趋势口径”或“宽松复现口径”。

## 9. 该口径的主要问题

- 把缺失支付信息解释为 0，可能混淆“没有支付”和“无法判断”。
- 使用 `shift(1)` 可能在公司财政年度不连续时错误匹配上一年。
- 第一条公司观测的 lag 变量可能被错误设为 0。
- 回购年份数可能被低估或误分类。
- Table 2 的 0 股利列、0 回购行以及 Group I/III 样本可能偏大。

## 10. 使用建议

该口径不应被描述为最严格的数据清洗口径。若用于最终报告，应明确称为：

```text
宽松复现口径 / paper-like replication specification / sensitivity specification
```

并说明其目的是获得与 Skinner (2008) 图表趋势更可比的样本，而不是严格区分缺失状态与真实 0 支付状态。

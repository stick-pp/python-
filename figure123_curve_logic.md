# Figure 1-3 曲线制作逻辑说明书

本文档只记录当前 `replicate_skinner_2008.py` 中 Figure 1、Figure 2、Figure 3 的实际代码口径，用于和 Skinner (2008) 原论文进行逐项比对，并解释当前复现曲线与原文曲线可能存在差异的原因。本文档不加入新的处理设想，也不替代论文原文口径。

## 1. 输入文件与输出文件

当前 Python 脚本读取四类输入：

| 输入文件 | 作用 |
|---|---|
| `2.csv` | Compustat Fundamentals Annual 主数据 |
| `ajex.csv` | 拆股调整因子 `ajex`，主要用于 Table 3 的过去三年股票收益 |
| `CCM Link Table.csv` | Compustat `gvkey` 到 CRSP `permno` 的链接 |
| `crsp_dse_names.csv` | CRSP 证券名称历史表，用于股票层筛选 |

Figure 1-3 的源数据输出到：

| 图 | 源数据 |
|---|---|
| Figure 1 | `shared_artifacts/python_out/tables/figure1_annual_aggregates.csv` |
| Figure 2 Panel A | `shared_artifacts/python_out/tables/figure2_panel_a_earnings.csv` |
| Figure 2 Panel B | `shared_artifacts/python_out/tables/figure2_panel_b_earnings.csv` |
| Figure 3 | `shared_artifacts/python_out/tables/figure3_loss_fractions.csv` |

渲染图输出到：

| 图 | PNG/PDF |
|---|---|
| Figure 1 | `shared_artifacts/python_out/figures/figure1.png`, `figure1.pdf` |
| Figure 2 | `shared_artifacts/python_out/figures/figure2.png`, `figure2.pdf` |
| Figure 3 | `shared_artifacts/python_out/figures/figure3.png`, `figure3.pdf` |

## 2. 共同样本清洗逻辑

Figure 1-3 均建立在同一套清洗后的公司年数据上。代码处理顺序如下。

### 2.1 合并与基础格式筛选

1. `2.csv` 与 `ajex.csv` 按 `gvkey + datadate` 一对一合并。
2. 要求主数据和 `ajex` 数据中 `gvkey + datadate` 不重复。
3. 数值字段统一用 `pd.to_numeric(..., errors="coerce")` 转为数值，无法转换的值变为缺失。
4. 保留 WRDS/Compustat 标准年度工业格式：

```text
consol == "C"
indfmt == "INDL"
datafmt == "STD"
curcd == "USD"
```

5. 保留美国注册公司：

```text
fic == "USA"
```

### 2.2 行业筛选

代码先构造行业筛选变量：

```text
sic_use = sich if sich is not missing else sic
```

随后剔除：

```text
financial firms: 6000 <= sic_use <= 6999
utilities:       4900 <= sic_use <= 4999
```

如果 `sic` 和 `sich` 同时缺失，代码不会因为行业缺失直接删除这些观测；这些观测不会落入金融或公用事业排除区间，因此被保留。

### 2.3 CRSP/CCM 股票层筛选

代码使用 `CCM Link Table.csv` 和 `crsp_dse_names.csv` 做股票层筛选。

CCM 链接表保留：

```text
LINKTYPE in {"LC", "LU", "LS"}
LINKPRIM in {"P", "C"}
gvkey not missing
LPERMNO not missing
LINKDT not missing
```

`LINKENDDT` 若为空或为 `E`，按开放结束日期处理为 `2099-12-31`。公司年 `datadate` 必须落在：

```text
LINKDT <= datadate <= LINKENDDT
```

CRSP 名称历史表中，代码把 `DATE` 重命名为 `namedt`，并保留：

```text
SHRCD in {10, 11}
EXCHCD in {1, 2, 3}
PERMNO not missing
namedt not missing
```

`NAMEENDT` 若为空或为开放结束标记，按 `2099-12-31` 处理。公司年 `datadate` 必须落在：

```text
namedt <= datadate <= NAMEENDT
```

因此当前 Figure 1-3 不是纯 Compustat 全样本图，而是经过 CRSP/CCM 普通股、交易所和有效链接日期筛选后的 Compustat 工业公司样本。

## 3. 共同变量构建逻辑

### 3.1 股利

代码定义：

```text
dividend = dvc
```

缺失处理：

| 情形 | 代码处理 |
|---|---|
| `dvc > 0` | `dividend_dummy = 1` |
| `dvc == 0` | `dividend_dummy = 0` |
| `dvc` 缺失 | `dividend_dummy = missing` |

`dvc` 缺失不会被填成 0。因此公司是否支付股利只在 `dvc` 可观察时判定。

### 3.2 特殊项目

代码定义：

```text
special_items = spi.fillna(0)
```

也就是说，只有 `spi` 在 Figure 1 的特殊项目曲线中被缺失填 0。

### 3.3 收益

当前代码已经按论文 Figure 1/2/3 曲线口径改为：

```text
earnings = ib
```

这意味着：

| 项目 | 当前代码 |
|---|---|
| Figure 1 的 earnings 曲线 | 汇总 `ib` |
| Figure 2 的 earnings 曲线 | 按年度和组别汇总 `ib` |
| Figure 3 的亏损判定 | `ib < 0` |

注意：此前代码曾使用 `ib - 0.6 * spi`，该口径会把负特殊项目按 60% 税后影响加回收益，使 2001 年收益不容易跌破 0。当前版本已不再使用该口径。

### 3.4 净回购

净回购变量 `repurchase` 的构造依赖 `tstkc`、上一财政年度 `tstkc_lag1`、`prstkc` 和 `sstk`。

代码先按同一 `gvkey` 精确匹配上一财政年度：

```text
tstkc_lag1 = same gvkey, fyear - 1 的 tstkc
```

随后构造：

| 情形 | 代码处理 | `repurchase_source` |
|---|---|---|
| 当前年和上一年 `tstkc` 均可观察，且不都是 0 | `repurchase = tstkc - tstkc_lag1` | `treasury_stock_change` |
| 当前年和上一年 `tstkc` 均可观察且都为 0，并且 `prstkc/sstk` 完整 | `repurchase = prstkc - sstk` | `retirement_method` |
| 当前年和上一年 `tstkc` 均为 0，但 `prstkc/sstk` 不完整 | `repurchase = missing` | `missing_cashflow_inputs` |
| 当前年或上一年 `tstkc` 缺失，即使 `prstkc/sstk` 完整 | `repurchase = missing` | `missing_tstkc_pair_cashflow_available_not_used` |
| 当前年或上一年 `tstkc` 缺失，且 `prstkc/sstk` 不完整 | `repurchase = missing` | `missing_tstkc_pair_and_cashflow_inputs` |

然后：

```text
repurchase = repurchase clipped at lower bound 0
```

即构造出的负回购被置为 0。回购状态定义为：

| 情形 | 代码处理 |
|---|---|
| `repurchase > 0` | `repurchase_dummy = 1` |
| `repurchase == 0` | `repurchase_dummy = 0` |
| `repurchase` 缺失 | `repurchase_dummy = missing` |

代码不使用 `cashflow_fallback` 来填补当前年或上一年 `tstkc` 缺失导致的回购不可判定。

### 3.5 总支付

代码定义：

```text
total_payout = dividend + repurchase
```

由于 Python/pandas 中缺失值参与加法会得到缺失，因此若 `dividend` 或 `repurchase` 任一缺失，`total_payout` 也会缺失。Figure 1 的股利曲线和回购曲线分别使用各自变量汇总，不依赖 `total_payout`。

### 3.6 亏损指标

代码定义：

```text
loss = 1 if earnings < 0
loss = 0 if earnings >= 0
loss = missing if earnings is missing
```

由于当前 `earnings = ib`，所以 Figure 3 的亏损比例是：

```text
fraction of firms with ib < 0
```

## 4. 长期支付组别构造逻辑

Figure 2 和 Figure 3 依赖 1980-2005 长窗口的 Group I-V 分组。代码先对每家公司在 1980-2005 年内累计：

```text
div_years = dividend_dummy == 1 的年份数
rep_years = repurchase_dummy == 1 的年份数
div_valid_years = dividend_dummy 非缺失年份数
rep_valid_years = repurchase_dummy 非缺失年份数
firm_years = fyear 非重复年份数
```

进入长期分组的条件为：

```text
div_valid_years >= 1 and rep_valid_years >= 1
```

也就是说，公司必须至少有 1 年可判定股利状态，并且至少有 1 年可判定回购状态，才能进入 Table 2 和 Figure 2/3 的长期支付分类。

分组定义如下：

| 组别 | 代码定义 |
|---|---|
| Group I: Non-payers | `div_years == 0` 且 `rep_years == 0` |
| Group II: Regular div. + regular rep. | `div_years >= 16` 且 `rep_years >= 11` |
| Group III: Occasional rep. only | `div_years == 0` 且 `1 <= rep_years <= 5` |
| Group IV: Regular rep. only | `div_years == 0` 且 `rep_years >= 6` |
| Group V: Dividend-only regular | `rep_years == 0` 且 `div_years >= 6` |
| Other | 满足进入条件但不属于 Group I-V |

当前输出中的长期分组公司数为：

| 组别 | 当前公司数 |
|---|---:|
| Other | 3,142 |
| Group I: Non-payers | 3,971 |
| Group II: Regular div. + regular rep. | 302 |
| Group III: Occasional rep. only | 3,115 |
| Group IV: Regular rep. only | 387 |
| Group V: Dividend-only regular | 192 |

## 5. Figure 1 曲线制作逻辑

### 5.1 样本窗口

Figure 1 使用：

```text
1970 <= fyear <= 2005
```

该窗口建立在前述清洗和 CRSP/CCM 股票层筛选之后。

### 5.2 曲线定义

代码按 `fyear` 汇总：

| 曲线 | 源变量 | 汇总方法 | 缺失处理 |
|---|---|---|---|
| Compustat earnings | `earnings = ib` | 按年求和 | `sum(min_count=1)`，若全年全缺失则为缺失 |
| Special items | `special_items = spi.fillna(0)` | 按年求和 | 单条观测 `spi` 缺失先填 0 |
| Dividends | `dividend = dvc` | 按年求和 | 不把 `dvc` 缺失填 0；求和时跳过缺失 |
| Net repurchases | `repurchase` | 按年求和 | 不把不可判定回购填 0；求和时跳过缺失 |

代码使用的求和函数为：

```python
series.sum(min_count=1)
```

含义是：只要某年该变量至少有一个非缺失值，就对非缺失值求和；如果某年该变量全部缺失，年度汇总结果为缺失。

### 5.3 绘图坐标设置

| 项目 | 当前设置 |
|---|---|
| 横轴 | 1970-2005 |
| 横轴位置 | y = 0 |
| 纵轴 | -400,000 到 600,000 |
| 单位 | Compustat 百万美元 |

### 5.4 当前关键诊断

当前 Figure 1 最低年度收益出现在 2001 年：

| 年份 | earnings | special_items | dividends | net_repurchases | firms |
|---:|---:|---:|---:|---:|---:|
| 2001 | -78,860.9 | -284,476.8 | 98,488.0 | 87,448.7 | 4,243 |

这说明当前 `earnings = ib` 口径已经允许 Figure 1 收益线跌破 0。若与论文仍有数值差异，主要应从样本宇宙、数据版本、CRSP/CCM 链接和股票层筛选差异、以及回购变量缺失处理差异解释，而不是从 `ib - 0.6 * spi` 口径解释。

## 6. Figure 2 曲线制作逻辑

### 6.1 样本窗口

Figure 2 使用：

```text
1980 <= fyear <= 2005
```

分组来自 1980-2005 长窗口 Group I-V。

### 6.2 Panel A 曲线定义

Panel A 有两条曲线：

| 曲线 | 代码口径 |
|---|---|
| All industrials | 清洗样本中所有 1980-2005 公司年，按 `fyear` 汇总 `earnings = ib` |
| Group II | `group_id == 2` 的公司年，按 `fyear` 汇总 `earnings = ib` |

Group II 如果某年没有观测，代码把该年 Group II 年度汇总填为 0：

```python
panel_a["Regular div. + regular rep."] = panel_a["Regular div. + regular rep."].fillna(0)
```

### 6.3 Panel B 曲线定义

Panel B 绘制四组：

| 曲线 | 组别 |
|---|---|
| Group I: Non-payers | `group_id == 1` |
| Group III: Occasional rep. | `group_id == 3` |
| Group IV: Regular rep. | `group_id == 4` |
| Group V: Dividend only | `group_id == 5` |

代码按：

```text
fyear + group_name
```

对 `earnings = ib` 求和。Panel B 不对缺失的组别年度组合补 0；只有实际存在的年度组别汇总会进入图形。

### 6.4 绘图坐标设置

Panel A：

| 项目 | 当前设置 |
|---|---|
| 横轴 | 1980-2005 |
| 横轴位置 | y = 0 |
| 纵轴 | 0 到 600,000 |

Panel B：

| 项目 | 当前设置 |
|---|---|
| 横轴 | 1980-2005 |
| 横轴位置 | y = 0 |
| 纵轴 | -80,000 到 40,000 |

Figure 2 当前使用上下两张子图排列。

### 6.5 当前关键诊断

当前 Figure 2 Panel B 在 2000-2005 年的源数据为：

| 年份 | Dividend-only regular | Non-payers | Occasional rep. only | Regular rep. only |
|---:|---:|---:|---:|---:|
| 2000 | 1,456.5 | -53,704.6 | -21,264.7 | 13,584.2 |
| 2001 | -4,410.7 | -145,076.0 | -67,381.9 | -787.2 |
| 2002 | -2,159.4 | -35,327.5 | -27,256.3 | 7,269.4 |
| 2003 | 1,620.6 | -9,448.4 | 11,195.3 | 17,788.7 |
| 2004 | 3,880.7 | -3,900.7 | 17,924.3 | 22,258.8 |
| 2005 | 6,051.6 | -1,835.7 | 21,110.0 | 17,802.6 |

这解释了当前图中 `Non-payers` 和 `Occasional rep. only` 与原文形态不同的直接数据原因：

1. 当前 `Non-payers` 在 2000-2002 年比 `Occasional rep. only` 更负。
2. 当前 `Occasional rep. only` 从 2003 年开始转正并高于 `Non-payers`。
3. 因此当前数据不会自然形成原文中 2000-2005 年两条线的两个交点。
4. `Regular rep. only` 在 2005 年低于 2004 年，是源数据中该组年度 `ib` 汇总从 22,258.8 降到 17,802.6 的结果，不是绘图标签互换。

这些差异不是由 Figure 2 画图标签导致的；它们来自分组后的年度 `ib` 汇总值。

## 7. Figure 3 曲线制作逻辑

### 7.1 样本窗口

Figure 3 使用：

```text
1980 <= fyear <= 2005
group_id in {1, 2, 3, 4, 5}
```

也就是说，Figure 3 只包括长期支付组别 Group I-V，不包括 `Other`。

### 7.2 曲线定义

代码先在公司年层面构造：

```text
loss = 1 if ib < 0
loss = 0 if ib >= 0
loss = missing if ib is missing
```

然后按：

```text
fyear + group_name
```

计算：

```text
loss_fraction = mean(loss)
```

因此 Figure 3 的纵轴是每个年度、每个长期支付组中 `ib < 0` 的公司年比例。`ib` 缺失的公司年不参与均值计算。

### 7.3 绘图坐标设置

| 项目 | 当前设置 |
|---|---|
| 横轴 | 1980-2005 |
| 纵轴 | 0.000 到 0.900 |
| 纵轴显示 | 百分比格式 |

### 7.4 当前关键诊断

当前 2001 年各组亏损比例为：

| 组别 | 2001 loss_fraction |
|---|---:|
| Dividend-only regular | 0.511 |
| Non-payers | 0.779 |
| Occasional rep. only | 0.620 |
| Regular div. + regular rep. | 0.150 |
| Regular rep. only | 0.389 |

Figure 3 与原文差异可能来自两个层面：

1. 当前亏损定义已经是 `ib < 0`，不再是 `ib - 0.6 * spi < 0`。
2. 亏损比例仍然高度依赖 Group I-V 分组公司集合；如果 Table 2 分组公司数与原文不同，则 Figure 3 的每组年度亏损比例也会不同。

## 8. 当前曲线与原文差异的代码层原因清单

以下原因均来自当前代码口径，可作为和论文对照时的检查清单。

### 8.1 样本宇宙不同

当前 Figure 1-3 使用经过 CRSP/CCM 筛选后的 Compustat 工业公司样本，而不是未经股票层筛选的纯 Compustat 工业公司全集。筛选包括：

```text
CCM LINKTYPE in LC/LU/LS
CCM LINKPRIM in P/C
datadate inside link date interval
CRSP SHRCD in 10/11
CRSP EXCHCD in 1/2/3
datadate inside CRSP name date interval
```

若原文 Figure 1 的 “Aggregate Compustat earnings” 使用更宽的 Compustat 工业公司宇宙，则当前 Figure 1 总量可能偏小或趋势不同。

### 8.2 Group I-V 公司数与原文不同

当前长期分组公司数与原文 Table 2 并不完全一致。Figure 2 和 Figure 3 又直接依赖这些组，因此组内年度 `ib` 汇总和亏损比例会随分组差异而变化。

尤其是：

```text
Group I: 3,971
Group III: 3,115
Group IV: 387
Group V: 192
```

如果原文中 `Non-payers` 与 `Occasional rep.` 的公司集合不同，Panel B 曲线位置也会不同。

### 8.3 回购缺失处理影响分组

当前代码在 `tstkc` 当前年或上一年缺失时，不使用 `prstkc - sstk` 作为自动现金流 fallback。即使 `prstkc/sstk` 完整，也将回购保持为缺失。

这会影响：

1. `repurchase_dummy` 的可判定年份数；
2. `rep_years` 累计；
3. Group I、III、IV、V 的归类；
4. Figure 2 和 Figure 3 的组内公司集合。

### 8.4 进入长期分组要求股利和回购都至少有 1 年可判定

当前长期分组进入条件是：

```text
div_valid_years >= 1 and rep_valid_years >= 1
```

若某公司 1980-2005 年中股利状态或回购状态完全不可判定，则不会进入 Table 2 和 Figure 2/3 分组。

### 8.5 Figure 1 与 Figure 2 使用同一收益变量，但样本维度不同

Figure 1：

```text
1970-2005 所有清洗后公司年，按年汇总 ib
```

Figure 2：

```text
1980-2005 所有清洗后公司年或 Group I-V 组内公司年，按年汇总 ib
```

因此 Figure 1 的总量趋势和 Figure 2 Panel A 的 All industrials 都使用 `ib`，但窗口不同，且 Figure 2 同时叠加了长期分组口径。

### 8.6 缺失值没有统一填 0

当前代码只对 `spi` 缺失填 0。其他关键变量不是统一填 0：

| 变量 | 缺失处理 |
|---|---|
| `ib` | 保持缺失 |
| `dvc` | 保持缺失 |
| `repurchase` | 不可判定时保持缺失 |
| `loss` | `ib` 缺失时保持缺失 |

年度求和时，非缺失值会被求和，缺失值被跳过；但如果某年度某变量全部缺失，年度汇总结果保持缺失。

## 9. 与论文比对时应优先检查的问题

根据当前代码逻辑，若 Figure 1-3 仍与原文存在曲线差异，建议按以下顺序比对：

1. 原文 Figure 1 的 “Aggregate Compustat earnings” 是否使用完整 Compustat 工业公司宇宙，还是也隐含 CRSP/CCM 普通股筛选。
2. 原文 Figure 2 和 Figure 3 的 Group I-V 是否严格由 Table 2 的 1980-2005 支付年份数定义，且进入样本条件是否与当前 `div_valid_years >= 1 and rep_valid_years >= 1` 一致。
3. 原文对回购变量在 `tstkc` 当前年或上一年缺失但 `prstkc/sstk` 完整时是否允许现金流 fallback。
4. 原文是否对 `dvc`、`repurchase`、`ib` 的缺失值做了额外处理；当前代码没有把这些缺失统一填 0。
5. 当前 CRSP/CCM 链接表和 CRSP names/history 表是否与原文样本期和数据版本一致。

## 10. 结论

当前 Figure 1-3 的曲线逻辑可以概括为：

```text
共同清洗样本
-> 美国 Compustat 工业公司
-> CRSP/CCM 普通股与交易所筛选
-> earnings = ib
-> Figure 1: 1970-2005 全样本年度总量
-> Table 2 Group I-V: 1980-2005 长期支付行为分组
-> Figure 2: 1980-2005 按 Group I-V 汇总 ib
-> Figure 3: 1980-2005 按 Group I-V 计算 ib < 0 的公司比例
```

因此，当前 Figure 2 中 `Non-payers` 与 `Occasional rep.` 曲线位置和原文不同，不是绘图标签错误，而是当前清洗样本、长期分组和年度 `ib` 汇总共同作用的结果。当前 Figure 1 收益线已经使用 `ib`，并在 2001 年跌破 0；若与原文数值仍不同，应继续从样本宇宙、数据版本和支付组别构成差异解释。

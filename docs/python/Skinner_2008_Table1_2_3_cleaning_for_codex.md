# Skinner (2008) Table 1、Table 2、Table 3 数据清洗与变量构造规范

本文档合并了 Table 1、Table 2 的支付变量清洗与长期分组规则，以及 Table 3 的解释变量、因变量和回归样本准备规则。请 Codex 将本文档视为修改 `replicate_skinner_2008.py` 的统一实施规范。

---

# Skinner (2008) Table 1、Table 2 数据清洗与分组规范

## 1. 目标

本文档用于指导 Codex 修改 `replicate_skinner_2008.py` 中与 Skinner (2008) Table 1、Table 2 有关的数据清洗、支付变量构造、长期分组和 QA 逻辑。

核心原则：

1. 样本单位为公司—财政年度。
2. 公司—年度识别键使用 `gvkey + fyear`。
3. 股利和净回购的缺失状态不得自动解释为 0。
4. 上年库存股必须来自同一公司准确的 `fyear - 1`。
5. 净回购只有在原始输入完整时才能计算。
6. 计算结果为负时设为 0；无法计算时继续保留 `NaN`。
7. 某公司在分析窗口内支付年份数无法可靠确定时，应标记为“无法分类”，不能放入 0 年支付组。
8. Table 1、Table 2 的公司分类应基于完整且可判定的支付历史。

---

## 2. 样本筛选

### 2.1 数据来源

使用 Compustat Fundamentals Annual 年度公司数据。

### 2.2 基本格式筛选

保留：

```text
consol = "C"
indfmt = "INDL"
datafmt = "STD"
```

如数据中存在货币字段，主样本还应保证金额单位可比，例如：

```text
curcd = "USD"
```

### 2.3 美国注册公司

保留：

```text
fic = "USA"
```

### 2.4 排除金融业和公用事业

优先使用历史 SIC `sich`，缺失时使用 `sic` 作为替代。

建议：

```python
df["sic_use"] = df["sich"].where(
    df["sich"].notna(),
    df["sic"],
)
```

排除：

```text
金融业：6000–6999
公用事业：4900–4999
```

如项目决定使用 4900–4949，应在报告中统一说明并保持代码与文档一致。

### 2.5 公司—年度唯一性

以：

```text
gvkey + fyear
```

作为公司—财政年度识别键。

必须检查：

```python
df.duplicated(["gvkey", "fyear"]).any()
```

如存在重复，不能直接保留第一条。应先检查：

- `datadate`
- `consol`
- `indfmt`
- `datafmt`
- `popsrc`
- `curcd`
- 是否存在财年变更或过渡财年

只有在明确规则下才能去重。

---

## 3. DVC：普通股现金股利

### 3.1 原始字段

```text
DVC
Dividends Common/Ordinary
```

### 3.2 缺失值处理

`dvc` 缺失值保留为 `NaN`。

不得执行：

```python
df["dvc"] = df["dvc"].fillna(0)
```

### 3.3 公司年度股利状态

定义：

\[
DividendDummy_{it}
=
\begin{cases}
1, & DVC_{it} > 0 \\
0, & DVC_{it} = 0 \\
NaN, & DVC_{it}\text{ 缺失}
\end{cases}
\]

建议代码：

```python
df["dividend_dummy"] = np.select(
    [
        df["dvc"].gt(0),
        df["dvc"].eq(0),
    ],
    [
        1.0,
        0.0,
    ],
    default=np.nan,
)
```

### 3.4 股利金额

```python
df["dividend"] = df["dvc"]
```

不对缺失值填 0。

---

## 4. 净回购构造

### 4.1 原始字段

```text
TSTKC   Treasury Stock - Common
PRSTKC  Purchase of Common and Preferred Stock
SSTK    Sale of Common and Preferred Stock
```

### 4.2 上年库存股必须按真实连续年度匹配

不能直接使用：

```python
df.groupby("gvkey")["tstkc"].shift(1)
```

因为上一行可能不是上一财政年度。

应按同一公司准确的 `fyear - 1` 匹配：

```python
lag_tstkc = df[["gvkey", "fyear", "tstkc"]].copy()
lag_tstkc["fyear"] = lag_tstkc["fyear"] + 1
lag_tstkc = lag_tstkc.rename(
    columns={"tstkc": "tstkc_lag1"}
)

df = df.merge(
    lag_tstkc,
    on=["gvkey", "fyear"],
    how="left",
    validate="one_to_one",
)
```

---

## 5. TSTKC 缺失值与会计方法识别

### 5.1 库存股数据可用条件

只有以下条件同时满足时，才认为本年和上年库存股数据可用：

```python
tstkc_pair_observed = (
    df["tstkc"].notna()
    & df["tstkc_lag1"].notna()
)
```

### 5.2 注销法识别条件

只有同一公司、连续两个财政年度的 `tstkc` 都真实观察为 0，才识别为注销法：

```python
retirement_method = (
    tstkc_pair_observed
    & df["tstkc"].eq(0)
    & df["tstkc_lag1"].eq(0)
)
```

以下情形均不能据此识别为注销法：

- 年度不连续；
- 本年 `tstkc` 缺失；
- 上年 `tstkc` 缺失；
- 本年和上年都缺失；
- 公司第一条可观察记录没有准确上一年。

这些情形继续保留为无法判断，不得将缺失填为 0。

### 5.3 库存股法识别条件

当连续两年 `tstkc` 均可观察，但不同时为 0 时，使用库存股法：

```python
treasury_method = (
    tstkc_pair_observed
    & ~retirement_method
)
```

---

## 6. PRSTKC 与 SSTK 缺失值处理

现金流法计算净回购必须满足：

```python
cashflow_complete = (
    df["prstkc"].notna()
    & df["sstk"].notna()
)
```

以下任一情况出现时，不能根据现金流法计算净回购：

- `prstkc` 缺失、`sstk` 非缺失；
- `prstkc` 非缺失、`sstk` 缺失；
- 两者同时缺失。

不得分别对 `prstkc` 或 `sstk` 执行 `fillna(0)`。

---

## 7. 净回购计算规则

### 7.1 初始化

```python
df["repurchase"] = np.nan
df["repurchase_source"] = pd.NA
```

### 7.2 库存股法

当 `treasury_method == True`：

\[
Repurchase_{it}
=
TSTKC_{it} - TSTKC_{i,t-1}
\]

建议：

```python
df.loc[treasury_method, "repurchase"] = (
    df.loc[treasury_method, "tstkc"]
    - df.loc[treasury_method, "tstkc_lag1"]
)

df.loc[
    treasury_method,
    "repurchase_source",
] = "treasury_stock_change"
```

### 7.3 注销法

当：

```text
retirement_method == True
```

且：

```text
PRSTKC 与 SSTK 均非缺失
```

则：

\[
Repurchase_{it}
=
PRSTKC_{it} - SSTK_{it}
\]

建议：

```python
retirement_complete = (
    retirement_method
    & cashflow_complete
)

df.loc[retirement_complete, "repurchase"] = (
    df.loc[retirement_complete, "prstkc"]
    - df.loc[retirement_complete, "sstk"]
)

df.loc[
    retirement_complete,
    "repurchase_source",
] = "purchase_minus_issuance"
```

### 7.4 库存股数据不可用时

如果：

- 本年或上年 `tstkc` 缺失；
- 或不存在准确 `fyear - 1`；

则主口径下净回购保持 `NaN`，不自动改用现金流法。

如项目希望使用现金流法作为替代口径，应单独生成扩展变量，例如：

```python
df["repurchase_alt"] = df["repurchase"]
```

再对库存股不可用但 `prstkc`、`sstk` 完整的公司年度应用现金流差额。该口径必须在报告中作为敏感性检验单独披露，不能与主口径混在一起。

### 7.5 负值处理

只有在净回购已经成功计算后，负值才设为 0：

```python
df["repurchase"] = df["repurchase"].clip(lower=0)
```

禁止：

```python
df["repurchase"] = (
    df["repurchase"]
    .fillna(0)
    .clip(lower=0)
)
```

因为这会把“无法计算”错误转成“没有回购”。

---

## 8. 公司年度回购状态

定义：

\[
RepurchaseDummy_{it}
=
\begin{cases}
1, & Repurchase_{it} > 0 \\
0, & Repurchase_{it} = 0 \\
NaN, & Repurchase_{it}\text{ 无法计算}
\end{cases}
\]

建议：

```python
df["repurchase_dummy"] = np.select(
    [
        df["repurchase"].gt(0),
        df["repurchase"].eq(0),
    ],
    [
        1.0,
        0.0,
    ],
    default=np.nan,
)
```

禁止：

```python
(df["repurchase"] > 0).astype(int)
```

因为这会把缺失值错误编码为 0。

---

## 9. 总支付金额

定义：

\[
TotalPayout_{it}
=
Dividend_{it} + Repurchase_{it}
\]

严格口径：

```python
df["total_payout"] = (
    df["dividend"] + df["repurchase"]
)
```

只要任一组成部分缺失，总支付就保持 `NaN`。

禁止使用默认跳过缺失值的横向求和：

```python
df[["dividend", "repurchase"]].sum(axis=1)
```

如使用 `groupby().sum()` 聚合，应使用：

```python
x.sum(min_count=1)
```

避免整组全部缺失时被自动计算为 0。

---

## 10. 支付年份统计与可分类条件

### 10.1 每个窗口内需要同时统计

对每家公司、每个分析窗口，至少统计：

```text
div_years
rep_years
div_valid_years
rep_valid_years
firm_years
div_missing_years
rep_missing_years
```

建议：

```python
firm = (
    period.groupby("gvkey")
    .agg(
        div_years=(
            "dividend_dummy",
            lambda x: int((x == 1).sum()),
        ),
        rep_years=(
            "repurchase_dummy",
            lambda x: int((x == 1).sum()),
        ),
        div_valid_years=(
            "dividend_dummy",
            "count",
        ),
        rep_valid_years=(
            "repurchase_dummy",
            "count",
        ),
        firm_years=(
            "fyear",
            "nunique",
        ),
        total_payout=(
            "total_payout",
            lambda x: x.sum(min_count=1),
        ),
    )
    .reset_index()
)

firm["div_missing_years"] = (
    firm["firm_years"]
    - firm["div_valid_years"]
)

firm["rep_missing_years"] = (
    firm["firm_years"]
    - firm["rep_valid_years"]
)
```

### 10.2 可分类条件

严格主口径要求，公司在其实际存在的全部公司年度中，支付状态均可观察：

```python
firm["div_classifiable"] = (
    firm["div_valid_years"]
    == firm["firm_years"]
)

firm["rep_classifiable"] = (
    firm["rep_valid_years"]
    == firm["firm_years"]
)

firm["payout_classifiable"] = (
    firm["div_classifiable"]
    & firm["rep_classifiable"]
)
```

公司不需要完整存续整个十年或整个 1980–2005 年；但在其实际存在的公司年度中，股利和回购状态必须完整可判定。

### 10.3 无法分类

以下公司不能进入支付年份分组：

- 时间区间内 `dividend_dummy` 存在缺失；
- 时间区间内 `repurchase_dummy` 存在缺失；
- 回购年数无法可靠确认；
- 股利年数无法可靠确认。

必须标记为：

```text
unclassifiable
```

不能把：

```text
rep_years = 缺失
```

归入：

```text
0 年回购
```

---

## 11. Table 1

### 11.1 四个重叠十年窗口

```text
1980–1989
1985–1994
1990–1999
1995–2004
```

每个窗口只保留：

```python
firm["payout_classifiable"] == True
```

的公司。

### 11.2 股利年份分组

```text
0
1–4
5–9
10
```

建议：

```python
def div_bucket_table1(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 4:
        return "1-4"
    if n <= 9:
        return "5-9"
    return "10"
```

注意：某公司即使只在窗口内存在 4 年且 4 年都支付股利，仍属于 `1–4`，不是 `10`。

### 11.3 回购年份分组

```text
0
1–4
5–10
```

建议：

```python
def rep_bucket_table1(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 4:
        return "1-4"
    return "5-10"
```

### 11.4 Panel A

报告每个 `3 × 4` 单元格中的：

1. 公司数；
2. 公司数占该窗口全部可分类公司的比例。

### 11.5 Panel B

对每家公司在窗口内的总支付进行累计：

\[
WindowPayout_i
=
\sum_{t\in window} TotalPayout_{it}
\]

再按支付分组加总：

\[
CellPayout_g
=
\sum_{i\in g} WindowPayout_i
\]

括号内报告该单元格支付占窗口内全部可分类公司总支付的比例。

公司年度总支付缺失时不得自动填 0。

---

## 12. Table 2

### 12.1 分析期

```text
1980–2005
```

仅保留在其实际存在公司年度中，股利和回购状态均完整可观察的公司。

### 12.2 股利与回购年份分组

两者均使用：

```text
0
1–5
6–10
11–15
16–20
>20
```

建议：

```python
def bucket_table2(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 5:
        return "1-5"
    if n <= 10:
        return "6-10"
    if n <= 15:
        return "11-15"
    if n <= 20:
        return "16-20"
    return ">20"
```

形成 `6 × 6` 公司数量表。

---

## 13. Group I–V 固定分类

分组基于完整的 1980–2005 长期支付历史，并仅对可分类公司定义。

### Group I：Non-payers

```text
DividendYears = 0
RepurchaseYears = 0
```

### Group II：Regular dividends + regular repurchases

```text
DividendYears >= 16
RepurchaseYears >= 11
```

### Group III：Occasional repurchases only

```text
DividendYears = 0
1 <= RepurchaseYears <= 5
```

### Group IV：Regular repurchases only

```text
DividendYears = 0
RepurchaseYears >= 6
```

### Group V：Dividend-only regular

```text
RepurchaseYears = 0
DividendYears >= 6
```

未满足以上任一条件的可分类公司记为：

```text
Other
```

存在支付状态缺失的公司记为：

```text
Unclassifiable
```

不能把 `Unclassifiable` 与 `Other` 混为一组。

建议：

```python
firm["group_id"] = pd.Series(pd.NA, index=firm.index, dtype="Int64")

classifiable = firm["payout_classifiable"]

firm.loc[
    classifiable
    & firm["div_years"].eq(0)
    & firm["rep_years"].eq(0),
    "group_id",
] = 1

firm.loc[
    classifiable
    & firm["div_years"].ge(16)
    & firm["rep_years"].ge(11),
    "group_id",
] = 2

firm.loc[
    classifiable
    & firm["div_years"].eq(0)
    & firm["rep_years"].between(1, 5, inclusive="both"),
    "group_id",
] = 3

firm.loc[
    classifiable
    & firm["div_years"].eq(0)
    & firm["rep_years"].ge(6),
    "group_id",
] = 4

firm.loc[
    classifiable
    & firm["rep_years"].eq(0)
    & firm["div_years"].ge(6),
    "group_id",
] = 5

firm.loc[
    classifiable
    & firm["group_id"].isna(),
    "group_id",
] = 0
```

其中：

```text
group_id = 0
```

表示可分类但不属于 Group I–V；

```text
group_id = NA
```

表示无法分类。

---

## 14. QA 输出

Codex 应生成以下诊断。

### 14.1 原始字段缺失率

按年份报告：

- `dvc` 缺失率；
- `tstkc` 缺失率；
- `prstkc` 缺失率；
- `sstk` 缺失率。

### 14.2 回购构造来源

按年份统计：

```text
treasury_stock_change
purchase_minus_issuance
missing_tstkc_pair
missing_cashflow_inputs
```

### 14.3 无法计算回购的原因

至少统计：

- 无准确 `fyear - 1`；
- 当期 `tstkc` 缺失；
- 上期 `tstkc` 缺失；
- 注销法下 `prstkc` 缺失；
- 注销法下 `sstk` 缺失；
- 注销法下二者均缺失。

### 14.4 可分类公司数量

分别报告：

- 每个 Table 1 窗口的公司总数；
- 可分类公司数；
- 无法分类公司数；
- 因股利缺失无法分类公司数；
- 因回购缺失无法分类公司数。

Table 2 同样报告上述数量。

### 14.5 与论文数字对照

输出：

- Table 1 每个窗口公司数；
- Table 2 总公司数；
- Table 2 各单元格公司数；
- Group I–V 当前公司数；
- 与论文公司数的差异。

---

## 15. Codex 修改要求

请 Codex 完成以下任务：

1. 删除 `dvc`、`tstkc`、`prstkc`、`sstk` 的无条件 `fillna(0)`。
2. 使用 `gvkey + fyear - 1` 精确匹配上年库存股。
3. 只有连续两年 `tstkc` 都真实为 0 时才识别注销法。
4. `prstkc` 与 `sstk` 任意一个缺失时，现金流净回购保持缺失。
5. 只把已经成功计算的负回购值设为 0。
6. `repurchase_dummy` 保留 1、0、缺失三种状态。
7. `dividend_dummy` 保留 1、0、缺失三种状态。
8. 增加支付变量有效年份数和缺失年份数。
9. 公司支付历史不完整时标记为无法分类，不得进入 0 年组。
10. Table 1、Table 2 只使用支付状态完整可分类的公司。
11. `total_payout` 只在股利和净回购均可观察时计算。
12. Group I–V 只对可分类公司定义。
13. 增加上述 QA 输出。
14. 不要修改论文规定的窗口、分组边界和 Group I–V 阈值。
15. 修改后运行脚本并确认所有表格、图形和回归仍可生成。

---

## 16. Table 1、Table 2 验收标准

- [ ] `dvc` 缺失未被填 0；
- [ ] `tstkc` 缺失未被填 0；
- [ ] `prstkc` 缺失未被填 0；
- [ ] `sstk` 缺失未被填 0；
- [ ] 上年库存股来自准确 `fyear - 1`；
- [ ] 只有连续两年真实 `tstkc = 0` 才识别注销法；
- [ ] 现金流法要求 `prstkc`、`sstk` 同时非缺失；
- [ ] 负回购设为 0，无法计算的回购保持缺失；
- [ ] `dividend_dummy` 与 `repurchase_dummy` 均保留缺失状态；
- [ ] 公司窗口内存在支付状态缺失时标记为无法分类；
- [ ] 无法分类公司未进入 0 年支付组；
- [ ] Table 1 使用四个正确的重叠十年窗口；
- [ ] Table 1 使用正确的 `3 × 4` 分组；
- [ ] Table 1 Panel B 使用可观察的股利加净回购；
- [ ] Table 2 使用 1980–2005 长期分类；
- [ ] Group I–V 仅对可分类公司固定定义；
- [ ] QA 输出完整。


---

# Skinner (2008) Table 3 变量清洗与样本构造规范

## 1. 目标

本文档用于指导 Codex 修改 `replicate_skinner_2008.py` 中与 Skinner (2008) Table 3 有关的数据清洗、变量构造和回归样本准备逻辑。

核心原则：

1. 原始变量缺失值默认保留为 `NaN`，不进行零填充或插值。
2. 滞后变量必须按同一公司、准确财政年度匹配，不能默认上一行就是上一期。
3. 构造变量时，只要任一必要输入缺失或分母无效，结果保持 `NaN`。
4. `Repurchase dummy` 必须保留三种状态：1、0、缺失。
5. 每个 Logit 规格按照自身变量集合进行完整案例删除，不要提前统一删除所有缺失观测。

---

## 2. 论文 Table 3 使用的核心变量

### 2.1 因变量

\[
RepurchaseDummy_{it}
=
\begin{cases}
1, & NetRepurchase_{it} > 0 \\
0, & NetRepurchase_{it} = 0 \\
NaN, & NetRepurchase_{it}\text{ 无法计算}
\end{cases}
\]

必须避免直接使用：

```python
(df["repurchase"] > 0).astype(int)
```

因为 `NaN > 0` 会变成 `False`，进而错误编码为 0。

正确写法：

```python
df["repurchase_dummy"] = np.select(
    [
        df["repurchase"].gt(0),
        df["repurchase"].eq(0),
    ],
    [
        1.0,
        0.0,
    ],
    default=np.nan,
)
```

---

## 3. ROA

### 3.1 原始字段

- `OIBDP`：Operating Income Before Depreciation
- `AT`：Assets - Total

### 3.2 构造公式

\[
ROA_{it}
=
\frac{OIBDP_{it}}{AT_{i,t-1}}
\]

### 3.3 计算条件

仅在以下条件全部满足时计算：

1. `oibdp_t` 非缺失；
2. `at_{t-1}` 非缺失；
3. `at_{t-1} > 0`；
4. `at_{t-1}` 来自同一 `gvkey` 的准确 `fyear - 1`。

否则：

```text
ROA = NaN
```

### 3.4 正确的滞后资产构造

不要直接使用：

```python
df.groupby("gvkey")["at"].shift(1)
```

因为公司年度可能不连续。

建议按 `gvkey + fyear` 精确匹配：

```python
lag_at = df[["gvkey", "fyear", "at"]].copy()
lag_at["fyear"] = lag_at["fyear"] + 1
lag_at = lag_at.rename(columns={"at": "at_lag1"})

df = df.merge(
    lag_at,
    on=["gvkey", "fyear"],
    how="left",
    validate="one_to_one",
)

df["roa"] = np.where(
    df["oibdp"].notna()
    & df["at_lag1"].notna()
    & df["at_lag1"].gt(0),
    df["oibdp"] / df["at_lag1"],
    np.nan,
)
```

---

## 4. Cash

### 4.1 原始字段

- `CHE`：Cash and Short-Term Investments
- `AT`：Assets - Total

### 4.2 构造公式

\[
Cash_{it}
=
\frac{CHE_{it}}{AT_{it}}
\]

### 4.3 计算条件

仅在以下条件全部满足时计算：

1. `che_t` 非缺失；
2. `at_t` 非缺失；
3. `at_t > 0`。

否则：

```text
Cash = NaN
```

建议代码：

```python
df["cash"] = np.where(
    df["che"].notna()
    & df["at"].notna()
    & df["at"].gt(0),
    df["che"] / df["at"],
    np.nan,
)
```

注意：

- ROA 使用滞后总资产；
- Cash 使用当期总资产。

---

## 5. Past stock return

### 5.1 原始字段

- `PRCC_F`：Price Close - Annual - Fiscal Year
- `AJEX`：累计拆股调整因子

### 5.2 拆股调整价格

\[
AdjustedPrice_{it}
=
\frac{PRCC\_F_{it}}{AJEX_{it}}
\]

仅在以下条件满足时计算：

1. `prcc_f` 非缺失；
2. `ajex` 非缺失；
3. `ajex > 0`；
4. 调整后价格有效。

建议代码：

```python
df["adjusted_price"] = np.where(
    df["prcc_f"].notna()
    & df["ajex"].notna()
    & df["ajex"].gt(0),
    df["prcc_f"] / df["ajex"],
    np.nan,
)
```

不要无条件使用：

```python
abs(prcc_f)
```

若出现异常负价格，先保留缺失或单独核查，不要自动取绝对值而不说明。

### 5.3 三年股票收益率

\[
PastStockReturn_{it}
=
\frac{AdjustedPrice_{it}}
{AdjustedPrice_{i,t-3}}-1
\]

必须使用同一公司准确的 `fyear - 3`。

建议代码：

```python
lag_price = df[
    ["gvkey", "fyear", "adjusted_price"]
].copy()

lag_price["fyear"] = lag_price["fyear"] + 3

lag_price = lag_price.rename(
    columns={
        "adjusted_price": "adjusted_price_lag3"
    }
)

df = df.merge(
    lag_price,
    on=["gvkey", "fyear"],
    how="left",
    validate="one_to_one",
)

df["past_stock_return"] = np.where(
    df["adjusted_price"].notna()
    & df["adjusted_price_lag3"].notna()
    & df["adjusted_price_lag3"].gt(0),
    df["adjusted_price"]
    / df["adjusted_price_lag3"]
    - 1,
    np.nan,
)
```

### 5.4 以下任一条件出现时，Past stock return 必须保持缺失

- 当期 `PRCC_F` 缺失；
- 当期 `AJEX` 缺失；
- 当期 `AJEX <= 0`；
- 三年前 `PRCC_F` 缺失；
- 三年前 `AJEX` 缺失；
- 三年前 `AJEX <= 0`；
- 同一公司不存在准确的 `fyear - 3`；
- 三年前调整后价格不大于 0；
- 当期或三年前调整后价格无效。

禁止：

- 使用最近可得年份替代 `fyear - 3`；
- 对价格做线性插值；
- 对收益率做插值；
- 将缺失收益率填 0。

---

## 6. ESO dilution

### 6.1 原始字段

- `XINTOPT`：Implied Option Expense
- `SALE`：Sales/Turnover
- `Past stock return`

### 6.2 构造公式

\[
ESODilution_{it}
=
\frac{XINTOPT_{it}}{SALE_{it}}
\times PastStockReturn_{it}
\]

### 6.3 计算条件

仅在以下条件全部满足时计算：

1. `xintopt` 非缺失；
2. `sale` 非缺失；
3. `sale > 0`；
4. `past_stock_return` 非缺失。

否则：

```text
ESO dilution = NaN
```

建议代码：

```python
df["eso_dilution"] = np.where(
    df["xintopt"].notna()
    & df["sale"].notna()
    & df["sale"].gt(0)
    & df["past_stock_return"].notna(),
    (df["xintopt"] / df["sale"])
    * df["past_stock_return"],
    np.nan,
)
```

其他要求：

- `xintopt` 缺失不能填 0；
- 1995 年以前的 ESO 数据保持缺失；
- 1980–1994 的回归不加入 ESO；
- 1995–2005 的第三列规格加入 ESO。

---

## 7. Panel B 额外变量

### 7.1 Regular dummy

\[
Regular_i=
\begin{cases}
1,& i\in Group\ IV\\
0,& i\in Group\ III
\end{cases}
\]

定义：

- Group III：不支付股利，1980–2005 年回购 1–5 年；
- Group IV：不支付股利，1980–2005 年回购至少 6 年。

建议：

```python
df["regular_dummy"] = np.where(
    df["group_id"].eq(4),
    1.0,
    np.where(
        df["group_id"].eq(3),
        0.0,
        np.nan,
    ),
)
```

不要对 Group II 或其他组强行赋值 0。

### 7.2 ROA × Regular

\[
ROARegular_{it}
=
ROA_{it}
\times Regular_i
\]

建议：

```python
df["roa_regular"] = (
    df["roa"] * df["regular_dummy"]
)
```

当 `roa` 或 `regular_dummy` 缺失时，交互项也应缺失。

---

## 8. Table 3 样本分组

### 8.1 Panel A

样本为 Group II：

\[
DividendYears \ge 16
\]

且

\[
RepurchaseYears \ge 11
\]

分时段估计：

- 1980–1994；
- 1995–2005；
- 1995–2005，加入 ESO dilution。

### 8.2 Panel B

样本为 Group III 和 Group IV：

- Group III：`DividendYears = 0` 且 `1 <= RepurchaseYears <= 5`
- Group IV：`DividendYears = 0` 且 `RepurchaseYears >= 6`

分时段估计：

- 1980–1994；
- 1995–2005；
- 1995–2005，加入 ESO dilution。

---

## 9. 回归样本删除规则

不要在整个数据集层面一次性删除所有缺失变量。

必须按每个回归规格分别进行完整案例删除。

### 9.1 Panel A，不含 ESO

所需变量：

```python
[
    "repurchase_dummy",
    "roa",
    "past_stock_return",
    "cash",
]
```

### 9.2 Panel A，含 ESO

所需变量：

```python
[
    "repurchase_dummy",
    "roa",
    "past_stock_return",
    "cash",
    "eso_dilution",
]
```

### 9.3 Panel B，不含 ESO

所需变量：

```python
[
    "repurchase_dummy",
    "regular_dummy",
    "roa",
    "roa_regular",
    "past_stock_return",
    "cash",
]
```

### 9.4 Panel B，含 ESO

所需变量：

```python
[
    "repurchase_dummy",
    "regular_dummy",
    "roa",
    "roa_regular",
    "past_stock_return",
    "cash",
    "eso_dilution",
]
```

建议封装：

```python
def prepare_logit_sample(
    data: pd.DataFrame,
    required_cols: list[str],
) -> pd.DataFrame:
    return (
        data[required_cols]
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
        .copy()
    )
```

---

## 10. 明确禁止的处理

以下做法均应禁止：

```python
df["oibdp"] = df["oibdp"].fillna(0)
df["at"] = df["at"].fillna(0)
df["che"] = df["che"].fillna(0)
df["prcc_f"] = df["prcc_f"].fillna(0)
df["ajex"] = df["ajex"].fillna(1)
df["xintopt"] = df["xintopt"].fillna(0)
df["past_stock_return"] = df["past_stock_return"].fillna(0)
df["eso_dilution"] = df["eso_dilution"].fillna(0)
```

也禁止：

```python
df.groupby("gvkey")["at"].shift(1)
```

直接作为滞后资产而不检查财政年度是否连续。

同样禁止：

```python
(df["repurchase"] > 0).astype(int)
```

因为这会把缺失净回购错误编码为 0。

---

## 11. 建议增加的 QA 输出

Codex 应增加以下诊断输出，用于验证清洗是否正确。

### 11.1 变量覆盖率

按年份统计：

- `roa` 非缺失比例；
- `cash` 非缺失比例；
- `adjusted_price` 非缺失比例；
- `past_stock_return` 非缺失比例；
- `eso_dilution` 非缺失比例；
- `repurchase_dummy` 非缺失比例。

### 11.2 连续年度检查

输出：

- 因缺少 `fyear - 1` 无法构造 ROA 的公司年数量；
- 因缺少 `fyear - 3` 无法构造 Past stock return 的公司年数量。

### 11.3 分母无效检查

输出：

- `at_lag1 <= 0` 的数量；
- `at <= 0` 的数量；
- `sale <= 0` 的数量；
- `ajex <= 0` 的数量；
- `adjusted_price_lag3 <= 0` 的数量。

### 11.4 回归样本数量

逐个模型输出最终样本量，并与论文 Table 3 的观测数对照：

Panel A：

- 1980–1994；
- 1995–2005；
- 1995–2005 + ESO。

Panel B：

- 1980–1994；
- 1995–2005；
- 1995–2005 + ESO。

---

## 12. Codex 修改要求

请 Codex 完成以下任务：

1. 检查 `clean_and_construct()` 中 ROA、Cash、Adjusted Price、Past stock return、ESO dilution 的当前构造。
2. 将所有普通 `shift(1)` 滞后资产逻辑改为 `gvkey + fyear - 1` 精确匹配。
3. 保证 Past stock return 使用同一公司准确 `fyear - 3`。
4. 删除上述 Table 3 原始变量的零填充或插值。
5. 修改 `repurchase_dummy`，保留净回购缺失状态。
6. 修改 `regular_dummy`，仅在 Group III 和 Group IV 内赋值。
7. 保证 `roa_regular` 在任何必要输入缺失时保持缺失。
8. 保证每个 Logit 规格按自身变量集合单独 `dropna()`。
9. 增加 QA 输出和回归样本数量核验。
10. 不改变 Table 1、Table 2、Figure 1–3 的其他既有逻辑，除非变量共享部分确实依赖上述修正。
11. 修改后运行脚本，确认：
    - 无重复键错误；
    - 无除零警告；
    - 无无限值进入回归；
    - Table 3 六个规格均能正常估计；
    - 输出文件成功生成。

---

## 13. 最终验收标准

满足以下条件才视为 Table 3 变量清洗完成：

- [ ] OIBDP、AT、PRCC_F、AJEX、CHE、XINTOPT、SALE 缺失值均未被零填充；
- [ ] ROA 仅使用准确 `fyear - 1` 的滞后资产；
- [ ] Cash 使用当期 `CHE / AT`；
- [ ] Past stock return 仅使用准确 `fyear - 3`；
- [ ] ESO dilution 仅在 XINTOPT、SALE、Past stock return 均有效时计算；
- [ ] Repurchase dummy 保留缺失状态；
- [ ] Regular dummy 仅在 Group III 和 Group IV 内定义；
- [ ] ROA × Regular 在输入缺失时保持缺失；
- [ ] 每个模型独立进行完整案例删除；
- [ ] 输出覆盖率、连续年度、分母有效性和样本量 QA；
- [ ] 六个 Table 3 Logit 规格全部成功运行。


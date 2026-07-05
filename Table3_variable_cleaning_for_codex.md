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

# XINTOPT 缺失来源审计表

本表用于审计 Table 3 的 1995-2005 ESO 样本从 Compustat 公司年到最终样本的逐步流失。
脚本只做审计，不修改主复现脚本或正式回归结果。

## 总样本逐步审计

|   step | condition                                            |   firm_years |   dropped_from_previous |   retained_rate_from_previous |   cumulative_rate_from_first_step |
|-------:|:-----------------------------------------------------|-------------:|------------------------:|------------------------------:|----------------------------------:|
|      1 | 1995-2005 所有 Compustat 公司年                      |       115966 |                       0 |                    nan        |                         1         |
|      2 | 满足 C/INDL/STD、USD、USA、非金融非公用事业          |        75668 |                   40298 |                      0.652502 |                         0.652502  |
|      3 | Group II / III / IV（V2 当前 CRSP/CCM 主样本分组后） |        20459 |                   55209 |                      0.270378 |                         0.176422  |
|      4 | repurchase_dummy 有效                                |        18147 |                    2312 |                      0.886993 |                         0.156486  |
|      5 | ROA 有效                                             |        18092 |                      55 |                      0.996969 |                         0.156011  |
|      6 | past_stock_return 有效                               |        15612 |                    2480 |                      0.862923 |                         0.134626  |
|      7 | cash 有效                                            |        15608 |                       4 |                      0.999744 |                         0.134591  |
|      8 | at > 0                                               |        15608 |                       0 |                      1        |                         0.134591  |
|      9 | xintopt 非缺失                                       |        10086 |                    5522 |                      0.646207 |                         0.0869738 |
|     10 | final ESO sample（含 at>0 审计口径）                 |        10086 |                       0 |                      1        |                         0.0869738 |

## Panel A / Panel B 分组审计

| panel                 |   step | condition                            |   firm_years |   dropped_from_previous |   retained_rate_from_previous |   cumulative_rate_from_panel_first_step |
|:----------------------|-------:|:-------------------------------------|-------------:|------------------------:|------------------------------:|----------------------------------------:|
| Panel A: Group II     |      1 | Group II / III / IV                  |         3036 |                       0 |                    nan        |                                1        |
| Panel A: Group II     |      2 | repurchase_dummy 有效                |         3016 |                      20 |                      0.993412 |                                0.993412 |
| Panel A: Group II     |      3 | ROA 有效                             |         3006 |                      10 |                      0.996684 |                                0.990119 |
| Panel A: Group II     |      4 | past_stock_return 有效               |         3006 |                       0 |                      1        |                                0.990119 |
| Panel A: Group II     |      5 | cash 有效                            |         3002 |                       4 |                      0.998669 |                                0.988801 |
| Panel A: Group II     |      6 | at > 0                               |         3002 |                       0 |                      1        |                                0.988801 |
| Panel A: Group II     |      7 | xintopt 非缺失                       |         2357 |                     645 |                      0.785143 |                                0.77635  |
| Panel A: Group II     |      8 | final ESO sample（含 at>0 审计口径） |         2357 |                       0 |                      1        |                                0.77635  |
| Panel B: Group III/IV |      1 | Group II / III / IV                  |        17423 |                       0 |                    nan        |                                1        |
| Panel B: Group III/IV |      2 | repurchase_dummy 有效                |        15131 |                    2292 |                      0.86845  |                                0.86845  |
| Panel B: Group III/IV |      3 | ROA 有效                             |        15086 |                      45 |                      0.997026 |                                0.865867 |
| Panel B: Group III/IV |      4 | past_stock_return 有效               |        12606 |                    2480 |                      0.835609 |                                0.723526 |
| Panel B: Group III/IV |      5 | cash 有效                            |        12606 |                       0 |                      1        |                                0.723526 |
| Panel B: Group III/IV |      6 | at > 0                               |        12606 |                       0 |                      1        |                                0.723526 |
| Panel B: Group III/IV |      7 | xintopt 非缺失                       |         7729 |                    4877 |                      0.613121 |                                0.443609 |
| Panel B: Group III/IV |      8 | final ESO sample（含 at>0 审计口径） |         7729 |                       0 |                      1        |                                0.443609 |

说明：`at > 0` 与 V2 当前正式 ESO dilution 计算口径一致，即 `xintopt / at * past_stock_return`。

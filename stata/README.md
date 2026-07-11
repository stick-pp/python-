# Skinner (2008) Table 3 Stata Task

This directory contains the Stata-only Table 3 runner for the `task/stata`
worktree.

## Files

```text
stata/table3_replication.do
stata/run_table3_stata.ps1
stata/README.md
```

## Inputs

The runner reads Python-exported final Table 3 regression data from:

```text
shared_artifacts/python_out/stata
```

Input priority:

```text
table3_regression_data.dta
table3_regression_data.csv
```

The runner also requires:

```text
shared_artifacts/python_out/manifest.csv
shared_artifacts/python_out/tables/qa_table3_regression_sample_counts.csv
```

The input data must already contain Python-defined variables and sample flags:

```text
repurchase_dummy regular_dummy roa roa_regular past_stock_return cash eso_dilution
sample_A_1980_1994 sample_A_1995_2005 sample_A_1995_2005_eso
sample_B_1980_1994 sample_B_1995_2005 sample_B_1995_2005_eso
```

## Run

Run from the `worktrees/stata` worktree root:

```powershell
.\stata\run_table3_stata.ps1
```

Or run from this directory:

```powershell
.\run_table3_stata.ps1
```

Outputs are written to:

```text
shared_artifacts/stata_out
```

Main outputs:

```text
table3_stata_results.csv
table3_stata_results.dta
table3_stata_sample_counts.csv
table3_stata_python_sample_check.csv
table3_stata.log
table3_stata_run_summary.txt
```

## Boundary

The Stata code does not clean Compustat raw fields, redefine Group I-V, screen
industries, or generate lagged variables. It uses only Python-exported sample
flags and does not fall back to `group_id`/`fyear` sample construction.

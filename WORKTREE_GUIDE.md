# Skinner (2008) Worktree Workflow

This project is split into three isolated Git worktrees so each subtask can be handled in a separate chat without editing the same files in the same working directory.

## Worktrees

- `worktrees/python`
  - Branch: `task/python`
  - Responsibility: data cleaning, variable construction, Figure 1-3 source data, and table source files as CSV/XLSX.
  - Should not produce the final PDF.

- `worktrees/stata`
  - Branch: `task/stata`
  - Responsibility: Table 3 regressions from Python-exported regression data.
  - Should not rebuild raw Compustat variables or redefine samples independently.

- `worktrees/latex`
  - Branch: `task/latex`
  - Responsibility: academic tables, figures assembled from exported files, and final PDF generation.
  - Should not change Python cleaning logic or Stata regression logic.

## Sequential Flow

1. Python worktree exports cleaned analysis files to `shared_artifacts/python_out/`.
2. Stata worktree reads the Python regression data and exports Table 3 results to `shared_artifacts/stata_out/`.
3. LaTeX worktree reads the Python and Stata artifacts and builds the final report in `shared_artifacts/latex_out/`.

## Conflict Control

- Edit Python source only in `worktrees/python`.
- Edit Stata do-files and regression formatting only in `worktrees/stata`.
- Edit LaTeX tables, captions, and report source only in `worktrees/latex`.
- Merge changes back to `main` only after each stage has been verified.
- Do not edit the same file from multiple worktrees unless deliberately coordinating a merge.

## Data Handling

- Raw data files `2.csv` and `ajex.csv` are intentionally ignored by Git.
- If a worktree needs raw data, use local links or copies created outside Git tracking.
- Generated outputs are intentionally ignored by Git and should be passed through `shared_artifacts/`.

version 18.0
clear all
set more off

capture log close

local data_dta : environment SKINNER_TABLE3_DTA
local data_csv : environment SKINNER_TABLE3_CSV
local out_dir : environment SKINNER_STATA_OUT

if "`out_dir'" == "" {
    local out_dir "../../shared_artifacts/stata_out"
}

capture mkdir "`out_dir'"

log using "`out_dir'/table3_stata.log", replace text

display as text "Skinner (2008) Table 3 Stata replication"
display as text "Input DTA: `data_dta'"
display as text "Input CSV: `data_csv'"
display as text "Output directory: `out_dir'"

if "`data_dta'" != "" {
    capture confirm file "`data_dta'"
    if _rc {
        display as error "Missing Python-exported regression DTA: `data_dta'"
        exit 601
    }
    use "`data_dta'", clear
}
else if "`data_csv'" != "" {
    capture confirm file "`data_csv'"
    if _rc {
        display as error "Missing Python-exported regression CSV: `data_csv'"
        exit 601
    }
    import delimited using "`data_csv'", clear varnames(1)
}
else {
    display as error "No Python regression data was supplied. Set SKINNER_TABLE3_DTA or SKINNER_TABLE3_CSV."
    exit 601
}

capture confirm variable sample_A_1980_1994
if !_rc rename sample_A_1980_1994 sample_a_1980_1994
capture confirm variable sample_A_1995_2005
if !_rc rename sample_A_1995_2005 sample_a_1995_2005
capture confirm variable sample_A_1995_2005_eso
if !_rc rename sample_A_1995_2005_eso sample_a_1995_2005_eso
capture confirm variable sample_B_1980_1994
if !_rc rename sample_B_1980_1994 sample_b_1980_1994
capture confirm variable sample_B_1995_2005
if !_rc rename sample_B_1995_2005 sample_b_1995_2005
capture confirm variable sample_B_1995_2005_eso
if !_rc rename sample_B_1995_2005_eso sample_b_1995_2005_eso

local required_vars ///
    gvkey fyear group_id repurchase_dummy regular_dummy roa roa_regular ///
    past_stock_return cash eso_dilution ///
    sample_a_1980_1994 sample_a_1995_2005 sample_a_1995_2005_eso ///
    sample_b_1980_1994 sample_b_1995_2005 sample_b_1995_2005_eso

foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        display as error "Required Python-exported variable is missing: `v'"
        exit 111
    }
}

assert inlist(repurchase_dummy, 0, 1) if !missing(repurchase_dummy)
foreach flag in sample_a_1980_1994 sample_a_1995_2005 sample_a_1995_2005_eso ///
    sample_b_1980_1994 sample_b_1995_2005 sample_b_1995_2005_eso {
    assert inlist(`flag', 0, 1) if !missing(`flag')
}

capture postclose results
postfile results str8 panel str16 model str24 term double coef se p pseudo_r2 N y1 y0 ///
    using "`out_dir'/table3_stata_results.dta", replace

capture postclose samples
postfile samples str8 panel str16 model double N y1 y0 using "`out_dir'/table3_stata_sample_counts.dta", replace

program define post_one_model
    syntax, Panel(string) Model(string) Terms(string)
    local r2 = e(r2_p)
    local n = e(N)
    quietly summarize repurchase_dummy if e(sample), meanonly
    local y1 = r(sum)
    local y0 = `n' - `y1'

    foreach t of local terms {
        local b = .
        local s = .
        local p = .
        capture local b = _b[`t']
        if _rc == 0 {
            capture local s = _se[`t']
            if _rc == 0 & `s' < . & `s' > 0 {
                local p = 2 * normal(-abs(`b' / `s'))
            }
        }
        post results ("`panel'") ("`model'") ("`t'") (`b') (`s') (`p') (`r2') (`n') (`y1') (`y0')
    }
    post samples ("`panel'") ("`model'") (`n') (`y1') (`y0')
end

program define require_estimable_sample
    syntax, Flag(name) Y(name)
    quietly count if `flag' == 1
    if r(N) == 0 {
        display as error "No observations in Python sample flag: `flag'"
        exit 2000
    }
    quietly levelsof `y' if `flag' == 1, local(y_levels)
    local n_levels : word count `y_levels'
    if `n_levels' < 2 {
        display as error "Dependent variable has fewer than two classes in Python sample flag: `flag'"
        exit 2001
    }
end

local terms_a "_cons roa past_stock_return cash eso_dilution"
local terms_b "_cons regular_dummy roa roa_regular past_stock_return cash eso_dilution"

require_estimable_sample, flag(sample_a_1980_1994) y(repurchase_dummy)
quietly logit repurchase_dummy roa past_stock_return cash if sample_a_1980_1994 == 1
post_one_model, panel("Panel A") model("1980-1994") terms("`terms_a'")

require_estimable_sample, flag(sample_a_1995_2005) y(repurchase_dummy)
quietly logit repurchase_dummy roa past_stock_return cash if sample_a_1995_2005 == 1
post_one_model, panel("Panel A") model("1995-2005") terms("`terms_a'")

require_estimable_sample, flag(sample_a_1995_2005_eso) y(repurchase_dummy)
quietly logit repurchase_dummy roa past_stock_return cash eso_dilution if sample_a_1995_2005_eso == 1
post_one_model, panel("Panel A") model("1995-2005 ESO") terms("`terms_a'")

require_estimable_sample, flag(sample_b_1980_1994) y(repurchase_dummy)
quietly logit repurchase_dummy regular_dummy roa roa_regular past_stock_return cash if sample_b_1980_1994 == 1
post_one_model, panel("Panel B") model("1980-1994") terms("`terms_b'")

require_estimable_sample, flag(sample_b_1995_2005) y(repurchase_dummy)
quietly logit repurchase_dummy regular_dummy roa roa_regular past_stock_return cash if sample_b_1995_2005 == 1
post_one_model, panel("Panel B") model("1995-2005") terms("`terms_b'")

require_estimable_sample, flag(sample_b_1995_2005_eso) y(repurchase_dummy)
quietly logit repurchase_dummy regular_dummy roa roa_regular past_stock_return cash eso_dilution if sample_b_1995_2005_eso == 1
post_one_model, panel("Panel B") model("1995-2005 ESO") terms("`terms_b'")

postclose results
postclose samples

use "`out_dir'/table3_stata_results.dta", clear
export delimited using "`out_dir'/table3_stata_results.csv", replace

use "`out_dir'/table3_stata_sample_counts.dta", clear
export delimited using "`out_dir'/table3_stata_sample_counts.csv", replace

display as text "Table 3 Stata regression completed."
log close

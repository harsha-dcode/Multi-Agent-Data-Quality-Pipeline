import pandas as pd
import numpy as np
import re
from datetime import datetime

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

INPUT = str(_HERE / "input" / "house_50k_sample.csv")
OUT = str(_HERE / "01_profile_report.txt")

df = pd.read_csv(INPUT, encoding="utf-8", dtype=str, keep_default_na=False)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(f"Rows: {len(df)}  Cols: {len(df.columns)}\n\n")

    # numeric columns to profile as float
    plain_numeric_cols = ["bedrooms","bathrooms","floors","parking_spots","built_year",
        "total_area","land_area","latitude","longitude","postal_code",
        "interest_rate","inflation_index","housing_index","luxury_demand_index",
        "final_sale_price","price_per_sqm","property_tax","days_on_market",
        "price_revision_count"] + [f"noise_{i}" for i in range(15)]

    f.write("=== NUMERIC COLUMN STATS (plain, no currency prefix expected) ===\n")
    for c in plain_numeric_cols:
        s = pd.to_numeric(df[c], errors="coerce")
        n_unparseable = s.isna().sum()
        f.write(f"\n{c}: n={s.notna().sum()} unparseable={n_unparseable} "
                f"min={s.min()} max={s.max()} mean={s.mean():.4f} median={s.median():.4f} "
                f"std={s.std():.4f} skew={s.skew():.4f} negatives={(s<0).sum()} zeros={(s==0).sum()}\n")

    # currency-prefixed columns: listing_price, hoa_fee
    f.write("\n\n=== listing_price: currency symbol vs `currency` column agreement ===\n")
    sym_pat = re.compile(r"^(₹|£|\$|€|AED)")
    def extract_sym(v):
        m = sym_pat.match(v)
        return m.group(1) if m else None
    lp_sym = df["listing_price"].apply(extract_sym)
    mismatches = (lp_sym != df["currency"]).sum()
    none_found = lp_sym.isna().sum()
    f.write(f"rows where listing_price symbol present: {lp_sym.notna().sum()}, missing symbol: {none_found}\n")
    f.write(f"rows where symbol != currency column: {mismatches}\n")
    lp_num = df["listing_price"].str.replace(sym_pat, "", regex=True)
    lp_num = pd.to_numeric(lp_num, errors="coerce")
    f.write(f"listing_price numeric parse failures after stripping symbol: {lp_num.isna().sum()}\n")
    f.write(f"listing_price stats: min={lp_num.min()} max={lp_num.max()} mean={lp_num.mean():.2f} median={lp_num.median():.2f} negatives={(lp_num<0).sum()}\n")

    f.write("\n\n=== hoa_fee: currency-prefix presence pattern ===\n")
    hoa_sym = df["hoa_fee"].apply(extract_sym)
    f.write(f"rows WITH currency prefix: {hoa_sym.notna().sum()}\n")
    f.write(f"rows WITHOUT currency prefix (bare number): {hoa_sym.isna().sum()}\n")
    mismatches_hoa = ((hoa_sym.notna()) & (hoa_sym != df["currency"])).sum()
    f.write(f"rows where hoa_fee HAS a prefix that != currency column: {mismatches_hoa}\n")
    hoa_num = df["hoa_fee"].str.replace(sym_pat, "", regex=True)
    hoa_num = pd.to_numeric(hoa_num, errors="coerce")
    f.write(f"hoa_fee numeric parse failures after stripping symbol: {hoa_num.isna().sum()}\n")
    f.write(f"hoa_fee stats: min={hoa_num.min()} max={hoa_num.max()} mean={hoa_num.mean():.2f} median={hoa_num.median():.2f} negatives={(hoa_num<0).sum()}\n")

    # lat/long range check
    f.write("\n\n=== Lat/Long range sanity ===\n")
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    f.write(f"latitude range [{lat.min()}, {lat.max()}] out-of-range(<-90 or >90): {((lat<-90)|(lat>90)).sum()}\n")
    f.write(f"longitude range [{lon.min()}, {lon.max()}] out-of-range(<-180 or >180): {((lon<-180)|(lon>180)).sum()}\n")
    f.write(f"negative latitude count: {(lat<0).sum()}, negative longitude count: {(lon<0).sum()}\n")

    # built_year sanity vs current date
    f.write("\n\n=== built_year sanity ===\n")
    by = pd.to_numeric(df["built_year"], errors="coerce")
    CURRENT_YEAR = 2026
    f.write(f"built_year range [{by.min()}, {by.max()}]\n")
    f.write(f"built_year > {CURRENT_YEAR} (future, impossible): {(by>CURRENT_YEAR).sum()}\n")
    f.write(f"built_year < 1800 (implausible): {(by<1800).sum()}\n")

    # listing_date parse
    f.write("\n\n=== listing_date parse (DD-MM-YYYY expected) ===\n")
    parsed = pd.to_datetime(df["listing_date"], format="%d-%m-%Y", errors="coerce")
    f.write(f"unparseable under DD-MM-YYYY: {parsed.isna().sum()}\n")
    f.write(f"date range: {parsed.min()} to {parsed.max()}\n")
    future_dates = (parsed > pd.Timestamp("2026-07-29")).sum()
    f.write(f"listing_date in the future (> 2026-07-29): {future_dates}\n")

    # property_id duplicates
    f.write("\n\n=== Duplicate check ===\n")
    f.write(f"property_id nunique: {df['property_id'].nunique()} of {len(df)}\n")
    full_row_dupe_mask = df.duplicated(keep=False)
    f.write(f"full-row duplicate rows (all cols identical, incl copies): {full_row_dupe_mask.sum()}\n")
    f.write(f"full-row duplicate GROUPS beyond first occurrence (rows to remove): {df.duplicated(keep='first').sum()}\n")
    id_dupe_count = df['property_id'].duplicated(keep='first').sum()
    f.write(f"property_id duplicated (excess beyond first): {id_dupe_count}\n")

    # total_area negative & outlier
    f.write("\n\n=== total_area sign-flip & outlier diagnostics ===\n")
    ta = pd.to_numeric(df["total_area"], errors="coerce")
    f.write(f"total_area negatives: {(ta<0).sum()}\n")
    med_ta = ta[ta>0].median()
    f.write(f"total_area median (positive only): {med_ta:.4f}\n")
    f.write(f"total_area >10x median: {(ta.abs()>10*med_ta).sum()} ({(ta.abs()>10*med_ta).mean()*100:.2f}%)\n")

    # cross check: for negative total_area rows, does price_per_sqm ~ final_sale_price/abs(total_area)?
    neg_mask = ta < 0
    fsp = pd.to_numeric(df["final_sale_price"], errors="coerce")
    pps = pd.to_numeric(df["price_per_sqm"], errors="coerce")
    implied_pps_from_abs = fsp[neg_mask] / ta[neg_mask].abs()
    actual_pps = pps[neg_mask]
    ratio = actual_pps / implied_pps_from_abs
    f.write(f"For negative total_area rows: price_per_sqm / (final_sale_price/abs(total_area)) ratio stats: "
            f"mean={ratio.mean():.4f} median={ratio.median():.4f} min={ratio.min():.4f} max={ratio.max():.4f}\n")

    # final_sale_price cross check against listing_price for >10x median candidates
    f.write("\n\n=== final_sale_price decimal-typo candidate cross-check (per feedback-outlier-judgment) ===\n")
    med_fsp = fsp.median()
    cand_mask = fsp > 10*med_fsp
    f.write(f"final_sale_price median: {med_fsp:.2f}\n")
    f.write(f"candidates (>10x median): {cand_mask.sum()}\n")
    ratio_to_listing = fsp[cand_mask] / lp_num[cand_mask]
    f.write(f"final_sale_price/listing_price ratio for candidates: min={ratio_to_listing.min():.4f} "
            f"max={ratio_to_listing.max():.4f} mean={ratio_to_listing.mean():.4f} median={ratio_to_listing.median():.4f}\n")
    # normal population ratio for comparison
    normal_ratio = fsp[~cand_mask] / lp_num[~cand_mask]
    f.write(f"final_sale_price/listing_price ratio for NON-candidates (normal pop): min={normal_ratio.min():.4f} "
            f"max={normal_ratio.max():.4f} mean={normal_ratio.mean():.4f} median={normal_ratio.median():.4f}\n")
    in_band = ((ratio_to_listing >= normal_ratio.quantile(0.01)) & (ratio_to_listing <= normal_ratio.quantile(0.99))).sum()
    f.write(f"candidates whose ratio falls within normal population's 1st-99th pct band: {in_band} of {cand_mask.sum()}\n")

    # price_per_sqm candidates cross check
    f.write("\n\n=== price_per_sqm decimal-typo candidate cross-check ===\n")
    med_pps = pps.median()
    cand_pps = pps > 10*med_pps
    f.write(f"price_per_sqm median: {med_pps:.2f}\n")
    f.write(f"candidates (>10x median): {cand_pps.sum()} ({cand_pps.mean()*100:.2f}%)\n")
    implied_pps = fsp / ta.abs()
    ratio_pps = pps[cand_pps] / implied_pps[cand_pps]
    f.write(f"price_per_sqm / (final_sale_price/abs(total_area)) ratio for candidates: "
            f"min={ratio_pps.min():.4f} max={ratio_pps.max():.4f} mean={ratio_pps.mean():.4f} median={ratio_pps.median():.4f}\n")

    # currency vs country chi-square
    f.write("\n\n=== currency vs country independence (chi-square) ===\n")
    from scipy.stats import chi2_contingency
    ct = pd.crosstab(df["country"], df["currency"])
    chi2, p, dof, exp = chi2_contingency(ct)
    f.write(f"chi2={chi2:.4f} p={p:.4f} dof={dof}\n")
    f.write(ct.to_string() + "\n")

    # city fuzzy collision check (Munich/München, Sao Paulo/São Paulo)
    f.write("\n\n=== City collision guard (token_sort_ratio) ===\n")
    from rapidfuzz import fuzz
    pairs = [("Munich","München"), ("Sao Paulo","São Paulo")]
    for a,b in pairs:
        f.write(f"token_sort_ratio('{a}','{b}') = {fuzz.token_sort_ratio(a,b)}\n")

print("done")

"""
data_processor.py
------------------
Loads an uploaded Excel workbook, auto-detects the real header row
(handles the common case where the sheet has a blank first column /
title rows above the actual table), cleans the data, and computes
summary insights used by the dashboard.

Expected (but flexible) columns per sheet:
    Period, Region, Product ID, Customer ID, Sales $ / Forecast $, Sales KG / Forecast KG
"""

import pandas as pd
import numpy as np


def _find_header_row(raw: pd.DataFrame, keyword: str = "Period", max_scan: int = 5) -> int:
    """Scan the first few rows of a headerless read to find the row that
    actually contains the column names (looks for a 'Period' cell)."""
    for i in range(min(max_scan, len(raw))):
        row_values = raw.iloc[i].astype(str)
        if row_values.str.contains(keyword, case=False, na=False).any():
            return i
    return 0


def load_workbook(filepath: str) -> dict:
    """Reads every sheet in the workbook and returns {sheet_name: cleaned_dataframe}."""
    xl = pd.ExcelFile(filepath)
    sheets = {}
    for name in xl.sheet_names:
        raw = pd.read_excel(xl, sheet_name=name, header=None, nrows=10)
        header_row = _find_header_row(raw)

        df = pd.read_excel(xl, sheet_name=name, header=header_row)
        # drop fully-empty / "Unnamed" columns created by blank leading columns
        df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
        df = df.dropna(how="all")
        df.columns = [str(c).strip() for c in df.columns]
        sheets[name] = df
    return sheets


def identify_value_column(df: pd.DataFrame) -> str:
    """Finds the $ value column in a sheet (e.g. 'Sales $' or 'Forecast $')."""
    for col in df.columns:
        if "$" in col:
            return col
    raise ValueError(f"No currency ($) column found among: {list(df.columns)}")


def prepare(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Type-cleans a sheet: parses Period (YYYYMM) into a real date, coerces
    numeric columns, and drops unusable rows."""
    df = df.copy()
    df["Period"] = df["Period"].astype(str).str.strip()
    df["period_dt"] = pd.to_datetime(df["Period"], format="%Y%m", errors="coerce")
    df = df.dropna(subset=["period_dt"])
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
    for col in df.columns:
        if col.endswith("KG"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def compute_insights(df: pd.DataFrame, value_col: str, top_n: int = 10) -> dict:
    """Builds all the summary numbers/tables the dashboard needs."""
    monthly = df.groupby("period_dt")[value_col].sum().sort_index()

    by_region = df.groupby("Region")[value_col].sum().sort_values(ascending=False)

    by_product = (
        df.groupby("Product ID")[value_col].sum().sort_values(ascending=False).head(top_n)
    )

    by_customer = (
        df.groupby("Customer ID")[value_col].sum().sort_values(ascending=False).head(top_n)
    )

    # month-over-month growth for the most recent month available
    mom_growth = None
    if len(monthly) >= 2:
        prev, last = monthly.iloc[-2], monthly.iloc[-1]
        if prev != 0:
            mom_growth = round(((last - prev) / prev) * 100, 2)

    return {
        "total_value": float(df[value_col].sum()),
        "record_count": int(len(df)),
        "date_min": monthly.index.min().strftime("%b %Y"),
        "date_max": monthly.index.max().strftime("%b %Y"),
        "regions": list(by_region.index),
        "by_region": {k: float(v) for k, v in by_region.items()},
        "by_product": {str(k): float(v) for k, v in by_product.items()},
        "by_customer": {str(k): float(v) for k, v in by_customer.items()},
        "monthly_labels": [d.strftime("%b %Y") for d in monthly.index],
        "monthly_values": [float(v) for v in monthly.values],
        "mom_growth_pct": mom_growth,
        "unique_products": int(df["Product ID"].nunique()),
        "unique_customers": int(df["Customer ID"].nunique()),
    }


def monthly_series(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Returns a tidy monthly-aggregated series (period_dt, value) sorted by date,
    used as the input for forecasting."""
    s = df.groupby("period_dt")[value_col].sum().sort_index()
    return s.reset_index().rename(columns={value_col: "value"})

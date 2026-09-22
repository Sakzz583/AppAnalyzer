
"""
Fast Excel data processing for the Sales Insights & Forecast app.
"""

import pandas as pd
import numpy as np


REQUIRED_COLUMNS = {"Period", "Region", "Product ID", "Customer ID"}


def _find_header_row(raw: pd.DataFrame, keyword="Period", max_scan=10) -> int:
    """Find the row containing the real table header."""
    limit = min(max_scan, len(raw))

    for i in range(limit):
        values = raw.iloc[i].astype(str).str.strip().str.lower()
        if values.eq(keyword.lower()).any():
            return i

    return 0


def load_workbook(filepath: str) -> dict:
    """
    Load all usable Excel sheets.

    The header is detected from a small preview and each usable sheet
    is then read only once.
    """
    xl = pd.ExcelFile(filepath, engine="openpyxl")
    sheets = {}

    for sheet_name in xl.sheet_names:
        # Only inspect a small number of rows to locate the header.
        preview = pd.read_excel(
            xl,
            sheet_name=sheet_name,
            header=None,
            nrows=10,
            engine="openpyxl",
        )

        header_row = _find_header_row(preview)

        # Read the actual sheet once.
        df = pd.read_excel(
            xl,
            sheet_name=sheet_name,
            header=header_row,
            engine="openpyxl",
        )

        # Remove completely empty / unnamed columns.
        df = df.loc[
            :,
            ~df.columns.astype(str).str.match(r"^Unnamed", case=False),
        ]

        df = df.dropna(how="all")

        if df.empty:
            continue

        df.columns = [str(c).strip() for c in df.columns]

        # Skip sheets that clearly aren't sales data.
        if "Period" not in df.columns:
            continue

        if not REQUIRED_COLUMNS.issubset(df.columns):
            continue

        # Find currency column immediately.
        value_cols = [c for c in df.columns if "$" in c]

        if not value_cols:
            continue

        sheets[sheet_name] = df

    return sheets


def identify_value_column(df: pd.DataFrame) -> str:
    """Find the first $ value column."""
    for col in df.columns:
        if "$" in str(col):
            return col

    raise ValueError(
        f"No currency ($) column found among: {list(df.columns)}"
    )


def prepare(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Clean and type-convert the data efficiently."""
    df = df.copy()

    # Period
    period = (
        df["Period"]
        .astype("string")
        .str.strip()
    )

    df["period_dt"] = pd.to_datetime(
        period,
        format="%Y%m",
        errors="coerce",
    )

    # Currency
    df[value_col] = pd.to_numeric(
        df[value_col],
        errors="coerce",
    ).fillna(0)

    # Remove unusable periods.
    df = df.dropna(subset=["period_dt"])

    # Clean grouping columns.
    for col in ["Region", "Product ID", "Customer ID"]:
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("Unknown")

    # KG columns, if present.
    for col in df.columns:
        if str(col).upper().endswith("KG"):
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            ).fillna(0)

    return df


def compute_insights(
    df: pd.DataFrame,
    value_col: str,
    top_n: int = 10,
) -> dict:
    """Build dashboard metrics."""

    # Monthly aggregation.
    monthly = (
        df.groupby("period_dt", sort=True, observed=True)[value_col]
        .sum()
    )

    # One aggregation for the three dashboard dimensions.
    by_region = (
        df.groupby("Region", observed=True)[value_col]
        .sum()
        .sort_values(ascending=False)
    )

    by_product = (
        df.groupby("Product ID", observed=True)[value_col]
        .sum()
        .nlargest(top_n)
    )

    by_customer = (
        df.groupby("Customer ID", observed=True)[value_col]
        .sum()
        .nlargest(top_n)
    )

    # MoM.
    mom_growth = None

    if len(monthly) >= 2:
        previous = monthly.iloc[-2]
        current = monthly.iloc[-1]

        if previous != 0:
            mom_growth = round(
                ((current - previous) / previous) * 100,
                2,
            )

    return {
        "total_value": float(df[value_col].sum()),
        "record_count": int(len(df)),

        "date_min": monthly.index.min().strftime("%b %Y"),
        "date_max": monthly.index.max().strftime("%b %Y"),

        "regions": [str(x) for x in by_region.index],

        "by_region": {
            str(k): float(v)
            for k, v in by_region.items()
        },

        "by_product": {
            str(k): float(v)
            for k, v in by_product.items()
        },

        "by_customer": {
            str(k): float(v)
            for k, v in by_customer.items()
        },

        "monthly_labels": [
            d.strftime("%b %Y")
            for d in monthly.index
        ],

        "monthly_values": [
            float(v)
            for v in monthly.values
        ],

        "mom_growth_pct": mom_growth,

        "unique_products": int(
            df["Product ID"].nunique()
        ),

        "unique_customers": int(
            df["Customer ID"].nunique()
        ),
    }


def monthly_series(
    df: pd.DataFrame,
    value_col: str,
) -> pd.DataFrame:
    """Return monthly totals for forecasting."""

    monthly = (
        df.groupby("period_dt", sort=True, observed=True)[value_col]
        .sum()
        .reset_index()
    )

    return monthly.rename(
        columns={value_col: "value"}
    )

# """
# data_processor.py
# ------------------
# Loads an uploaded Excel workbook, auto-detects the real header row
# (handles the common case where the sheet has a blank first column /
# title rows above the actual table), cleans the data, and computes
# summary insights used by the dashboard.

# Expected (but flexible) columns per sheet:
#     Period, Region, Product ID, Customer ID, Sales $ / Forecast $, Sales KG / Forecast KG
# """

# import pandas as pd
# import numpy as np


# def _find_header_row(raw: pd.DataFrame, keyword: str = "Period", max_scan: int = 5) -> int:
#     """Scan the first few rows of a headerless read to find the row that
#     actually contains the column names (looks for a 'Period' cell)."""
#     for i in range(min(max_scan, len(raw))):
#         row_values = raw.iloc[i].astype(str)
#         if row_values.str.contains(keyword, case=False, na=False).any():
#             return i
#     return 0


# def load_workbook(filepath: str) -> dict:
#     """Reads every sheet in the workbook and returns {sheet_name: cleaned_dataframe}."""
#     xl = pd.ExcelFile(filepath)
#     sheets = {}
#     for name in xl.sheet_names:
#         raw = pd.read_excel(xl, sheet_name=name, header=None, nrows=10)
#         header_row = _find_header_row(raw)

#         df = pd.read_excel(xl, sheet_name=name, header=header_row)
#         # drop fully-empty / "Unnamed" columns created by blank leading columns
#         df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
#         df = df.dropna(how="all")
#         df.columns = [str(c).strip() for c in df.columns]
#         sheets[name] = df
#     return sheets


# def identify_value_column(df: pd.DataFrame) -> str:
#     """Finds the $ value column in a sheet (e.g. 'Sales $' or 'Forecast $')."""
#     for col in df.columns:
#         if "$" in col:
#             return col
#     raise ValueError(f"No currency ($) column found among: {list(df.columns)}")


# def prepare(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
#     """Type-cleans a sheet: parses Period (YYYYMM) into a real date, coerces
#     numeric columns, and drops unusable rows."""
#     df = df.copy()
#     df["Period"] = df["Period"].astype(str).str.strip()
#     df["period_dt"] = pd.to_datetime(df["Period"], format="%Y%m", errors="coerce")
#     df = df.dropna(subset=["period_dt"])
#     df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
#     for col in df.columns:
#         if col.endswith("KG"):
#             df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
#     return df


# def compute_insights(df: pd.DataFrame, value_col: str, top_n: int = 10) -> dict:
#     """Builds all the summary numbers/tables the dashboard needs."""
#     monthly = df.groupby("period_dt")[value_col].sum().sort_index()

#     by_region = df.groupby("Region")[value_col].sum().sort_values(ascending=False)

#     by_product = (
#         df.groupby("Product ID")[value_col].sum().sort_values(ascending=False).head(top_n)
#     )

#     by_customer = (
#         df.groupby("Customer ID")[value_col].sum().sort_values(ascending=False).head(top_n)
#     )

#     # month-over-month growth for the most recent month available
#     mom_growth = None
#     if len(monthly) >= 2:
#         prev, last = monthly.iloc[-2], monthly.iloc[-1]
#         if prev != 0:
#             mom_growth = round(((last - prev) / prev) * 100, 2)

#     return {
#         "total_value": float(df[value_col].sum()),
#         "record_count": int(len(df)),
#         "date_min": monthly.index.min().strftime("%b %Y"),
#         "date_max": monthly.index.max().strftime("%b %Y"),
#         "regions": list(by_region.index),
#         "by_region": {k: float(v) for k, v in by_region.items()},
#         "by_product": {str(k): float(v) for k, v in by_product.items()},
#         "by_customer": {str(k): float(v) for k, v in by_customer.items()},
#         "monthly_labels": [d.strftime("%b %Y") for d in monthly.index],
#         "monthly_values": [float(v) for v in monthly.values],
#         "mom_growth_pct": mom_growth,
#         "unique_products": int(df["Product ID"].nunique()),
#         "unique_customers": int(df["Customer ID"].nunique()),
#     }


# def monthly_series(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
#     """Returns a tidy monthly-aggregated series (period_dt, value) sorted by date,
#     used as the input for forecasting."""
#     s = df.groupby("period_dt")[value_col].sum().sort_index()
#     return s.reset_index().rename(columns={value_col: "value"})

"""
Fast monthly trend + seasonality forecasting.
"""

import numpy as np
import pandas as pd


def forecast(
    monthly_df: pd.DataFrame,
    periods: int = 6,
) -> dict:

    monthly_df = (
        monthly_df
        .sort_values("period_dt")
        .reset_index(drop=True)
    )

    n = len(monthly_df)

    if n == 0:
        return {
            "method": "flat average",
            "future_labels": [],
            "future_values": [],
            "fitted_values": [],
            "mape": None,
        }

    # Not enough history for trend + seasonality.
    if n < 3:
        avg = float(monthly_df["value"].mean())

        last_date = monthly_df["period_dt"].max()

        future_dates = _next_months(
            last_date,
            periods,
        )

        return {
            "method": "flat average (insufficient history)",
            "future_labels": [
                d.strftime("%b %Y")
                for d in future_dates
            ],
            "future_values": [avg] * periods,
            "fitted_values": [
                float(v)
                for v in monthly_df["value"]
            ],
            "mape": None,
        }

    y = monthly_df["value"].to_numpy(
        dtype=float
    )

    t = np.arange(n, dtype=float)

    # NumPy linear regression.
    slope, intercept = np.polyfit(
        t,
        y,
        1,
    )

    trend = intercept + slope * t

    # Prevent division by zero.
    trend_safe = np.where(
        np.abs(trend) < 1e-9,
        1e-9,
        trend,
    )

    ratio = y / trend_safe

    month_numbers = (
        monthly_df["period_dt"]
        .dt.month
        .to_numpy()
    )

    # Calculate seasonal indexes.
    seasonal_lookup = {}

    for month in range(1, 13):
        mask = month_numbers == month

        if mask.any():
            seasonal_lookup[month] = float(
                ratio[mask].mean()
            )
        else:
            seasonal_lookup[month] = 1.0

    # Normalize seasonal indexes.
    mean_index = np.mean(
        list(seasonal_lookup.values())
    )

    if mean_index != 0:
        for month in seasonal_lookup:
            seasonal_lookup[month] /= mean_index

    # Historical fitted values.
    fitted = np.array([
        trend[i] *
        seasonal_lookup[month_numbers[i]]
        for i in range(n)
    ])

    # MAPE.
    nonzero = y != 0

    if nonzero.any():
        mape = (
            np.mean(
                np.abs(
                    (y[nonzero] - fitted[nonzero])
                    / y[nonzero]
                )
            ) * 100
        )

        mape = round(float(mape), 2)
    else:
        mape = None

    # Future dates.
    last_date = monthly_df["period_dt"].max()

    future_dates = _next_months(
        last_date,
        periods,
    )

    future_t = np.arange(
        n,
        n + periods,
        dtype=float,
    )

    future_trend = (
        intercept +
        slope * future_t
    )

    future_values = []

    for i, date in enumerate(future_dates):
        seasonal = seasonal_lookup.get(
            date.month,
            1.0,
        )

        value = max(
            0.0,
            float(
                future_trend[i] *
                seasonal
            ),
        )

        future_values.append(value)

    return {
        "method": (
            "linear trend x seasonal index "
            "(classical multiplicative decomposition)"
        ),

        "future_labels": [
            d.strftime("%b %Y")
            for d in future_dates
        ],

        "future_values": future_values,

        "fitted_values": [
            float(v)
            for v in fitted
        ],

        "mape": mape,

        "trend_slope_per_month": float(
            slope
        ),
    }


def _next_months(
    last_date: pd.Timestamp,
    periods: int,
) -> list:

    return [
        last_date + pd.DateOffset(months=i)
        for i in range(1, periods + 1)
    ]

# """
# forecasting.py
# --------------
# Forecasts future monthly sales using a lightweight, dependency-free
# "trend + seasonality" decomposition model (classical multiplicative
# decomposition, similar in spirit to Holt-Winters but implemented with
# plain linear regression so it needs no extra heavy libraries).

# METHODOLOGY (see README.md for the full write-up):
#  1. Aggregate raw transaction-level sales into a monthly total time series.
#  2. Fit a linear trend line (ordinary least squares) through the monthly
#     totals -> captures long-term growth/decline.
#  3. Compute how far each historical month's actual value deviates from the
#     trend line, as a ratio (actual / trend). Average that ratio per
#     calendar month (Jan, Feb, ... Dec) across all available years -> this
#     is the "seasonal index" for each month (e.g. December might typically
#     run 20% above trend).
#  4. Forecast = (trend line extended into the future) x (seasonal index for
#     that future month's calendar month).
#  5. Model fit quality is reported back as MAPE (Mean Absolute Percentage
#     Error) computed on the historical in-sample fit.

# This approach is transparent and explainable to a business user (no black
# box), handles both growth trend and repeating seasonal patterns, and only
# needs numpy/pandas/scikit-learn.
# """

# import numpy as np
# import pandas as pd
# from sklearn.linear_model import LinearRegression


# def forecast(monthly_df: pd.DataFrame, periods: int = 6) -> dict:
#     """
#     monthly_df: DataFrame with columns ['period_dt', 'value'], sorted by date,
#                 one row per month (as produced by data_processor.monthly_series).
#     periods:    number of future months to forecast.
#     """
#     monthly_df = monthly_df.sort_values("period_dt").reset_index(drop=True)
#     n = len(monthly_df)

#     if n < 3:
#         # Not enough history for a meaningful trend/seasonality split.
#         avg = monthly_df["value"].mean() if n else 0.0
#         last_date = monthly_df["period_dt"].max() if n else pd.Timestamp.today()
#         future_dates = _next_months(last_date, periods)
#         return {
#             "method": "flat average (insufficient history for trend model)",
#             "future_labels": [d.strftime("%b %Y") for d in future_dates],
#             "future_values": [float(avg)] * periods,
#             "fitted_values": [float(v) for v in monthly_df["value"]],
#             "mape": None,
#         }

#     t = np.arange(n).reshape(-1, 1)
#     y = monthly_df["value"].values.astype(float)

#     # 1) trend
#     model = LinearRegression().fit(t, y)
#     trend = model.predict(t)
#     trend_safe = np.where(trend == 0, 1e-9, trend)

#     # 2) seasonal index per calendar month
#     ratio = y / trend_safe
#     month_num = monthly_df["period_dt"].dt.month.values
#     seasonal_lookup = {}
#     for m in range(1, 13):
#         mask = month_num == m
#         seasonal_lookup[m] = ratio[mask].mean() if mask.any() else 1.0
#     # normalize so the average seasonal index across the year is 1.0
#     mean_idx = np.mean(list(seasonal_lookup.values()))
#     if mean_idx != 0:
#         seasonal_lookup = {m: v / mean_idx for m, v in seasonal_lookup.items()}

#     # in-sample fitted values (trend * seasonal) for accuracy reporting
#     fitted = np.array([trend[i] * seasonal_lookup[month_num[i]] for i in range(n)])
#     nonzero = y != 0
#     mape = float(np.mean(np.abs((y[nonzero] - fitted[nonzero]) / y[nonzero])) * 100) if nonzero.any() else None

#     # 3) forecast future periods
#     future_t = np.arange(n, n + periods).reshape(-1, 1)
#     future_trend = model.predict(future_t)
#     last_date = monthly_df["period_dt"].max()
#     future_dates = _next_months(last_date, periods)
#     future_months = [d.month for d in future_dates]
#     future_values = [
#         max(0.0, float(future_trend[i] * seasonal_lookup[future_months[i]])) for i in range(periods)
#     ]

#     return {
#         "method": "linear trend x seasonal index (classical multiplicative decomposition)",
#         "future_labels": [d.strftime("%b %Y") for d in future_dates],
#         "future_values": future_values,
#         "fitted_values": [float(v) for v in fitted],
#         "mape": round(mape, 2) if mape is not None else None,
#         "trend_slope_per_month": float(model.coef_[0]),
#     }


# def _next_months(last_date: pd.Timestamp, periods: int) -> list:
#     return [last_date + pd.DateOffset(months=i) for i in range(1, periods + 1)]

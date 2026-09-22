# Sales Insights & Forecast — Web App

A small Flask website: upload an Excel file with sales/forecast data, and it
automatically cleans the data, computes business insights, draws charts, and
predicts sales for the next 6 months.

## Project structure

```
sales_forecast_app/
├── app.py                # Flask routes (upload page + dashboard)
├── data_processor.py      # Reads the Excel file, cleans it, computes insights
├── forecasting.py         # Sales prediction model (trend + seasonality)
├── requirements.txt
├── templates/
│   ├── index.html         # Upload page
│   └── dashboard.html     # Results page with charts (Chart.js)
├── static/
│   └── style.css
├── uploads/                # Uploaded files are saved here (auto-created)
└── README.md
```

## Setup

```bash
cd sales_forecast_app
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser, upload your `.xlsx` file, and
you'll be taken straight to the dashboard.

### Expected file format

Each sheet in the workbook should have these columns (the app auto-detects
the header row even if there are blank rows/columns above it):

| Period (YYYYMM) | Region | Product ID | Customer ID | Sales $ / Forecast $ | Sales KG / Forecast KG |
|---|---|---|---|---|---|

Any sheet with a "$" column is analyzed automatically — the app works with
one sheet (e.g. just "Sales Data") or several (e.g. "Sales Data" and
"Forecast Data" side by side), as in the sample file this was built against.

## What the dashboard shows (per sheet)

- **KPIs**: total value, record count, date range covered, month-over-month
  growth %, number of unique products/customers.
- **Monthly trend + 6-month forecast** line chart.
- **By Region** breakdown (doughnut chart).
- **Top 10 Products** and **Top 10 Customers** by value (bar charts).

## Sales prediction methodology

The forecast uses a **classical multiplicative trend + seasonality
decomposition** — a transparent, explainable model rather than a black box.
Implemented in `forecasting.py`:

1. **Aggregate** every transaction into a single monthly total (sum of
   `Sales $` per calendar month).
2. **Fit a trend line.** An ordinary least-squares linear regression is fit
   through the monthly totals (`sklearn.linear_model.LinearRegression`),
   capturing the long-run growth or decline in the business.
3. **Extract seasonality.** For every historical month, the ratio
   `actual ÷ trend` is computed. These ratios are averaged separately for
   each calendar month (all the Januaries together, all the Februaries
   together, etc.) to produce a **seasonal index per calendar month** — e.g.
   "December typically runs 15% above trend." The indices are normalized so
   their average is 1.0.
4. **Forecast** = (trend line extended forward) × (seasonal index for that
   future month). This reproduces both the underlying growth direction and
   the repeating seasonal pattern.
5. **Accuracy check.** The model's in-sample fitted values (trend × seasonal
   index for historical months) are compared against actuals to report a
   **MAPE (Mean Absolute Percentage Error)** — shown under the trend chart —
   so you can judge how reliable the forecast is for that dataset.

If a sheet has fewer than 3 months of history, the app falls back to a flat
average, since a trend/seasonality split isn't meaningful with that little
data.

### Why this approach (vs. ARIMA/Prophet/Holt-Winters libraries)

This method needs no heavy statistical dependencies (just NumPy/pandas/
scikit-learn, which are already required for the data handling), runs
instantly even on large files, and — importantly — every number in the
forecast can be explained in plain English to a non-technical stakeholder.
For more sophisticated forecasting (e.g. `statsmodels`' `ExponentialSmoothing`/
Holt-Winters, or Facebook `Prophet`) you can swap the contents of
`forecasting.py`'s `forecast()` function while keeping the same input/output
shape used by `app.py`.

## Extending this project

- Swap the forecasting model (see above) without touching the Flask routes.
- Add authentication if this will be used by multiple people.
- Persist uploaded results in a database instead of recomputing on every
  upload, if the same file will be viewed repeatedly.
- Add a CSV export button for the computed insights.

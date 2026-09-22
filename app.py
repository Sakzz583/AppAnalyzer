import os
import uuid

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    flash,
)

from data_processor import (
    load_workbook,
    identify_value_column,
    prepare,
    compute_insights,
    monthly_series,
)

from forecasting import forecast


UPLOAD_FOLDER = os.path.join(
    os.path.dirname(__file__),
    "uploads",
)

ALLOWED_EXTENSIONS = {
    "xlsx",
    "xls",
}

FORECAST_PERIODS = 6


app = Flask(__name__)

app.secret_key = "dev-secret-key"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True,
)


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(
            ".",
            1,
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


@app.route("/")
def index():
    return render_template(
        "index.html"
    )


@app.route(
    "/upload",
    methods=["POST"],
)
def upload():

    file = request.files.get("file")

    if not file or not file.filename:
        flash(
            "Please choose an Excel file."
        )
        return redirect("/")

    if not allowed_file(file.filename):
        flash(
            "Unsupported file type. "
            "Please upload a .xlsx or .xls file."
        )
        return redirect("/")

    original_filename = file.filename

    safe_name = (
        f"{uuid.uuid4().hex}_"
        f"{original_filename}"
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        safe_name,
    )

    file.save(filepath)

    try:

        sheets = load_workbook(filepath)

        results = {}

        for sheet_name, df in sheets.items():

            try:
                value_col = identify_value_column(df)
            except ValueError:
                continue

            df = prepare(
                df,
                value_col,
            )

            if df.empty:
                continue

            insights = compute_insights(
                df,
                value_col,
            )

            series = monthly_series(
                df,
                value_col,
            )

            fc = forecast(
                series,
                periods=FORECAST_PERIODS,
            )

            results[sheet_name] = {
                "value_col": value_col,
                "insights": insights,
                "forecast": fc,
            }

        if not results:
            flash(
                "No usable sheets found. "
                "Each sheet needs Period, Region, "
                "Product ID, Customer ID and a $ value column."
            )
            return redirect("/")

        return render_template(
            "dashboard.html",
            results=results,
            filename=original_filename,
        )

    except Exception as exc:

        flash(
            f"Could not process the Excel file: {exc}"
        )

        return redirect("/")

    finally:

        # Delete temporary upload.
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass


if __name__ == "__main__":
    app.run(
        debug=True
    )

# """
# app.py
# ------
# Flask web app:
#   1. GET  /            -> upload form
#   2. POST /upload      -> reads the uploaded Excel file, computes insights
#                            and a 6-month forecast per sheet, renders the
#                            dashboard with the results.

# Run with:  python app.py
# Then open: http://127.0.0.1:5000
# """

# import os
# import uuid
# from flask import Flask, render_template, request, redirect, flash

# from data_processor import load_workbook, identify_value_column, prepare, compute_insights, monthly_series
# from forecasting import forecast

# UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
# ALLOWED_EXTENSIONS = {"xlsx", "xls"}
# FORECAST_PERIODS = 6

# app = Flask(__name__)
# app.secret_key = "dev-secret-key"  # only needed for flash messages
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# def allowed_file(filename: str) -> bool:
#     return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# @app.route("/")
# def index():
#     return render_template("index.html")


# @app.route("/upload", methods=["POST"])
# def upload():
#     file = request.files.get("file")
#     if not file or file.filename == "":
#         flash("Please choose an Excel file (.xlsx) to upload.")
#         return redirect("/")
#     if not allowed_file(file.filename):
#         flash("Unsupported file type. Please upload a .xlsx or .xls file.")
#         return redirect("/")

#     # save with a unique name to avoid collisions
#     safe_name = f"{uuid.uuid4().hex}_{file.filename}"
#     filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
#     file.save(filepath)

#     try:
#         sheets = load_workbook(filepath)
#     except Exception as exc:
#         flash(f"Could not read the Excel file: {exc}")
#         return redirect("/")

#     results = {}
#     for sheet_name, df in sheets.items():
#         try:
#             value_col = identify_value_column(df)
#         except ValueError:
#             continue  # skip sheets with no $ column (nothing to analyze)

#         df = prepare(df, value_col)
#         if df.empty:
#             continue

#         insights = compute_insights(df, value_col)
#         series = monthly_series(df, value_col)
#         fc = forecast(series, periods=FORECAST_PERIODS)

#         results[sheet_name] = {
#             "value_col": value_col,
#             "insights": insights,
#             "forecast": fc,
#         }

#     if not results:
#         flash("No usable sheets found. Each sheet needs 'Period', 'Region' and a '$' value column.")
#         return redirect("/")

#     return render_template("dashboard.html", results=results, filename=file.filename)


# if __name__ == "__main__":
#     app.run(debug=True)

import io
import pandas as pd
import openpyxl
from backend.analysis.missing_analyzer import analyze_missing
from backend.cleaning.cleaning_engine import fill_missing
from backend.services.file_handler import read_csv, read_excel_sheet
from backend.utils.df_utils import get_missing_mask, clean_numeric_series


def test_missing_values_detection_explicit():
    # Test dataset requested in Requirement 10 & 15
    df = pd.DataFrame([
        {"Name": "John", "Age": "25", "City": "Chennai"},
        {"Name": "Alex", "Age": "",   "City": "Hyderabad"},
        {"Name": "Sam",  "Age": "30", "City": "   "},
        {"Name": "Ravi", "Age": None, "City": "Chennai"},
    ])

    res = analyze_missing(df)
    affected = {col["column"]: col for col in res["affected_columns"]}

    assert "Age" in affected
    assert affected["Age"]["missing_count"] == 2

    assert "City" in affected
    assert affected["City"]["missing_count"] == 1

    assert "Name" not in affected


def test_missing_values_types():
    df = pd.DataFrame({
        "A": [1, None, pd.NA, float("nan"), ""],
        "B": ["hello", "   ", "nan", "NULL", "none"],
    })
    mask = get_missing_mask(df)
    assert int(mask["A"].sum()) == 4  # None, pd.NA, nan, ""
    assert int(mask["B"].sum()) == 4  # "   ", "nan", "NULL", "none"


def test_currency_string_missing_values_imputation():
    # Column with currency strings and null strings
    df = pd.DataFrame({
        "Price": ["$420.21", "-445.34", "null", "$810.99", "null", "$100.00"]
    })

    res = analyze_missing(df)
    affected = {col["column"]: col for col in res["affected_columns"]}
    assert "Price" in affected
    assert affected["Price"]["missing_count"] == 2

    # Impute missing values via mean
    new_df, entry = fill_missing(df, "Price", "mean")
    res_after = analyze_missing(new_df)
    assert res_after["total_missing"] == 0
    assert entry["affected_rows"] == 2


def test_csv_missing_values_loading():
    csv_data = "Name,Age,City\nJohn,25,Chennai\nAlex,,Hyderabad\nSam,30,  \nRavi,,Chennai\n"
    df = read_csv(csv_data.encode("utf-8"))

    res = analyze_missing(df)
    affected = {col["column"]: col for col in res["affected_columns"]}

    assert affected["Age"]["missing_count"] == 2
    assert affected["City"]["missing_count"] == 1


def test_excel_missing_values_loading():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Name", "Age", "City"])
    ws.append(["John", "25", "Chennai"])
    ws.append(["Alex", None, "Hyderabad"])
    ws.append(["Sam", "30", "   "])
    ws.append(["Ravi", "", "Chennai"])

    buf = io.BytesIO()
    wb.save(buf)
    excel_bytes = buf.getvalue()

    df = read_excel_sheet(excel_bytes, "Sheet1")
    res = analyze_missing(df)
    affected = {col["column"]: col for col in res["affected_columns"]}

    assert affected["Age"]["missing_count"] == 2
    assert affected["City"]["missing_count"] == 1

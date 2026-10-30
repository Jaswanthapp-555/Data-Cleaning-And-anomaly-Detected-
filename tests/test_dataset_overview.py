"""Tests for the auto-generated 5-chart Dataset Overview in Visualization."""
import io
import pandas as pd
import pytest
from backend.visualization.chart_builder import build_dataset_overview


def test_build_dataset_overview_edge_case_zero_missing():
    # Dataset with zero missing values everywhere
    df = pd.DataFrame({
        "ID": [1, 2, 3, 4],
        "Category": ["Electronics", "Clothing", "Home", "Clothing"],
        "Price": [99.9, 29.5, 45.0, 19.99],
        "Quantity": [10, 5, 2, 8],
    })
    result = build_dataset_overview(df)
    charts = result["charts"]
    assert "missing_values" in charts
    # Edge case: zero missing must NOT render a broken blank chart — it must return clean confirmation
    assert charts["missing_values"]["status"] == "clean"
    assert "No missing values" in charts["missing_values"]["message"]


def test_build_dataset_overview_with_missing_values():
    df = pd.DataFrame({
        "A": [1, None, 3, None],
        "B": ["x", "y", None, "w"],
        "C": [10.0, 20.0, 30.0, 40.0],
    })
    result = build_dataset_overview(df)
    charts = result["charts"]
    assert charts["missing_values"]["status"] == "chart"
    assert "chart" in charts["missing_values"]


def test_build_dataset_overview_correlation_too_few_numeric():
    # Only 1 numeric column
    df = pd.DataFrame({
        "Category": ["A", "B", "C"],
        "City": ["NYC", "LA", "Chicago"],
        "Price": [10.0, 20.0, 30.0],
    })
    result = build_dataset_overview(df)
    charts = result["charts"]
    # Edge case: Correlation heatmap with < 2 numeric cols must show notice instead of breaking
    assert charts["correlation_heatmap"]["status"] == "notice"
    assert "requires at least 2" in charts["correlation_heatmap"]["message"].lower()


def test_build_dataset_overview_correlation_with_enough_numeric():
    # 3 numeric columns
    df = pd.DataFrame({
        "Price": [10.0, 20.0, 30.0, 40.0],
        "Cost": [5.0, 12.0, 18.0, 25.0],
        "Quantity": [100, 200, 150, 80],
    })
    result = build_dataset_overview(df)
    charts = result["charts"]
    assert charts["correlation_heatmap"]["status"] == "chart"


def test_build_dataset_overview_no_categorical_columns():
    # Pure numeric dataset
    df = pd.DataFrame({
        "A": [1.0, 2.0, 3.0, 4.0],
        "B": [10.0, 20.0, 30.0, 40.0],
    })
    result = build_dataset_overview(df)
    charts = result["charts"]
    assert "categorical_breakdown" in charts
    assert charts["categorical_breakdown"]["status"] in ("notice", "chart")


def test_dataset_overview_api_endpoint(client):
    csv_data = b"ID,Product,Category,Price,Units\n1,Laptop,Tech,999.9,12\n2,Shirt,Apparel,29.9,50\n3,Coffee,Food,8.5,100\n4,Phone,Tech,699.0,25\n"
    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    upload_res = client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(csv_data), "shop.csv"), "dataset": "single"},
        content_type="multipart/form-data",
        headers={"X-Session-Id": sid},
    )
    assert upload_res.status_code == 200

    # Call /api/viz/overview
    ov_res = client.get(f"/api/viz/overview?session_id={sid}&dataset=single&which=working")
    assert ov_res.status_code == 200
    data = ov_res.get_json()
    assert "charts" in data
    assert "missing_values" in data["charts"]
    assert "dtype_distribution" in data["charts"]
    assert "correlation_heatmap" in data["charts"]
    assert "categorical_breakdown" in data["charts"]
    assert "numeric_distribution" in data["charts"]


def test_dataset_overview_decoded_plotly_traces_and_real_data():
    """Item 7: Verify that chart traces are decoded into native Python lists and contain real dataset values."""
    real_prices = [10.5, 25.0, 49.99, 120.0, 99.5, 15.0]
    df = pd.DataFrame({
        "customer_id": [f"CUST_{i}" for i in range(len(real_prices))],
        "price": real_prices,
        "department": ["Shoes", "Books", "Electronics", "Electronics", "Books", "Shoes"],
    })

    result = build_dataset_overview(df)
    charts = result["charts"]

    # 1. Exactly 4-5 fixed charts
    expected_keys = {"missing_values", "dtype_distribution", "correlation_heatmap", "numeric_distribution", "categorical_breakdown"}
    assert set(charts.keys()) == expected_keys

    # 2. Check numeric distribution chart
    num_chart_data = charts["numeric_distribution"]
    assert num_chart_data["status"] == "chart"
    assert num_chart_data["column"] == "price"

    chart_dict = num_chart_data["chart"]
    assert "data" in chart_dict
    assert len(chart_dict["data"]) > 0

    trace = chart_dict["data"][0]
    # Verify trace['x'] is a native Python list, NOT a binary buffer dict {'bdata': ...}
    assert isinstance(trace["x"], list)
    assert not isinstance(trace["x"], dict)
    # Verify real dataset values reached the chart!
    assert sorted(trace["x"]) == sorted(real_prices)


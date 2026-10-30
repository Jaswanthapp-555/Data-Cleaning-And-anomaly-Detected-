import pandas as pd
from backend.cleaning import cleaning_engine as ce


def test_edit_cell():
    df = pd.DataFrame({"A": [1, 2, 3]})
    new_df, entry = ce.edit_cell(df, 0, "A", 99)
    assert new_df.at[0, "A"] == 99
    assert df.at[0, "A"] == 1  # Original immutable


def test_delete_rows():
    df = pd.DataFrame({"A": [10, 20, 30, 40]})
    new_df, entry = ce.delete_rows(df, [1, 3])
    assert len(new_df) == 2
    assert list(new_df["A"]) == [10, 30]


def test_delete_columns():
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    new_df, entry = ce.delete_columns(df, ["B"])
    assert "B" not in new_df.columns
    assert list(new_df.columns) == ["A", "C"]


def test_rename_column():
    df = pd.DataFrame({"OldName": [1, 2]})
    new_df, entry = ce.rename_column(df, "OldName", "NewName")
    assert "NewName" in new_df.columns
    assert "OldName" not in new_df.columns


def test_fill_missing_mean():
    df = pd.DataFrame({"A": [10.0, 20.0, None]})
    new_df, entry = ce.fill_missing(df, "A", "mean")
    assert new_df.at[2, "A"] == 15.0


def test_fill_missing_mean_excl_outliers():
    # Mean of 10, 12, 14 is 12. 1000 is outlier.
    df = pd.DataFrame({"A": [10.0, 12.0, 14.0, 1000.0, None]})
    new_df, entry = ce.fill_missing(df, "A", "mean_excl_outliers")
    assert new_df.at[4, "A"] == 12.0


def test_remove_duplicates():
    df = pd.DataFrame({"A": [1, 1, 2], "B": ["x", "x", "y"]})
    new_df, entry = ce.remove_duplicates(df)
    assert len(new_df) == 2


def test_preview_and_repair_six_conversions():
    from backend.analysis.type_analyzer import preview_type_conversion

    # 1. Int -> Float
    df1 = pd.DataFrame({"ints": [10, 20, 30]})
    prev1 = preview_type_conversion(df1, "ints", "float64")
    assert prev1["conversion_code"] == "int_to_float"
    assert prev1["is_safe"] is True
    res_df1, _ = ce.repair_type(df1, "ints", "float64")
    assert pd.api.types.is_float_dtype(res_df1["ints"])

    # 2. Float -> Int (whole vs decimals)
    df2_whole = pd.DataFrame({"floats": [10.0, 20.0, None]})
    prev2_whole = preview_type_conversion(df2_whole, "floats", "int64")
    assert prev2_whole["conversion_code"] == "float_to_int"
    assert prev2_whole["decimal_loss_count"] == 0
    assert prev2_whole["is_safe"] is True

    df2_dec = pd.DataFrame({"floats": [10.25, 20.75, 30.0]})
    prev2_dec = preview_type_conversion(df2_dec, "floats", "int64")
    assert prev2_dec["conversion_code"] == "float_to_int"
    assert prev2_dec["decimal_loss_count"] == 2
    assert prev2_dec["is_safe"] is False
    res_df2, _ = ce.repair_type(df2_dec, "floats", "int64")
    assert res_df2["floats"].tolist() == [10, 21, 30]

    # 3. Int/Float -> Text
    df3 = pd.DataFrame({"ids": [101, 102, None]})
    prev3 = preview_type_conversion(df3, "ids", "str")
    assert prev3["conversion_code"] == "num_to_text"
    res_df3, _ = ce.repair_type(df3, "ids", "str")
    assert res_df3["ids"].iloc[0] == "101"

    # 4. Text -> Int / Float (with failures)
    df4 = pd.DataFrame({"mixed_nums": ["118", "119", "N/A", "unknown"]})
    prev4 = preview_type_conversion(df4, "mixed_nums", "int64")
    assert prev4["conversion_code"] == "text_to_int"
    assert prev4["convertible_count"] == 2
    assert prev4["non_convertible_count"] == 2
    assert any("N/A" in x for x in prev4["non_convertible_examples"])
    res_df4, _ = ce.repair_type(df4, "mixed_nums", "int64")
    assert res_df4["mixed_nums"].iloc[0] == 118
    assert pd.isna(res_df4["mixed_nums"].iloc[2])

    # 5. Text -> Date (with failures)
    df5 = pd.DataFrame({"dates": ["2024-01-01", "2024-02-01", "invalid_date"]})
    prev5 = preview_type_conversion(df5, "dates", "datetime64")
    assert prev5["conversion_code"] == "text_to_date"
    assert prev5["convertible_count"] == 2
    assert prev5["non_convertible_count"] == 1
    assert any("invalid_date" in x for x in prev5["non_convertible_examples"])
    res_df5, _ = ce.repair_type(df5, "dates", "datetime64")
    assert pd.api.types.is_datetime64_any_dtype(res_df5["dates"])

    # 6. Date -> Text
    df6 = pd.DataFrame({"dt": pd.to_datetime(["2024-01-01", None])})
    prev6 = preview_type_conversion(df6, "dt", "str")
    assert prev6["conversion_code"] == "date_to_text"
    assert prev6["is_safe"] is True
    res_df6, _ = ce.repair_type(df6, "dt", "str")
    assert res_df6["dt"].iloc[0] == "2024-01-01"


import pandas as pd
from backend.analysis.quality_scorer import compute_quality_score
from backend.analysis import run_full_analysis


def test_clean_dataset_score():
    df = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": ["a", "b", "c", "d", "e"]})
    analysis = run_full_analysis(df)
    score_res = compute_quality_score(df, analysis)
    assert score_res["score"] == 100.0
    assert score_res["label"] == "Excellent"


def test_dirty_dataset_score():
    df = pd.DataFrame({
        "A": [None, None, None, 4, 5],  # 60% missing
        "B": ["a", "a", "a", "a", "a"],  # duplicate candidate
    })
    # Add duplicate row
    df = pd.concat([df, df], ignore_index=True)
    analysis = run_full_analysis(df)
    score_res = compute_quality_score(df, analysis)
    assert score_res["score"] < 100.0
    assert len(score_res["factors"]) > 0

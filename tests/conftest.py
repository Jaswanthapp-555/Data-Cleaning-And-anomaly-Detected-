import pytest
import io
import pandas as pd
from backend.app import create_app
from backend.services import session_manager as sm


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "A": [1, 2, 3, 4, 100, None, 7, 8, 9, 10],
        "B": ["cat", "dog", "cat", "dog", "cat", "dog", "cat", "dog", "cat", None],
        "C": [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8, 9.9, 10.0],
    })


@pytest.fixture
def sample_csv_bytes():
    csv_str = "ID,Name,Age,City\n1,Alice,25,Chennai\n2,Bob,30,Mumbai\n3,Charlie,,Delhi\n4,David,40,Chennai\n4,David,40,Chennai\n"
    return csv_str.encode("utf-8")

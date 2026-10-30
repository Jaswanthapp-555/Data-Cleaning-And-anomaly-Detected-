import io
from backend.services.file_handler import read_csv


def test_session_creation(client):
    res = client.post("/api/session/new")
    assert res.status_code == 200
    data = res.get_json()
    assert "session_id" in data


def test_csv_upload(client, sample_csv_bytes):
    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]

    data = {
        "file": (io.BytesIO(sample_csv_bytes), "test.csv"),
        "dataset": "single",
    }
    upload_res = client.post(
        "/api/upload/file",
        data=data,
        headers={"X-Session-Id": sid},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 200
    json_data = upload_res.get_json()
    assert json_data["source_info"]["rows"] == 5
    assert "ID" in json_data["columns"]


def test_empty_csv_upload(client):
    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]

    data = {
        "file": (io.BytesIO(b""), "empty.csv"),
        "dataset": "single",
    }
    upload_res = client.post(
        "/api/upload/file",
        data=data,
        headers={"X-Session-Id": sid},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 400
    assert "empty" in upload_res.get_json()["error"].lower()

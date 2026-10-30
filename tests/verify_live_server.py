import urllib.request
import json

def test_live_server():
    # 1. Home page
    res = urllib.request.urlopen("http://127.0.0.1:5000/")
    assert res.getcode() == 200
    print("1. Home page loaded: HTTP 200 OK")

    # 2. Check CSS contains new button tokens and toned-down hero card
    css = urllib.request.urlopen("http://127.0.0.1:5000/static/css/main.css").read().decode("utf-8")
    assert ".btn-purple" in css, "Missing .btn-purple"
    assert ".btn-amber" in css, "Missing .btn-amber"
    assert "Hero Card Refinement" in css, "Missing toned-down hero card styling"
    print("2. main.css has .btn-purple, .btn-amber, and toned-down hero card styling.")

    # 3. Create session
    req_sess = urllib.request.Request("http://127.0.0.1:5000/api/session/new", data=b"{}", headers={"Content-Type": "application/json"})
    sess_res = urllib.request.urlopen(req_sess)
    sid = json.loads(sess_res.read().decode("utf-8"))["session_id"]
    print(f"3. Session created: {sid}")

    # 4. Upload demo_sample.csv
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open("uploads/demo_sample.csv", "rb") as f:
        file_bytes = f.read()

    header_part = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="dataset"\r\n\r\n'
        f"single\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="demo_sample.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8")
    footer_part = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = header_part + file_bytes + footer_part

    req_up = urllib.request.Request("http://127.0.0.1:5000/api/upload/file", data=body)
    req_up.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req_up.add_header("X-Session-Id", sid)
    up_res = urllib.request.urlopen(req_up)
    assert up_res.getcode() == 200
    print("4. demo_sample.csv uploaded and analyzed successfully.")

    # 5. Test preview on mixed_floats -> int64
    prev_payload = json.dumps({
        "session_id": sid,
        "dataset": "single",
        "column": "mixed_floats",
        "target_type": "int64"
    }).encode("utf-8")
    req_prev = urllib.request.Request(
        "http://127.0.0.1:5000/api/clean/preview-type-conversion",
        data=prev_payload,
        headers={"Content-Type": "application/json"}
    )
    p1 = json.loads(urllib.request.urlopen(req_prev).read().decode("utf-8"))
    print("\n5. PREVIEW RESULTS FOR mixed_floats -> int64:")
    print("   Total values:", p1["total_values"])
    print("   Decimal loss count:", p1["decimal_loss_count"])
    print("   Decimal loss examples:", p1["decimal_loss_examples"])
    print("   Is safe:", p1["is_safe"])
    assert p1["decimal_loss_count"] == 3
    assert p1["is_safe"] is False

    # 6. Test preview on mixed_text_num -> int64
    prev_payload2 = json.dumps({
        "session_id": sid,
        "dataset": "single",
        "column": "mixed_text_num",
        "target_type": "int64"
    }).encode("utf-8")
    req_prev2 = urllib.request.Request(
        "http://127.0.0.1:5000/api/clean/preview-type-conversion",
        data=prev_payload2,
        headers={"Content-Type": "application/json"}
    )
    p2 = json.loads(urllib.request.urlopen(req_prev2).read().decode("utf-8"))
    print("\n6. PREVIEW RESULTS FOR mixed_text_num -> int64:")
    print("   Total values:", p2["total_values"])
    print("   Convertible count:", p2["convertible_count"])
    print("   Non-convertible count:", p2["non_convertible_count"])
    print("   Non-convertible examples:", p2["non_convertible_examples"])
    assert p2["convertible_count"] == 3
    assert p2["non_convertible_count"] == 2
    assert any("pending" in x and "3" in x for x in p2["non_convertible_examples"])
    assert any("unknown" in x and "5" in x for x in p2["non_convertible_examples"])

    # 7. Test repair-type execution on live server
    rep_payload = json.dumps({
        "session_id": sid,
        "dataset": "single",
        "column": "mixed_floats",
        "target_type": "int64"
    }).encode("utf-8")
    req_rep = urllib.request.Request(
        "http://127.0.0.1:5000/api/clean/repair-type",
        data=rep_payload,
        headers={"Content-Type": "application/json"}
    )
    r1 = json.loads(urllib.request.urlopen(req_rep).read().decode("utf-8"))
    assert r1["success"] is True
    print("\n7. repair-type executed successfully for mixed_floats -> int64")
    print("   New column type:", r1["entry"]["new_value"])

    print("\n[OK] ALL LIVE SERVER VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_live_server()

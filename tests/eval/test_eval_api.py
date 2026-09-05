from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_eval_runtime_reports_heuristic_without_gemini() -> None:
    response = client.get("/v1/eval/runtime")
    assert response.status_code == 200
    body = response.json()
    assert body["compiler"] == "heuristic"
    assert body["semantic"] == "heuristic"
    assert body["policy_version"]
    assert "policy UAR" in body["note"]


def test_eval_run_prints_uar_fields_and_zero_unsafe() -> None:
    response = client.post("/v1/eval/run")
    assert response.status_code == 200
    body = response.json()
    assert body["unsafe_approval_rate"] == 0
    assert body["unsafe_approvals"] == 0
    assert body["total"] >= 40
    assert body["mismatches"] == []
    assert len(body["cases"]) == body["total"]
    assert body["cases"][0]["id"]
    assert "policy UAR" in body["note"]

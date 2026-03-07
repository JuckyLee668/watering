from fastapi.testclient import TestClient

from app.main import app


def test_admin_dashboard_page():
    with TestClient(app) as client:
        resp = client.get("/api/v1/admin/dashboard")
        assert resp.status_code == 200
        assert "浇水记录管理后台" in resp.text
        assert "导出 CSV" in resp.text


def test_admin_records_and_statistics_and_export():
    with TestClient(app) as client:
        records_resp = client.get("/api/v1/records")
        assert records_resp.status_code == 200
        assert isinstance(records_resp.json(), list)

        stats_resp = client.get("/api/v1/statistics")
        assert stats_resp.status_code == 200
        stats_data = stats_resp.json()
        assert "total_count" in stats_data
        assert "total_volume" in stats_data

        export_resp = client.get("/api/v1/records/export")
        assert export_resp.status_code == 200
        assert "text/csv" in export_resp.headers.get("content-type", "")
        assert "记录ID" in export_resp.text

from src.main import app


def test_openapi_contains_backend_v1_contract() -> None:
    paths = app.openapi()["paths"]
    assert {"/api/v1/posts/{post_id}/comments", "/api/v1/posts/{post_id}/like", "/api/v1/posts/{post_id}/shares", "/api/v1/admin/reports", "/api/v1/admin/reports/{report_id}"} <= paths.keys()

from src.main import app


def test_openapi_contains_backend_v1_contract() -> None:
    paths = app.openapi()["paths"]
    assert {"/api/v1/posts/{post_id}/comments", "/api/v1/posts/{post_id}/like", "/api/v1/posts/{post_id}/shares", "/api/v1/posts/{post_id}/bookmark", "/api/v1/bookmarks", "/api/v1/drafts", "/api/v1/drafts/{draft_id}/publish", "/api/v1/users/{username}/comments", "/api/v1/admin/reports", "/api/v1/admin/reports/count", "/api/v1/admin/reports/{report_id}", "/api/v1/conversations/direct/{user_id}", "/api/v1/conversations", "/api/v1/conversations/{conversation_id}/messages", "/api/v1/messages/{message_id}", "/api/v1/users/{user_id}/block"} <= paths.keys()

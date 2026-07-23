import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import User


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_reports_validate_target_and_prevent_open_duplicates(client: AsyncClient) -> None:
    csrf = await register(client, "reporter")
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    post_id = post.json()["id"]
    report = await client.post("/api/v1/reports", json={"post_id": post_id, "reason": "spam"}, headers={"X-CSRF-Token": csrf})
    assert report.status_code == 201
    duplicate = await client.post("/api/v1/reports", json={"post_id": post_id, "reason": "spam"}, headers={"X-CSRF-Token": csrf})
    assert duplicate.status_code == 409
    invalid = await client.post("/api/v1/reports", json={"reason": "spam"}, headers={"X-CSRF-Token": csrf})
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_process_reports(client: AsyncClient) -> None:
    admin_csrf = await register(client, "adminuser")
    async with client._transport.app.state.session_factory() as session:
        admin = await session.scalar(select(User).where(User.username_normalized == "adminuser"))
        admin.role = "admin"
        await session.commit()
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": admin_csrf})
    report = await client.post("/api/v1/reports", json={"post_id": post.json()["id"], "reason": "spam"}, headers={"X-CSRF-Token": admin_csrf})
    queue = await client.get("/api/v1/admin/reports")
    assert queue.status_code == 200
    assert queue.json()["items"][0]["id"] == report.json()["id"]
    assert (await client.get("/api/v1/admin/reports/count")).json()["open_count"] >= 1
    detail = await client.get(f"/api/v1/admin/reports/{report.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["target"]["kind"] == "post"
    processed = await client.patch(f"/api/v1/admin/reports/{report.json()['id']}", json={"status": "resolved", "resolution": "Handled"}, headers={"X-CSRF-Token": admin_csrf})
    assert processed.status_code == 200
    assert processed.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_regular_user_cannot_access_admin_queue(client: AsyncClient) -> None:
    await register(client, "regularuser")
    assert (await client.get("/api/v1/admin/reports")).status_code == 403


@pytest.mark.asyncio
async def test_admin_assigns_moderator_and_moderator_cannot_assign_roles(client: AsyncClient) -> None:
    admin_csrf = await register(client, "roleadmin")
    moderator = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        moderator_csrf = await register(moderator, "newmoder")
        async with client._transport.app.state.session_factory() as session:
            admin = await session.scalar(select(User).where(User.username_normalized == "roleadmin"))
            target = await session.scalar(select(User).where(User.username_normalized == "newmoder"))
            admin.role = "admin"
            await session.commit()
        assigned = await client.patch(f"/api/v1/admin/users/{target.id}/role", json={"role": "moderator", "reason": "trusted"}, headers={"X-CSRF-Token": admin_csrf})
        assert assigned.status_code == 200
        assert assigned.json()["role"] == "moderator"
        denied = await moderator.patch(f"/api/v1/admin/users/{admin.id}/role", json={"role": "user", "reason": "no"}, headers={"X-CSRF-Token": moderator_csrf})
        assert denied.status_code == 403
        actions = await client.get("/api/v1/admin/moderation-actions")
        assert actions.status_code == 200
        assert any(action["action"] == "user_role" for action in actions.json()["items"])
    finally:
        await moderator.aclose()


@pytest.mark.asyncio
async def test_moderator_can_ban_user_with_reason_only(client: AsyncClient) -> None:
    moderator_csrf = await register(client, "banmoder")
    target = AsyncClient(transport=client._transport, base_url="http://testserver")
    other_moderator = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        target_csrf = await register(target, "banneduser")
        await register(other_moderator, "othermoder")
        async with client._transport.app.state.session_factory() as session:
            moderator = await session.scalar(select(User).where(User.username_normalized == "banmoder"))
            user = await session.scalar(select(User).where(User.username_normalized == "banneduser"))
            peer = await session.scalar(select(User).where(User.username_normalized == "othermoder"))
            moderator.role = "moderator"
            peer.role = "moderator"
            await session.commit()
        assert (await client.get("/api/v1/admin/reports")).status_code == 200
        assert (await client.patch(f"/api/v1/admin/users/{user.id}/moderation", json={"action": "ban"}, headers={"X-CSRF-Token": moderator_csrf})).status_code == 403
        banned = await client.patch(f"/api/v1/admin/users/{user.id}/moderation", json={"action": "ban", "reason": "spam"}, headers={"X-CSRF-Token": moderator_csrf})
        assert banned.status_code == 200
        assert (await target.get("/api/v1/users/me")).status_code == 401
        assert (await client.patch(f"/api/v1/admin/users/{peer.id}/moderation", json={"action": "ban", "reason": "bad"}, headers={"X-CSRF-Token": moderator_csrf})).status_code == 403
        assert target_csrf
    finally:
        await target.aclose()
        await other_moderator.aclose()


@pytest.mark.asyncio
async def test_moderator_resolves_report_hides_target_bans_author_and_admin_restores(client: AsyncClient) -> None:
    moderator_csrf = await register(client, "reportmoder")
    author = AsyncClient(transport=client._transport, base_url="http://testserver")
    admin = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        author_csrf = await register(author, "reportedauthor")
        admin_csrf = await register(admin, "restoreadmin")
        post = await author.post("/api/v1/posts", json={"title": "Bad", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": author_csrf})
        report = await client.post("/api/v1/reports", json={"post_id": post.json()["id"], "reason": "spam"}, headers={"X-CSRF-Token": moderator_csrf})
        async with client._transport.app.state.session_factory() as session:
            moderator = await session.scalar(select(User).where(User.username_normalized == "reportmoder"))
            restore_admin = await session.scalar(select(User).where(User.username_normalized == "restoreadmin"))
            moderator.role = "moderator"
            restore_admin.role = "admin"
            await session.commit()
        resolved = await client.patch(f"/api/v1/admin/reports/{report.json()['id']}", json={"status": "resolved", "resolution": "spam account", "hide_target": True, "ban_author": True}, headers={"X-CSRF-Token": moderator_csrf})
        assert resolved.status_code == 200
        assert resolved.json()["target"]["is_deleted"] is True
        assert (await author.get("/api/v1/users/me")).status_code == 401
        assert (await admin.patch(f"/api/v1/admin/posts/{post.json()['id']}/restore", json={"reason": "appeal"}, headers={"X-CSRF-Token": admin_csrf})).status_code == 204
        actions = await admin.get("/api/v1/admin/moderation-actions")
        names = {action["action"] for action in actions.json()["items"]}
        assert {"report_resolved", "post_hide", "user_ban", "post_restore"} <= names
    finally:
        await author.aclose()
        await admin.aclose()


@pytest.mark.asyncio
async def test_moderator_can_hide_post(client: AsyncClient) -> None:
    moderator_csrf = await register(client, "postmoder")
    author = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        author_csrf = await register(author, "postauthor")
        post = await author.post("/api/v1/posts", json={"title": "Hidden", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": author_csrf})
        async with client._transport.app.state.session_factory() as session:
            moderator = await session.scalar(select(User).where(User.username_normalized == "postmoder"))
            moderator.role = "moderator"
            await session.commit()
        hidden = await client.patch(f"/api/v1/admin/posts/{post.json()['id']}/hide", json={"reason": "spam"}, headers={"X-CSRF-Token": moderator_csrf})
        assert hidden.status_code == 204
        assert (await author.get(f"/api/v1/posts/{post.json()['id']}")).status_code == 404
    finally:
        await author.aclose()


@pytest.mark.asyncio
async def test_banned_author_and_post_remain_public(client: AsyncClient) -> None:
    admin_csrf = await register(client, "visibilityadmin")
    author = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        author_csrf = await register(author, "visiblebanned")
        post = await author.post("/api/v1/posts", json={"title": "Visible", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": author_csrf})
        async with client._transport.app.state.session_factory() as session:
            admin = await session.scalar(select(User).where(User.username_normalized == "visibilityadmin"))
            target = await session.scalar(select(User).where(User.username_normalized == "visiblebanned"))
            admin.role = "admin"
            await session.commit()
        banned = await client.patch(f"/api/v1/admin/users/{target.id}/moderation", json={"action": "ban", "reason": "spam"}, headers={"X-CSRF-Token": admin_csrf})
        assert banned.status_code == 200
        public_post = await client.get(f"/api/v1/posts/{post.json()['id']}")
        assert public_post.status_code == 200
        assert public_post.json()["author"]["status"] == "banned"
        assert public_post.json()["author"]["is_banned"] is True
    finally:
        await author.aclose()


@pytest.mark.asyncio
async def test_admin_deletes_account_without_deleting_old_post(client: AsyncClient) -> None:
    admin_csrf = await register(client, "deleteadmin")
    target = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        target_csrf = await register(target, "deletedauthor")
        post = await target.post("/api/v1/posts", json={"title": "Retained", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": target_csrf})
        async with client._transport.app.state.session_factory() as session:
            admin = await session.scalar(select(User).where(User.username_normalized == "deleteadmin"))
            victim = await session.scalar(select(User).where(User.username_normalized == "deletedauthor"))
            admin.role = "admin"
            await session.commit()
        assert (await client.delete(f"/api/v1/admin/users/{admin.id}", headers={"X-CSRF-Token": admin_csrf})).status_code == 403
        deleted = await client.delete(f"/api/v1/admin/users/{victim.id}", headers={"X-CSRF-Token": admin_csrf})
        assert deleted.status_code == 204
        retained = await client.get(f"/api/v1/posts/{post.json()['id']}")
        assert retained.status_code == 200
        assert retained.json()["author"]["is_deleted"] is True
        assert retained.json()["author"]["avatar_url"] is None
        assert (await client.get("/api/v1/users/deletedauthor")).status_code == 404
        actions = await client.get("/api/v1/admin/moderation-actions")
        assert any(action["action"] == "user_delete" for action in actions.json()["items"])
    finally:
        await target.aclose()

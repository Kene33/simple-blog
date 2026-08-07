import { expect, test } from "@playwright/test";

for (const path of ["/", "/login", "/messages"]) {
  test(`route ${path} renders without an application error`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(path, { waitUntil: "networkidle" });
    await expect(page.locator("body")).not.toBeEmpty();
    await expect(page.locator(".vite-error-overlay, [data-nextjs-dialog]")).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test("messages page exposes offline state for a signed-in user", async ({ page, context }) => {
  await page.route(/\/api\/v1\/users\/me(?:\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "u1", username: "alice", role: "user", status: "active" }) }));
  await page.route(/\/api\/v1\/conversations(?:\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ id: "c1", kind: "direct", participant: { id: "u2", username: "bob" }, participants: [{ id: "u2", username: "bob" }], muted: false, blocked: false, unread_count: 0, last_message: null }], next_cursor: null }) }));
  await page.route(/\/api\/v1\/conversations\/c1\/messages(?:\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], next_cursor: null }) }));
  await page.route(/\/api\/v1\/messaging\/devices(?:\?.*)?$/, (route) => route.fulfill({ status: route.request().method() === "POST" ? 201 : 200, contentType: "application/json", body: JSON.stringify(route.request().method() === "POST" ? { id: "d1", user_id: "u1", public_key: { kty: "EC", crv: "P-256", x: "x", y: "y" }, created_at: new Date().toISOString() } : { items: [] }) }));
  await page.route(/\/api\/v1\/conversations\/c1\/devices$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ id: "d1", user_id: "u1", public_key: { kty: "EC", crv: "P-256", x: "x", y: "y" } }] }) }));
  await page.goto("/messages", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /bob/i }).click();
  await context.setOffline(true);
  await expect(page.locator(".socket-state")).toContainText("Офлайн");
  await expect(page.locator(".message-composer")).toBeVisible();
});

test("messages page resyncs history after websocket reconnect", async ({ page }) => {
  await page.addInitScript(() => {
    window.__socketInstances = [];
    class FakeWebSocket {
      static OPEN = 1;
      constructor() {
        this.readyState = FakeWebSocket.OPEN;
        window.__socketInstances.push(this);
        setTimeout(() => this.onopen?.(), 0);
      }
      send() {}
      close() {
        this.readyState = 3;
        this.onclose?.();
      }
    }
    window.WebSocket = FakeWebSocket;
  });
  let historyRequests = 0;
  await page.route(/\/api\/v1\/users\/me(?:\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "u1", username: "alice", role: "user", status: "active" }) }));
  await page.route(/\/api\/v1\/conversations(?:\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ id: "c1", kind: "direct", participant: { id: "u2", username: "bob" }, participants: [{ id: "u2", username: "bob" }], muted: false, blocked: false, unread_count: 0, last_message: null }], next_cursor: null }) }));
  await page.route(/\/api\/v1\/conversations\/c1\/messages(?:\?.*)?$/, (route) => {
    historyRequests += 1;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], next_cursor: null }) });
  });
  await page.route(/\/api\/v1\/messaging\/devices(?:\?.*)?$/, (route) => route.fulfill({ status: route.request().method() === "POST" ? 201 : 200, contentType: "application/json", body: JSON.stringify(route.request().method() === "POST" ? { id: "d1", user_id: "u1", public_key: { kty: "EC", crv: "P-256", x: "x", y: "y" }, created_at: new Date().toISOString() } : { items: [] }) }));
  await page.route(/\/api\/v1\/conversations\/c1\/devices$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ id: "d1", user_id: "u1", public_key: { kty: "EC", crv: "P-256", x: "x", y: "y" } }] }) }));
  await page.goto("/messages", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /bob/i }).click();
  await expect(page.locator(".socket-state")).toContainText("В сети");
  const beforeReconnect = historyRequests;
  await page.evaluate(() => window.__socketInstances.at(-1).close());
  await expect.poll(() => historyRequests, { timeout: 5000 }).toBeGreaterThan(beforeReconnect);
  await expect(page.locator(".socket-state")).toContainText("В сети");
});

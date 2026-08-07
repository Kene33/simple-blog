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
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "u1", username: "alice", role: "user", status: "active" }) }));
  await page.route("**/api/v1/conversations", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ id: "c1", kind: "direct", participant: { id: "u2", username: "bob" }, participants: [{ id: "u2", username: "bob" }], muted: false, blocked: false, unread_count: 0, last_message: null }], next_cursor: null }) }));
  await page.route("**/api/v1/conversations/c1/messages**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], next_cursor: null }) }));
  await page.goto("/messages", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /bob/i }).click();
  await context.setOffline(true);
  await expect(page.locator(".socket-state")).toContainText("Офлайн");
  await expect(page.locator(".message-composer")).toBeVisible();
});

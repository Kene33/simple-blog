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

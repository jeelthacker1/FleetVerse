import { test, expect } from "@playwright/test";

test("desktop and tablet layouts render without horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Every robot/ }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/landing.png", fullPage: true });
  await page.goto("/console");
  await page.getByLabel("Password", { exact: true }).fill("fleetverse-demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Warehouse live view" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/mission-control.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1024, height: 900 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "test-results/tablet.png", fullPage: true });
});

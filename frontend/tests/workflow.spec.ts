import { test, expect, Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

async function completeCase(page: Page, name = "Amina Khan", adjust?: (page: Page) => Promise<void>) {
  await page.goto("/");
  await expect(page.getByText("Service connected")).toBeVisible();
  await page.getByLabel("Patient name", { exact: true }).fill(name);
  await page.getByLabel("Patient age", { exact: true }).fill("39");
  await page.getByLabel("Patient gender", { exact: true }).selectOption("female");
  await page.getByLabel("Body mass", { exact: true }).fill("61");
  await page.getByRole("group", { name: "Allergies", exact: true }).getByLabel("None known", { exact: true }).check();
  await page.getByRole("group", { name: "Ongoing medications", exact: true }).getByLabel("None known", { exact: true }).check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("group", { name: "Heart & circulation history" }).getByLabel("No known problem", { exact: true }).check();
  await page.getByRole("group", { name: "Kidneys history" }).getByLabel("Known conditions", { exact: true }).check();
  await page.getByLabel("Add Kidneys condition", { exact: true }).selectOption("ckd");
  await page.getByRole("group", { name: "Liver history" }).getByLabel("No known problem", { exact: true }).check();
  await page.getByRole("group", { name: "Lungs & breathing history" }).getByLabel("Unknown / not assessed", { exact: true }).check();
  await page.getByLabel("BP-related history", { exact: true }).selectOption("none_known");
  await page.getByLabel("Systolic blood pressure", { exact: true }).fill("118");
  await page.getByLabel("Diastolic blood pressure", { exact: true }).fill("76");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Medication 1", { exact: true }).selectOption("ibuprofen");
  await page.getByLabel("Dose 1", { exact: true }).fill("400");
  await page.getByLabel("Start time 1", { exact: true }).fill("10");
  await page.getByRole("button", { name: "Add medication", exact: true }).click();
  await page.getByLabel("Medication 2", { exact: true }).selectOption("morphine");
  await page.getByLabel("Dose 2", { exact: true }).fill("5");
  await page.getByLabel("Start time 2", { exact: true }).fill("20");
  if (adjust) await adjust(page);
  await page.getByRole("button", { name: "Review assessment", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review the assessment", exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: /Run the evidence assessment/ }).check();
  await page.getByRole("button", { name: "Run assessment", exact: true }).click();
  await expect(page.getByRole("heading", { name: name || "Patient assessment", exact: true })).toBeVisible();
  await expect(page.getByText("Assessment complete", { exact: true })).toBeVisible();
  await expect(page.locator("canvas")).toBeVisible();
}

test("complete intake, scene, seeking, graphs, report and PDF", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await completeCase(page);
  await page.getByRole("button", { name: "Pause playback", exact: true }).click();
  await page.getByLabel("Simulation time", { exact: true }).fill("100");
  await page.getByRole("button", { name: "Inspect Kidneys", exact: true }).click();
  await expect(page.locator(".organ-inspection").getByText("Review concern", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../artifacts/rebuild/desktop-simulation.png", fullPage: true });
  const first = await page.locator("canvas").screenshot();
  fs.writeFileSync("../artifacts/rebuild/canvas-still.png", first);
  await page.getByRole("button", { name: "Play playback", exact: true }).click();
  await page.waitForTimeout(700);
  const second = await page.locator("canvas").screenshot();
  fs.writeFileSync("../artifacts/rebuild/canvas-moving.png", second);
  expect(first.equals(second)).toBeFalsy();
  await page.getByRole("tab", { name: "Assessment report", exact: true }).click();
  await expect(page.getByText("Systolic blood pressure", { exact: true })).toBeVisible();
  await expect(page.locator(".lab-report").getByText("400 mg", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../artifacts/rebuild/desktop-report.png", fullPage: true });
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF", exact: true }).click();
  const download = await downloading;
  await download.saveAs("../artifacts/rebuild/browser-report.pdf");
  expect(fs.readFileSync("../artifacts/rebuild/browser-report.pdf").subarray(0, 4).toString()).toBe("%PDF");
  await page.getByRole("tab", { name: "Graphs", exact: true }).click();
  await expect(page.locator(".graphs-view .recharts-surface")).toHaveCount(2);
  expect(errors).toEqual([]);
});

test("mobile workflow, body framing and no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await completeCase(page, "");
  await page.locator("canvas").screenshot({ path: "../artifacts/rebuild/canvas-mobile.png" });
  await page.screenshot({ path: "../artifacts/rebuild/mobile-simulation.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.locator("canvas").screenshot({ path: "../artifacts/rebuild/canvas-mobile-375.png" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole("tab", { name: "Assessment report", exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: "../artifacts/rebuild/mobile-report.png", fullPage: true });
});

test("repeated administrations display only applied events at the selected time", async ({ page }) => {
  await completeCase(page, "Repeat Schedule", async page => {
    await page.getByLabel("Administrations 1", { exact: true }).fill("2");
    await page.getByLabel("Interval 1", { exact: true }).fill("30");
  });
  await page.getByLabel("Simulation time", { exact: true }).fill("5");
  await expect(page.locator(".active-exposures > div")).toHaveCount(0);
  await page.getByLabel("Simulation time", { exact: true }).fill("35");
  await expect(page.locator(".active-exposures > div")).toHaveCount(2);
  await page.getByLabel("Simulation time", { exact: true }).fill("50");
  await expect(page.locator(".active-exposures > div")).toHaveCount(3);
  await expect(page.locator(".active-exposures").getByText("At 40s", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.locator("canvas").screenshot({ path: "../artifacts/rebuild/canvas-wide.png" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test("required patient fields prevent advancing and intake starts blank", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Service connected")).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Patient information", exact: true })).toBeVisible();
  await expect(page.getByLabel("Patient age", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Patient gender", { exact: true }).locator("option")).toHaveText(["Select gender...", "Male", "Female"]);
  await expect(page.getByLabel("Physiological sex parameter")).toHaveCount(0);
  await page.screenshot({ path: "../artifacts/rebuild/desktop-intake.png", fullPage: true });
});

test("restored report retains editable intake and measurement edits require review", async ({ page }) => {
  await completeCase(page, "Restored Patient");
  await page.reload();
  await page.getByRole("button", { name: "Open report", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Restored Patient", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit case", exact: true }).click();
  await expect(page.getByLabel("Patient name", { exact: true })).toHaveValue("Restored Patient");
  await expect(page.getByLabel("Patient age", { exact: true })).toHaveValue("39");
  await page.getByRole("navigation", { name: "Assessment workflow" }).getByRole("button", { name: /Medication plan/ }).click();
  await expect(page.getByLabel("Dose 1", { exact: true })).toHaveValue("400");
  await page.getByRole("button", { name: "Review assessment", exact: true }).click();
  await page.getByRole("checkbox", { name: /Run the evidence assessment/ }).check();
  await page.getByRole("navigation", { name: "Assessment workflow" }).getByRole("button", { name: /Patient information/ }).click();
  await page.getByRole("button", { name: "Add measurement", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Assessment workflow" }).getByRole("button", { name: /Review & run/ })).toBeDisabled();
  await page.getByLabel("Measurement 1", { exact: true }).selectOption("creatinine");
  await page.getByLabel("Measurement value 1", { exact: true }).fill("1.4");
  await page.getByRole("navigation", { name: "Assessment workflow" }).getByRole("button", { name: /Medication plan/ }).click();
  await page.getByRole("button", { name: "Review assessment", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: /Run the evidence assessment/ })).not.toBeChecked();
});

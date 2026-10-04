import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests", timeout: 60000, expect: { timeout: 15000 }, workers: 1,
  outputDir: "../artifacts/rebuild/browser", reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:3000", viewport: { width: 1440, height: 1000 }, headless: true,
    launchOptions: { args: ["--enable-unsafe-swiftshader"] }, screenshot: "only-on-failure" },
});

import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";

const frontendDirectory = fileURLToPath(new URL(".", import.meta.url));
const e2eDirectory = fileURLToPath(new URL("./tests/e2e", import.meta.url));

export default defineConfig({
  testDir: e2eDirectory,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    cwd: frontendDirectory,
    env: {
      VITE_DEV_BEARER_TOKEN: "codexforge-playwright-local-token",
    },
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
  },
});

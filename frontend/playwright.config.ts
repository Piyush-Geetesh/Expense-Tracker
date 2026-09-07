import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  use: { baseURL: "http://127.0.0.1:3001", channel: "msedge", trace: "retain-on-failure" },
  webServer: [
    { command: "python ../manage.py runserver 127.0.0.1:8001 --settings=config.e2e_settings --noreload",
      url: "http://127.0.0.1:8001/api/auth/csrf/", reuseExistingServer: false, timeout: 60000 },
    { command: "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3001",
      url: "http://127.0.0.1:3001/login", reuseExistingServer: false, timeout: 120000,
      env: { DJANGO_API_ORIGIN: "http://127.0.0.1:8001", NEXT_TELEMETRY_DISABLED: "1" } },
  ],
});

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

function config(origin, hosted = true) {
  const env = { ...process.env };
  delete env.DJANGO_API_ORIGIN;
  delete env.VERCEL;
  if (hosted) env.VERCEL = "1";
  if (origin !== undefined) env.DJANGO_API_ORIGIN = origin;
  return spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e",
    "const {default: c}=await import('./next.config.ts'); console.log(JSON.stringify(await c.rewrites()));"],
    { env, encoding: "utf8" });
}
test("Vercel rejects missing and local backend origins", () => {
  for (const origin of [undefined, "http://127.0.0.1:8000", "https://localhost", "https://[::1]"]) {
    assert.notEqual(config(origin).status, 0);
  }
});
test("Vercel forwards to the HTTPS backend with a trailing slash", () => {
  const result = config("https://expense-api.onrender.com");
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), [{source: "/api/:path*", destination: "https://expense-api.onrender.com/api/:path*/"}]);
});
test("origin must not contain credentials, paths, query, or fragments", () => {
  for (const origin of ["https://user:password@example.com", "https://example.com/api", "https://example.com?x=1", "https://example.com/#x"]) {
    assert.notEqual(config(origin).status, 0);
  }
});
test("local development retains the localhost fallback", () => {
  const result = config(undefined, false);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout)[0].destination, "http://127.0.0.1:8000/api/:path*/");
});

import { test } from "node:test";
import assert from "node:assert/strict";
import { publicHostingConfig } from "./public-hosting-config.mjs";
import { hostingConfig } from "./hosting-config.mjs";
import { assignmentHostingConfig } from "./assignment-hosting-config.mjs";
const env = {
  WORKPAPER_PROFILE: "public-demo",
  NEXT_PUBLIC_PUBLIC_DEMO: "1",
  NEXT_PUBLIC_API_URL: "",
  WORKPAPER_PUBLIC_ORIGIN: "https://public-demo.vercel.app",
  WORKPAPER_BACKEND_ORIGIN: "https://public-demo.onrender.com",
};
test("public demo needs no reviewer credentials or custom domain", () => {
  const config = publicHostingConfig(env);
  assert.equal(
    config.rewrites[0].destination,
    "https://public-demo.onrender.com/api/:path*",
  );
  assert.equal(
    config.redirects[0].destination,
    "https://public-demo.vercel.app/:path*",
  );
});
for (const change of [
  { WORKPAPER_PROFILE: "assignment-demo" },
  { WORKPAPER_HOSTED: "1" },
  { NEXT_PUBLIC_PUBLIC_DEMO: undefined },
  { NEXT_PUBLIC_API_URL: "http://localhost:8000" },
  { WORKPAPER_PUBLIC_ORIGIN: "https://evil.example" },
  { WORKPAPER_PUBLIC_ORIGIN: "https://public-demo.vercel.app/path" },
  { WORKPAPER_BACKEND_ORIGIN: "https://evil.example" },
  { WORKPAPER_BACKEND_ORIGIN: "https://secret@public-demo.onrender.com" },
  { WORKPAPER_BACKEND_ORIGIN: "http://public-demo.onrender.com" },
  { WORKPAPER_BACKEND_ORIGIN: "https://public-demo.onrender.com/path" },
  {
    WORKPAPER_BACKEND_ORIGIN: "http://127.0.0.1:8300",
    WORKPAPER_PUBLIC_ORIGIN: "https://localhost:3300",
    WORKPAPER_PUBLIC_TEST: "1",
    WORKPAPER_ENV: "test",
    VERCEL: "1",
  },
])
  test("public demo refuses " + JSON.stringify(Object.keys(change)), () =>
    assert.throws(() => publicHostingConfig({ ...env, ...change })),
  );
test("existing secure and assignment configurations remain fail closed", () => {
  assert.throws(() => hostingConfig({ ...env, WORKPAPER_HOSTED: "1" }));
  assert.throws(() => assignmentHostingConfig(env));
});

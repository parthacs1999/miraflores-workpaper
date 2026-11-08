import { test } from "node:test";
import assert from "node:assert/strict";
import { hostingConfig } from "./hosting-config.mjs";
test("local configuration retains explicit regression servers", () =>
  assert.deepEqual(
    hostingConfig({ NEXT_PUBLIC_API_URL: "http://localhost:8200" }),
    { hosted: false, rewrites: [], redirects: [] },
  ));
for (const value of [
  undefined,
  "http://localhost:8000",
  "https://evil.example",
])
  test("hosted refuses browser API destination " + value, () =>
    assert.throws(() =>
      hostingConfig({ WORKPAPER_HOSTED: "1", NEXT_PUBLIC_API_URL: value }),
    ),
  );
for (const origin of [
  "http://service.onrender.com",
  "https://evil.example",
  "https://service.onrender.com/a",
  "https://secret@service.onrender.com",
  "https://service.onrender.com?target=evil",
])
  test("fixed proxy rejects " + origin, () =>
    assert.throws(() =>
      hostingConfig({
        WORKPAPER_HOSTED: "1",
        WORKPAPER_PUBLIC_ORIGIN: "https://workpaper.example.test",
        NEXT_PUBLIC_API_URL: "",
        WORKPAPER_BACKEND_ORIGIN: origin,
      }),
    ),
  );
test("hosted exact same-origin proxy forwards the original API path", () =>
  assert.deepEqual(
    hostingConfig({
      WORKPAPER_HOSTED: "1",
      WORKPAPER_PUBLIC_ORIGIN: "https://workpaper.example.test",
      NEXT_PUBLIC_API_URL: "",
      WORKPAPER_BACKEND_ORIGIN: "https://tax-demo.onrender.com",
    }).rewrites,
    [
      {
        source: "/api/:path*",
        destination: "https://tax-demo.onrender.com/api/:path*",
      },
    ],
  ));
test("local test override cannot bypass hosted origin restrictions", () =>
  assert.throws(() =>
    hostingConfig({
      VERCEL: "1",
      WORKPAPER_ENV: "test",
      WORKPAPER_PROXY_TEST: "1",
      NEXT_PUBLIC_API_URL: "",
      WORKPAPER_BACKEND_ORIGIN: "http://127.0.0.1:8300",
    }),
  ));
test("isolated loopback proxy requires the explicit local test environment", () =>
  assert.equal(
    hostingConfig({
      WORKPAPER_ENV: "test",
      WORKPAPER_PROXY_TEST: "1",
      NEXT_PUBLIC_API_URL: "",
      WORKPAPER_BACKEND_ORIGIN: "http://127.0.0.1:8300",
    }).rewrites.length,
    1,
  ));

test("noncanonical aliases redirect only to the configured protected application", () => {
  const c = hostingConfig({
    WORKPAPER_HOSTED: "1",
    WORKPAPER_PUBLIC_ORIGIN: "https://workpaper.example.test",
    NEXT_PUBLIC_API_URL: "",
    WORKPAPER_BACKEND_ORIGIN: "https://tax-demo.onrender.com",
  });
  assert.equal(
    c.redirects[0].destination,
    "https://workpaper.example.test/:path*",
  );
  assert.equal(c.redirects[0].missing[0].value, "workpaper\\.example\\.test");
});
test("ordinary production builds fail closed even when platform system variables are absent", () =>
  assert.throws(() =>
    hostingConfig({
      NODE_ENV: "production",
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
    }),
  ));
test("explicit local build does not relax a Vercel build", () =>
  assert.throws(() =>
    hostingConfig({
      VERCEL: "1",
      WORKPAPER_LOCAL_BUILD: "1",
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
    }),
  ));

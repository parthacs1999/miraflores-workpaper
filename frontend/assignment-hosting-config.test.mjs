import { test } from "node:test";
import assert from "node:assert/strict";
import { assignmentHostingConfig } from "./assignment-hosting-config.mjs";
import { hostingConfig } from "./hosting-config.mjs";
const env = {
  WORKPAPER_ASSIGNMENT_VERCEL_ELIGIBILITY: "personal-noncommercial-confirmed",
  WORKPAPER_PROFILE: "assignment-demo",
  NEXT_PUBLIC_ASSIGNMENT_DEMO: "1",
  NEXT_PUBLIC_API_URL: "",
  WORKPAPER_PUBLIC_ORIGIN: "https://assignment.vercel.app",
  WORKPAPER_BACKEND_ORIGIN: "https://assignment.onrender.com",
};
test("separate free profile fixes its API target and labels itself explicitly", () => {
  const result = assignmentHostingConfig(env);
  assert.equal(
    result.rewrites[0].destination,
    "https://assignment.onrender.com/api/:path*",
  );
  assert.equal(
    result.redirects[0].destination,
    "https://assignment.vercel.app/:path*",
  );
});
for (const changes of [
  { WORKPAPER_ASSIGNMENT_VERCEL_ELIGIBILITY: undefined },
  { WORKPAPER_HOSTED: "1" },
  { NEXT_PUBLIC_API_URL: "http://localhost:8000" },
  { NEXT_PUBLIC_ASSIGNMENT_DEMO: undefined },
  { WORKPAPER_PUBLIC_ORIGIN: "https://evil.example" },
  { WORKPAPER_BACKEND_ORIGIN: "https://evil.example" },
  { WORKPAPER_BACKEND_ORIGIN: "https://user:secret@assignment.onrender.com" },
  { WORKPAPER_BACKEND_ORIGIN: "https://assignment.onrender.com/api" },
  {
    WORKPAPER_ASSIGNMENT_TUNNEL: "1",
    VERCEL: "1",
    WORKPAPER_PUBLIC_ORIGIN: "https://test.trycloudflare.com",
    WORKPAPER_BACKEND_ORIGIN: "http://127.0.0.1:8000",
  },
])
  test("assignment rejects " + JSON.stringify(Object.keys(changes)), () =>
    assert.throws(() => assignmentHostingConfig({ ...env, ...changes })),
  );
test("scheduled local tunnel allows only fixed loopback backend", () => {
  assert.equal(
    assignmentHostingConfig({
      ...env,
      WORKPAPER_ASSIGNMENT_TUNNEL: "1",
      WORKPAPER_PUBLIC_ORIGIN: "https://test.trycloudflare.com",
      WORKPAPER_BACKEND_ORIGIN: "http://127.0.0.1:8000",
    }).rewrites[0].destination,
    "http://127.0.0.1:8000/api/:path*",
  );
});
test("secure hosted policy continues rejecting free hostnames", () =>
  assert.throws(() => hostingConfig({ ...env, WORKPAPER_HOSTED: "1" })));

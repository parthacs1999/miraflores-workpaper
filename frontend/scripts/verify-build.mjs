/** Reject legacy or third-party backend artifacts after a real Next.js build. */
import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { resolve, relative } from "node:path";
import { pathToFileURL } from "node:url";
import { publicHostingConfig } from "../public-hosting-config.mjs";

function files(root) {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const name = resolve(root, entry.name);
    return entry.isDirectory() ? files(name) : entry.isFile() ? [name] : [];
  });
}
const forbidden = [
  ["Supabase", /supabase|\breview_notes\b|\baudit_log\b/i],
  ["Vite", /\bvite\b|__vite__|\/@vite\/|vite\.svg|import\.meta\.env/i],
];

export function verifyBuild(root, env = process.env) {
  root = resolve(root);
  for (const required of [
    "BUILD_ID",
    "build-manifest.json",
    "routes-manifest.json",
  ]) {
    if (
      !existsSync(resolve(root, required)) ||
      !statSync(resolve(root, required)).isFile()
    )
      throw new Error("Expected Next.js output is missing " + required);
  }
  if (!readFileSync(resolve(root, "BUILD_ID"), "utf8").trim())
    throw new Error("Next.js BUILD_ID is empty");
  JSON.parse(readFileSync(resolve(root, "build-manifest.json"), "utf8"));
  const assets = files(resolve(root, "static")).filter((p) =>
    /\.(js|css|html|map)$/.test(p),
  );
  const html = files(resolve(root, "server/app")).filter((p) =>
    p.endsWith(".html"),
  );
  if (!assets.some((p) => p.endsWith(".js")))
    throw new Error("Next.js browser JavaScript is missing");
  for (const file of [...assets, ...html]) {
    const content = readFileSync(file, "utf8");
    for (const [label, pattern] of forbidden)
      if (pattern.test(content))
        throw new Error(
          "Unexpected " +
            label +
            " reference in generated frontend asset " +
            relative(root, file),
        );
  }
  if (env.WORKPAPER_PROFILE === "public-demo") {
    const expected = publicHostingConfig(env).rewrites[0];
    const manifest = JSON.parse(
      readFileSync(resolve(root, "routes-manifest.json"), "utf8"),
    );
    const routes = Array.isArray(manifest.rewrites)
      ? manifest.rewrites
      : Object.values(manifest.rewrites ?? {}).flat();
    const api = routes.filter((r) => r.source === "/api/:path*");
    if (api.length !== 1 || api[0].destination !== expected.destination)
      throw new Error(
        "Public build must contain exactly the configured FastAPI /api rewrite",
      );
    const page = resolve(root, "server/app/index.html");
    if (
      !existsSync(page) ||
      !readFileSync(page, "utf8").includes("PUBLIC FICTIONAL DEMO") ||
      !readFileSync(page, "utf8").includes("/_next/")
    )
      throw new Error(
        "Public Next.js root page or demonstration indicator is missing",
      );
  }
  return { browserAssets: assets.length, htmlPages: html.length };
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  try {
    const result = verifyBuild(
      resolve(process.cwd(), process.env.NEXT_DIST_DIR ?? ".next"),
    );
    process.stdout.write(
      `Verified Next.js frontend: ${result.browserAssets} browser assets; no unexpected backend or Vite references.\n`,
    );
  } catch (error) {
    process.stderr.write(
      "Frontend artifact verification failed: " + error.message + "\n",
    );
    process.exitCode = 1;
  }
}

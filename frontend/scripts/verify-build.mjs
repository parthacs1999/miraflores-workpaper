/** Reject legacy or third-party backend artifacts after a real Next.js build. */
import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { resolve, relative, isAbsolute } from "node:path";
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

// Resolve artifact references from Next's manifests, never a guessed HTML location.
function artifact(root, name) {
  if (
    typeof name !== "string" ||
    isAbsolute(name) ||
    name.split(/[\\/]/).includes("..")
  )
    throw new Error("Invalid Next.js artifact reference");
  const path = resolve(root, name);
  if (!existsSync(path) || !statSync(path).isFile() || !statSync(path).size)
    throw new Error("Expected Next.js artifact is missing: " + name);
  return path;
}
function jsonArtifact(root, name) {
  return JSON.parse(readFileSync(artifact(root, name), "utf8"));
}
function rootClientScripts(root, assets) {
  const routes = jsonArtifact(root, "app-path-routes-manifest.json");
  const entries = jsonArtifact(root, "server/app-paths-manifest.json");
  const pages = Object.keys(routes).filter(
    (key) => routes[key] === "/" && key.endsWith("/page"),
  );
  if (!pages.length)
    throw new Error("Next.js root page is missing from route manifests");
  const scripts = new Set();
  for (const page of pages) {
    const entry = entries[page];
    artifact(root, typeof entry === "string" ? "server/" + entry : entry);
    if (!entry.endsWith(".js"))
      throw new Error("Unsupported Next.js root page entry");
    const source = readFileSync(
      artifact(
        root,
        "server/" + entry.replace(/\.js$/, "_client-reference-manifest.js"),
      ),
      "utf8",
    );
    // Next emits a JSON assignment. Parse its data without executing build output.
    const match = source.match(
      /globalThis\.__RSC_MANIFEST\[("(?:[^"\\]|\\.)*")\]\s*=\s*([\s\S]+?)\s*;?\s*$/,
    );
    if (!match || JSON.parse(match[1]) !== page)
      throw new Error("Invalid Next.js root client-reference manifest");
    const manifest = JSON.parse(match[2].replace(/;\s*$/, ""));
    const chunks = Object.values(manifest.clientModules ?? {})
      .flatMap((module) => module.chunks ?? [])
      .filter(
        (chunk) =>
          typeof chunk === "string" &&
          chunk.startsWith("static/") &&
          chunk.endsWith(".js"),
      );
    if (!chunks.length)
      throw new Error("Next.js root page client chunks are missing");
    for (const chunk of chunks) {
      const path = artifact(root, chunk);
      if (!assets.includes(path))
        throw new Error("Unscanned Next.js root client chunk");
      scripts.add(path);
    }
  }
  return [...scripts];
}

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
  const html = files(resolve(root, "server")).filter((p) =>
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
    // Adapter-enabled builds put HTML in scoped route-cache directories. The
    // route -> compiled entry -> client-reference graph is valid in both layouts.
    const scripts = rootClientScripts(root, assets);
    if (
      !scripts.some((path) =>
        readFileSync(path, "utf8").includes("PUBLIC FICTIONAL DEMO"),
      )
    )
      throw new Error(
        "Public demonstration indicator is missing from root-linked client chunks",
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

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, relative } from "node:path";
import ts from "typescript";
import { verifyBuild } from "./verify-build.mjs";
const frontend = resolve(import.meta.dirname, "..");
const env = {
  WORKPAPER_PROFILE: "public-demo",
  NEXT_PUBLIC_PUBLIC_DEMO: "1",
  NEXT_PUBLIC_API_URL: "",
  WORKPAPER_PUBLIC_ORIGIN: "https://demo.vercel.app",
  WORKPAPER_BACKEND_ORIGIN: "https://demo.onrender.com",
};
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "miraflores-artifact-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const dir of ["static/chunks", "server/app"])
    mkdirSync(join(root, dir), { recursive: true });
  writeFileSync(
    join(root, "app-path-routes-manifest.json"),
    JSON.stringify({ "/page": "/" }),
  );
  writeFileSync(
    join(root, "server/app-paths-manifest.json"),
    JSON.stringify({ "/page": "app/page.js" }),
  );
  writeFileSync(join(root, "server/app/page.js"), "module.exports = {};");
  writeFileSync(
    join(root, "server/app/page_client-reference-manifest.js"),
    'globalThis.__RSC_MANIFEST=(globalThis.__RSC_MANIFEST||{});globalThis.__RSC_MANIFEST["/page"]=' +
      JSON.stringify({
        clientModules: { page: { chunks: ["123", "static/chunks/page.js"] } },
      }) +
      ";",
  );
  writeFileSync(join(root, "BUILD_ID"), "isolated-test-build");
  writeFileSync(join(root, "build-manifest.json"), "{}");
  writeFileSync(
    join(root, "routes-manifest.json"),
    JSON.stringify({
      rewrites: {
        afterFiles: [
          {
            source: "/api/:path*",
            destination: "https://demo.onrender.com/api/:path*",
          },
        ],
      },
    }),
  );
  writeFileSync(
    join(root, "static/chunks/page.js"),
    'fetch("/api/workflow/notes");"PUBLIC FICTIONAL DEMO";',
  );
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html>PUBLIC FICTIONAL DEMO<script src="/_next/static/chunks/page.js"></script></html>',
  );
  return root;
}
test("valid Next.js public artifact uses the one existing FastAPI rewrite", (t) =>
  assert.equal(verifyBuild(fixture(t), env).browserAssets, 1));
for (const signature of [
  "https://wrong.supabase.co/rest/v1/review_notes",
  "@supabase/supabase-js",
  "audit_log",
  "import.meta.env.VITE_URL",
  "/@vite/client",
  "vite.svg",
])
  test("build rejects legacy signature " + signature, (t) => {
    const root = fixture(t);
    writeFileSync(join(root, "static/chunks/page.js"), signature);
    assert.throws(() => verifyBuild(root, env), /Unexpected/);
  });
test("Vite-only output cannot pass as Next.js", (t) => {
  const root = fixture(t);
  rmSync(join(root, "BUILD_ID"));
  assert.throws(() => verifyBuild(root, env), /Next.js output/);
});
test("missing or wrong API rewrite fails the production gate", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "routes-manifest.json"),
    JSON.stringify({ rewrites: [] }),
  );
  assert.throws(() => verifyBuild(root, env), /FastAPI/);
  writeFileSync(
    join(root, "routes-manifest.json"),
    JSON.stringify({
      rewrites: [
        {
          source: "/api/:path*",
          destination: "https://wrong.onrender.com/api/:path*",
        },
      ],
    }),
  );
  assert.throws(() => verifyBuild(root, env), /FastAPI/);
});
test("HTML cannot substitute for the real root route", (t) => {
  const root = fixture(t);
  writeFileSync(join(root, "app-path-routes-manifest.json"), "{}");
  assert.throws(() => verifyBuild(root, env), /root page/);
});
test("Git auto-deployment is not disabled and the production build always verifies artifacts", () => {
  const config = JSON.parse(
    readFileSync(join(frontend, "vercel.json"), "utf8"),
  );
  const pkg = JSON.parse(readFileSync(join(frontend, "package.json"), "utf8"));
  assert.equal(config.git?.deploymentEnabled, undefined);
  assert.equal(config.github?.enabled, undefined);
  assert.equal(config.framework, "nextjs");
  assert.equal(config.installCommand, "npm ci");
  assert.equal(config.buildCommand, "npm run build -- --webpack");
  assert.equal(config.outputDirectory, undefined);
  assert.equal(pkg.scripts.build, "next build");
  assert.equal(pkg.scripts.postbuild, "node scripts/verify-build.mjs");
  assert.ok(
    !Object.keys({ ...pkg.dependencies, ...pkg.devDependencies }).some((p) =>
      /supabase|axios|^vite$/.test(p),
    ),
  );
});
function sources(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory()
      ? sources(join(root, e.name))
      : /\.(tsx?|jsx?)$/.test(e.name)
        ? [join(root, e.name)]
        : [],
  );
}
test("all browser network calls use the shared FastAPI session client; no third-party SDKs or endpoints", () => {
  const direct = [];
  for (const file of sources(join(frontend, "src"))) {
    const content = readFileSync(file, "utf8");
    assert.doesNotMatch(
      content,
      /supabase|\breview_notes\b|\baudit_log\b|\baxios\b|\bcreateClient\b/i,
      file,
    );
    const source = ts.createSourceFile(
      file,
      content,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    function visit(node) {
      if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        node.expression.text === "fetch"
      )
        direct.push(relative(frontend, file));
      if (ts.isNewExpression(node))
        assert.ok(
          !["XMLHttpRequest", "WebSocket", "EventSource"].includes(
            node.expression.getText(source),
          ),
          file,
        );
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
  assert.deepEqual(direct, ["src/components/session.tsx"]);
  const config = readFileSync(join(frontend, "src/lib/api-config.ts"), "utf8");
  assert.match(config, /NEXT_PUBLIC_API_URL/);
});

test("public indicator may be in a root-linked Client Component instead of the prerendered shell", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html><div>Loading…</div><script defer src="/_next/static/chunks/page.js?dpl=fixture"></script></html>',
  );
  writeFileSync(
    join(root, "static/chunks/page.js"),
    'document.body.textContent="PUBLIC FICTIONAL DEMO";',
  );
  assert.equal(verifyBuild(root, env).browserAssets, 1);
});

test("HTML text boundaries and encoded whitespace do not hide the public indicator", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html><p>PUBLIC<!-- boundary --> <span>FICTIONAL</span>&nbsp;DEMO</p><script src="/_next/static/chunks/page.js"></script></html>',
  );
  assert.equal(verifyBuild(root, env).browserAssets, 1);
});

test("missing public indicator still fails even with correct config and Next.js assets", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "static/chunks/page.js"),
    'fetch("/api/workflow/notes");',
  );
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html>Loading<script src="/_next/static/chunks/page.js"></script></html>',
  );
  assert.throws(
    () => verifyBuild(root, env),
    /demonstration indicator is missing/,
  );
  writeFileSync(
    join(root, "static/chunks/unrelated-page.js"),
    '"PUBLIC FICTIONAL DEMO";',
  );
  assert.throws(
    () => verifyBuild(root, env),
    /demonstration indicator is missing/,
  );
});

test("Vercel adapter scoped HTML passes without server/app/index.html", (t) => {
  const root = fixture(t);
  const scoped = join(root, "server/route-cache/APP_PAGE/hash/$");
  mkdirSync(scoped, { recursive: true });
  writeFileSync(
    join(scoped, "index.html"),
    readFileSync(join(root, "server/app/index.html")),
  );
  rmSync(join(root, "server/app/index.html"));
  assert.equal(verifyBuild(root, { ...env, VERCEL: "1" }).htmlPages, 1);
  rmSync(join(scoped, "index.html"));
  assert.equal(verifyBuild(root, env).htmlPages, 0);
});
for (const name of [
  "app-path-routes-manifest.json",
  "server/app-paths-manifest.json",
  "server/app/page.js",
  "server/app/page_client-reference-manifest.js",
  "static/chunks/page.js",
]) {
  test("missing required root artifact fails: " + name, (t) => {
    const root = fixture(t);
    rmSync(join(root, name));
    assert.throws(() => verifyBuild(root, env), /missing/);
  });
}
for (const value of [
  'globalThis.__RSC_MANIFEST["/other/page"]={};',
  'globalThis.__RSC_MANIFEST["/page"]={};',
  'globalThis.__RSC_MANIFEST["/page"]={invalid};',
  'globalThis.__RSC_MANIFEST["/page"]={"clientModules":{"x":{"chunks":["static/../escape.js"]}}};',
  'globalThis.__RSC_MANIFEST["/page"]={"clientModules":{"x":{"chunks":["static/missing.js"]}}};',
])
  test("invalid or incomplete root client graph fails: " + value, (t) => {
    const root = fixture(t);
    writeFileSync(
      join(root, "server/app/page_client-reference-manifest.js"),
      value,
    );
    assert.throws(() => verifyBuild(root, env));
  });
test("scoped HTML still rejects forbidden assets", (t) => {
  const root = fixture(t);
  mkdirSync(join(root, "server/route-cache"), { recursive: true });
  writeFileSync(
    join(root, "server/route-cache/page.html"),
    '<script src="/@vite/client"></script>',
  );
  assert.throws(() => verifyBuild(root, env), /Unexpected Vite/);
});
test("route groups and manifest-selected entries work without a fixed page path", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "app-path-routes-manifest.json"),
    JSON.stringify({ "/(demo)/page": "/" }),
  );
  writeFileSync(
    join(root, "server/app-paths-manifest.json"),
    JSON.stringify({ "/(demo)/page": "app/custom.js" }),
  );
  writeFileSync(join(root, "server/app/custom.js"), "module.exports={};");
  writeFileSync(
    join(root, "server/app/custom_client-reference-manifest.js"),
    readFileSync(
      join(root, "server/app/page_client-reference-manifest.js"),
      "utf8",
    ).replace('["/page"]', '["/(demo)/page"]'),
  );
  assert.equal(verifyBuild(root, env).browserAssets, 1);
});

for (const name of [
  "NEXT_PUBLIC_PUBLIC_DEMO",
  "NEXT_PUBLIC_API_URL",
  "WORKPAPER_PUBLIC_ORIGIN",
  "WORKPAPER_BACKEND_ORIGIN",
]) {
  test("public build still rejects missing configuration " + name, (t) => {
    const root = fixture(t);
    assert.throws(() => verifyBuild(root, { ...env, [name]: undefined }));
  });
}

test("public indicator cannot excuse Supabase in a referenced script", (t) => {
  const root = fixture(t);
  writeFileSync(
    join(root, "server/app/index.html"),
    '<html>Loading<script src="/_next/static/chunks/page.js"></script></html>',
  );
  writeFileSync(
    join(root, "static/chunks/page.js"),
    '"PUBLIC FICTIONAL DEMO"; "https://wrong.supabase.co";',
  );
  assert.throws(() => verifyBuild(root, env), /Unexpected Supabase/);
});

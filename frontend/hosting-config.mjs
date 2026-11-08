/** Server-side only: request input never selects a destination or trust domain. */
export function hostingConfig(env = process.env) {
  const localBuild =
    env.WORKPAPER_LOCAL_BUILD === "1" ||
    [
      ".next-e2e",
      ".next-workflow-e2e",
      ".next-proxy-e2e",
      ".next-ui-verification",
    ].includes(env.NEXT_DIST_DIR);
  const hosted =
    env.VERCEL === "1" ||
    env.VERCEL_ENV === "production" ||
    env.WORKPAPER_HOSTED === "1" ||
    (env.NODE_ENV === "production" && !localBuild);
  const origin = env.WORKPAPER_BACKEND_ORIGIN;
  if (hosted && env.NEXT_PUBLIC_API_URL !== "")
    throw new Error(
      "Hosted frontend requires an explicitly empty NEXT_PUBLIC_API_URL for same-origin API access",
    );
  if (hosted && !origin)
    throw new Error("Hosted frontend requires WORKPAPER_BACKEND_ORIGIN");
  const redirects = [];
  if (hosted) {
    let publicUrl;
    try {
      publicUrl = new URL(env.WORKPAPER_PUBLIC_ORIGIN);
    } catch {
      throw new Error("Hosted frontend requires WORKPAPER_PUBLIC_ORIGIN");
    }
    if (
      publicUrl.protocol !== "https:" ||
      publicUrl.port ||
      publicUrl.username ||
      publicUrl.password ||
      publicUrl.pathname !== "/" ||
      publicUrl.search ||
      publicUrl.hash ||
      !publicUrl.hostname.includes(".") ||
      publicUrl.hostname.endsWith(".vercel.app") ||
      publicUrl.hostname.endsWith(".onrender.com") ||
      /^[\d.:]+$/.test(publicUrl.hostname)
    )
      throw new Error(
        "Public origin must be an exact HTTPS identity-protected custom domain",
      );
    const host = publicUrl.hostname.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    redirects.push({
      source: "/:path*",
      missing: [{ type: "host", value: host }],
      destination: publicUrl.origin + "/:path*",
      permanent: false,
    });
  }
  if (!origin) return { rewrites: [], hosted, redirects };
  let target;
  try {
    target = new URL(origin);
  } catch {
    throw new Error("Invalid backend origin");
  }
  const isolatedProxy =
    !hosted &&
    !env.VERCEL &&
    env.WORKPAPER_ENV === "test" &&
    env.WORKPAPER_PROXY_TEST === "1" &&
    target.protocol === "http:" &&
    ["localhost", "127.0.0.1"].includes(target.hostname);
  if (
    (!isolatedProxy &&
      (target.protocol !== "https:" ||
        !/^[a-z0-9-]+\.onrender\.com$/.test(target.hostname) ||
        target.port ||
        target.username ||
        target.password ||
        target.pathname !== "/" ||
        target.search ||
        target.hash)) ||
    (isolatedProxy &&
      (target.username ||
        target.password ||
        target.pathname !== "/" ||
        target.search ||
        target.hash))
  )
    throw new Error(
      "Backend must be an HTTPS Render origin without credentials, path or query",
    );
  if (env.NEXT_PUBLIC_API_URL !== "")
    throw new Error(
      "Proxy configuration requires an empty NEXT_PUBLIC_API_URL",
    );
  return {
    hosted,
    redirects,
    rewrites: [
      { source: "/api/:path*", destination: target.origin + "/api/:path*" },
    ],
  };
}

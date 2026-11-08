import { rmSync } from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";
export default function cleanup() {
  const folder = process.env.PROXY_E2E_DIR;
  if (
    folder &&
    path.dirname(folder) === tmpdir() &&
    path.basename(folder).startsWith("miraflores-proxy-e2e-")
  )
    rmSync(folder, { recursive: true, force: true });
}

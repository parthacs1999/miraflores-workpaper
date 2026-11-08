// TLS termination around the real production Next server, mimicking a hosting edge.
import https from "node:https";
import http from "node:http";
import { readFileSync } from "node:fs";
import path from "node:path";
const directory = process.env.PROXY_E2E_DIR;
if (process.env.WORKPAPER_ENV !== "test" || !directory)
  throw new Error("Isolated TLS fixture required");
const server = https.createServer(
  {
    key: readFileSync(path.join(directory, "tls-key.pem")),
    cert: readFileSync(path.join(directory, "tls-cert.pem")),
  },
  (req, res) => {
    const upstream = http.request(
      {
        hostname: "127.0.0.1",
        port: 3301,
        path: req.url,
        method: req.method,
        headers: req.headers,
      },
      (response) => {
        res.writeHead(response.statusCode, response.headers);
        response.pipe(res);
      },
    );
    upstream.on("error", () => {
      res.writeHead(502);
      res.end("Local test upstream unavailable");
    });
    req.pipe(upstream);
  },
);
server.listen(3300, "127.0.0.1");
process.on("SIGTERM", () => server.close());
process.on("SIGINT", () => server.close());

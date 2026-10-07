import { createServer, type RequestListener } from "node:http";
import { gzipSync } from "node:zlib";
import { expect, test } from "@playwright/test";
import { proxyGateway } from "../src/lib/gateway-proxy";

async function upstream(handler: RequestListener) {
  const server = createServer(handler);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("Missing test upstream address.");
  return { gateway: `http://127.0.0.1:${address.port}`, close: () => { server.closeAllConnections(); server.close(); } };
}

test("proxy retries one reset GET, preserving query/auth/binary and excluding hop-by-hop metadata", async () => {
  let calls = 0;
  const bytes = Buffer.from([0, 255, 13, 128]);
  const service = await upstream((request, response) => {
    ++calls;
    expect(request.url).toBe("/images/a%20b?x=one&x=two");
    expect(request.headers.authorization).toBe("Bearer fixture-only");
    expect(request.headers.connection).toBe("close");
    expect(request.headers["x-untrusted"]).toBeUndefined();
    expect(request.headers.host).not.toBe("untrusted.invalid");
    if (calls === 1) { request.socket.destroy(); return; }
    response.writeHead(206, { "content-type": "image/png", "content-encoding": "gzip", "content-length": gzipSync(bytes).length, "content-range": "bytes 0-3/4", etag: "fixture" });
    response.end(gzipSync(bytes));
  });
  try {
    const response = await proxyGateway(new Request("http://localhost:3000/api/images/a%20b?x=one&x=two", { headers: { authorization: "Bearer fixture-only", host: "untrusted.invalid", "x-untrusted": "ignored" } }), ["images", "a b"], service);
    expect(calls).toBe(2);
    expect(response.status).toBe(206);
    expect(response.headers.get("content-type")).toBe("image/png");
    expect(response.headers.get("content-range")).toBe("bytes 0-3/4");
    expect(response.headers.get("content-encoding")).toBeNull();
    expect(response.headers.get("content-length")).toBeNull();
    expect(Buffer.from(await response.arrayBuffer())).toEqual(bytes);
  } finally { service.close(); }
});

for (const method of ["POST", "PUT", "DELETE"]) {
  test(`proxy never retries a reset ${method} whose command may already have applied`, async () => {
    let calls = 0;
    let received = "";
    const service = await upstream((request) => {
      ++calls;
      expect(request.method).toBe(method);
      request.on("data", (chunk) => { received += chunk; });
      request.on("end", () => request.socket.destroy()); // simulate apply followed by lost acknowledgement
    });
    try {
      const response = await proxyGateway(new Request("http://localhost:3000/api/reset", { method, headers: { "content-type": "application/json" }, body: '{"fixture":true}' }), ["reset"], service);
      expect(calls).toBe(1);
      expect(received).toBe('{"fixture":true}');
      expect(response.status).toBe(502);
      expect((await response.json()).detail).toContain("command outcome is unknown");
    } finally { service.close(); }
  });
}

test("proxy preserves a gateway HTTP error without retrying it", async () => {
  let calls = 0;
  const service = await upstream((_request, response) => {
    ++calls;
    response.writeHead(401, { "content-type": "application/json", "www-authenticate": "Bearer" });
    response.end('{"detail":"Token expired"}');
  });
  try {
    const response = await proxyGateway(new Request("http://localhost:3000/api/auth/me"), ["auth", "me"], service);
    expect(calls).toBe(1);
    expect(response.status).toBe(401);
    expect(response.headers.get("www-authenticate")).toBe("Bearer");
    expect(await response.json()).toEqual({ detail: "Token expired" });
  } finally { service.close(); }
});

test("proxy bounds transport waits and does not retry timeouts", async () => {
  let calls = 0;
  const stalledFetch: typeof fetch = async (_url, init) => {
    ++calls;
    return await new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("Aborted")), { once: true }));
  };
  const response = await proxyGateway(new Request("http://localhost:3000/api/snapshot"), ["snapshot"], { fetch: stalledFetch, timeoutMs: 20 });
  expect(calls).toBe(1);
  expect(response.status).toBe(504);
  expect((await response.json()).detail).toContain("timed out");
});

test("proxy timeout still covers a stalled body after upstream headers arrive", async () => {
  const stalledBody: typeof fetch = async (_url, init) => new Response(new ReadableStream<Uint8Array>({
    start(controller) { init?.signal?.addEventListener("abort", () => controller.error(new Error("Body aborted")), { once: true }); },
  }));
  const response = await proxyGateway(new Request("http://localhost:3000/api/evaluation"), ["evaluation"], { fetch: stalledBody, timeoutMs: 20 });
  expect(response.status).toBe(504);
});

test("proxy stops after the second reset read and never retries client cancellation", async () => {
  let calls = 0;
  const resetFetch: typeof fetch = async () => { ++calls; throw Object.assign(new Error("Reset"), { code: "ECONNRESET" }); };
  const unavailable = await proxyGateway(new Request("http://localhost:3000/api/snapshot"), ["snapshot"], { fetch: resetFetch });
  expect(unavailable.status).toBe(502);
  expect(calls).toBe(2);
  calls = 0;
  const cancelled = new AbortController();
  cancelled.abort();
  const response = await proxyGateway(new Request("http://localhost:3000/api/snapshot", { signal: cancelled.signal }), ["snapshot"], { fetch: resetFetch });
  expect(response.status).toBe(499);
  expect(calls).toBe(1);
});

test("proxy preserves no-content HEAD and same-origin redirect paths", async () => {
  const service = await upstream((request, response) => {
    if (request.method === "HEAD") { response.writeHead(204); response.end(); return; }
    response.writeHead(307, { location: "/backend/?kind=sim" }); response.end();
  });
  try {
    const head = await proxyGateway(new Request("http://localhost:3000/api/health", { method: "HEAD" }), ["health"], service);
    expect(head.status).toBe(204);
    expect(await head.text()).toBe("");
    const redirect = await proxyGateway(new Request("http://localhost:3000/api/backend"), ["backend"], service);
    expect(redirect.status).toBe(307);
    expect(redirect.headers.get("location")).toBe("http://localhost:3000/api/backend/?kind=sim");
  } finally { service.close(); }
});

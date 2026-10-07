/** Server-only HTTP transport. The browser WebSocket continues directly to the gateway. */
const REQUEST_HEADERS = ["accept", "accept-language", "authorization", "content-type", "content-encoding", "cookie", "if-match", "if-none-match", "if-modified-since", "range", "x-request-id"];
const RESPONSE_HEADERS = ["content-type", "content-disposition", "content-range", "accept-ranges", "etag", "last-modified", "location", "retry-after", "vary", "www-authenticate"];
const RESET_CODES = new Set(["ECONNRESET", "EPIPE", "UND_ERR_SOCKET"]);

type Options = { gateway?: string; fetch?: typeof globalThis.fetch; timeoutMs?: number };

function transientReset(error: unknown): boolean {
  let current = error;
  for (let depth = 0; depth < 4 && current && typeof current === "object"; depth++) {
    const value = current as { code?: string; cause?: unknown };
    if (value.code && RESET_CODES.has(value.code)) return true;
    current = value.cause;
  }
  return false;
}

/** Preserve method/query/body/status/binary content; never retry a possibly applied command. */
export async function proxyGateway(request: Request, segments: string[], options: Options = {}): Promise<Response> {
  if (segments.some((segment) => segment === "." || segment === "..")) return Response.json({ detail: "Invalid gateway path." }, { status: 400 });
  const gateway = (options.gateway ?? process.env.GATEWAY_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const upstreamURL = new URL(`${gateway}/${segments.map(encodeURIComponent).join("/")}`);
  upstreamURL.search = new URL(request.url).search;
  const safeRead = request.method === "GET" || request.method === "HEAD";
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort(request.signal.reason);
  if (request.signal.aborted) cancel();
  else request.signal.addEventListener("abort", cancel, { once: true });
  const timeoutMs = options.timeoutMs ?? (segments.includes("copilot") || segments.includes("report") ? 90000 : 15000);
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const headers = new Headers({ connection: "close" }); // No stale pooled local-demo socket.
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  try {
    const body = safeRead ? undefined : await request.arrayBuffer();
    for (let attempt = 0; ; attempt++) {
      try {
        const upstream = await (options.fetch ?? globalThis.fetch)(upstreamURL, {
          method: request.method, headers, body, signal: controller.signal, redirect: "manual", cache: "no-store",
        });
        // Buffer under the same deadline: body-read resets and slow responses are covered too.
        const payload = request.method === "HEAD" || [204, 205, 304].includes(upstream.status) ? null : await upstream.arrayBuffer();
        const responseHeaders = new Headers({ "cache-control": "no-store" });
        for (const name of RESPONSE_HEADERS) {
          const value = upstream.headers.get(name);
          if (value !== null) responseHeaders.set(name, value);
        }
        // fetch decodes compressed content, so upstream content-length/encoding cannot be reused.
        for (const cookie of upstream.headers.getSetCookie()) responseHeaders.append("set-cookie", cookie);
        const location = responseHeaders.get("location");
        if (location) {
          const redirect = new URL(location, upstreamURL);
          if (redirect.origin === upstreamURL.origin) {
            const publicURL = new URL(request.url);
            publicURL.pathname = `/api${redirect.pathname}`;
            publicURL.search = redirect.search;
            publicURL.hash = redirect.hash;
            responseHeaders.set("location", publicURL.toString());
          }
        }
        return new Response(payload, { status: upstream.status, statusText: upstream.statusText, headers: responseHeaders });
      } catch (error) {
        // A transport reset may happen after a command already applied. Retry only idempotent reads.
        if (safeRead && attempt === 0 && !controller.signal.aborted && transientReset(error)) continue;
        throw error;
      }
    }
  } catch {
    const status = timedOut ? 504 : request.signal.aborted ? 499 : 502;
    const detail = timedOut ? "The gateway timed out."
      : request.signal.aborted ? "The request was cancelled."
      : "The gateway connection failed.";
    return Response.json({ detail: `${detail}${safeRead ? " Retry when the connection recovers." : " The command outcome is unknown; check the current incident and audit before retrying."}` }, { status, headers: { "cache-control": "no-store" } });
  } finally {
    clearTimeout(timer);
    request.signal.removeEventListener("abort", cancel);
  }
}

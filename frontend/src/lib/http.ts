/** JSON transport with bounded waits, cancellation and useful proxy/server errors. */
export async function requestJSON<T>(url: string, init: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort(init.signal?.reason);
  if (init.signal?.aborted) abort();
  else init.signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { cache: "no-store", ...init, signal: controller.signal });
    const text = await response.text();
    let body: unknown;
    try { body = text ? JSON.parse(text) : null; }
    catch { throw new Error(response.ok ? "The server returned an invalid response." : `Server unavailable (${response.status}). Please try again.`); }
    if (!response.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : null;
      const error = new Error(typeof detail === "string" ? detail : `Request failed (${response.status}).`);
      Object.assign(error, { status: response.status });
      throw error;
    }
    return body as T;
  } catch (error) {
    if (controller.signal.aborted && !init.signal?.aborted) throw new Error("Request timed out. Please try again.");
    throw error;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener("abort", abort);
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The request failed. Please try again.";
}

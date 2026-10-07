"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage, requestJSON } from "./http";

/** Abort obsolete requests, and never display another resource's previous response. */
export function useQuery<T>(path: string, version = "", intervalMs = 0) {
  const [refreshCount, setRefreshCount] = useState(0);
  const [result, setResult] = useState<{ key: string; resource: string; data: T | null; error: string }>({ key: "", resource: "", data: null, error: "" });
  const resource = `${path}|${version}`;
  const key = `${resource}|${refreshCount}`;
  const refresh = useCallback(() => setRefreshCount((count) => count + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    requestJSON<T>(path, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setResult({ key, resource, data, error: "" }); })
      .catch((error) => { if (!controller.signal.aborted) setResult((previous) => ({ key, resource, data: previous.resource === resource ? previous.data : null, error: errorMessage(error) })); });
    return () => controller.abort();
  }, [key, path, resource]);
  useEffect(() => {
    if (!intervalMs) return;
    const timer = setInterval(refresh, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, refresh]);
  const current = result.key === key;
  const sameResource = result.resource === resource;
  return { data: sameResource ? result.data : null, error: current ? result.error : "", loading: !current && !sameResource, refresh };
}

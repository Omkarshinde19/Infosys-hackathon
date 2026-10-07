"use client";

export function QueryState({ loading, error, refresh }: { loading: boolean; error: string; refresh: () => void }) {
  if (!loading && !error) return null;
  return <div role="status" className="glass mx-auto max-w-6xl p-5 text-sm text-fg-muted">{loading ? "Loading measured results…" : error}{error && <button onClick={refresh} className="ml-3 underline">Try again</button>}</div>;
}

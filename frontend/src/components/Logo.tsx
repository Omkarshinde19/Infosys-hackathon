/** Three connected nodes with a heartbeat through the middle. */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 font-semibold tracking-tight ${className}`}>
      <svg viewBox="0 0 32 32" className="size-7" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="6" cy="16" r="3" />
        <circle cx="26" cy="7" r="3" />
        <circle cx="26" cy="25" r="3" />
        <path d="M9 16h4l2-5 3 10 2-5h2M23.5 8.5 18 12M23.5 23.5 20 21" strokeLinecap="round" />
      </svg>
      NetHeal
    </span>
  );
}

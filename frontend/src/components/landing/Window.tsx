/** A macOS-style app window, used on the landing page to show pieces of the product. */
export function Window({ title, children, className = "" }: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`overflow-hidden rounded-xl border border-[var(--glass-border)] bg-[var(--window)] shadow-[var(--window-shadow)] ${className}`}>
      <div className="flex items-center gap-1.5 border-b border-[var(--glass-border)] bg-[var(--window-bar)] px-3 py-2">
        <span className="size-2.5 rounded-full bg-[#ff5f57]" />
        <span className="size-2.5 rounded-full bg-[#febc2e]" />
        <span className="size-2.5 rounded-full bg-[#28c840]" />
        {title && <span className="ml-2 text-[11px] text-fg-muted">{title}</span>}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

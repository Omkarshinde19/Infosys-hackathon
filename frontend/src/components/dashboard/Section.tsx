import { Reveal } from "@/components/Reveal";

/** One scrolling "window" of the Control Room. */
export function Section({ id, title, subtitle, actions, children }: {
  id: string;
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-6">
      <Reveal>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
            <p className="text-sm text-fg-muted">{subtitle}</p>
          </div>
          {actions}
        </div>
        {children}
      </Reveal>
    </section>
  );
}

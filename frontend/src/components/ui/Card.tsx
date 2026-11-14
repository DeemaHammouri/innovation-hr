import { Ltr } from "./Ltr";

export function Card({ children, className = "", as: Tag = "div", ...rest }: React.HTMLAttributes<HTMLElement> & { as?: "div" | "section" | "li" }) {
  return (
    <Tag {...rest} className={`rounded-card border border-line bg-surface ${className}`}>
      {children}
    </Tag>
  );
}

/** iOS Settings style group: a small heading above, then rows with the label at the start and the value at the end. */
export function InsetList({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={className}>
      {title ? <h2 className="mb-2 px-1 text-label text-ink-2">{title}</h2> : null}
      <dl className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">{children}</dl>
    </section>
  );
}

export function InsetRow({ label, children, ltr }: { label: string; children: React.ReactNode; ltr?: boolean }) {
  return (
    <div className="flex min-h-12 items-start justify-between gap-4 px-4 py-3">
      <dt className="shrink-0 text-body text-ink-2">{label}</dt>
      <dd className="min-w-0 break-words text-end text-body text-ink">{ltr ? <Ltr>{children}</Ltr> : children}</dd>
    </div>
  );
}

const TONES = {
  success: "bg-success-bg text-success-ink",
  warning: "bg-warning-bg text-warning-ink",
  danger: "bg-danger-bg text-danger-ink",
  neutral: "bg-neutral-bg text-neutral",
  primary: "bg-primary-tint text-primary-hover",
};
const DOTS = { success: "bg-success", warning: "bg-warning", danger: "bg-danger", neutral: "bg-neutral", primary: "bg-primary" };

export function StatusPill({ tone = "neutral", children, dot = true }: { tone?: keyof typeof TONES; children: React.ReactNode; dot?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-caption ${TONES[tone]}`}>
      {dot ? <span aria-hidden className={`size-1.5 rounded-full ${DOTS[tone]}`} /> : null}
      {children}
    </span>
  );
}

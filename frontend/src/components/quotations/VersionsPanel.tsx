"use client";

import { useState } from "react";
import { Card, StatusPill } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { Segmented } from "@/components/ui/Segmented";
import type { Quotation, QuotationLine, QuotationVersion } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useMoney } from "./quoteUi";

const FIELDS = ["description", "quantity", "unit_price", "discount_percent", "tax_percent"] as const;

/** Every version, read-only, with a side-by-side comparison of any two. A signed version is marked, and nothing here can change it. */
export function VersionsPanel({ quotation }: { quotation: Quotation }) {
  const { t, formatDateTime } = useI18n();
  const money = useMoney();
  const versions = quotation.versions ?? [];
  const [mode, setMode] = useState<"view" | "compare">("view");
  const last = versions[versions.length - 1];
  const [a, setA] = useState(String((versions[versions.length - 2] ?? last)?.number ?? ""));
  const [b, setB] = useState(String(last?.number ?? ""));
  if (!last) return null;
  const find = (n: string) => versions.find((v) => String(v.number) === n) ?? last;
  const options = versions.map((v) => ({ value: String(v.number), label: t("qt.versionN", { number: v.number }) + (v.is_draft ? ` · ${t("qt.draft")}` : "") }));

  return (
    <Card as="section" aria-labelledby="qt-versions" className="overflow-hidden">
      <div className="space-y-3 p-4">
        <h2 id="qt-versions" className="text-section text-ink">{t("qt.versions")}</h2>
        {versions.length > 1 ? (
          <Segmented
            label={t("qt.versionsMode")}
            value={mode}
            onChange={setMode}
            segments={[{ value: "view", label: t("qt.view") }, { value: "compare", label: t("qt.compare") }]}
            className="w-full md:w-fit"
          />
        ) : null}
        <div className={`grid gap-3 ${mode === "compare" ? "sm:grid-cols-2" : "sm:max-w-xs"}`}>
          <Select name="version-a" label={mode === "compare" ? t("qt.compareFrom") : t("qt.versionPick")} value={mode === "compare" ? a : b} onChange={(e) => (mode === "compare" ? setA(e.target.value) : setB(e.target.value))} options={options} />
          {mode === "compare" ? <Select name="version-b" label={t("qt.compareTo")} value={b} onChange={(e) => setB(e.target.value)} options={options} /> : null}
        </div>
      </div>
      <div className="border-t border-line">
        {mode === "view" ? <VersionView v={find(b)} signed={quotation.signed_version === find(b).number} money={money} /> : <Diff from={find(a)} to={find(b)} money={money} />}
      </div>
      <p className="border-t border-line px-4 py-2.5 text-caption text-ink-2">
        {t("qt.versionMeta", { name: find(mode === "compare" ? b : b).created_by_name, date: formatDateTime(find(b).created_at) })}
      </p>
    </Card>
  );
}

type Money = ReturnType<typeof useMoney>;

function VersionView({ v, signed, money }: { v: QuotationVersion; signed: boolean; money: Money }) {
  const { t, formatDate } = useI18n();
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 px-4 pt-3">
        {signed ? <StatusPill tone="success">{t("qt.signedVersion")}</StatusPill> : null}
        {v.is_draft ? <StatusPill tone="warning" dot={false}>{t("qt.draft")}</StatusPill> : null}
        {v.valid_until ? <span className="text-label font-normal text-ink-2">{t("qt.validUntilOn", { date: formatDate(v.valid_until) })}</span> : null}
      </div>
      <ul className="divide-y divide-line">
        {v.lines.length === 0 ? <li className="px-4 py-5 text-center text-label font-normal text-ink-2">{t("qt.noLines")}</li> : null}
        {v.lines.map((l, i) => (
          <li key={l.id ?? i} className="flex items-start justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <p className="text-body text-ink">{l.description}</p>
              <p className="tnum text-label font-normal text-ink-2" dir="ltr">
                {Number(l.quantity)} × {money(l.unit_price, v.currency)}
                {Number(l.discount_percent) ? ` − ${Number(l.discount_percent)}%` : ""}
                {Number(l.tax_percent) ? ` + ${Number(l.tax_percent)}% ${t("qt.taxShort")}` : ""}
              </p>
            </div>
            <p className="tnum shrink-0 text-body font-semibold text-ink" dir="ltr">{money(l.line_total ?? 0, v.currency)}</p>
          </li>
        ))}
      </ul>
      <dl className="tnum space-y-1.5 border-t border-line bg-canvas/50 px-4 py-3 text-label">
        <Tot label={t("qt.subtotal")} value={money(v.subtotal, v.currency)} />
        <Tot label={t("qt.discount")} value={`− ${money(v.discount_total, v.currency)}`} />
        <Tot label={t("qt.tax")} value={money(v.tax_total, v.currency)} />
        <div className="flex justify-between pt-1 text-body font-semibold text-ink"><dt>{t("qt.total")}</dt><dd dir="ltr">{money(v.total, v.currency)}</dd></div>
      </dl>
      {v.notes ? <p className="whitespace-pre-line border-t border-line px-4 py-3 text-label font-normal text-ink-2">{v.notes}</p> : null}
    </div>
  );
}

function Tot({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between text-ink-2"><dt>{label}</dt><dd dir="ltr" className="text-ink">{value}</dd></div>;
}

function Diff({ from, to, money }: { from: QuotationVersion; to: QuotationVersion; money: Money }) {
  const { t } = useI18n();
  if (from.number === to.number) return <p className="px-4 py-6 text-center text-label font-normal text-ink-2">{t("qt.compareSame")}</p>;
  const rows = Math.max(from.lines.length, to.lines.length);
  const entries: { i: number; before?: QuotationLine; after?: QuotationLine; changed: (typeof FIELDS)[number][] }[] = [];
  for (let i = 0; i < rows; i++) {
    const before = from.lines[i];
    const after = to.lines[i];
    const changed: (typeof FIELDS)[number][] = before && after ? FIELDS.filter((f) => String(before[f]) !== String(after[f]) && !(f !== "description" && Number(before[f]) === Number(after[f]))) : [];
    entries.push({ i, before, after, changed });
  }
  const delta = Number(to.total) - Number(from.total);
  const same = entries.every((e) => e.before && e.after && e.changed.length === 0);
  return (
    <div>
      <ul className="divide-y divide-line">
        {entries.map((e) => (
          <li key={e.i} className="px-4 py-3">
            {e.before && !e.after ? <Removed line={e.before} money={money} cur={from.currency} /> : null}
            {!e.before && e.after ? <Added line={e.after} money={money} cur={to.currency} /> : null}
            {e.before && e.after ? (
              e.changed.length === 0 ? (
                <p className="text-label font-normal text-ink-2">{e.after.description} · {t("qt.unchanged")}</p>
              ) : (
                <div>
                  <p className="text-body text-ink">{e.after.description}</p>
                  <ul className="mt-1 space-y-0.5 text-label">
                    {e.changed.map((f) => (
                      <li key={f} className="flex flex-wrap items-center gap-x-2">
                        <span className="text-ink-2">{t(`qt.field.${f}`)}:</span>
                        <del className="text-danger-ink" dir="ltr">{String(e.before![f])}</del>
                        <ins className="font-semibold text-success-ink no-underline" dir="ltr">{String(e.after![f])}</ins>
                      </li>
                    ))}
                  </ul>
                </div>
              )
            ) : null}
          </li>
        ))}
      </ul>
      <div className="tnum flex flex-wrap items-center justify-between gap-2 border-t border-line bg-canvas/50 px-4 py-3 text-body">
        <span className="text-ink-2">{from.currency !== to.currency ? t("qt.currencyChanged", { from: from.currency, to: to.currency }) : same && !delta ? t("qt.noChanges") : t("qt.totalChange")}</span>
        <span className="font-semibold text-ink" dir="ltr">{money(from.total, from.currency)} → {money(to.total, to.currency)}</span>
      </div>
    </div>
  );
}

function Added({ line, money, cur }: { line: QuotationLine; money: Money; cur: string }) {
  const { t } = useI18n();
  return <p className="text-body text-success-ink"><span className="font-semibold">{t("qt.added")}</span> · {line.description} · <span dir="ltr">{money(line.line_total ?? 0, cur)}</span></p>;
}
function Removed({ line, money, cur }: { line: QuotationLine; money: Money; cur: string }) {
  const { t } = useI18n();
  return <p className="text-body text-danger-ink"><span className="font-semibold">{t("qt.removed")}</span> · <del>{line.description}</del> · <span dir="ltr">{money(line.line_total ?? 0, cur)}</span></p>;
}

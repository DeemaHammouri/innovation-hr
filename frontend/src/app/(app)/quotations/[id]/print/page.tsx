"use client";

import { Printer } from "@phosphor-icons/react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { Button, buttonClass } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { ErrorState, Skeleton } from "@/components/ui/States";
import type { Quotation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import Link from "next/link";
import ar from "@/locales/ar.json";
import en from "@/locales/en.json";

type DocLang = "en" | "ar";
const DICT: Record<DocLang, Record<string, string>> = { en, ar };
const LOCALE: Record<DocLang, string> = { en: "en-US", ar: "ar-u-nu-latn" };

/**
 * The signed version as a printable A4 page, in English or Arabic whatever the screen language is.
 * Print and choose "Save as PDF": the browser lays out right-to-left text and Arabic letter shapes correctly.
 */
export default function QuotationPrintPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const ui = useI18n();
  const { data, error, reload } = useFetch<Quotation>(user ? `/quotations/${id}/` : null);
  const [docLang, setDocLang] = useState<DocLang>(ui.lang);
  if (!user) return null;
  const back = { href: `/quotations/${id}`, label: ui.t("qt.title") };
  if (error) return <><PageHeader title={ui.t("qt.print")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) return <><PageHeader title={ui.t("qt.print")} back={back} /><Skeleton className="h-96 max-w-3xl rounded-card" /></>;
  const version = data.versions?.find((v) => v.number === data.signed_version);
  if (!data.permissions.can_print || !version) return <NoAccess />;

  const tt = (key: string, vars?: Record<string, string | number>) => (DICT[docLang][key] ?? en[key as keyof typeof en] ?? key).replace(/\{(\w+)\}/g, (_, k) => String(vars?.[k] ?? `{${k}}`));
  const num = (n: string | number) => new Intl.NumberFormat(LOCALE[docLang], { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(n));
  const pct = (n: string) => new Intl.NumberFormat(LOCALE[docLang], { maximumFractionDigits: 2 }).format(Number(n));
  const date = (iso: string) => new Intl.DateTimeFormat(LOCALE[docLang], { dateStyle: "long" }).format(new Date(iso));
  const dir = docLang === "ar" ? "rtl" : "ltr";
  const cur = version.currency;

  return (
    <>
      <div data-print-hide>
        <PageHeader
          back={back}
          title={ui.t("qt.print")}
          description={ui.t("qt.printHint")}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <Segmented
                label={ui.t("qt.docLanguage")}
                value={docLang}
                onChange={setDocLang}
                segments={[{ value: "en", label: "English", lang: "en" }, { value: "ar", label: "العربية", lang: "ar" }]}
              />
              <Button icon={<Printer size={20} aria-hidden />} onClick={() => window.print()}>{ui.t("qt.printNow")}</Button>
            </div>
          }
        />
      </div>
      <article dir={dir} lang={docLang} aria-label={tt("qt.docTitle")} className="mx-auto max-w-[210mm] rounded-card border border-line bg-white p-8 text-[13px] leading-relaxed text-black shadow-card print:max-w-none print:rounded-none print:border-0 print:p-0 print:shadow-none md:p-12">
        <header className="flex items-start justify-between gap-6 border-b-2 border-black pb-5">
          <div>
            <p className="text-[18px] font-bold">{tt("brand.company")}</p>
            <p className="mt-1 text-[22px] font-semibold">{tt("qt.docTitle")}</p>
          </div>
          <dl className="text-end">
            <div><dt className="inline font-semibold">{tt("qt.docRef")}: </dt><dd className="inline" dir="ltr">{data.ref}</dd></div>
            <div><dt className="inline font-semibold">{tt("qt.docDate")}: </dt><dd className="inline">{data.signed_at ? date(data.signed_at) : ""}</dd></div>
            {version.valid_until ? <div><dt className="inline font-semibold">{tt("qt.validUntil")}: </dt><dd className="inline">{date(version.valid_until)}</dd></div> : null}
          </dl>
        </header>

        <section className="mt-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-600">{tt("qt.docPreparedFor")}</h2>
          <p className="mt-1 text-[15px] font-semibold">{data.lead_company}</p>
          {data.lead_contact ? <p>{data.lead_contact}</p> : null}
        </section>

        <table className="mt-6 w-full border-collapse text-start">
          <thead>
            <tr className="border-y border-black bg-neutral-100 text-start">
              <th className="px-2 py-2 text-start font-semibold">#</th>
              <th className="px-2 py-2 text-start font-semibold">{tt("qt.description")}</th>
              <th className="px-2 py-2 text-end font-semibold">{tt("qt.quantity")}</th>
              <th className="px-2 py-2 text-end font-semibold">{tt("qt.unitPrice")}</th>
              <th className="px-2 py-2 text-end font-semibold">{tt("qt.discountPct")}</th>
              <th className="px-2 py-2 text-end font-semibold">{tt("qt.taxPct")}</th>
              <th className="px-2 py-2 text-end font-semibold">{tt("qt.lineTotal")}</th>
            </tr>
          </thead>
          <tbody>
            {version.lines.map((l, i) => (
              <tr key={l.id ?? i} className="border-b border-neutral-300 align-top">
                <td className="px-2 py-2">{i + 1}</td>
                <td className="px-2 py-2">{l.description}</td>
                <td className="px-2 py-2 text-end" dir="ltr">{pct(l.quantity)}</td>
                <td className="px-2 py-2 text-end" dir="ltr">{num(l.unit_price)}</td>
                <td className="px-2 py-2 text-end" dir="ltr">{pct(l.discount_percent)}</td>
                <td className="px-2 py-2 text-end" dir="ltr">{pct(l.tax_percent)}</td>
                <td className="px-2 py-2 text-end font-semibold" dir="ltr">{num(l.line_total ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <dl className="ms-auto mt-4 w-72 space-y-1">
          <div className="flex justify-between"><dt>{tt("qt.subtotal")}</dt><dd dir="ltr">{num(version.subtotal)}</dd></div>
          <div className="flex justify-between"><dt>{tt("qt.discount")}</dt><dd dir="ltr">− {num(version.discount_total)}</dd></div>
          <div className="flex justify-between"><dt>{tt("qt.tax")}</dt><dd dir="ltr">{num(version.tax_total)}</dd></div>
          <div className="flex justify-between border-t-2 border-black pt-2 text-[15px] font-bold"><dt>{tt("qt.total")} ({cur})</dt><dd dir="ltr">{num(version.total)}</dd></div>
        </dl>

        {version.notes ? (
          <section className="mt-6">
            <h2 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-600">{tt("qt.notes")}</h2>
            <p className="mt-1 whitespace-pre-line">{version.notes}</p>
          </section>
        ) : null}

        <footer className="mt-10 flex items-end justify-between gap-6 border-t border-neutral-400 pt-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-600">{tt("qt.docSignedBy")}</p>
            <p className="mt-1 text-[15px] font-semibold">{data.signed_by_name}</p>
            <p>{data.signed_at ? new Intl.DateTimeFormat(LOCALE[docLang], { dateStyle: "long", timeStyle: "short" }).format(new Date(data.signed_at)) : ""}</p>
          </div>
          <p className="text-[11px] text-neutral-600">{tt("qt.docVersion", { number: version.number })}</p>
        </footer>
      </article>
      <p data-print-hide className="mx-auto mt-4 max-w-[210mm]"><Link href={back.href} className={buttonClass("secondary")}>{ui.t("common.done")}</Link></p>
    </>
  );
}

"use client";

import { Printer } from "@phosphor-icons/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button, buttonClass } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { ErrorState, Skeleton } from "@/components/ui/States";
import type { Payslip } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import ar from "@/locales/ar.json";
import en from "@/locales/en.json";

type DocLang = "en" | "ar";
const DICT: Record<DocLang, Record<string, string>> = { en, ar };
const LOCALE: Record<DocLang, string> = { en: "en-US", ar: "ar-u-nu-latn" };

/** The employee's own payslip as a printable A4 page, in English or Arabic. Only the owner can open it. */
export default function PayslipPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const ui = useI18n();
  const { data, error, reload } = useFetch<Payslip>(user ? `/hr/payslips/${id}/` : null);
  const [docLang, setDocLang] = useState<DocLang>(ui.lang);
  if (!user) return null;
  const back = { href: "/payroll", label: ui.t("payroll.title") };
  if (error) return <><PageHeader title={ui.t("payroll.payslip")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) return <><PageHeader title={ui.t("payroll.payslip")} back={back} /><Skeleton className="h-96 max-w-3xl rounded-card" /></>;

  const tt = (key: string, vars?: Record<string, string | number>) => (DICT[docLang][key] ?? en[key as keyof typeof en] ?? key).replace(/\{(\w+)\}/g, (_, k) => String(vars?.[k] ?? `{${k}}`));
  const num = (n: string) => new Intl.NumberFormat(LOCALE[docLang], { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(n));
  const rows: [string, string, boolean?][] = [
    [tt("payroll.base"), num(data.base_salary)],
    [tt("payroll.allowances"), num(data.allowances)],
    [tt("payroll.deductions"), num(data.deductions)],
  ];
  return (
    <>
      <div data-print-hide>
        <PageHeader
          back={back}
          title={ui.t("payroll.payslip")}
          action={<Button icon={<Printer size={20} aria-hidden />} onClick={() => window.print()}>{ui.t("payroll.print")}</Button>}
        />
        <Segmented label={ui.t("qt.docLanguage")} value={docLang} onChange={setDocLang} segments={[{ value: "en", label: "English", lang: "en" }, { value: "ar", label: "العربية", lang: "ar" }]} className="mb-5 w-fit" />
      </div>
      <article dir={docLang === "ar" ? "rtl" : "ltr"} lang={docLang} className="mx-auto max-w-[210mm] rounded-card border border-line bg-white p-8 text-[13px] leading-relaxed text-black print:border-0 print:p-0">
        <header className="mb-6 flex items-start justify-between border-b-2 border-black pb-4">
          <div>
            <p className="text-[18px] font-bold">{tt("brand.company")}</p>
            <p className="text-neutral-600">{tt("payroll.payslipFor", { month: data.month })}</p>
          </div>
          <p dir="ltr" className="text-[11px] text-neutral-600">{data.paid_at ? new Intl.DateTimeFormat(LOCALE[docLang], { dateStyle: "long" }).format(new Date(data.paid_at)) : ""}</p>
        </header>
        <dl className="mb-6 grid grid-cols-2 gap-4">
          <div><dt className="text-[11px] font-semibold uppercase tracking-wide text-neutral-600">{tt("payroll.employee")}</dt><dd className="text-[15px] font-semibold">{data.user_name}</dd></div>
          <div><dt className="text-[11px] font-semibold uppercase tracking-wide text-neutral-600">{tt("payroll.department")}</dt><dd className="text-[15px] font-semibold">{data.department}</dd></div>
        </dl>
        <table className="w-full border-collapse">
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className="border-b border-neutral-300"><th className="px-2 py-2 text-start font-normal">{label}</th><td dir="ltr" className="px-2 py-2 text-end">{value}</td></tr>
            ))}
            <tr className="border-t-2 border-black text-[15px] font-bold"><th className="px-2 py-3 text-start">{tt("payroll.net")} ({data.currency})</th><td dir="ltr" className="px-2 py-3 text-end">{num(data.net)}</td></tr>
          </tbody>
        </table>
        {data.note ? <p className="mt-4 whitespace-pre-line">{data.note}</p> : null}
        <p className="mt-10 text-[11px] text-neutral-600">{tt("payroll.confidential")}</p>
      </article>
      <p data-print-hide className="mx-auto mt-4 max-w-[210mm]"><Link href={back.href} className={buttonClass("secondary")}>{ui.t("common.done")}</Link></p>
    </>
  );
}

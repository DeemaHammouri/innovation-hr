"use client";

import { DownloadSimple, FileCsv, UploadSimple } from "@phosphor-icons/react";
import { can } from "@/lib/can";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import { ApiError, downloadFile, errorMessage, type ImportBatch, type PreviewResult, type PreviewRow, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card as="section" className="p-5 md:p-6">
      <h2 className="text-section text-ink">{title}</h2>
      <div className="mt-4 space-y-4">{children}</div>
    </Card>
  );
}

const TONE = { ok: "success", error: "danger", duplicate: "warning" } as const;

export default function ImportLeadsPage() {
  const { user } = useAuth();
  const { t, msg, formatNumber, lang } = useI18n();
  const toast = useToast();
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [problem, setProblem] = useState("");
  const [checking, setChecking] = useState(false);
  const [importing, setImporting] = useState(false);
  const [finished, setFinished] = useState<ImportBatch | null>(null);

  if (!user) return null;
  if (!can(user, "lead.import")) return <NoAccess />;

  function form(extra?: Record<string, string>) {
    const f = new FormData();
    if (file) f.append("file", file);
    for (const [k, v] of Object.entries(extra ?? {})) f.append(k, v);
    return f;
  }

  async function check() {
    setProblem("");
    if (!file) {
      setProblem("lead.import.noFile");
      input.current?.focus();
      return;
    }
    setChecking(true);
    try {
      setPreview(await upload<PreviewResult>("/leads/import/preview/", form()));
    } catch (err) {
      setPreview(null);
      setProblem(err instanceof ApiError && err.status === 400 ? (err.fieldErrors().file ?? err.message) : errorMessage(err, "lead.saveFailed"));
    }
    setChecking(false);
  }

  const ready = preview ? preview.summary.ok : 0;

  async function confirm() {
    setProblem("");
    if (ready === 0) {
      setProblem("lead.import.confirmNone");
      return;
    }
    setImporting(true);
    try {
      const batch = await upload<ImportBatch>("/leads/import/confirm/", form());
      toast.success(t("lead.import.done", { count: formatNumber(batch.imported_count) }));
      if (batch.skip_report.length === 0) router.push("/leads?tab=imports");
      else {
        setFinished(batch);
        setImporting(false);
      }
    } catch (err) {
      setProblem(err instanceof ApiError && err.status === 400 ? (err.fieldErrors().file ?? err.message) : errorMessage(err, "lead.saveFailed"));
      setImporting(false);
    }
  }

  function describe(r: PreviewRow) {
    if (r.state === "error") return r.errors.map((e) => msg(e.message)).join(" ");
    if (r.duplicate_of) return t("lead.import.dupOf", { ref: r.duplicate_of });
    if (r.duplicate_in_file) return t("lead.import.dupInFile", { row: formatNumber(r.duplicate_in_file) });
    return "";
  }

  if (finished) {
    return (
      <>
        <PageHeader title={t("lead.import.reportTitle")} description={t("lead.import.reportText", { imported: formatNumber(finished.imported_count), skipped: formatNumber(finished.skip_report.length) })} back={{ href: "/leads", label: t("lead.title") }} />
        <div className="max-w-3xl space-y-4 md:space-y-6">
          <Step title={t("lead.import.skippedHeading")}>
            <div className="max-h-96 overflow-auto rounded-control border border-line">
              <table className="w-full min-w-[34rem] text-start text-label">
                <caption className="sr-only">{t("lead.import.skippedHeading")}</caption>
                <thead className="sticky top-0 bg-canvas">
                  <tr className="text-ink-2">
                    <th scope="col" className="px-3 py-2 text-start font-semibold">{t("lead.import.row")}</th>
                    <th scope="col" className="px-3 py-2 text-start font-semibold">{t("lead.company")}</th>
                    <th scope="col" className="px-3 py-2 text-start font-semibold">{t("lead.import.state")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {finished.skip_report.map((r) => (
                    <tr key={r.row}>
                      <td className="tnum px-3 py-2 align-top text-ink-2">{formatNumber(r.row)}</td>
                      <td className="max-w-48 px-3 py-2 align-top"><span className="block truncate font-medium text-ink">{r.company_name || "—"}</span></td>
                      <td className="px-3 py-2 align-top">
                        <StatusPill tone={TONE[r.state]}>{t(`lead.import.state.${r.state}`)}</StatusPill>
                        <p className="mt-1 font-normal text-ink-2">{describe({ ...r, contact_name: "", position: "", location: "", source: "", notes: "" })}</p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Link href="/leads?tab=imports" className={buttonClass("primary")}>{t("lead.import.reportDone")}</Link>
          </Step>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title={t("lead.import.title")} description={t("lead.import.description")} back={{ href: "/leads", label: t("lead.title") }} />
      <div className="max-w-3xl space-y-4 md:space-y-6">
        <Step title={t("lead.import.step1")}>
          <p className="text-body text-ink-2">{t("lead.import.templateText")}</p>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {(
              [
                ["lead.import.templateEnXlsx", "?lang=en", "leads-template-en.xlsx"],
                ["lead.import.templateArXlsx", "?lang=ar", "leads-template-ar.xlsx"],
                ["lead.import.templateCsv", `?file=csv&lang=${lang}`, `leads-template-${lang}.csv`],
              ] as const
            ).map(([label, query, name]) => (
              <Button key={label} variant="secondary" icon={<DownloadSimple size={20} aria-hidden />} onClick={() => downloadFile(`/leads/import/template/${query}`, name).catch(() => toast.error(t("lead.saveFailed")))}>
                {t(label)}
              </Button>
            ))}
          </div>
        </Step>

        <Step title={t("lead.import.step2")}>
          <input
            ref={input}
            id="field-file"
            type="file"
            accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setPreview(null);
              setProblem("");
            }}
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label htmlFor="field-file" className={`${buttonClass("secondary")} cursor-pointer`}>
              <UploadSimple size={20} aria-hidden />
              {t(file ? "lead.import.change" : "lead.import.choose")}
            </label>
            {file ? (
              <span className="flex min-w-0 items-center gap-2 text-body text-ink">
                <FileCsv size={20} aria-hidden className="shrink-0 text-primary-strong" />
                <span className="truncate"><Ltr>{file.name}</Ltr></span>
              </span>
            ) : null}
          </div>
          <p className="text-label font-normal text-ink-2">{t("lead.import.fileHint")}</p>
          {problem && !preview ? <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">{msg(problem)}</p> : null}
          <Button loading={checking} onClick={check}>{checking ? t("lead.import.checking") : t("lead.import.preview")}</Button>
        </Step>

        {preview ? (
          <Step title={t("lead.import.step3")}>
            <div className="flex flex-wrap items-center gap-2" role="status">
              <StatusPill tone="success">{t("lead.import.summary", { ok: formatNumber(preview.summary.ok), duplicates: formatNumber(preview.summary.duplicates), errors: formatNumber(preview.summary.errors) })}</StatusPill>
            </div>
            <div className="max-h-96 overflow-auto rounded-control border border-line">
              <table className="w-full min-w-[34rem] text-start text-label">
                <caption className="sr-only">{t("lead.import.title")}</caption>
                <thead className="sticky top-0 bg-canvas">
                  <tr className="text-ink-2">
                    <th scope="col" className="px-3 py-2 text-start font-semibold">{t("lead.import.row")}</th>
                    <th scope="col" className="px-3 py-2 text-start font-semibold">{t("lead.company")}</th>
                    <th scope="col" className="px-3 py-2 text-start font-semibold">{t("common.phone")}</th>
                    <th scope="col" className="px-3 py-2 text-start font-semibold">{t("lead.import.state")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {preview.rows.map((r) => (
                    <tr key={r.row} className={r.state === "error" ? "bg-danger-bg/40" : r.state === "duplicate" ? "bg-warning-bg/40" : ""}>
                      <td className="tnum px-3 py-2 align-top text-ink-2">{formatNumber(r.row)}</td>
                      <td className="max-w-48 px-3 py-2 align-top"><span className="block truncate font-medium text-ink">{r.company_name || "—"}</span>{r.email ? <span className="block truncate font-normal text-ink-2"><Ltr>{r.email}</Ltr></span> : null}</td>
                      <td className="tnum px-3 py-2 align-top">{r.phone ? <Ltr>{r.phone}</Ltr> : "—"}</td>
                      <td className="px-3 py-2 align-top">
                        <StatusPill tone={TONE[r.state]}>{t(`lead.import.state.${r.state}`)}</StatusPill>
                        {describe(r) ? <p className="mt-1 font-normal text-ink-2">{describe(r)}</p> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview.summary.errors + preview.summary.duplicates > 0 ? <p className="text-label font-normal text-ink-2">{t("lead.import.skippedNote")}</p> : null}
            {problem ? <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">{msg(problem)}</p> : null}
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Link href="/leads" className={buttonClass("secondary")}>{t("common.cancel")}</Link>
              <Button loading={importing} onClick={confirm}>{ready > 0 ? t("lead.import.confirm", { count: formatNumber(ready) }) : t("lead.import.confirmNone")}</Button>
            </div>
          </Step>
        ) : null}
      </div>
    </>
  );
}

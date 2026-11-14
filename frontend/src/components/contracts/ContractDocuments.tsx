"use client";

import { Archive, CheckCircle, DownloadSimple, Paperclip } from "@phosphor-icons/react";
import { useRef, useState } from "react";
import { Button, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { api, downloadFile, errorMessage, upload, type Contract, type Page, type RecordFile } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

const SLOTS = ["draft", "visit_report", "client_signed_copy", "final_signed"] as const;
const REQUIRED_BY: Record<(typeof SLOTS)[number], string> = { draft: "drafting", visit_report: "meeting_logged", client_signed_copy: "meeting_logged", final_signed: "signed" };

/** The four documents a contract moves on: the draft, the visit report, the client-signed copy and the final signed contract. */
export function ContractDocuments({ contract, onChanged }: { contract: Contract; onChanged: () => void }) {
  const { t, formatDateTime, msg } = useI18n();
  const toast = useToast();
  const { data, reload } = useFetch<Page<RecordFile>>(`/files/?target=contract:${contract.id}&page_size=100`);
  const [busy, setBusy] = useState("");
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});
  const all = data?.results ?? [];

  async function pick(slot: string, e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(slot);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("category", slot);
      await upload(`/files/?target=contract:${contract.id}`, form);
      toast.success(t("files.added"));
      reload();
      onChanged();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
    setBusy("");
  }
  async function archive(f: RecordFile) {
    try {
      await api(`/files/${f.id}/archive/`, { method: "POST", body: {} });
      toast.success(t("files.archived"));
      reload();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }
  async function open(f: RecordFile) {
    try {
      await downloadFile(`/files/${f.id}/download/`, f.original_name);
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }

  return (
    <Card as="section" aria-labelledby="ct-docs" className="overflow-hidden">
      <h2 id="ct-docs" className="px-4 pt-4 text-section text-ink">{t("ct.documents")}</h2>
      <ul className="mt-2 divide-y divide-line">
        {SLOTS.map((slot) => {
          const files = all.filter((f) => f.category === slot);
          const canUpload = contract.attachable.includes(slot);
          return (
            <li key={slot} className="px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-body font-semibold text-ink">
                    {files.length ? <CheckCircle size={18} weight="fill" className="text-success" aria-hidden /> : null}
                    {t(`ct.doc.${slot}`)}
                  </p>
                  <p className="text-label font-normal text-ink-2">{t(`ct.doc.${slot}Hint`)}</p>
                </div>
                {canUpload ? (
                  <>
                    <input ref={(el) => { inputs.current[slot] = el; }} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx" aria-label={t(`ct.doc.${slot}`)} onChange={(e) => pick(slot, e)} />
                    <Button variant="secondary" icon={<Paperclip size={18} aria-hidden />} loading={busy === slot} onClick={() => inputs.current[slot]?.click()}>
                      {t("files.upload")}
                    </Button>
                  </>
                ) : null}
              </div>
              {files.length ? (
                <ul className="mt-2 space-y-1">
                  {files.map((f) => (
                    <li key={f.id} className="flex items-center gap-2 rounded-control bg-canvas px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <p dir="auto" className="truncate text-label text-ink">{f.original_name}</p>
                        <p className="truncate text-caption text-ink-2">{f.uploaded_by_name} · {formatDateTime(f.created_at)}</p>
                      </div>
                      <IconButton label={t("files.download")} onClick={() => open(f)}><DownloadSimple size={20} aria-hidden /></IconButton>
                      {canUpload ? <IconButton label={t("files.archive")} onClick={() => archive(f)}><Archive size={20} aria-hidden /></IconButton> : null}
                    </li>
                  ))}
                </ul>
              ) : contract.status === REQUIRED_BY[slot] || (slot === "draft" && contract.status === "returned") ? (
                <p className="mt-2 text-label font-medium text-warning-ink">{t("ct.doc.missing")}</p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

"use client";

import { FilePdf, FileDoc } from "@phosphor-icons/react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import { Sheet } from "@/components/ui/Sheet";
import { downloadFile, errorMessage } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Lang = "en" | "ar" | "both";

/** Download a record as a branded PDF or Word file. `path` is the record's document endpoint, which checks access on the server. */
export function DownloadSheet({ path, fileBase, onClose }: { path: string; fileBase: string; onClose: () => void }) {
  const { t, lang: current, msg } = useI18n();
  const [lang, setLang] = useState<Lang>(current === "ar" ? "ar" : "en");
  const [busy, setBusy] = useState<"" | "pdf" | "docx">("");
  const [error, setError] = useState("");

  async function get(fmt: "pdf" | "docx") {
    setBusy(fmt);
    setError("");
    try {
      await downloadFile(`${path}?fmt=${fmt}&lang=${lang}`, `${fileBase}-${lang}.${fmt}`);
    } catch (err) {
      setError(errorMessage(err, "err.generic"));
    }
    setBusy("");
  }

  return (
    <Sheet open onClose={onClose} title={t("doc.title")} footer={<Button variant="secondary" onClick={onClose}>{t("common.close")}</Button>}>
      <p className="mb-4 text-body text-ink-2">{t("doc.text")}</p>
      <Segmented
        label={t("doc.language")}
        value={lang}
        onChange={setLang}
        segments={[{ value: "en", label: "English" }, { value: "ar", label: "العربية" }, { value: "both", label: t("doc.both") }]}
      />
      {error ? <p role="alert" className="mt-3 text-label font-medium text-danger-ink">{msg(error)}</p> : null}
      <div className="mt-5 flex flex-wrap gap-3">
        <Button loading={busy === "pdf"} icon={<FilePdf size={20} aria-hidden />} onClick={() => void get("pdf")}>{t("doc.pdf")}</Button>
        <Button variant="secondary" loading={busy === "docx"} icon={<FileDoc size={20} aria-hidden />} onClick={() => void get("docx")}>{t("doc.word")}</Button>
      </div>
    </Sheet>
  );
}

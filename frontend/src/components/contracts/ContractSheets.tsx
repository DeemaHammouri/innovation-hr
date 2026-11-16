"use client";

import { useRef, useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { StampNotice, useStampStatus } from "@/components/company/StampNotice";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { SignaturePad } from "@/components/ui/SignaturePad";
import { useToast } from "@/components/ui/Toast";
import { api, upload, type Contract, type ContractTemplate, type Lead } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Done = (c: Contract) => void;

export function RequestContractSheet({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const [note, setNote] = useState("");
  const action = useAction(["note"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<Contract>("/contracts/", { method: "POST", body: { lead: lead.id, note: note.trim() } }));
    if (saved) {
      toast.success(t("ct.requested"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("ct.request.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="request-contract-form" loading={action.saving}>{t("ct.request.save")}</Button>
        </>
      }
    >
      <form id="request-contract-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{t("ct.request.text", { name: lead.company_name })}</p>
        <Textarea name="note" label={t("ct.request.note")} hint={t("ct.request.noteHint")} rows={3} value={note} onChange={(e) => setNote(e.target.value)} error={action.errors.note} />
      </form>
    </Sheet>
  );
}

/** HR edits the working draft: the wording in both languages, terms and dates; or switches the template, which refills the text. */
export function DraftSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const v = contract.versions?.[contract.versions.length - 1];
  const { data: templates } = useFetch<ContractTemplate[] | { results: ContractTemplate[] }>("/contract-templates/");
  const list = Array.isArray(templates) ? templates : templates?.results ?? [];
  const [f, setF] = useState({ body_en: v?.body_en ?? "", body_ar: v?.body_ar ?? "", payment_terms: v?.payment_terms ?? "", start_date: v?.start_date ?? "", end_date: v?.end_date ?? "" });
  const [template, setTemplate] = useState("");
  const action = useAction(["body_en", "body_ar", "payment_terms", "start_date", "end_date", "template"]);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  async function save() {
    const body: Record<string, string> = { ...f };
    if (template) body.template = template;
    const saved = await action.run(() => api<Contract>(`/contracts/${contract.id}/draft/`, { method: "POST", body }));
    if (saved) {
      toast.success(t("ct.draftSaved"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("ct.draft.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button loading={action.saving} onClick={save}>{t("ct.draft.save")}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <FormError message={action.formError} />
        <Select
          name="template"
          label={t("ct.draft.template")}
          hint={t("ct.draft.templateHint")}
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
          placeholder={t("ct.draft.keepText")}
          options={list.map((x) => ({ value: String(x.id), label: `${x.country} · ${lang === "ar" ? x.name_ar : x.name_en}` }))}
          error={action.errors.template}
        />
        <Textarea name="body_en" label={t("ct.draft.bodyEn")} rows={8} dir="ltr" value={f.body_en} onChange={set("body_en")} error={action.errors.body_en} />
        <Textarea name="body_ar" label={t("ct.draft.bodyAr")} rows={8} dir="rtl" value={f.body_ar} onChange={set("body_ar")} error={action.errors.body_ar} />
        <Textarea name="payment_terms" label={t("ct.draft.terms")} rows={2} value={f.payment_terms} onChange={set("payment_terms")} error={action.errors.payment_terms} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input name="start_date" label={t("ct.draft.start")} type="date" value={f.start_date} onChange={set("start_date")} error={action.errors.start_date} />
          <Input name="end_date" label={t("ct.draft.end")} type="date" value={f.end_date} onChange={set("end_date")} error={action.errors.end_date} />
        </div>
      </div>
    </Sheet>
  );
}

/** One confirmation that posts to an action with no input (send to Commercial's note is optional, the rest are plain). */
function ConfirmSheet({ contract, onClose, onDone, path, title, text, save, done, note }: { contract: Contract; onClose: () => void; onDone: Done; path: string; title: string; text: string; save: string; done: string; note?: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const [value, setValue] = useState("");
  const action = useAction(["note"]);
  async function go() {
    const saved = await action.run(() => api<Contract>(`/contracts/${contract.id}/${path}/`, { method: "POST", body: note ? { note: value.trim() } : {} }));
    if (saved) {
      toast.success(done);
      onDone(saved);
    }
  }
  return (
    <Sheet open onClose={onClose} title={title} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={go}>{save}</Button></>}>
      <FormError message={action.formError} />
      <p className="text-body text-ink-2">{text}</p>
      {note ? <div className="mt-4"><Textarea name="note" label={note} rows={3} value={value} onChange={(e) => setValue(e.target.value)} error={action.errors.note} /></div> : null}
    </Sheet>
  );
}

export function SendSheet(p: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return <ConfirmSheet {...p} path="send" title={t("ct.send.title")} text={t("ct.send.text")} save={t("ct.send.save")} done={t("ct.sent")} note={t("ct.send.note")} />;
}

export function ConfirmContractSheet(p: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return <ConfirmSheet {...p} path="confirm" title={t("ct.confirm.title")} text={t("ct.confirm.text")} save={t("ct.confirm.save")} done={t("ct.confirmed")} />;
}

export function SendToClientSheet(p: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return <ConfirmSheet {...p} path="send-to-client" title={t("ct.toClient.title")} text={t("ct.toClient.text")} save={t("ct.toClient.save")} done={t("ct.sentToClient")} />;
}

export function CommercialReturnSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Contract>
      path={`/contracts/${contract.id}/commercial-return/`}
      onClose={onClose}
      onDone={onDone}
      field="comment"
      title={t("ct.cReturn.title")}
      intro={t("ct.cReturn.text")}
      question={t("ct.return.comment")}
      confirm={t("ct.cReturn.save")}
      done={t("ct.returned")}
      emptyKey="qt.err.comment"
    />
  );
}

/** Staff upload the copy the client signed on paper. */
export function ClientCopySheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["file"]);
  const [file, setFile] = useState<File | null>(null);
  const [local, setLocal] = useState("");
  async function go() {
    if (!file) return setLocal("ct.copy.error");
    setLocal("");
    const form = new FormData();
    form.append("file", file);
    const saved = await action.run(() => upload<Contract>(`/contracts/${contract.id}/client-copy/`, form));
    if (saved) {
      toast.success(t("ct.copy.done"));
      onDone(saved);
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("ct.copy.title")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={go}>{t("ct.copy.save")}</Button></>}>
      <FormError message={action.formError} />
      <p className="mb-4 text-body text-ink-2">{t("ct.copy.text")}</p>
      <Input name="file" label={t("ct.copy.file")} type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} error={local ? t(local) : action.errors.file} required />
    </Sheet>
  );
}

/** The CEO signs: draw the signature (the company stamp is added) or upload the final signed copy. */
export function ApproveSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const [mode, setMode] = useState<"draw" | "upload">("draw");
  const [signature, setSignature] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [local, setLocal] = useState("");
  const action = useAction(["signature", "stamp", "file"]);
  const pad = useRef(null);
  const stamp = useStampStatus();
  async function go() {
    if (mode === "draw" && stamp && !stamp.has_stamp) return setLocal("stamp.missing.title");
    if (mode === "draw" && !signature) return setLocal("sign.drawHere");
    if (mode === "upload" && !file) return setLocal("ct.copy.error");
    setLocal("");
    const saved = await action.run(() => {
      if (mode === "upload") {
        const form = new FormData();
        form.append("file", file as File);
        return upload<Contract>(`/contracts/${contract.id}/approve/`, form);
      }
      return api<Contract>(`/contracts/${contract.id}/approve/`, { method: "POST", body: { signature } });
    });
    if (saved) {
      toast.success(t("ct.approved"));
      onDone(saved);
    }
  }
  return (
    <Sheet open alert onClose={onClose} title={t("ct.approve.title")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={go}>{t("ct.approve.save")}</Button></>}>
      <FormError message={action.formError} />
      <p className="text-body text-ink-2">{t("ct.approve.text", { name: contract.lead_company })}</p>
      <div className="mt-4 flex gap-2" role="group" aria-label={t("ct.approve.how")}>
        <Button variant={mode === "draw" ? "primary" : "secondary"} onClick={() => setMode("draw")} aria-pressed={mode === "draw"}>{t("ct.approve.draw")}</Button>
        <Button variant={mode === "upload" ? "primary" : "secondary"} onClick={() => setMode("upload")} aria-pressed={mode === "upload"}>{t("ct.approve.upload")}</Button>
      </div>
      <div className="mt-4" ref={pad}>
        {mode === "draw" ? (
          <>
            <StampNotice status={stamp} />
            <SignaturePad label={t("sign.pad")} onChange={(d) => { setSignature(d); setLocal(""); }} error={local ? t(local) : action.errors.signature} />
          </>
        ) : (
          <Input name="file" label={t("ct.approve.file")} type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} error={local ? t(local) : action.errors.file} required />
        )}
      </div>
    </Sheet>
  );
}

export function ReturnSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Contract>
      path={`/contracts/${contract.id}/return/`}
      onClose={onClose}
      onDone={onDone}
      field="comment"
      title={t("ct.return.title")}
      intro={t("ct.return.text")}
      question={t("ct.return.comment")}
      confirm={t("ct.return.save")}
      done={t("ct.returned")}
      emptyKey="qt.err.comment"
    />
  );
}

export function CancelContractSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Contract>
      path={`/contracts/${contract.id}/cancel/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("ct.cancel.title")}
      intro={t("ct.cancel.text", { ref: contract.ref })}
      question={t("ct.cancel.reason")}
      confirm={t("ct.cancel.save")}
      done={t("ct.cancelled")}
      danger
      emptyKey="ct.err.cancel"
    />
  );
}

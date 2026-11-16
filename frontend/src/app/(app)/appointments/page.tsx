"use client";

import { CalendarCheck, CalendarPlus, Check, DotsThreeVertical, FileText, NotePencil, Prohibit, Clock } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { WriteReportSheet } from "@/components/meetings/WriteReportSheet";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { Segmented } from "@/components/ui/Segmented";
import { Sheet } from "@/components/ui/Sheet";
import { EmptyState, ErrorState, RowsSkeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type Appointment, type Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

const TYPES = ["meeting", "call", "visit", "follow_up", "other"] as const;
const PAGE_SIZE = 10;

/** `datetime-local` wants local wall time without a zone. */
const toLocalInput = (d: Date) => {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
const tomorrowNine = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  return toLocalInput(d);
};

type Assignee = { id: number; full_name: string };

function CreateSheet({ leadId, onClose, onDone }: { leadId: string | null; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const [type, setType] = useState(leadId ? "follow_up" : "meeting");
  const [title, setTitle] = useState("");
  const [startsAt, setStartsAt] = useState(tomorrowNine());
  const [notes, setNotes] = useState("");
  const [owner, setOwner] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["type", "title", "starts_at", "owner", "lead", "notes"]);
  const canAssign = can(user, "appointment.assign");
  const { data: people } = useFetch<Assignee[]>(canAssign ? "/appointments/assignees/" : null);
  const errors = { ...action.errors, ...local };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!title.trim()) found.title = "appt.err.title";
    if (!startsAt) found.starts_at = "appt.err.start";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return void document.getElementById(`field-${first}`)?.focus();
    const body: Record<string, unknown> = { type, title, notes, starts_at: new Date(startsAt).toISOString() };
    if (leadId) body.lead = Number(leadId);
    if (owner) body.owner = Number(owner);
    const saved = await action.run(() => api<Appointment>("/appointments/", { method: "POST", body }));
    if (saved) {
      toast.success(t("appt.created"));
      onDone();
    }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={t("appt.new")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="appt-form" loading={action.saving}>{t("appt.save")}</Button>
        </>
      }
    >
      <form id="appt-form" onSubmit={submit} noValidate className="space-y-5">
        <FormError message={action.formError} />
        <Select name="type" label={t("appt.type")} value={type} onChange={(e) => setType(e.target.value)} error={errors.type} options={TYPES.filter((x) => leadId || x !== "follow_up").map((v) => ({ value: v, label: t(`appt.type.${v}`) }))} />
        <Input name="title" label={t("appt.title")} value={title} onChange={(e) => setTitle(e.target.value)} error={errors.title} required />
        <Input name="starts_at" label={t("appt.when")} type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} error={errors.starts_at} required />
        {canAssign && people ? (
          <Select name="owner" label={t("appt.owner")} value={owner} onChange={(e) => setOwner(e.target.value)} error={errors.owner} placeholder={t("appt.ownerMe")} options={people.filter((p) => p.id !== user?.id).map((p) => ({ value: String(p.id), label: p.full_name }))} />
        ) : null}
        <Textarea name="notes" label={t("appt.notes")} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} error={errors.notes} />
      </form>
    </Sheet>
  );
}

function RescheduleSheet({ appt, onClose, onDone }: { appt: Appointment; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [startsAt, setStartsAt] = useState(toLocalInput(new Date(appt.starts_at)));
  const action = useAction(["starts_at"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<Appointment>(`/appointments/${appt.id}/reschedule/`, { method: "POST", body: { starts_at: new Date(startsAt).toISOString() } }));
    if (saved) {
      toast.success(t("appt.rescheduled"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("appt.reschedule")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button type="submit" form="resched-form" loading={action.saving}>{t("appt.save")}</Button></>}>
      <form id="resched-form" onSubmit={submit} noValidate className="space-y-5">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{appt.lead_ref ? t("appt.followUpNote") : appt.title}</p>
        <Input name="starts_at" label={t("appt.when")} type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} error={action.errors.starts_at} required />
      </form>
    </Sheet>
  );
}

function CancelSheet({ appt, onClose, onDone }: { appt: Appointment; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [reason, setReason] = useState("");
  const action = useAction(["detail"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<Appointment>(`/appointments/${appt.id}/cancel/`, { method: "POST", body: { reason } }));
    if (saved) {
      toast.success(t("appt.cancelled"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("appt.cancel")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.close")}</Button><Button type="submit" form="cancel-form" variant="danger" loading={action.saving}>{t("appt.cancelConfirm")}</Button></>}>
      <form id="cancel-form" onSubmit={submit} noValidate className="space-y-5">
        <FormError message={action.formError} />
        <p className="text-body text-ink">{appt.title}</p>
        <Input name="reason" label={t("appt.reason")} value={reason} onChange={(e) => setReason(e.target.value)} />
      </form>
    </Sheet>
  );
}

function Content() {
  const { user } = useAuth();
  const { t, formatDateTime } = useI18n();
  const toast = useToast();
  const params = useSearchParams();
  const newLead = params.get("lead");
  const viewAll = can(user, "appointment.view_all");
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const [status, setStatus] = useState<"scheduled" | "done" | "cancelled">("scheduled");
  const [page, setPage] = useState(1);
  const [sheet, setSheet] = useState<"new" | null>(newLead ? "new" : null);
  const [target, setTarget] = useState<{ appt: Appointment; kind: "reschedule" | "cancel" } | null>(null);
  const [writing, setWriting] = useState<Appointment | null>(null);
  const router = useRouter();
  const qs = `/appointments/?status=${status}&scope=${scope}&page=${page}&page_size=${PAGE_SIZE}`;
  const { data, error, loading, reload } = useFetch<Page<Appointment>>(user ? qs : null);
  if (!user) return null;
  if (!can(user, "appointment.access")) return <NoAccess />;

  async function complete(a: Appointment) {
    try {
      await api(`/appointments/${a.id}/complete/`, { method: "POST" });
      toast.success(t("appt.completed"));
      reload();
    } catch {
      toast.error(t("lead.saveFailed"));
    }
  }

  return (
    <>
      <PageHeader
        title={t("appt.title.page")}
        description={t("appt.description")}
        action={<Button icon={<CalendarPlus size={20} aria-hidden />} onClick={() => setSheet("new")}>{t("appt.new")}</Button>}
      />
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
        <Segmented
          label={t("appt.status")}
          value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          segments={[
            { value: "scheduled", label: t("appt.status.scheduled") },
            { value: "done", label: t("appt.status.done") },
            { value: "cancelled", label: t("appt.status.cancelled") },
          ]}
          className="w-full md:w-fit"
        />
        {viewAll ? (
          <Segmented
            label={t("appt.scope")}
            value={scope}
            onChange={(v) => { setScope(v); setPage(1); }}
            segments={[{ value: "mine", label: t("appt.scope.mine") }, { value: "all", label: t("appt.scope.all") }]}
            className="w-full md:w-fit"
          />
        ) : null}
      </div>
      {error ? <ErrorState message={error} onRetry={reload} /> : loading && !data ? <RowsSkeleton /> : data && data.results.length === 0 ? (
        <Card><EmptyState icon={<CalendarCheck size={24} aria-hidden />} title={t("appt.emptyTitle")} description={t("appt.emptyText")} /></Card>
      ) : data ? (
        <Card as="section" className="divide-y divide-line overflow-hidden">
          <h2 className="sr-only">{t("appt.title.page")}</h2>
          <ul className="divide-y divide-line">
            {data.results.map((a) => (
              <li key={a.id} className="flex items-start gap-3 px-4 py-3.5">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill tone="primary" dot={false}>{t(`appt.type.${a.type}`)}</StatusPill>
                    {a.overdue ? <StatusPill tone="danger">{t("appt.overdue")}</StatusPill> : null}
                    <span className="truncate text-body font-medium text-ink">{a.title}</span>
                  </div>
                  <p className="mt-1 flex flex-wrap items-center gap-x-3 text-label font-normal text-ink-2">
                    <span className="inline-flex items-center gap-1"><Clock size={16} aria-hidden />{formatDateTime(a.starts_at)}</span>
                    <span>{a.owner_name}</span>
                    {a.lead ? <Link href={`/leads/${a.lead}`} className="text-primary-strong hover:underline"><Ltr>{a.lead_ref}</Ltr> {a.lead_company}</Link> : null}
                  </p>
                  {a.cancel_reason ? <p className="mt-1 text-label font-normal text-ink-2">{a.cancel_reason}</p> : null}
                </div>
                {a.permissions.can_write_report ? (
                  <Button variant="secondary" icon={<NotePencil size={18} aria-hidden />} onClick={() => setWriting(a)}>{t("mr.write.short")}</Button>
                ) : a.permissions.report_id ? (
                  <Link href={`/meetings/${a.permissions.report_id}`} className="inline-flex items-center gap-1.5 text-label font-semibold text-primary-strong hover:underline"><FileText size={18} aria-hidden />{t("mr.open")}</Link>
                ) : null}
                {a.permissions.can_edit ? (
                  <Menu
                    label={t("common.actions")}
                    trigger={({ open, ...props }) => <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${open ? "bg-canvas" : ""}`}><DotsThreeVertical size={22} weight="bold" aria-hidden /></IconButton>}
                  >
                    {(close) => (
                      <>
                        <MenuItem icon={<Check size={18} aria-hidden />} onSelect={() => { close(); void complete(a); }}>{t("appt.complete")}</MenuItem>
                        <MenuItem icon={<Clock size={18} aria-hidden />} onSelect={() => { close(); setTarget({ appt: a, kind: "reschedule" }); }}>{t("appt.reschedule")}</MenuItem>
                        {!(a.type === "follow_up" && a.lead) ? <MenuItem icon={<Prohibit size={18} aria-hidden />} danger onSelect={() => { close(); setTarget({ appt: a, kind: "cancel" }); }}>{t("appt.cancel")}</MenuItem> : null}
                      </>
                    )}
                  </Menu>
                ) : null}
              </li>
            ))}
          </ul>
          <Pagination page={page} total={data.count} onPage={setPage} pageSize={PAGE_SIZE} />
        </Card>
      ) : null}
      {writing ? <WriteReportSheet fixed={writing} onClose={() => setWriting(null)} onDone={(r) => { setWriting(null); router.push(`/meetings/${r.id}`); }} /> : null}
      {sheet === "new" ? <CreateSheet leadId={newLead} onClose={() => setSheet(null)} onDone={() => { setSheet(null); reload(); }} /> : null}
      {target?.kind === "reschedule" ? <RescheduleSheet appt={target.appt} onClose={() => setTarget(null)} onDone={() => { setTarget(null); reload(); }} /> : null}
      {target?.kind === "cancel" ? <CancelSheet appt={target.appt} onClose={() => setTarget(null)} onDone={() => { setTarget(null); reload(); }} /> : null}
    </>
  );
}

export default function AppointmentsPage() {
  return (
    <Suspense fallback={null}>
      <Content />
    </Suspense>
  );
}

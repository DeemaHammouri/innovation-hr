"use client";

import { DotsThreeVertical, PencilSimple, Target as TargetIcon, Trash } from "@phosphor-icons/react";
import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { Segmented } from "@/components/ui/Segmented";
import { Sheet } from "@/components/ui/Sheet";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type LeadTargetProgress } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** One bar per day: the same numbers the figures above it show. Days after today have no bar yet. */
export function Bars({ days, label }: { days: { date: string; count: number | null }[]; label: string }) {
  const { formatNumber, formatDate } = useI18n();
  const max = Math.max(1, ...days.map((d) => d.count ?? 0));
  return (
    <figure>
      <div className="flex h-36 items-end gap-0.5" role="img" aria-label={label}>
        {days.map((d) => (
          <div key={d.date} className="flex h-full min-w-0 flex-1 items-end" title={`${formatDate(d.date)}: ${formatNumber(d.count ?? 0)}`}>
            <div className={`w-full rounded-t-sm ${d.count === null ? "bg-line" : "bg-primary"}`} style={{ height: `${d.count === null ? 3 : Math.max(3, ((d.count ?? 0) / max) * 100)}%` }} />
          </div>
        ))}
      </div>
      <figcaption className="mt-2 flex justify-between text-caption text-ink-2">
        <span>{formatDate(days[0].date)}</span>
        <span>{formatDate(days[days.length - 1].date)}</span>
      </figcaption>
    </figure>
  );
}

type Person = { id: number; full_name: string };

function TargetSheet({ editing, onClose, onDone }: { editing: LeadTargetProgress | null; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [user, setUser] = useState(editing?.user ? String(editing.user) : "");
  const [start, setStart] = useState(editing?.start_date ?? "");
  const [end, setEnd] = useState(editing?.end_date ?? "");
  const [value, setValue] = useState(editing ? String(editing.target) : "");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["user", "start_date", "end_date", "target"]);
  const { data: people } = useFetch<Person[]>("/leads/targets/assignees/");
  const errors = { ...action.errors, ...local };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!user) found.user = "dash.err.user";
    if (!start) found.start_date = "dash.err.start";
    if (!end) found.end_date = "dash.err.end";
    else if (start && end < start) found.end_date = "dash.err.order";
    if (!value) found.target = "dash.err.target";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return void document.getElementById(`field-${first}`)?.focus();
    const body = { user: Number(user), start_date: start, end_date: end, target: value };
    const saved = await action.run(() => api<LeadTargetProgress>(editing ? `/leads/targets/${editing.id}/` : "/leads/targets/", { method: editing ? "PATCH" : "POST", body }));
    if (saved) {
      toast.success(t("dash.targetSaved"));
      onDone();
    }
  }

  return (
    <Sheet open onClose={onClose} title={t(editing ? "dash.editTarget" : "dash.setTarget")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button type="submit" form="target-form" loading={action.saving}>{t("appt.save")}</Button></>}>
      <form id="target-form" onSubmit={submit} noValidate className="space-y-5">
        <FormError message={action.formError} />
        <Select name="user" label={t("dash.employee")} value={user} onChange={(e) => setUser(e.target.value)} placeholder={t("dash.chooseEmployee")} error={errors.user} options={(people ?? []).map((p) => ({ value: String(p.id), label: p.full_name }))} required />
        <div className="grid gap-5 sm:grid-cols-2">
          <Input name="start_date" label={t("dash.from")} type="date" value={start} onChange={(e) => setStart(e.target.value)} error={errors.start_date} required />
          <Input name="end_date" label={t("dash.to")} type="date" value={end} onChange={(e) => setEnd(e.target.value)} error={errors.end_date} required />
        </div>
        <Input name="target" label={t("dash.targetLabel")} hint={t("dash.targetHint")} type="number" inputMode="numeric" min={1} value={value} onChange={(e) => setValue(e.target.value)} error={errors.target} required />
      </form>
    </Sheet>
  );
}

function TargetCard({ g, manager, onEdit, onRemove }: { g: LeadTargetProgress; manager: boolean; onEdit: () => void; onRemove: () => void }) {
  const { t, formatNumber, formatDate } = useI18n();
  const pct = (n: number) => `${formatNumber(n)}%`;
  const tone = g.state === "upcoming" ? "neutral" : g.on_track ? "success" : "warning";
  const label = g.state === "upcoming" ? t("dash.upcoming") : g.state === "ended" && g.on_track ? t("dash.met") : g.on_track ? t("dash.onTrack") : t("dash.behind");
  return (
    <Card as="section" className="p-5 md:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-section text-ink">{g.user_name ?? t("dash.teamTarget")}</h3>
          <p className="text-label font-normal text-ink-2">{formatDate(g.start_date)} – {formatDate(g.end_date)} · {t("dash.targetSetBy", { name: g.set_by_name })}</p>
        </div>
        {manager ? (
          <Menu label={t("common.actions")} trigger={({ open, ...props }) => <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${open ? "bg-canvas" : ""}`}><DotsThreeVertical size={20} weight="bold" aria-hidden /></IconButton>}>
            {(close) => (
              <>
                <MenuItem icon={<PencilSimple size={18} aria-hidden />} onSelect={() => { close(); onEdit(); }}>{t("dash.editTarget")}</MenuItem>
                <MenuItem danger icon={<Trash size={18} aria-hidden />} onSelect={() => { close(); onRemove(); }}>{t("dash.removeTarget")}</MenuItem>
              </>
            )}
          </Menu>
        ) : null}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="tnum text-title text-ink">{formatNumber(g.added)} / {formatNumber(g.target)}</span>
        <StatusPill tone={tone}>{label}</StatusPill>
      </div>
      <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, g.percent)} aria-label={g.user_name ?? t("dash.teamTarget")}>
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, g.percent)}%` }} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          [t("dash.progress"), pct(g.percent)],
          [t("dash.remaining"), formatNumber(g.remaining)],
          [t("dash.daysElapsed"), `${formatNumber(g.days_elapsed)} / ${formatNumber(g.days_in_range)}`],
          [t("dash.daysLeft"), formatNumber(g.days_left)],
          [t("dash.expected"), formatNumber(g.expected_by_today)],
        ].map(([k, v]) => (
          <div key={k}><dt className="text-label font-normal text-ink-2">{k}</dt><dd className="tnum text-body font-semibold text-ink">{v}</dd></div>
        ))}
        {g.required_per_day !== null ? <div><dt className="text-label font-normal text-ink-2">{t("dash.requiredPerDay")}</dt><dd className="tnum text-body font-semibold text-ink">{formatNumber(g.required_per_day)}</dd></div> : null}
      </dl>
      <div className="mt-5"><Bars days={g.days} label={t("dash.perDayChart")} /></div>
    </Card>
  );
}

/** The targets the signed-in person may see. A manager sees everyone's and can set, change and remove them. */
export function Targets() {
  const { user } = useAuth();
  const { t } = useI18n();
  const toast = useToast();
  const manager = can(user, "lead.target_manage");
  const [scope, setScope] = useState<"current" | "all">("current");
  const [sheet, setSheet] = useState<{ editing: LeadTargetProgress | null } | null>(null);
  const { data, error, reload } = useFetch<LeadTargetProgress[]>(user ? `/leads/targets/${scope === "all" ? "?all=1" : ""}` : null);

  async function remove(g: LeadTargetProgress) {
    try {
      await api(`/leads/targets/${g.id}/`, { method: "DELETE" });
      toast.success(t("dash.targetRemoved"));
      reload();
    } catch {
      toast.error(t("lead.saveFailed"));
    }
  }

  return (
    <section aria-label={t("dash.targetTitle")} className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-section text-ink">{t("dash.targetTitle")}</h2>
        <div className="flex flex-wrap items-center gap-3">
          <Segmented label={t("dash.targetScope")} value={scope} onChange={setScope} segments={[{ value: "current", label: t("dash.scopeCurrent") }, { value: "all", label: t("dash.scopeAll") }]} />
          {manager ? <Button variant="secondary" icon={<TargetIcon size={20} aria-hidden />} onClick={() => setSheet({ editing: null })}>{t("dash.setTarget")}</Button> : null}
        </div>
      </div>
      {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <Skeleton className="h-40 rounded-card" /> : data.length === 0 ? (
        <Card className="p-5"><p className="text-body text-ink-2">{t(manager ? "dash.targetNoneManager" : "dash.targetNone")}</p></Card>
      ) : (
        data.map((g) => <TargetCard key={g.id} g={g} manager={manager} onEdit={() => setSheet({ editing: g })} onRemove={() => void remove(g)} />)
      )}
      {sheet ? <TargetSheet editing={sheet.editing} onClose={() => setSheet(null)} onDone={() => { setSheet(null); reload(); }} /> : null}
    </section>
  );
}

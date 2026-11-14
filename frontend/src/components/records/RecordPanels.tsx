"use client";

import { At, ClockCounterClockwise, DownloadSimple, FileText, Paperclip, Archive, ChatCircleText } from "@phosphor-icons/react";
import { useRef, useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Button, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Field";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import {
  type ActivityEntry,
  ApiError,
  type Page,
  type RecordComment,
  type RecordFile,
  type Target,
  api,
  downloadFile,
  errorMessage,
  upload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

const enc = encodeURIComponent;

function Loading({ show }: { show: boolean }) {
  return show ? <RowsSkeleton rows={3} /> : null;
}

/** Read-only timeline: who did what, when, from which value to which. */
export function ActivityPanel({ target }: { target: Target }) {
  const { t, relativeTime, formatDateTime } = useI18n();
  const { data, error, loading, reload } = useFetch<Page<ActivityEntry>>(`/activity/?target=${enc(target)}&page_size=100`);
  const show = useDelayed(loading);
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <Loading show={show} />;
  if (data.results.length === 0) {
    return (
      <Card>
        <EmptyState compact icon={<ClockCounterClockwise size={24} aria-hidden />} title={t("activity.emptyTitle")} description={t("activity.emptyText")} />
      </Card>
    );
  }
  return (
    <Card as="section" className="overflow-hidden">
      <ol className="divide-y divide-line">
        {data.results.map((e) => (
          <li key={e.id} className="flex gap-3 px-4 py-3">
            <Avatar name={e.actor_name ?? "?"} />
            <div className="min-w-0 flex-1">
              <p className="text-body text-ink">
                <span className="font-medium">{e.actor_name ?? t("activity.system")}</span>{" "}
                <span className="text-ink-2">{t(`activity.${e.action}`)}</span>
                {e.from_value || e.to_value ? (
                  <span className="text-ink-2">
                    {" "}
                    {e.from_value ? <span dir="auto">{e.from_value}</span> : null}
                    {e.from_value && e.to_value ? <span aria-hidden> {t("activity.arrow")} </span> : null}
                    {e.to_value ? <span dir="auto" className="text-ink">{e.to_value}</span> : null}
                  </span>
                ) : null}
              </p>
              {e.comment ? <p className="mt-1 whitespace-pre-line text-label font-normal text-ink-2">{e.comment}</p> : null}
              <time dateTime={e.created_at} title={formatDateTime(e.created_at)} className="mt-0.5 block text-caption text-ink-2">
                {relativeTime(e.created_at)}
              </time>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

type Person = { id: number; full_name: string };

function draftKey(userId: number, target: Target) {
  return `innovation.draft.${userId}.comment.${target}`;
}
function readDraft(key: string) {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}
function writeDraft(key: string, value: string) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    /* private mode: the draft is just not kept */
  }
}

/** Internal comments. @mention only offers people who can open the record. The draft survives a reload. */
export function CommentsPanel({ target }: { target: Target }) {
  const { t, relativeTime, formatDateTime, msg } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<Page<RecordComment>>(`/comments/?target=${enc(target)}&page_size=100`);
  const people = useFetch<Person[]>(`/mentionable/?target=${enc(target)}`);
  const show = useDelayed(loading);
  const key = user ? draftKey(user.id, target) : "";
  const [body, setBody] = useState(() => (key ? readDraft(key) : ""));
  const [mentions, setMentions] = useState<Person[]>([]);
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  function change(value: string) {
    setBody(value);
    setErr("");
    if (key) writeDraft(key, value);
  }

  function mention(p: Person) {
    if (!mentions.some((m) => m.id === p.id)) setMentions([...mentions, p]);
    change(`${body}${body && !body.endsWith(" ") ? " " : ""}@${p.full_name} `);
    setPicking(false);
  }

  async function send() {
    if (!body.trim()) {
      setErr("Write a comment first.");
      return;
    }
    setBusy(true);
    try {
      // Only people whose @Name is still in the text are really mentioned.
      const ids = mentions.filter((m) => body.includes(`@${m.full_name}`)).map((m) => m.id);
      await api(`/comments/?target=${enc(target)}`, { method: "POST", body: { body, mentions: ids } });
      change("");
      setMentions([]);
      reload();
      toast.success(t("comments.posted"));
    } catch (e) {
      setErr(errorMessage(e));
      if (!(e instanceof ApiError) || e.status >= 500) toast.error(msg(errorMessage(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <Textarea
          name="comment"
          label={t("comments.add")}
          value={body}
          onChange={(e) => change(e.target.value)}
          error={err}
          rows={3}
          maxLength={4000}
        />
        {picking ? (
          <ul className="mt-3 flex flex-wrap gap-2" aria-label={t("comments.mentionWho")}>
            {(people.data ?? []).length === 0 ? (
              <li className="text-label font-normal text-ink-2">{t("comments.nobody")}</li>
            ) : (
              (people.data ?? []).map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => mention(p)}
                    className="rounded-full border border-line bg-canvas px-3 py-1.5 text-label text-ink hover:border-primary-line hover:bg-primary-tint"
                  >
                    {p.full_name}
                  </button>
                </li>
              ))
            )}
          </ul>
        ) : null}
        <div className="mt-3 flex items-center justify-between gap-3">
          <Button variant="ghost" icon={<At size={20} aria-hidden />} onClick={() => setPicking((p) => !p)} aria-expanded={picking}>
            {t("comments.mention")}
          </Button>
          <Button onClick={send} loading={busy}>
            {t("comments.post")}
          </Button>
        </div>
      </Card>

      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        <Loading show={show} />
      ) : data.results.length === 0 ? (
        <Card>
          <EmptyState compact icon={<ChatCircleText size={24} aria-hidden />} title={t("comments.emptyTitle")} description={t("comments.emptyText")} />
        </Card>
      ) : (
        <Card as="section" className="overflow-hidden">
          <ul className="divide-y divide-line">
            {data.results.map((c) => (
              <li key={c.id} className="flex gap-3 px-4 py-3">
                <Avatar name={c.author_name} />
                <div className="min-w-0 flex-1">
                  <p className="text-body text-ink">
                    <span className="font-medium">{c.author_name}</span>{" "}
                    <time dateTime={c.created_at} title={formatDateTime(c.created_at)} className="text-label font-normal text-ink-2">
                      {relativeTime(c.created_at)}
                    </time>
                  </p>
                  <p dir="auto" className="mt-0.5 whitespace-pre-line break-words text-body font-normal text-ink">
                    {c.body}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function size(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Files on a record. Downloads go through the authenticated endpoint; there is never a public link. */
export function FilesPanel({ target, canAttach, category = "" }: { target: Target; canAttach: boolean; category?: string }) {
  const { t, formatDateTime, formatNumber, msg } = useI18n();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<Page<RecordFile>>(`/files/?target=${enc(target)}&page_size=100`);
  const show = useDelayed(loading);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      if (category) form.append("category", category);
      await upload(`/files/?target=${enc(target)}`, form);
      reload();
      toast.success(t("files.added"));
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    } finally {
      setBusy(false);
    }
  }

  async function open(f: RecordFile) {
    try {
      await downloadFile(`/files/${f.id}/download/`, f.original_name);
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }

  async function archive(f: RecordFile) {
    try {
      await api(`/files/${f.id}/archive/`, { method: "POST", body: {} });
      reload();
      toast.success(t("files.archived"));
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }

  return (
    <div className="space-y-4">
      {canAttach ? (
        <div>
          <input ref={input} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx" onChange={pick} />
          <Button variant="secondary" icon={<Paperclip size={20} aria-hidden />} loading={busy} onClick={() => input.current?.click()}>
            {t("files.upload")}
          </Button>
          <p className="mt-2 text-label font-normal text-ink-2">{t("files.rules")}</p>
        </div>
      ) : null}
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        <Loading show={show} />
      ) : data.results.length === 0 ? (
        <Card>
          <EmptyState compact icon={<FileText size={24} aria-hidden />} title={t("files.emptyTitle")} description={t("files.emptyText")} />
        </Card>
      ) : (
        <Card as="section" className="overflow-hidden">
          <ul className="divide-y divide-line">
            {data.results.map((f) => (
              <li key={f.id} className="flex items-center gap-3 px-4 py-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-control bg-primary-tint text-primary-strong">
                  <FileText size={22} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p dir="auto" className="truncate text-body text-ink">{f.original_name}</p>
                  <p className="truncate text-label font-normal text-ink-2">
                    {size(f.size).replace(/\d+(\.\d+)?/, (n) => formatNumber(Number(n)))} · {f.uploaded_by_name} · {formatDateTime(f.created_at)}
                  </p>
                </div>
                <IconButton label={t("files.download")} onClick={() => open(f)}>
                  <DownloadSimple size={22} aria-hidden />
                </IconButton>
                {canAttach ? (
                  <IconButton label={t("files.archive")} onClick={() => archive(f)}>
                    <Archive size={22} aria-hidden />
                  </IconButton>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

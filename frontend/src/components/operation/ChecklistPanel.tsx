"use client";

import { DotsThreeVertical, Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { FilesPanel } from "@/components/records/RecordPanels";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, type ChecklistItem, type OpClient } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { AddItemSheet, NotApplicableSheet } from "./OpSheets";
import { ItemStatusPill } from "./opUi";

type Open = { kind: "files" | "na"; item: ChecklistItem } | { kind: "add" } | null;

/** The KYC / legal checklist. Required items must be verified (or not applicable, with a reason) before the client is Active. */
export function ChecklistPanel({ client, onChanged }: { client: OpClient; onChanged: () => void }) {
  const { t, lang, msg, formatDateTime, formatNumber } = useI18n();
  const toast = useToast();
  const [open, setOpen] = useState<Open>(null);
  const items = client.checklist ?? [];
  const { can_work: work, can_manage: manage } = client.permissions;
  const pct = client.required_total ? Math.round((client.required_done / client.required_total) * 100) : 100;

  async function post(item: ChecklistItem, path: string, message: string, body: object = {}) {
    try {
      await api(`/operations/checklist/${item.id}/${path}/`, { method: "POST", body });
      toast.success(message);
      onChanged();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }
  const close = () => setOpen(null);
  const changed = () => {
    setOpen(null);
    onChanged();
  };

  return (
    <Card as="section" aria-labelledby="op-checklist" className="overflow-hidden">
      <div className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 id="op-checklist" className="text-section text-ink">{t("op.checklist")}</h2>
          {manage ? <Button variant="secondary" icon={<Plus size={18} aria-hidden />} onClick={() => setOpen({ kind: "add" })}>{t("op.item.add")}</Button> : null}
        </div>
        <div>
          <div className="flex items-center justify-between text-label text-ink-2">
            <span>{t("op.checklist.progress", { done: formatNumber(client.required_done), total: formatNumber(client.required_total) })}</span>
            <span className="tnum">{formatNumber(pct)}%</span>
          </div>
          <div role="progressbar" aria-label={t("op.checklist")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} className="mt-1.5 h-2 overflow-hidden rounded-full bg-line">
            <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
          </div>
          {client.status === "onboarding" ? <p className="mt-2 text-label font-normal text-ink-2">{t("op.checklist.rule")}</p> : null}
        </div>
      </div>
      {items.length === 0 ? (
        <p className="border-t border-line px-4 py-6 text-center text-label font-normal text-ink-2">{t("op.checklist.empty")}</p>
      ) : (
        <ul className="divide-y divide-line border-t border-line">
          {items.map((item) => (
            <li key={item.id} className="px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-body font-semibold text-ink">{lang === "ar" ? item.name_ar : item.name_en}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <ItemStatusPill status={item.status} />
                    {!item.required ? <StatusPill tone="neutral" dot={false}>{t("op.item.optional")}</StatusPill> : null}
                  </div>
                  {item.status === "not_applicable" ? <p className="mt-1 text-label font-normal text-ink-2">{t("op.item.naBecause", { reason: item.na_reason })}</p> : null}
                  {item.verified_at ? <p className="mt-0.5 text-caption text-ink-2">{item.verified_by_name} · {formatDateTime(item.verified_at)}</p> : null}
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" onClick={() => setOpen({ kind: "files", item })}>{t("op.item.documents")}</Button>
                  {work && item.status === "uploaded" ? <Button onClick={() => post(item, "verify", t("op.item.verified"))}>{t("op.item.verify")}</Button> : null}
                  {work ? (
                    <Menu
                      label={t("common.actions")}
                      trigger={({ open: isOpen, ...props }) => (
                        <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${isOpen ? "bg-canvas" : ""}`}>
                          <DotsThreeVertical size={20} weight="bold" aria-hidden />
                        </IconButton>
                      )}
                    >
                      {(done) => (
                        <>
                          {item.status !== "not_applicable" ? <MenuItem onSelect={() => { done(); setOpen({ kind: "na", item }); }}>{t("op.item.markNa")}</MenuItem> : null}
                          {item.status !== "pending" ? <MenuItem onSelect={() => { done(); void post(item, "reset", t("op.item.reset")); }}>{t("op.item.sendBack")}</MenuItem> : null}
                          {manage ? <MenuItem onSelect={() => { done(); void post(item, "required", t(item.required ? "op.item.nowOptional" : "op.item.nowRequired"), { required: !item.required }); }}>{t(item.required ? "op.item.makeOptional" : "op.item.makeRequired")}</MenuItem> : null}
                          {manage ? <MenuItem danger onSelect={() => { done(); void post(item, "archive", t("op.item.removed")); }}>{t("op.item.remove")}</MenuItem> : null}
                        </>
                      )}
                    </Menu>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      {open?.kind === "files" ? (
        <Sheet open onClose={changed} title={lang === "ar" ? open.item.name_ar : open.item.name_en} footer={<Button onClick={changed}>{t("common.done")}</Button>}>
          <FilesPanel target={`checklist_item:${open.item.id}`} canAttach={work} category="kyc" />
        </Sheet>
      ) : null}
      {open?.kind === "na" ? <NotApplicableSheet itemId={open.item.id} name={lang === "ar" ? open.item.name_ar : open.item.name_en} onClose={close} onDone={changed} /> : null}
      {open?.kind === "add" ? <AddItemSheet client={client} onClose={close} onDone={changed} /> : null}
    </Card>
  );
}

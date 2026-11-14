"use client";

import { ArrowsLeftRight, CaretDown } from "@phosphor-icons/react";
import { useState } from "react";
import { Menu, MenuItem } from "@/components/ui/Popover";
import type { Lead } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { AssignSheet, ContactSheet } from "./LeadSheets";
import { type Move, movesFor } from "./leadUi";

type Active = { lead: Lead; move: Move } | null;

/**
 * Every way of moving a lead (drag, the "Move to…" menu, the detail page's primary action) ends here.
 * A move that needs input (a date, a reason, a person) opens a sheet first; nothing changes until it is saved.
 */
export function useLeadMoves(onChanged: (lead: Lead) => void) {
  const [active, setActive] = useState<Active>(null);
  const close = () => setActive(null);
  const done = (lead: Lead) => {
    close();
    onChanged(lead);
  };

  function start(lead: Lead, move: Move) {
    setActive({ lead, move });
  }

  let sheet: React.ReactNode = null;
  if (active) {
    const { lead, move } = active;
    if (move === "assign") sheet = <AssignSheet key={lead.id} lead={lead} onClose={close} onDone={done} />;
    else {
      const initialOutcome = move === "waiting" ? "waiting" : move === "qualified" ? "accepted" : move === "rejected" ? "rejected" : "";
      // Before the first contact the outcome is logged together with the contact. After it, only the outcome is asked for.
      const mode = lead.status === "new" || (lead.status === "waiting" && move === "waiting") || move === "contacted" ? "contact" : "outcome";
      sheet = <ContactSheet key={`${lead.id}-${move}`} lead={lead} mode={mode} initialOutcome={initialOutcome} onClose={close} onDone={done} />;
    }
  }
  return { start, sheet };
}

/** The status a card dropped on a board column would move to, or null when that column is not a valid target. */
export function moveForColumn(lead: Lead, column: string): Move | null {
  const allowed = movesFor(lead);
  if (column === "contacted" || column === "waiting" || column === "qualified" || column === "rejected") {
    if (lead.status === column && column !== "waiting") return null;
    return allowed.includes(column) ? column : null;
  }
  return null;
}

export function MoveMenu({ lead, onMove, compact }: { lead: Lead; onMove: (move: Move) => void; compact?: boolean }) {
  const { t } = useI18n();
  const moves = movesFor(lead);
  if (moves.length === 0) return null;
  return (
    <Menu
      label={t("lead.moveLead", { name: lead.company_name })}
      trigger={({ open, ...props }) => (
        <button
          type="button"
          {...props}
          aria-label={`${t("lead.moveTo")} ${lead.company_name}`}
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-control border border-line bg-surface px-2.5 text-label font-semibold text-primary-strong hover:bg-primary-tint ${compact ? "h-9" : "h-10"} ${open ? "bg-primary-tint" : ""}`}
        >
          <ArrowsLeftRight size={16} aria-hidden />
          {t("lead.moveTo")}
          <CaretDown size={12} aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <>
          {moves.map((m) => (
            <MenuItem key={m} onSelect={() => { close(); onMove(m); }}>
              {t(`lead.move.${m}`)}
            </MenuItem>
          ))}
        </>
      )}
    </Menu>
  );
}

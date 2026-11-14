"use client";

import { useId, useState } from "react";
import { Segmented } from "@/components/ui/Segmented";
import type { Target } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { ActivityPanel, CommentsPanel, FilesPanel } from "./RecordPanels";

type Tab = "overview" | "activity" | "files" | "comments";

/**
 * The tab strip every record detail page shares: Overview | Activity | Files | Comments.
 * The page passes its own overview content; the other three are the same everywhere.
 */
export function RecordTabs({
  target,
  overview,
  canAttach,
  attachCategory,
}: {
  target: Target;
  overview: React.ReactNode;
  canAttach: boolean;
  attachCategory?: string;
}) {
  const t = useT();
  const [tab, setTab] = useState<Tab>("overview");
  const base = useId();
  const segments = (["overview", "activity", "files", "comments"] as const).map((v) => ({
    value: v,
    label: t(`record.tab.${v}`),
    id: `${base}-tab-${v}`,
    controls: `${base}-panel`,
  }));
  return (
    <div className="max-w-2xl">
      <Segmented segments={segments} value={tab} onChange={setTab} label={t("record.tabs")} mode="tablist" className="mb-5 w-full md:w-fit" />
      <div role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-tab-${tab}`}>
        {tab === "overview" ? overview : null}
        {tab === "activity" ? <ActivityPanel target={target} /> : null}
        {tab === "files" ? <FilesPanel target={target} canAttach={canAttach} category={attachCategory} /> : null}
        {tab === "comments" ? <CommentsPanel target={target} /> : null}
      </div>
    </div>
  );
}

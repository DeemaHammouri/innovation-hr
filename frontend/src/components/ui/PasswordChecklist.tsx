"use client";

import { Check, Circle } from "@phosphor-icons/react";
import { useI18n } from "@/lib/i18n";

/**
 * Live requirements with a segmented strength bar. Only the three existing rules are required; the bar is guidance
 * and never blocks anything. `sameAsTemporary` is undefined when the temporary password isn't known here.
 */
export function PasswordChecklist({
  password,
  confirm,
  sameAsTemporary,
}: {
  password: string;
  confirm: string;
  sameAsTemporary?: boolean;
}) {
  const { t } = useI18n();
  const long = password.length >= 8;
  const rules = [
    { key: "min", ok: long, text: t("pw.ruleLength") },
    {
      key: "diff",
      ok: sameAsTemporary === undefined ? null : password.length > 0 && !sameAsTemporary,
      text: t("pw.ruleDifferent"),
    },
    { key: "match", ok: password.length > 0 && confirm === password, text: t("pw.ruleMatch") },
  ];

  let score = 0;
  if (long) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password) && /\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  const labels = ["pw.empty", "pw.weak", "pw.fair", "pw.good", "pw.strong"];
  const tone = ["bg-line", "bg-danger", "bg-warning", "bg-primary", "bg-success"][score];

  return (
    <div className="space-y-3 rounded-control bg-canvas p-3.5">
      <div>
        <div className="flex gap-1.5" aria-hidden>
          {[1, 2, 3, 4].map((i) => (
            <span key={i} className={`h-1.5 flex-1 rounded-full ${i <= score ? tone : "bg-line"}`} />
          ))}
        </div>
        <p className="mt-1.5 text-caption text-ink-2" aria-live="polite">
          {t("pw.strength")}: {t(labels[score])}
        </p>
      </div>
      <ul className="space-y-1.5">
        {rules.map((r) => (
          <li key={r.key} className={`flex items-center gap-2 text-label font-medium ${r.ok ? "text-success-ink" : "text-ink-2"}`}>
            {r.ok ? <Check size={16} weight="bold" aria-hidden /> : <Circle size={16} aria-hidden />}
            <span>{r.text}</span>
            <span className="sr-only">{r.ok ? t("pw.met") : t("pw.notMet")}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

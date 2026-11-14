"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { flushSync } from "react-dom";
import ar from "@/locales/ar.json";
import en from "@/locales/en.json";
import { LANG_COOKIE, type Lang } from "./lang";

type Vars = Record<string, string | number>;

const dictionaries: Record<Lang, Record<string, string>> = { en, ar };
// Western digits (0-9) in both languages.
const LOCALES: Record<Lang, string> = { en: "en-US", ar: "ar-u-nu-latn" };

function interpolate(text: string, vars?: Vars) {
  return vars ? text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`)) : text;
}

/** What the backend says (in English) mapped to a dictionary key. Stored values never change; only display does. */
const API_MESSAGES: Record<string, string> = {
  "Only the CEO can change these settings.": "err.ceoSettings",
  "Record not found.": "err.recordNotFound",
  "File not found.": "err.fileNotFound",
  "Notification not found.": "err.recordNotFound",
  "Write a comment first.": "v.commentRequired",
  "Keep the comment under 4000 characters.": "v.commentLong",
  "Choose people from the list.": "err.mention",
  "You can only mention people who can open this record.": "err.mention",
  "You can't comment on this record.": "err.noComment",
  "You can't add files to this record.": "err.noAttach",
  "You can't archive this file.": "err.noArchive",
  "Upload a PDF, PNG, JPG, DOCX or XLSX file.": "v.fileType",
  "This file is over 10 MB. Upload a smaller one.": "v.fileSize",
  "This file is empty.": "v.fileEmpty",
  "Choose a file to upload.": "v.fileChoose",
  "This name is already in the list.": "v.nameTaken",
  "Enter the English name.": "v.nameEn",
  "Enter the Arabic name.": "v.nameAr",
  "Enter your email and password.": "err.enterBoth",
  "That email and password don't match. Check them and try again.": "login.mismatch",
  "Please set your new password first.": "err.passwordFirst",
  "Only the CEO can do this.": "err.ceoOnly",
  "Only the Operation Manager and the CEO can manage clients.": "err.clientsOnly",
  "Your password is already set.": "err.passwordSet",
  "You can't deactivate your own account.": "err.selfDeactivate",
  "Use at least 8 characters.": "v.min8",
  "Enter the person's full name.": "v.fullName",
  "Someone already uses this email.": "err.emailTaken",
  "Add a temporary password.": "err.tempRequired",
  "You can't change your own department or role.": "err.selfChange",
  "Choose a password that's different from the temporary one.": "err.differentFromTemp",
  "The two passwords don't match.": "v.mismatch",
  "Enter the company name.": "v.company",
  "Administration only has the CEO, who is its head.": "err.adminOnlyHead",
  "Administration already has its CEO.": "err.adminHasCeo",
  "Marketing already has its one person.": "err.marketingFull",
  "This field is required.": "err.required",
  "This field may not be blank.": "err.required",
  "Enter a valid email address.": "v.emailFormat",
  "Keep the company name under 200 characters.": "lead.err.0",
  "Enter a phone number with at least 7 digits (numbers, spaces, + and - only).": "lead.err.1",
  "Add a phone number or an email so someone can reach this lead.": "lead.err.2",
  "Keep the contact name under 150 characters.": "lead.err.3",
  "Keep the source under 150 characters.": "lead.err.4",
  "This lead is archived.": "lead.err.5",
  "This lead is already closed.": "lead.err.6",
  "Log the first contact before recording an outcome.": "lead.err.7",
  "Choose what happened: waiting, rejected or accepted.": "lead.err.8",
  "Choose a follow-up date.": "lead.err.9",
  "Choose today or a later date.": "lead.err.10",
  "Choose a date within the next year.": "lead.err.11",
  "Choose why this lead was rejected.": "lead.err.12",
  "Choose a time that has already passed.": "lead.err.13",
  "Only a rejected lead can be reopened.": "lead.err.14",
  "Write a note explaining why you are reopening it.": "lead.err.15",
  "Choose someone from the Commercial team.": "lead.err.16",
  "Write why you are archiving this lead.": "lead.err.17",
  "This lead isn't archived.": "lead.err.18",
  "This lead is already archived.": "lead.err.19",
  "Choose how you were in touch.": "lead.err.20",
  "Upload a .csv file. In Excel, choose Save As > CSV UTF-8.": "lead.err.21",
  "This file is over 2 MB. Split it into smaller files.": "lead.err.22",
  "We couldn't read this file. Save it as CSV (UTF-8) and try again.": "lead.err.23",
  "The file needs a company_name column. Download the template to see the format.": "lead.err.24",
  "The file has no rows to import.": "lead.err.25",
  "Import up to 2000 rows at a time.": "lead.err.26",
  "This batch was already undone.": "lead.err.27",
  "Some leads in this batch have already been contacted, so it can't be undone.": "lead.err.28",
  "There is nothing to import. Fix the rows marked in the preview and try again.": "lead.err.29",
  "Only Marketing can add or import leads.": "err.leadsMarketing",
  "Only the Commercial head can do this.": "err.leadsHead",
  "You can't change this lead.": "err.leadNoEdit",
  "You can't log contacts on this lead.": "err.leadNoLog",
  "You can't archive this lead.": "err.leadNoArchive",
  "Only the person who imported this batch can undo it.": "err.leadNoUndo",
  "Choose a period of up to 2 years.": "p7.api.1",
  "You don't have access to this report.": "p7.api.2",
  "Add at least one instalment.": "p6.api.0",
  "A schedule can have up to 36 instalments.": "p6.api.1",
  "Choose a valid due date.": "p6.api.2",
  "Enter an amount greater than zero.": "p6.api.3",
  "Enter a 3-letter currency code, such as JOD.": "p6.api.4",
  "This client already has instalments in another currency.": "p6.api.5",
  "Keep this under 200 characters.": "p6.api.6",
  "This instalment already has payments, so it can't be changed.": "p6.api.7",
  "Write why you are cancelling this instalment.": "p6.api.8",
  "Reverse the payments on this instalment before cancelling it.": "p6.api.9",
  "Choose the date the money was received. It can't be in the future.": "p6.api.10",
  "That is more than the balance still due on this instalment.": "p6.api.11",
  "Choose how it was paid.": "p6.api.12",
  "Keep the reference under 100 characters.": "p6.api.13",
  "Write why this payment is being reversed.": "p6.api.14",
  "This payment has already been reversed.": "p6.api.15",
  "A reversal can't be reversed. Record the payment again instead.": "p6.api.16",
  "Choose one of this client's contracts.": "p6.api.17",
  "Keep this under 300 characters.": "p6.api.18",
  "You don't have access to payments.": "p6.api.19",
  "Choose a leave type.": "p6.api.20",
  "Choose valid start and end dates.": "p6.api.21",
  "The end date can't be before the start date.": "p6.api.22",
  "Leave can't start more than 30 days in the past.": "p6.api.23",
  "A request can cover up to 366 days.": "p6.api.24",
  "A request must stay within one calendar year. Split it in two.": "p6.api.25",
  "Those dates have no working days.": "p6.api.26",
  "Keep the reason under 500 characters.": "p6.api.27",
  "You already have leave requested or approved on some of these dates.": "p6.api.28",
  "That is more than the days left for this leave type.": "p6.api.29",
  "Write why you are rejecting this request.": "p6.api.30",
  "You can only cancel your own request.": "p6.api.31",
  "Leave that has already started can't be cancelled. Ask HR.": "p6.api.32",
  "Enter the leave type name in both languages.": "p6.api.33",
  "Enter a number of days from 1 to 366, or leave it empty for no limit.": "p6.api.34",
  "You can't decide this request.": "p6.api.35",
  "The CEO doesn't request leave.": "p6.api.36",
  "Only the HR head can do this.": "p6.api.37",
  "You don't have access to payroll.": "p6.api.38",
  "Choose a date range of up to 93 days.": "p6.api.39",
  "Choose valid dates.": "p6.api.40",
  "Choose a month, like 2026-11.": "p6.api.41",
  "Choose a valid year.": "p6.api.42",
  "You can only see your own balance.": "p6.api.43",
  "You don't have access to the attendance report.": "p6.api.44",
  "You don't have access to everyone's leave requests.": "p6.api.45",
  "You can't run payroll for a future month.": "p6.api.46",
  "There is already a payroll run for that month.": "p6.api.47",
  "No employee has a salary on file yet. Add salaries first.": "p6.api.48",
  "All salaries in one run must use the same currency.": "p6.api.49",
  "Enter an amount of zero or more.": "p6.api.50",
  "Deductions can't be more than the salary plus allowances.": "p6.api.51",
  "Write why you are sending this run back to draft.": "p6.api.52",
  "This run has no entries.": "p6.api.53",
  "Enter a salary of zero or more.": "p6.api.54",
  "Choose an employee.": "p6.api.55",
  "That can't be done in the current state.": "op.api.0",
  "Upload the document first.": "op.api.1",
  "Write why this item does not apply.": "op.api.2",
  "Enter the document name in both languages.": "op.api.3",
  "Keep this under 1000 characters.": "op.api.4",
  "Enter a title for the task.": "op.api.5",
  "Choose how often it repeats.": "op.api.6",
  "Enter a number of days from 1 to 365.": "op.api.7",
  "Choose the first due date.": "op.api.8",
  "Choose someone from Operation.": "op.api.9",
  "Write why you are skipping this task.": "op.api.10",
  "Choose a date after the meeting.": "op.api.14",
  "Enter a number of days from 7 to 365.": "op.api.15",
  "This task is already closed.": "op.api.16",
  "Only Operation can do this.": "op.api.17",
  "Only the Operation head can do this.": "op.api.18",
  "You can only handle tasks assigned to you.": "op.api.19",
  "You don't have access to Operation.": "op.api.20",
  "A contract can start once the quotation is confirmed or skipped.": "ct.api.0",
  "This lead already has a contract in progress.": "ct.api.1",
  "This contract can't do that in its current state.": "ct.api.2",
  "Upload the draft contract file before sending it to Commercial.": "ct.api.3",
  "Choose the date the meeting took place.": "ct.api.4",
  "The meeting date can't be in the future.": "ct.api.5",
  "Write what was discussed in the meeting.": "ct.api.6",
  "Upload the visit report before sending this to the CEO.": "ct.api.7",
  "Upload the copy signed by the client before sending this to the CEO.": "ct.api.8",
  "Write why you are cancelling this contract.": "ct.api.9",
  "Upload the final signed contract before handing it over.": "ct.api.10",
  "You can't request a contract for this lead.": "ct.api.11",
  "Only HR can prepare contracts.": "ct.api.12",
  "You don't have access to contracts.": "ct.api.14",
  "Only a qualified lead can get a quotation.": "qt.api.0",
  "Quotation was skipped for this lead.": "qt.api.1",
  "This lead already has a quotation in progress.": "qt.api.2",
  "This quotation can't do that in its current state.": "qt.api.3",
  "Add at least one line before sending this for review.": "qt.api.4",
  "Choose how long this quotation is valid.": "qt.api.5",
  "Enter a 3-letter currency code, for example JOD.": "qt.api.6",
  "A quotation can have up to 100 lines.": "qt.api.7",
  "Describe what is being sold.": "qt.api.8",
  "Keep the description under 300 characters.": "qt.api.9",
  "Enter a number.": "qt.api.10",
  "Enter a quantity above zero.": "qt.api.11",
  "Enter a price of zero or more.": "qt.api.12",
  "Enter a percentage from 0 to 100.": "qt.api.13",
  "Choose a service from the list.": "qt.api.14",
  "Write what needs to change.": "qt.api.15",
  "Write why you are cancelling this quotation.": "qt.api.16",
  "Choose what the client decided: confirmed, waiting or rejected.": "qt.api.17",
  "Choose why the client said no.": "qt.api.18",
  "Keep the notes under 2000 characters.": "qt.api.19",
  "There is no draft to edit.": "qt.api.20",
  "You can't request a quotation for this lead.": "qt.api.21",
  "Only HR can prepare quotations.": "qt.api.22",
  "Only the Commercial head or the assigned member can do this.": "qt.api.24",
  "You don't have access to quotations.": "qt.api.25",
  "Only a qualified lead can skip the quotation.": "qt.api.26",
  "The quotation was already skipped for this lead.": "qt.api.27",
};

type I18n = {
  lang: Lang;
  dir: "ltr" | "rtl";
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Vars) => string;
  /** Turns a dictionary key or a backend message into text in the active language. */
  msg: (raw: string) => string;
  formatDate: (iso: string) => string;
  formatDateTime: (iso: string) => string;
  formatTime: (iso: string) => string;
  formatLongDate: (date: Date) => string;
  formatMonthYear: (date: Date) => string;
  formatNumber: (n: number) => string;
  /** "5 minutes ago", "yesterday" */
  relativeTime: (iso: string) => string;
  /** "Good evening" for the hour of the day */
  greeting: () => string;
  dept: (name: string | null) => string;
  role: (role: string) => string;
};

const I18nContext = createContext<I18n | null>(null);

export function LanguageProvider({ initialLang, children }: { initialLang: Lang; children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback((next: Lang) => {
    const apply = () => {
      // Update the page direction in the same tick so nothing flashes in the wrong direction.
      document.documentElement.lang = next;
      document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
      document.cookie = `${LANG_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
      flushSync(() => setLangState(next));
    };
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const transition = (document as Document & { startViewTransition?: (cb: () => void) => unknown }).startViewTransition;
    // The sidebar glides to the other side and the content cross-fades. Instant under reduced motion.
    if (!reduce && transition) transition.call(document, apply);
    else apply();
  }, []);

  const value = useMemo<I18n>(() => {
    const t = (key: string, vars?: Vars) => interpolate(dictionaries[lang][key] ?? dictionaries.en[key] ?? key, vars);
    const dept = (name: string | null) => (name ? (dictionaries[lang][`dept.${name}`] ?? name) : t("common.none"));
    const msg = (raw: string) => {
      if (dictionaries.en[raw] !== undefined) return t(raw); // already a key
      if (API_MESSAGES[raw]) return t(API_MESSAGES[raw]);
      if (/^This file doesn't look like a real/.test(raw)) return t("v.fileFake");
      const head = raw.match(/^(.+) already has a head\. Change their role first\.$/);
      if (head) return t("err.deptHasHead", { dept: dept(head[1]) });
      return lang === "en" ? raw : t("err.generic");
    };
    return {
      lang,
      dir: lang === "ar" ? "rtl" : "ltr",
      setLang,
      t,
      msg,
      formatDate: (iso: string) => new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: "medium" }).format(new Date(iso)),
      formatDateTime: (iso: string) =>
        new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso)),
      formatTime: (iso: string) => new Intl.DateTimeFormat(LOCALES[lang], { timeStyle: "short" }).format(new Date(iso)),
      formatLongDate: (d: Date) =>
        new Intl.DateTimeFormat(LOCALES[lang], { weekday: "long", day: "numeric", month: "long" }).format(d),
      formatMonthYear: (d: Date) => new Intl.DateTimeFormat(LOCALES[lang], { month: "long", year: "numeric" }).format(d),
      formatNumber: (n: number) => new Intl.NumberFormat(LOCALES[lang]).format(n),
      relativeTime: (iso: string) => {
        const diff = (new Date(iso).getTime() - Date.now()) / 1000;
        const rtf = new Intl.RelativeTimeFormat(LOCALES[lang], { numeric: "auto" });
        const abs = Math.abs(diff);
        if (abs < 45) return rtf.format(0, "second");
        if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
        if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
        if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), "day");
        return rtf.format(Math.round(diff / (86400 * 30)), "month");
      },
      greeting: () => {
        const h = new Date().getHours();
        return t(h < 12 ? "greeting.morning" : h < 18 ? "greeting.afternoon" : "greeting.evening");
      },
      dept,
      role: (r: string) => t(`role.${r}`),
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export type { Lang };

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside LanguageProvider");
  return ctx;
}

/** The translate function: t("users.add"), t("home.welcome", { name }) */
export const useT = () => useI18n().t;

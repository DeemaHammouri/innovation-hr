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

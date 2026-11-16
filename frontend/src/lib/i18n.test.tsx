import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import ar from "@/locales/ar.json";
import en from "@/locales/en.json";
import { LanguageProvider, useI18n } from "./i18n";
import { LANG_COOKIE, type Lang } from "./lang";

function withLang(lang: Lang) {
  return renderHook(() => useI18n(), { wrapper: ({ children }) => <LanguageProvider initialLang={lang}>{children}</LanguageProvider> });
}

beforeEach(() => {
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
});
afterEach(() => {
  document.cookie = `${LANG_COOKIE}=; max-age=0; path=/`;
});

describe("lang constants", () => {
  it("uses the lang cookie name", () => {
    expect(LANG_COOKIE).toBe("lang");
  });
});

describe("t(): lookup, fallback, interpolation", () => {
  it("looks a key up in the active language", () => {
    expect(withLang("en").result.current.t("common.cancel")).toBe("Cancel");
    expect(withLang("ar").result.current.t("common.cancel")).toBe(ar["common.cancel" as keyof typeof ar]);
  });

  it("returns the key itself when no dictionary has it", () => {
    expect(withLang("en").result.current.t("no.such.key")).toBe("no.such.key");
    expect(withLang("ar").result.current.t("no.such.key")).toBe("no.such.key");
  });

  it("falls back to English when Arabic lacks the key", () => {
    const missing = Object.keys(en).find((k) => !(k in ar));
    // Locales are kept in sync (i18n:check); the fallback is exercised only if a key is ever missing.
    if (missing) expect(withLang("ar").result.current.t(missing)).toBe((en as Record<string, string>)[missing]);
    else expect(Object.keys(ar).sort()).toEqual(Object.keys(en).sort());
  });

  it("fills {name} placeholders and leaves unknown ones visible", () => {
    const { t } = withLang("en").result.current;
    expect(t("search.noResults", { q: "acme" })).toBe('No results for "acme"');
    expect(t("search.noResults")).toBe('No results for "{q}"');
    expect(t("search.noResults", { other: 1 })).toBe('No results for "{q}"');
  });

  it("has the same placeholders in English and Arabic for every key", () => {
    const names = (s: string) => [...s.matchAll(/\{(\w+)/g)].map((m) => m[1]);
    const uniq = (s: string) => [...new Set(names(s))].sort().join(",");
    const bad = Object.keys(en).filter((k) => k in ar && uniq((en as Record<string, string>)[k]) !== uniq((ar as Record<string, string>)[k]));
    expect(bad).toEqual([]);
  });
});

describe("plural forms", () => {
  it("English picks one/other", () => {
    const { t } = withLang("en").result.current;
    expect(t("lead.count", { count: 1 })).toBe("1 lead");
    expect(t("lead.count", { count: 0 })).toBe("0 leads");
    expect(t("lead.count", { count: 2 })).toBe("2 leads");
    expect(t("lead.count", { count: 11 })).toBe("11 leads");
  });

  it("Arabic picks one / two / few (3-10) / many (11+)", () => {
    const { t } = withLang("ar").result.current;
    expect(t("lead.count", { count: 1 })).toBe("عميل محتمل واحد");
    expect(t("lead.count", { count: 2 })).toBe("عميلان محتملان");
    expect(t("lead.count", { count: 3 })).toBe("3 عملاء محتملين");
    expect(t("lead.count", { count: 10 })).toBe("10 عملاء محتملين");
    expect(t("lead.count", { count: 11 })).toBe("11 عميلًا محتملًا");
    expect(t("lead.count", { count: 25 })).toBe("25 عميلًا محتملًا");
  });

  it("Arabic uses the modulo-100 rule for larger numbers and treats 0 as many", () => {
    const { t } = withLang("ar").result.current;
    expect(t("lead.count", { count: 103 })).toBe("103 عملاء محتملين");
    expect(t("lead.count", { count: 100 })).toBe("100 عميلًا محتملًا");
    expect(t("lead.count", { count: 0 })).toBe("0 عميلًا محتملًا");
  });

  it("understands a formatted number with thousands separators", () => {
    const { t } = withLang("en").result.current;
    expect(t("lead.count", { count: "1,200" })).toBe("1,200 leads");
  });

  it("keeps the plural text untouched when the count is not a number", () => {
    const { t } = withLang("en").result.current;
    expect(t("lead.count", { count: "many" })).toContain("{count|lead|leads}");
  });

  it("supports # for the number inside a form", () => {
    const { t } = withLang("ar").result.current;
    expect(t("lead.assign.openLeads", { count: 5 })).toBe("5 عملاء مفتوحين");
  });
});

describe("msg(): backend messages", () => {
  it("treats a dictionary key as a key", () => {
    expect(withLang("en").result.current.msg("v.fullName")).toBe("Enter the person's full name.");
    expect(withLang("ar").result.current.msg("v.fullName")).toBe(ar["v.fullName" as keyof typeof ar]);
  });

  it("maps a known English backend message to the active language", () => {
    expect(withLang("en").result.current.msg("Someone already uses this email.")).toBe(en["err.emailTaken" as keyof typeof en]);
    expect(withLang("ar").result.current.msg("Someone already uses this email.")).toBe(ar["err.emailTaken" as keyof typeof ar]);
  });

  it("shows an unknown backend message as-is in English", () => {
    expect(withLang("en").result.current.msg("Something odd happened.")).toBe("Something odd happened.");
  });

  it("never shows an unknown English backend message raw in Arabic", () => {
    expect(withLang("ar").result.current.msg("Something odd happened.")).toBe(ar["err.generic" as keyof typeof ar]);
  });

  it("handles the department-has-a-head pattern and translates the department", () => {
    const en1 = withLang("en").result.current.msg("HR already has a head. Change their role first.");
    expect(en1).toContain("HR");
    const ar1 = withLang("ar").result.current.msg("HR already has a head. Change their role first.");
    expect(ar1).toContain(ar["dept.HR" as keyof typeof ar]);
  });

  it("maps the similar-password and fake-file patterns", () => {
    const { msg } = withLang("en").result.current;
    expect(msg("The password is too similar to your email address.")).toBe(en["err.pwSimilar" as keyof typeof en]);
    expect(msg("This file doesn't look like a real PDF.")).toBe(en["v.fileFake" as keyof typeof en]);
  });
});

describe("formatting uses Western digits in both languages", () => {
  it("formats numbers with 0-9 in Arabic", () => {
    expect(withLang("ar").result.current.formatNumber(1234567)).toMatch(/^[0-9,.٬٫  ]+$/);
    expect(withLang("ar").result.current.formatNumber(1234567)).not.toMatch(/[٠-٩]/);
    expect(withLang("en").result.current.formatNumber(1234567)).toBe("1,234,567");
  });

  it("formats dates and times without Arabic-Indic digits", () => {
    const { formatDate, formatTime, formatDateTime, formatMonthYear } = withLang("ar").result.current;
    for (const s of [formatDate("2026-03-14T10:30:00Z"), formatTime("2026-03-14T10:30:00Z"), formatDateTime("2026-03-14T10:30:00Z"), formatMonthYear(new Date(2026, 2, 1))]) {
      expect(s).not.toMatch(/[٠-٩]/);
      expect(s).toMatch(/\d/);
    }
  });

  it("formats an English date in medium form", () => {
    expect(withLang("en").result.current.formatDate("2026-03-14T12:00:00Z")).toBe("Mar 14, 2026");
  });
});

describe("dept() and role()", () => {
  it("translates a known department, passes an unknown one through, and shows 'none' for null", () => {
    const ar_ = withLang("ar").result.current;
    expect(ar_.dept("HR")).toBe(ar["dept.HR" as keyof typeof ar]);
    expect(ar_.dept("Skunkworks")).toBe("Skunkworks");
    expect(ar_.dept(null)).toBe(ar["common.none" as keyof typeof ar]);
    expect(withLang("en").result.current.role("head")).toBe("Head");
  });
});

describe("setLang", () => {
  it("flips lang and dir on <html>, saves the cookie and re-renders in the new language", () => {
    const { result } = withLang("en");
    expect(result.current.dir).toBe("ltr");
    act(() => result.current.setLang("ar"));
    expect(result.current.lang).toBe("ar");
    expect(result.current.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.cookie).toContain("lang=ar");
    expect(result.current.t("common.cancel")).toBe(ar["common.cancel" as keyof typeof ar]);
    act(() => result.current.setLang("en"));
    expect(document.documentElement.dir).toBe("ltr");
    expect(result.current.t("common.cancel")).toBe("Cancel");
  });

  it("throws a clear error outside the provider", () => {
    expect(() => renderHook(() => useI18n())).toThrow(/LanguageProvider/);
  });
});

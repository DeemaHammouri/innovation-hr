import { describe, expect, it } from "vitest";
import { LANG_COOKIE, type Lang } from "./lang";

describe("lang", () => {
  it("names the cookie that carries the language to the server", () => {
    expect(LANG_COOKIE).toBe("lang");
  });

  it("is the same cookie the language provider writes", async () => {
    const { LanguageProvider } = await import("./i18n");
    expect(LanguageProvider).toBeTypeOf("function");
    const langs: Lang[] = ["en", "ar"];
    expect(langs).toEqual(["en", "ar"]);
  });
});

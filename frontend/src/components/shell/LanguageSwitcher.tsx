"use client";

import { useChangeLanguage } from "@/lib/auth";
import { useI18n, type Lang } from "@/lib/i18n";
import { Segmented } from "@/components/ui/Segmented";

/**
 * "EN | ع" (and "EN | عربي" on wide screens). Labels are written in both languages on purpose:
 * a person must be able to find their own language whichever one the page is in.
 */
export function LanguageSwitcher({ wide = true, className = "" }: { wide?: boolean; className?: string }) {
  const { lang } = useI18n();
  const change = useChangeLanguage();
  return (
    <Segmented<Lang>
      label="Language · اللغة"
      value={lang}
      onChange={change}
      className={className}
      segments={[
        { value: "en", label: <span dir="ltr">EN</span>, ariaLabel: "English", lang: "en" },
        {
          value: "ar",
          label: wide ? (
            <>
              <span className="lg:hidden">ع</span>
              <span className="hidden lg:inline">عربي</span>
            </>
          ) : (
            "ع"
          ),
          ariaLabel: "العربية",
          lang: "ar",
        },
      ]}
    />
  );
}

import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic, Manrope } from "next/font/google";
import { cookies } from "next/headers";
import { AuthProvider } from "@/lib/auth";
import { LanguageProvider } from "@/lib/i18n";
import { LANG_COOKIE, type Lang } from "@/lib/lang";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

const latinFont = Manrope({
  variable: "--font-latin",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

// Arabic glyphs only: Latin text inside Arabic pages (emails, names) falls through to Manrope.
const arabicFont = IBM_Plex_Sans_Arabic({
  variable: "--font-arabic",
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  description: "Innovation internal system",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // The saved choice is read on the server, so the first paint already has the right language and direction.
  const lang: Lang = (await cookies()).get(LANG_COOKIE)?.value === "ar" ? "ar" : "en";
  return (
    <html lang={lang} dir={lang === "ar" ? "rtl" : "ltr"} className={`${latinFont.variable} ${arabicFont.variable}`}>
      <body className="min-h-dvh">
        <LanguageProvider initialLang={lang}>
          <ToastProvider>
            <AuthProvider>{children}</AuthProvider>
          </ToastProvider>
        </LanguageProvider>
      </body>
    </html>
  );
}

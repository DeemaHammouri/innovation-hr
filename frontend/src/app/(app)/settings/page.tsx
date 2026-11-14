"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Settings now lives on the profile page. The old address keeps working. */
export default function SettingsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/profile?tab=settings");
  }, [router]);
  return null;
}

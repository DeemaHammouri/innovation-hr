"use client";

import { GearSix, SignOut, UserCircle } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { Avatar } from "@/components/ui/Avatar";
import { MenuItem, Popover } from "@/components/ui/Popover";
import { Tooltip } from "@/components/ui/Tooltip";
import { useAuth, useSignOut } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function ProfileMenu() {
  const { user } = useAuth();
  const { t, dept, role } = useI18n();
  const router = useRouter();
  const signOut = useSignOut();
  if (!user) return null;
  return (
    <Popover
      label={t("common.profile")}
      width={288}
      trigger={({ open, ...props }) => (
        <Tooltip label={t("common.profile")} side="bottom-end">
          <button
            type="button"
            {...props}
            aria-label={`${t("common.profile")}: ${user.full_name}`}
            className={`flex size-11 items-center justify-center rounded-full transition-transform duration-[var(--dur-fast)] active:scale-95 md:size-10 ${open ? "ring-2 ring-primary" : ""}`}
          >
            <Avatar name={user.full_name} size="md" />
          </button>
        </Tooltip>
      )}
    >
      {(close) => (
        <div>
          <div className="flex items-center gap-3 px-3 py-3">
            <Avatar name={user.full_name} size="md" />
            <div className="min-w-0">
              <p className="truncate text-label text-ink">{user.full_name}</p>
              <p className="truncate text-caption font-normal text-ink-2">
                {dept(user.department_name)} · {role(user.role)}
              </p>
            </div>
          </div>
          <div className="my-1 border-t border-line" />
          <MenuItem
            plain
            icon={<UserCircle size={20} aria-hidden />}
            onSelect={() => {
              close();
              router.push("/profile");
            }}
          >
            {t("menu.myProfile")}
          </MenuItem>
          <MenuItem
            plain
            icon={<GearSix size={20} aria-hidden />}
            onSelect={() => {
              close();
              router.push("/profile?tab=settings");
            }}
          >
            {t("common.settings")}
          </MenuItem>
          <div className="flex items-center justify-between gap-3 px-3 py-2">
            <span className="text-body text-ink">{t("common.language")}</span>
            <LanguageSwitcher wide={false} />
          </div>
          <div className="my-1 border-t border-line" />
          <MenuItem plain danger icon={<SignOut size={20} className="rtl:-scale-x-100" aria-hidden />} onSelect={signOut}>
            {t("common.signOut")}
          </MenuItem>
        </div>
      )}
    </Popover>
  );
}

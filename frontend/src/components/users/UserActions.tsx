"use client";

import { Copy, Check } from "@phosphor-icons/react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Ltr } from "@/components/ui/Ltr";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, type User } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export type Credentials = { name: string; email: string; password: string; reason: "users.credAdded" | "users.credReset" };

/** Shown once, right after a user is created or a password is reset. The password is never stored. */
export function CredentialsSheet({ credentials, onClose }: { credentials: Credentials | null; onClose: () => void }) {
  const toast = useToast();
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const c = credentials ?? { name: "", email: "", password: "", reason: "users.credAdded" as const };
  const text = `${t("users.copyEmail", { email: c.email })}\n${t("users.copyPassword", { password: c.password })}`;

  function copy() {
    navigator.clipboard.writeText(text).then(
      () => {
        setCopied(true);
        toast.success(t("common.copied"));
      },
      () => toast.error(t("users.copyFailed")),
    );
  }

  return (
    <Sheet
      open={credentials !== null}
      title={t(c.reason)}
      onClose={onClose}
      hideClose
      footer={
        <>
          <Button variant="secondary" onClick={copy} icon={copied ? <Check size={20} aria-hidden /> : <Copy size={20} aria-hidden />}>
            {t("users.copy")}
          </Button>
          <Button onClick={onClose} data-autofocus>
            {t("common.done")}
          </Button>
        </>
      }
    >
      <p className="text-body text-ink-2">{t("users.credText", { name: c.name })}</p>
      <dl className="mt-4 divide-y divide-line overflow-hidden rounded-card border border-line bg-canvas">
        <div className="px-4 py-3">
          <dt className="text-label font-normal text-ink-2">{t("common.email")}</dt>
          <dd className="mt-0.5 break-all text-body text-ink">
            <Ltr>{c.email}</Ltr>
          </dd>
        </div>
        <div className="px-4 py-3">
          <dt className="text-label font-normal text-ink-2">{t("users.tempPassword")}</dt>
          <dd className="mt-0.5 break-all font-mono text-section font-semibold text-ink">
            <Ltr>{c.password}</Ltr>
          </dd>
        </div>
      </dl>
    </Sheet>
  );
}

/**
 * Deactivate, activate and reset password, with the named confirmation each one needs.
 * Used by the users list and by the user page, so both behave the same.
 */
export function useUserActions(onChanged: () => void) {
  const toast = useToast();
  const { t, msg } = useI18n();
  const [confirm, setConfirm] = useState<{ kind: "deactivate" | "reset"; user: User } | null>(null);
  const [open, setOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [credentials, setCredentials] = useState<Credentials | null>(null);

  async function run() {
    if (!confirm) return;
    setWorking(true);
    try {
      if (confirm.kind === "deactivate") {
        await api(`/users/${confirm.user.id}/deactivate/`, { method: "POST" });
        const target = confirm.user;
        toast.success(t("users.deactivated", { name: target.full_name }), {
          undo: () =>
            api(`/users/${target.id}/activate/`, { method: "POST" })
              .then(onChanged)
              .catch((err) => toast.error(msg(errorMessage(err, "users.activateFailed")))),
        });
      } else {
        const res = await api<{ temporary_password: string }>(`/users/${confirm.user.id}/reset-password/`, { method: "POST" });
        setCredentials({ name: confirm.user.full_name, email: confirm.user.email, password: res.temporary_password, reason: "users.credReset" });
      }
      setOpen(false);
      onChanged();
    } catch (err) {
      toast.error(msg(errorMessage(err, "users.actionFailed")));
    } finally {
      setWorking(false);
    }
  }

  async function activate(target: User) {
    try {
      await api(`/users/${target.id}/activate/`, { method: "POST" });
      toast.success(t("users.activated", { name: target.full_name }));
      onChanged();
    } catch (err) {
      toast.error(msg(errorMessage(err, "users.activateFailed")));
    }
  }

  const name = confirm?.user.full_name ?? "";
  const dialogs = (
    <>
      <Sheet
        open={open}
        alert
        title={confirm?.kind === "deactivate" ? t("users.confirmDeactivateTitle", { name }) : t("users.confirmResetTitle", { name })}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)} data-autofocus>
              {t("common.cancel")}
            </Button>
            <Button variant={confirm?.kind === "deactivate" ? "danger" : "primary"} loading={working} onClick={run}>
              {confirm?.kind === "deactivate" ? t("users.confirmDeactivate", { name }) : t("users.resetPassword")}
            </Button>
          </>
        }
      >
        <p className="text-body text-ink-2">{confirm?.kind === "deactivate" ? t("users.confirmDeactivateText", { name }) : t("users.confirmResetText", { name })}</p>
      </Sheet>
      <CredentialsSheet credentials={credentials} onClose={() => setCredentials(null)} />
    </>
  );

  return {
    askDeactivate: (user: User) => {
      setConfirm({ kind: "deactivate", user });
      setOpen(true);
    },
    askReset: (user: User) => {
      setConfirm({ kind: "reset", user });
      setOpen(true);
    },
    activate,
    dialogs,
  };
}

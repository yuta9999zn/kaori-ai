"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Save, Loader2, AlertCircle, Bot, Globe, Bell } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n/provider";
import { LocalePicker } from "@/components/i18n/locale-picker";

interface EnterpriseSettings {
  enterprise_name: string;
  locale: string;
  consent_external_ai: boolean;
  external_ai_model?: string;
  notification_email?: boolean;
}

export default function SettingsPage() {
  const t = useT();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<{ data: EnterpriseSettings }>({
    queryKey: ["enterprise-settings"],
    queryFn:  () => api("/api/v1/enterprises/me/settings"),
    staleTime: 60_000,
  });

  const settings = data?.data;
  const [consentExternal, setConsentExternal] = useState<boolean | null>(null);
  const [notifyEmail,     setNotifyEmail]     = useState<boolean | null>(null);
  const effectiveConsent = consentExternal ?? settings?.consent_external_ai ?? false;
  const effectiveNotify  = notifyEmail     ?? settings?.notification_email   ?? true;

  const { mutate: save, isPending: saving, isSuccess: saved, isError: saveError } = useMutation({
    mutationFn: () =>
      api("/api/v1/enterprises/me/settings", {
        method: "PATCH",
        body: JSON.stringify({
          consent_external_ai: effectiveConsent,
          notification_email:  effectiveNotify,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["enterprise-settings"] });
    },
  });

  const consentDirty = consentExternal !== null && consentExternal !== settings?.consent_external_ai;
  const notifyDirty  = notifyEmail     !== null && notifyEmail     !== settings?.notification_email;
  const isDirty      = consentDirty || notifyDirty;

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-h1 font-serif text-ink">{t("nav.settings")}</h1>
        <p className="text-small text-ink-muted mt-1">{t("settingsPage.subtitle")}</p>
      </div>

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-48" />
        </div>
      )}

      {!isLoading && settings && (
        <>
          {/* Language */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-brand-500" strokeWidth={1.75} />
                <CardTitle>{t("settingsPage.languageTitle")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pb-5">
              <p className="text-small text-ink-muted mb-3">
                {t("settingsPage.languageDesc")}
              </p>
              <LocalePicker />
            </CardContent>
          </Card>

          {/* AI consent */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-brand-500" strokeWidth={1.75} />
                <CardTitle>{t("settingsPage.aiSettingsTitle")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pb-5 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-body-strong text-ink">{t("settingsPage.externalAiLabel")}</p>
                  <p className="text-small text-ink-muted mt-0.5">
                    {t("settingsPage.externalAiDesc")}
                  </p>
                </div>
                <button
                  onClick={() => setConsentExternal(!effectiveConsent)}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-300 focus:ring-offset-2 ${
                    effectiveConsent ? "bg-brand-500" : "bg-[#D4C9BB]"
                  }`}
                  role="switch"
                  aria-checked={effectiveConsent}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                      effectiveConsent ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              {effectiveConsent && (
                <div className="bg-warning-50 border border-warning-100 rounded-xl px-4 py-3 text-small text-warning-700">
                  <strong>{t("settingsPage.noteLabel")}</strong> {t("settingsPage.externalAiWarning")}
                </div>
              )}

              {saveError && (
                <div className="flex items-center gap-2 text-danger-600 text-small">
                  <AlertCircle className="w-4 h-4" />
                  {t("error.generic")}
                </div>
              )}

              {saved && !isDirty && (
                <p className="text-small text-success-600">{t("settingsPage.savedSuccess")}</p>
              )}

              <div className="flex justify-end">
                <Button onClick={() => save()} loading={saving} disabled={!isDirty}>
                  <Save className="w-4 h-4 mr-1.5" />
                  {t("settingsPage.saveChanges")}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Notifications — Sprint 7 PR B (was placeholder; column has existed
              in `tenant_settings.notification_email` since migration 015). */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-brand-500" strokeWidth={1.75} />
                <CardTitle>{t("settingsPage.notificationsTitle")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pb-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-body-strong text-ink">{t("settingsPage.emailAlertsLabel")}</p>
                  <p className="text-small text-ink-muted mt-0.5">
                    {t("settingsPage.emailAlertsDesc")}
                  </p>
                </div>
                <button
                  onClick={() => setNotifyEmail(!effectiveNotify)}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-300 focus:ring-offset-2 ${
                    effectiveNotify ? "bg-brand-500" : "bg-[#D4C9BB]"
                  }`}
                  role="switch"
                  aria-checked={effectiveNotify}
                  aria-label={t("settingsPage.emailAlertsToggleAriaLabel")}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                      effectiveNotify ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

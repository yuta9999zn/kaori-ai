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
        <p className="text-small text-ink-muted mt-1">Cấu hình workspace và tùy chọn AI.</p>
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
                <CardTitle>Ngôn ngữ giao diện</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pb-5">
              <p className="text-small text-ink-muted mb-3">
                Ngôn ngữ hiển thị cho tài khoản của bạn. Thay đổi sẽ được lưu tự động.
              </p>
              <LocalePicker />
            </CardContent>
          </Card>

          {/* AI consent */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-brand-500" strokeWidth={1.75} />
                <CardTitle>Cài đặt AI</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pb-5 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-body-strong text-ink">AI ngoài (Claude / GPT-4o)</p>
                  <p className="text-small text-ink-muted mt-0.5">
                    Cho phép gửi dữ liệu (đã ẩn PII) đến AI bên ngoài để phân tích sâu hơn.
                    Mặc định Kaori dùng Qwen2.5 chạy nội bộ — riêng tư và miễn phí.
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
                  <strong>Lưu ý:</strong> Dữ liệu của bạn sẽ được ẩn PII trước khi gửi, nhưng vẫn rời khỏi
                  hạ tầng nội bộ. Đảm bảo tuân thủ chính sách dữ liệu của tổ chức bạn.
                </div>
              )}

              {saveError && (
                <div className="flex items-center gap-2 text-danger-600 text-small">
                  <AlertCircle className="w-4 h-4" />
                  {t("error.generic")}
                </div>
              )}

              {saved && !isDirty && (
                <p className="text-small text-success-600">Đã lưu thành công.</p>
              )}

              <div className="flex justify-end">
                <Button onClick={() => save()} loading={saving} disabled={!isDirty}>
                  <Save className="w-4 h-4 mr-1.5" />
                  Lưu thay đổi
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
                <CardTitle>Thông báo</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pb-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-body-strong text-ink">Cảnh báo qua email</p>
                  <p className="text-small text-ink-muted mt-0.5">
                    Gửi email khi sử dụng đạt ngưỡng 80% / 95% quota tháng,
                    khi pipeline hoàn tất hoặc thất bại, và khi có hoạt động bảo mật quan trọng.
                  </p>
                </div>
                <button
                  onClick={() => setNotifyEmail(!effectiveNotify)}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-300 focus:ring-offset-2 ${
                    effectiveNotify ? "bg-brand-500" : "bg-[#D4C9BB]"
                  }`}
                  role="switch"
                  aria-checked={effectiveNotify}
                  aria-label="Bật/tắt cảnh báo email"
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

// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 73. /p2/branding — Workspace Branding (F-026 ✅ Phase 1)
// ----------------------------------------------------------------------------
// PHASE 1 thật — wire `/api/v1/branding`:
//   GET   /api/v1/branding                 (current settings)
//   PATCH /api/v1/branding                 (update colors / tagline / sender)
//   POST  /api/v1/branding/logo            (multipart upload, max 1MB, PNG/SVG)
//   DELETE /api/v1/branding/logo           (revert to KaoriLockup default)
//
// Settings (CLAUDE.md §10 — chỉ ENT MID/MAX/ROI mới có quyền chỉnh):
//   - Logo URL hoặc upload (PNG/SVG, max 1MB)
//   - Brand colors (primary + accent) — KHÔNG đổi --bg-app cream để giữ identity Kaori
//   - Login page tagline (text Vietnamese, max 120 chars)
//   - Email sender display name (xuất hiện trong notification-service emails)
//   - Custom subdomain (Phase 2 only — disabled placeholder)
//
// Plan gating: chỉ MANAGER + plan ≥ MID mới chỉnh sửa được; VIEWER/ANALYST
// xem read-only; Pilot/Basic tier hiển thị upgrade nudge.
// ============================================================================

import React, { useEffect, useRef, useState } from 'react';
import {
  Palette, Upload, Image as ImageIcon, Trash2, Save, RefreshCw,
  ShieldCheck, Lock, AlertTriangle, ArrowUpRight, CheckCircle2,
  Eye, Mail, Globe,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, KaoriLockup, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type Plan = 'PILOT' | 'BASIC' | 'MID' | 'MAX' | 'ROI';
type Role = 'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER';

interface Branding {
  logo_url:           string | null;
  primary_color:      string;
  accent_color:       string;
  login_tagline:      string;
  email_sender_name:  string;
  custom_subdomain:   string | null;
  updated_at?:        string;
  updated_by_email?:  string;
}

interface MeContext {
  role: Role;
  plan: Plan;
}

const DEFAULT_BRANDING: Branding = {
  logo_url:          null,
  primary_color:     '#D4B88A',
  accent_color:      '#BFA88C',
  login_tagline:     'Biến dữ liệu kinh doanh thành quyết định',
  email_sender_name: 'Kaori Workspace',
  custom_subdomain:  null,
};

const MAX_LOGO_BYTES   = 1 * 1024 * 1024;   // 1 MB
const MAX_TAGLINE_LEN  = 120;
const MAX_SENDER_LEN   = 60;

const PLAN_GATED = new Set<Plan>(['PILOT', 'BASIC']);

export default function BrandingPage() {
  const t = useT();
  const [me,        setMe]        = useState<MeContext | null>(null);
  const [branding,  setBranding]  = useState<Branding>(DEFAULT_BRANDING);
  const [original,  setOriginal]  = useState<Branding>(DEFAULT_BRANDING);
  const [loading,   setLoading]   = useState(true);
  const [saving,    setSaving]    = useState(false);
  const [uploading, setUploading] = useState(false);
  const [problem,   setProblem]   = useState<ProblemDetails | null>(null);
  const [success,   setSuccess]   = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const [meRes, brand] = await Promise.all([
        api<MeContext>('/api/v1/me'),
        api<Branding>('/api/v1/branding'),
      ]);
      setMe(meRes);
      setBranding(brand);
      setOriginal(brand);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  const isManager = me?.role === 'MANAGER';
  const planLocked = me ? PLAN_GATED.has(me.plan) : false;
  const canEdit    = isManager && !planLocked;

  const dirty =
    branding.primary_color     !== original.primary_color     ||
    branding.accent_color      !== original.accent_color      ||
    branding.login_tagline     !== original.login_tagline     ||
    branding.email_sender_name !== original.email_sender_name;

  async function save() {
    if (!canEdit || !dirty) return;
    setSaving(true);
    setProblem(null);
    try {
      const updated = await api<Branding>('/api/v1/branding', {
        method: 'PATCH',
        body: JSON.stringify({
          primary_color:     branding.primary_color,
          accent_color:      branding.accent_color,
          login_tagline:     branding.login_tagline.trim(),
          email_sender_name: branding.email_sender_name.trim(),
        }),
      });
      setBranding(updated);
      setOriginal(updated);
      setSuccess(t('templates73Branding.successSaved'));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    setBranding(original);
    setSuccess(null);
    setProblem(null);
  }

  async function uploadLogo(file: File) {
    if (!canEdit) return;
    setProblem(null);
    if (file.size > MAX_LOGO_BYTES) {
      setProblem({
        title:  t('templates73Branding.errTooBigTitle'),
        detail: t('templates73Branding.errTooBigDetail', { size: (file.size / 1024).toFixed(0) }),
        status: 413,
      });
      return;
    }
    if (!['image/png', 'image/svg+xml'].includes(file.type)) {
      setProblem({
        title:  t('templates73Branding.errUnsupportedTitle'),
        detail: t('templates73Branding.errUnsupportedDetail'),
        status: 415,
      });
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      // Note: do NOT use the `api()` helper — multipart needs raw fetch
      const res = await fetch('/api/v1/branding/logo', {
        method:  'POST',
        headers: {
          Authorization:    `Bearer ${window.localStorage.getItem('kaori.access_token') ?? window.localStorage.getItem('kaori_jwt') ?? ''}`,
          'Idempotency-Key': (crypto as any).randomUUID?.() ?? `idem-${Date.now()}`,
          // Content-Type set automatically by browser including boundary
        },
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw { title: body?.title ?? `HTTP ${res.status}`, detail: body?.detail, status: res.status };
      }
      const updated = await res.json() as Branding;
      setBranding(updated);
      setOriginal(updated);
      setSuccess(t('templates73Branding.successLogoUploaded'));
    } catch (err: any) {
      setProblem(err?.title ? err : { title: t('templates73Branding.errUploadFailed'), detail: String(err?.message ?? err) });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function removeLogo() {
    if (!canEdit || !branding.logo_url) return;
    if (!confirm(t('templates73Branding.confirmRemoveLogo'))) return;
    setProblem(null);
    try {
      const updated = await api<Branding>('/api/v1/branding/logo', { method: 'DELETE' });
      setBranding(updated);
      setOriginal(updated);
      setSuccess(t('templates73Branding.successLogoRemoved'));
    } catch (err: any) {
      setProblem(err);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates73Branding.pageTitle')}
        description={t('templates73Branding.pageDescription')}
        actions={
          <>
            <Button variant="secondary" onClick={load}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('templates73Branding.reload')}
            </Button>
            {canEdit && dirty && (
              <Button variant="tertiary" onClick={reset}>{t('templates73Branding.discardChanges')}</Button>
            )}
            <Button onClick={save} isLoading={saving} disabled={!canEdit || !dirty}>
              <Save className="w-4 h-4 mr-2" />
              {t('templates73Branding.save')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {/* Plan gate */}
        {planLocked && (
          <div className="bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 rounded-lg-custom p-4 shadow-soft-sm flex items-start justify-between gap-3 flex-wrap">
            <div className="flex items-start gap-3">
              <Lock className="w-5 h-5 text-[var(--state-warning)] shrink-0 mt-0.5" />
              <div>
                <p className="font-serif text-base text-[#9E814D]">{t('templates73Branding.planGateTitle')}</p>
                <p className="text-sm text-[var(--text-primary)] mt-1">
                  {t('templates73Branding.planGateDetail', { plan: me?.plan ?? '' })}
                </p>
              </div>
            </div>
            <Button onClick={() => (window.location.href = '/p2/subscription/upgrade')}>
              <ArrowUpRight className="w-4 h-4 mr-2" />
              {t('templates73Branding.upgradePlan')}
            </Button>
          </div>
        )}

        {/* Role gate */}
        {!isManager && !planLocked && (
          <div className="bg-[var(--bg-app)]/40 border border-[var(--border-color)] rounded-md-custom p-3 flex items-start gap-2">
            <Lock className="w-4 h-4 text-[var(--text-secondary)] shrink-0 mt-0.5" />
            <p className="text-xs text-[var(--text-secondary)]">
              {t('templates73Branding.roleGatePrefix')} <span className="font-medium text-[var(--text-primary)]">{me?.role}</span> — {t('templates73Branding.roleGateSuffix')}
            </p>
          </div>
        )}

        {loading ? (
          <div className="h-96 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Left column: form (2/3 width) */}
            <div className="lg:col-span-2 space-y-5">
              {/* Logo */}
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
                <div className="flex items-center gap-2 mb-3">
                  <ImageIcon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates73Branding.logo')}</h3>
                </div>
                <p className="text-xs text-[var(--text-secondary)] mb-4">
                  {t('templates73Branding.logoHint')}
                </p>
                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 rounded-lg-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] flex items-center justify-center overflow-hidden">
                    {branding.logo_url
                      ? <img src={branding.logo_url} alt={t('templates73Branding.logo')} className="max-w-full max-h-full object-contain" />
                      : <KaoriLockup tagline="" iconOnly />}
                  </div>
                  <div className="flex-1">
                    <input
                      ref={fileRef}
                      type="file"
                      accept="image/png,image/svg+xml"
                      onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])}
                      disabled={!canEdit || uploading}
                      className="hidden"
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => fileRef.current?.click()}
                        disabled={!canEdit || uploading}
                        isLoading={uploading}
                      >
                        <Upload className="w-3.5 h-3.5 mr-1.5" />
                        {branding.logo_url ? t('templates73Branding.changeLogo') : t('templates73Branding.uploadLogo')}
                      </Button>
                      {branding.logo_url && (
                        <Button variant="tertiary" size="sm" onClick={removeLogo} disabled={!canEdit}>
                          <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                          {t('templates73Branding.delete')}
                        </Button>
                      )}
                    </div>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-2">
                      {t('templates73Branding.logoRecommendation')}
                    </p>
                  </div>
                </div>
              </div>

              {/* Colors */}
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
                <div className="flex items-center gap-2 mb-3">
                  <Palette className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates73Branding.brandColors')}</h3>
                </div>
                <p className="text-xs text-[var(--text-secondary)] mb-4">
                  {t('templates73Branding.colorsHintPrefix')} <span className="font-mono">#FAF7F2</span> {t('templates73Branding.colorsHintSuffix')}
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <ColorField
                    label={t('templates73Branding.colorPrimary')}
                    value={branding.primary_color}
                    onChange={(v) => setBranding({ ...branding, primary_color: v })}
                    disabled={!canEdit}
                  />
                  <ColorField
                    label={t('templates73Branding.colorAccent')}
                    value={branding.accent_color}
                    onChange={(v) => setBranding({ ...branding, accent_color: v })}
                    disabled={!canEdit}
                  />
                </div>
              </div>

              {/* Login tagline */}
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
                <div className="flex items-center gap-2 mb-3">
                  <Eye className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates73Branding.loginTagline')}</h3>
                </div>
                <Input
                  value={branding.login_tagline}
                  maxLength={MAX_TAGLINE_LEN}
                  onChange={(e) => setBranding({ ...branding, login_tagline: e.target.value })}
                  disabled={!canEdit}
                  helperText={t('templates73Branding.taglineHelper', { count: branding.login_tagline.length, max: MAX_TAGLINE_LEN })}
                />
              </div>

              {/* Email sender */}
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
                <div className="flex items-center gap-2 mb-3">
                  <Mail className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates73Branding.emailSenderName')}</h3>
                </div>
                <Input
                  value={branding.email_sender_name}
                  maxLength={MAX_SENDER_LEN}
                  onChange={(e) => setBranding({ ...branding, email_sender_name: e.target.value })}
                  disabled={!canEdit}
                  helperText={t('templates73Branding.senderHelper', { sender: branding.email_sender_name || 'Kaori Workspace' })}
                />
              </div>

              {/* Custom subdomain — Phase 2 */}
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm opacity-70">
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                    <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates73Branding.customSubdomain')}</h3>
                  </div>
                  <Badge variant="info">Phase 2</Badge>
                </div>
                <Input
                  value={branding.custom_subdomain ?? ''}
                  disabled
                  placeholder={t('templates73Branding.subdomainPlaceholder')}
                  helperText={t('templates73Branding.subdomainHelper')}
                />
              </div>
            </div>

            {/* Right column: live preview */}
            <div className="lg:col-span-1">
              <div className="sticky top-20 space-y-4">
                <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{t('templates73Branding.livePreview')}</p>

                {/* Login preview */}
                <div className="rounded-lg-custom border border-[var(--border-color)] bg-[#FAF7F2] p-5 shadow-soft-sm">
                  <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] mb-3">{t('templates73Branding.loginPage')}</p>
                  <div className="space-y-3">
                    <div className="flex items-center justify-center">
                      {branding.logo_url
                        ? <img src={branding.logo_url} alt="" className="h-10" />
                        : <KaoriLockup tagline="" iconOnly />}
                    </div>
                    <p className="font-serif text-base text-center text-[var(--text-primary)] leading-snug">
                      {branding.login_tagline || t('templates73Branding.taglinePlaceholder')}
                    </p>
                    <button
                      type="button"
                      style={{ backgroundColor: branding.primary_color }}
                      className="w-full px-4 py-2 rounded-md-custom text-sm font-medium text-[var(--text-primary)] shadow-soft-sm"
                    >
                      {t('templates73Branding.login')}
                    </button>
                  </div>
                </div>

                {/* Email preview */}
                <div className="rounded-lg-custom border border-[var(--border-color)] bg-white p-4 shadow-soft-sm">
                  <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] mb-3">{t('templates73Branding.sampleEmail')}</p>
                  <div className="border-l-4 pl-3 space-y-1" style={{ borderColor: branding.primary_color }}>
                    <p className="text-xs text-[var(--text-secondary)]">From: <span className="font-medium text-[var(--text-primary)]">{branding.email_sender_name || 'Kaori Workspace'}</span></p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">{t('templates73Branding.emailSubject')}</p>
                    <p className="text-xs text-[var(--text-secondary)] leading-snug">{t('templates73Branding.emailBody')}</p>
                    <button
                      type="button"
                      style={{ backgroundColor: branding.primary_color }}
                      className="mt-2 px-3 py-1.5 rounded-sm-custom text-xs font-medium text-[var(--text-primary)]"
                    >
                      {t('templates73Branding.confirm')}
                    </button>
                  </div>
                </div>

                {/* Updated meta */}
                {original.updated_at && (
                  <div className="text-[11px] text-[var(--text-secondary)] flex items-start gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--state-success)] shrink-0 mt-0.5" />
                    <span>
                      {t('templates73Branding.updatedAt', { date: original.updated_at })}
                      {original.updated_by_email && <> {t('templates73Branding.updatedBy', { email: original.updated_by_email })}</>}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Footer note */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates73Branding.auditPrefix')} <span className="font-mono">workspace_audit_log</span> {t('templates73Branding.auditMid')}
            <span className="font-mono"> actor_id</span> {t('templates73Branding.auditSuffix')}
          </p>
        </div>
      </div>
    </>
  );
}

// ----------------------------------------------------------------------------
// ColorField — hex input + native color picker swatch
// ----------------------------------------------------------------------------

function ColorField({
  label, value, onChange, disabled,
}: { label: string; value: string; onChange: (v: string) => void; disabled?: boolean }) {
  const t = useT();
  // Defensive normalization — keep #RRGGBB only
  const safe = /^#[0-9A-Fa-f]{6}$/.test(value) ? value : '#000000';
  return (
    <div>
      <label className="text-sm font-medium text-[var(--text-primary)]">{label}</label>
      <div className="mt-1 flex items-center gap-2">
        <label
          className={cn(
            'inline-block w-10 h-10 rounded-md-custom border border-[var(--border-color)] shadow-soft-sm',
            disabled ? 'cursor-not-allowed' : 'cursor-pointer',
          )}
          style={{ backgroundColor: safe }}
        >
          <input
            type="color"
            value={safe}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            disabled={disabled}
            className="opacity-0 w-0 h-0"
            aria-label={t('templates73Branding.chooseColor', { label })}
          />
        </label>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          maxLength={7}
          className="flex-1 px-3 py-2 font-mono text-sm bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-50"
          placeholder="#D4B88A"
        />
      </div>
    </div>
  );
}

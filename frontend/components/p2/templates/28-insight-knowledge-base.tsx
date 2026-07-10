// @ts-nocheck
'use client';

// ============================================================================
// 28. /p2/insights/knowledge-base — Knowledge Base (F-061 · CR-0017)
// ----------------------------------------------------------------------------
// Live wiring to the ai-orchestrator knowledge base:
//   POST /api/v1/knowledge-base/search     — semantic search (BGE-M3 cosine)
//   GET  /api/v1/knowledge-base/documents  — browse global (tier 1-3) + own
//   POST /api/v1/knowledge-base/documents  — ingest tenant (tier 4) knowledge
// X-Enterprise-ID is injected by the gateway from the JWT (RLS-scoped).
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  BookOpen, Search, Plus, ShieldCheck, Globe, Building2, Loader2,
} from 'lucide-react';

import { Button, Badge, Input, Label, ErrorBanner, SuccessBanner, cn } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { knowledgeApi } from '@/lib/api/client';
import { useT } from '@/lib/i18n/provider';

const TIER_KEY: Record<number, string> = {
  1: 'templates28InsightKnowledgeBase.tier1',
  2: 'templates28InsightKnowledgeBase.tier2',
  3: 'templates28InsightKnowledgeBase.tier3',
  4: 'templates28InsightKnowledgeBase.tier4',
};

function errText(err: any, t: (key: string, params?: Record<string, any>) => string): string {
  const d = err?.response?.data;
  return d?.detail?.title || d?.title || d?.detail || err?.message || t('templates28InsightKnowledgeBase.errGeneric');
}

function DocCard({ doc, showSimilarity }: { doc: any; showSimilarity?: boolean }) {
  const t = useT();
  const isGlobal = doc.scope === 'global';
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium text-sm text-[var(--text-primary)]">{doc.title}</p>
        {showSimilarity && doc.similarity != null && (
          <Badge variant="info">{t('templates28InsightKnowledgeBase.matchPercent', { percent: Math.round(doc.similarity * 100) })}</Badge>
        )}
      </div>
      {doc.snippet && (
        <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed">{doc.snippet}</p>
      )}
      <div className="mt-2.5 flex items-center gap-2 flex-wrap">
        <Badge variant={isGlobal ? 'default' : 'info'}>
          {isGlobal
            ? <><Globe className="w-3 h-3 mr-1 inline" />{t('templates28InsightKnowledgeBase.scopeGlobal')}</>
            : <><Building2 className="w-3 h-3 mr-1 inline" />{t('templates28InsightKnowledgeBase.scopeWorkspace')}</>}
        </Badge>
        <Badge variant="default">{TIER_KEY[doc.tier] ? t(TIER_KEY[doc.tier]) : `tier ${doc.tier}`}</Badge>
        {doc.category && <Badge variant="default">{doc.category}</Badge>}
        {doc.source && (
          <span className="text-xs text-[var(--text-secondary)]/80">· {doc.source}</span>
        )}
      </div>
    </div>
  );
}

export default function KnowledgeBasePage() {
  const t = useT();
  const [query, setQuery]       = useState('');
  const [results, setResults]   = useState<any[] | null>(null);
  const [searching, setSearching] = useState(false);

  const [docs, setDocs]         = useState<any[]>([]);
  const [listLoading, setListLoading] = useState(true);

  const [error, setError]       = useState<string | null>(null);
  const [success, setSuccess]   = useState<string | null>(null);

  const [showAdd, setShowAdd]   = useState(false);
  const [form, setForm]         = useState({ title: '', content: '', category: '' });
  const [saving, setSaving]     = useState(false);

  async function loadList() {
    setListLoading(true);
    try {
      const { data } = await knowledgeApi.list();
      setDocs(data.documents ?? []);
    } catch (err: any) {
      setError(errText(err, t));
    } finally {
      setListLoading(false);
    }
  }

  useEffect(() => { loadList(); }, []);

  async function onSearch(e?: React.FormEvent) {
    e?.preventDefault();
    const q = query.trim();
    if (!q) { setResults(null); return; }
    setSearching(true);
    setError(null);
    try {
      const { data } = await knowledgeApi.search(q, 8);
      setResults(data.results ?? []);
    } catch (err: any) {
      setError(errText(err, t));
    } finally {
      setSearching(false);
    }
  }

  async function onIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.content.trim()) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await knowledgeApi.ingest({
        title: form.title.trim(),
        content: form.content.trim(),
        category: form.category.trim() || undefined,
      });
      setSuccess(t('templates28InsightKnowledgeBase.successIngest'));
      setForm({ title: '', content: '', category: '' });
      setShowAdd(false);
      loadList();
    } catch (err: any) {
      setError(errText(err, t));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates28InsightKnowledgeBase.title')}
        description={t('templates28InsightKnowledgeBase.description')}
        actions={
          <Button variant="secondary" onClick={() => setShowAdd((v) => !v)}>
            <Plus className="w-4 h-4 mr-2" />{t('templates28InsightKnowledgeBase.addKnowledge')}
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {error && <ErrorBanner message={error} />}
        {success && <SuccessBanner message={success} />}

        {/* Semantic search */}
        <form onSubmit={onSearch} className="relative">
          <Search className="w-4 h-4 text-[var(--text-secondary)]/60 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('templates28InsightKnowledgeBase.searchPlaceholder')}
            className="w-full pl-9 pr-28 py-3 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/40"
          />
          <Button
            type="submit"
            disabled={searching || !query.trim()}
            className="absolute right-1.5 top-1/2 -translate-y-1/2"
          >
            {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : t('templates28InsightKnowledgeBase.searchButton')}
          </Button>
        </form>

        {/* Add-knowledge form */}
        {showAdd && (
          <form
            onSubmit={onIngest}
            className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3"
          >
            <p className="font-serif text-base text-[var(--text-primary)]">{t('templates28InsightKnowledgeBase.addFormTitle')}</p>
            <div>
              <Label htmlFor="kb-title">{t('templates28InsightKnowledgeBase.labelTitle')}</Label>
              <Input
                id="kb-title"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder={t('templates28InsightKnowledgeBase.titlePlaceholder')}
              />
            </div>
            <div>
              <Label htmlFor="kb-content">{t('templates28InsightKnowledgeBase.labelContent')}</Label>
              <textarea
                id="kb-content"
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                rows={4}
                placeholder={t('templates28InsightKnowledgeBase.contentPlaceholder')}
                className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/40"
              />
            </div>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <Label htmlFor="kb-cat">{t('templates28InsightKnowledgeBase.labelCategory')}</Label>
                <Input
                  id="kb-cat"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  placeholder={t('templates28InsightKnowledgeBase.categoryPlaceholder')}
                />
              </div>
              <Button type="submit" disabled={saving || !form.title.trim() || !form.content.trim()}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : t('templates28InsightKnowledgeBase.save')}
              </Button>
            </div>
          </form>
        )}

        {/* Search results */}
        {results !== null && (
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)] mb-3">
              {t('templates28InsightKnowledgeBase.searchResultsTitle')} {results.length > 0 && `(${results.length})`}
            </h3>
            {results.length === 0 ? (
              <p className="text-sm text-[var(--text-secondary)]">
                {t('templates28InsightKnowledgeBase.noResults')}
              </p>
            ) : (
              <div className="space-y-3">
                {results.map((d) => <DocCard key={d.document_id} doc={d} showSimilarity />)}
              </div>
            )}
          </div>
        )}

        {/* Browse all (when not searching) */}
        {results === null && (
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)] mb-3">
              {t('templates28InsightKnowledgeBase.allKnowledgeTitle')} {!listLoading && `(${docs.length})`}
            </h3>
            {listLoading ? (
              <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <Loader2 className="w-4 h-4 animate-spin" /> {t('templates28InsightKnowledgeBase.loading')}
              </div>
            ) : docs.length === 0 ? (
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-6 text-center">
                <BookOpen className="w-6 h-6 text-[var(--text-secondary)]/50 mx-auto mb-2" />
                <p className="text-sm text-[var(--text-secondary)]">
                  {t('templates28InsightKnowledgeBase.emptyState')}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {docs.map((d) => <DocCard key={d.document_id} doc={d} />)}
              </div>
            )}
          </div>
        )}

        {/* Privacy note */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates28InsightKnowledgeBase.privacyNote')}
          </p>
        </div>
      </div>
    </>
  );
}

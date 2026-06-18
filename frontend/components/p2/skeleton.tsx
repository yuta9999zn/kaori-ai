'use client';

// Skeleton loaders for P15-S11 Tuần 2 UX polish.
//
// Replaces the spin-then-content jank. While api() is in flight, render
// shaped placeholders that match the eventual layout — reduces apparent
// load time + lets the user see "real" structure immediately.

import React from 'react';
import { cn } from './foundation';

// ─── Primitive: animated shimmer block ───────────────────────────────

export function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse bg-[var(--border-color)]/40 rounded-md-custom',
        className,
      )}
    />
  );
}

// ─── Card grid skeleton (hub pages) ──────────────────────────────────

export function SkeletonCardGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5"
        >
          <div className="flex items-start justify-between mb-3">
            <SkeletonBlock className="w-10 h-10" />
            <SkeletonBlock className="w-16 h-5" />
          </div>
          <SkeletonBlock className="w-3/4 h-5 mb-2" />
          <SkeletonBlock className="w-full h-4 mb-1" />
          <SkeletonBlock className="w-1/2 h-4 mb-3" />
          <div className="pt-3 border-t border-[var(--border-color)]/60 flex justify-between">
            <SkeletonBlock className="w-20 h-4" />
            <SkeletonBlock className="w-10 h-4" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Stat tile row skeleton ──────────────────────────────────────────

export function SkeletonStatTiles({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5"
        >
          <SkeletonBlock className="w-24 h-3 mb-3" />
          <SkeletonBlock className="w-12 h-8" />
        </div>
      ))}
    </div>
  );
}

// ─── Org tree skeleton (left column) ─────────────────────────────────

export function SkeletonOrgTree() {
  return (
    <div className="space-y-1">
      {[1, 2, 3, 4, 5, 6, 7].map((i) => (
        <div
          key={i}
          className="flex items-center gap-2 px-2 py-1.5"
          style={{ paddingLeft: `${0.5 + (i % 3) * 1.25}rem` }}
        >
          <SkeletonBlock className="w-4 h-4" />
          <SkeletonBlock className="w-4 h-4" />
          <SkeletonBlock className="flex-1 h-4" />
          <SkeletonBlock className="w-12 h-3" />
        </div>
      ))}
    </div>
  );
}

// ─── Workflow detail skeleton (builder canvas + inspector) ──────────

export function SkeletonWorkflowDetail() {
  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-[var(--border-color)]">
        {[1, 2, 3].map((i) => (
          <SkeletonBlock key={i} className="w-24 h-8 m-1" />
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4">
        {/* Canvas */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-6 min-h-[480px]">
          <div className="flex flex-col items-center space-y-4">
            <SkeletonBlock className="w-32 h-12 rounded-full" />
            <SkeletonBlock className="w-1 h-6" />
            {[1, 2, 3].map((i) => (
              <React.Fragment key={i}>
                <SkeletonBlock className="w-[420px] h-20" />
                <SkeletonBlock className="w-1 h-6" />
              </React.Fragment>
            ))}
            <SkeletonBlock className="w-32 h-12 rounded-full" />
          </div>
        </div>
        {/* Inspector */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5">
          <SkeletonBlock className="w-32 h-5 mb-4 pb-3" />
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i}>
                <SkeletonBlock className="w-20 h-3 mb-1.5" />
                <SkeletonBlock className="w-full h-9" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Tree-tab skeleton (cards + cross-links) ─────────────────────────

export function SkeletonTreeTab() {
  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5">
        <div className="flex justify-between mb-4">
          <SkeletonBlock className="w-32 h-5" />
          <SkeletonBlock className="w-20 h-5" />
        </div>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="border border-[var(--border-color)] rounded-md-custom mb-3"
          >
            <SkeletonBlock className="h-10 m-2" />
            <SkeletonBlock className="h-6 mx-3 mb-3" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Stats / reports skeleton ────────────────────────────────────────

export function SkeletonReportsTab() {
  return (
    <div className="space-y-4">
      <SkeletonStatTiles count={4} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4"
          >
            <SkeletonBlock className="w-32 h-3 mb-3" />
            {[1, 2, 3].map((j) => (
              <div key={j} className="flex justify-between py-1.5">
                <SkeletonBlock className="w-24 h-4" />
                <SkeletonBlock className="w-12 h-4" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

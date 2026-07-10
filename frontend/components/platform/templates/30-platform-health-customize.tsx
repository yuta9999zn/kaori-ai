// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 30Plastform Heath customize.jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState, useEffect, useRef } from 'react';
import {
  LayoutDashboard, Briefcase, Key, CreditCard, Shield, Activity,
  Search, Bell, Menu, X, ChevronRight, ChevronLeft, MoreVertical,
  ArrowUpRight, ArrowDownRight, Settings, Laptop, Smartphone, MapPin,
  Globe, Clock, LogOut, AlertCircle, Loader2, Plus, ChevronsUpDown,
  User, Check, Calendar as CalendarIcon, ChevronDown, Info,
  CheckCircle2, Component, ShieldAlert, RefreshCw, PanelLeftOpen,
  PanelLeftClose, Eye, Edit2, Users, Ban, Trash2, ArrowLeft,
  Server, Zap, UserPlus, Mail, Send, Download, Receipt,
  HardDrive, FileText, FileJson, Save, AlertTriangle, Copy,
  RefreshCcw, BarChart3, Lock, Unlock, ShieldCheck, AlertOctagon,
  ExternalLink, SlidersHorizontal, LayoutTemplate, GripVertical, ListFilter
} from 'lucide-react';
import { useT } from '@/lib/i18n/provider';

const cn = (...classes) => classes.filter(Boolean).join(' ');

const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400&display=swap');

    :root {
      --primary-gold: #D4B88A;
      --primary-gold-dark: #BFA88C;
      --bg-app: #FAF7F2;
      --bg-sidebar: #F5F1EA;
      --bg-card: #FFFFFF;
      --border-color: #E9E7E2;
      --text-primary: #2F2F2F;
      --text-secondary: #8C8173;
      --state-success: #8FBFA0;
      --state-warning: #E6C07B;
      --state-error: #D97C7C;
      --state-info: #A5B4CB;
      --shadow-soft-sm: 0 2px 8px -2px rgba(47, 47, 47, 0.04), 0 1px 3px -1px rgba(47, 47, 47, 0.02);
      --shadow-soft-md: 0 6px 16px -4px rgba(47, 47, 47, 0.06), 0 4px 8px -2px rgba(47, 47, 47, 0.03);
      --shadow-soft-lg: 0 12px 24px -4px rgba(47, 47, 47, 0.08), 0 8px 12px -4px rgba(47, 47, 47, 0.04);
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
    }

    body { font-family: 'Inter', sans-serif; background-color: var(--bg-app); color: var(--text-primary); margin: 0; -webkit-font-smoothing: antialiased; }
    .font-serif { font-family: 'Playfair Display', serif; }
    .shadow-soft-sm { box-shadow: var(--shadow-soft-sm); }
    .shadow-soft-md { box-shadow: var(--shadow-soft-md); }
    .shadow-soft-lg { box-shadow: var(--shadow-soft-lg); }
    .rounded-sm-custom { border-radius: var(--radius-sm); }
    .rounded-md-custom { border-radius: var(--radius-md); }
    .rounded-lg-custom { border-radius: var(--radius-lg); }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #E9E7E2; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #D4B88A; }

    @keyframes slideUpFade { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    .animate-slide-up-fade { animation: slideUpFade 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
    @keyframes slideInRight { from { transform: translateX(100%); } to { transform: translateX(0); } }
    .animate-slide-in-right { animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
    @keyframes fadeInSlide { from { opacity: 0; transform: translateX(10px); } to { opacity: 1; transform: translateX(0); } }
    .animate-step { animation: fadeInSlide 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
    .sidebar-transition { transition: width 0.3s cubic-bezier(0.2, 0, 0, 1), padding 0.3s ease, opacity 0.2s ease; }

    .drag-over { border: 2px dashed var(--primary-gold) !important; background: var(--primary-gold) !important; opacity: 0.2; }
  `}</style>
);

const Badge = ({  variant = 'default', children, className  }: any) => {
  const variants = {
    default: "bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]",
    success: "bg-[var(--state-success)]/10 text-[#5C856A] border-[var(--state-success)]/30",
    warning: "bg-[var(--state-warning)]/10 text-[#9E814D] border-[var(--state-warning)]/30",
    error: "bg-[var(--state-error)]/10 text-[#9B5050] border-[var(--state-error)]/30",
    current: "bg-[var(--primary-gold)]/10 text-[#9E814D] border-[var(--primary-gold)]/30",
    operational: "bg-[#F3F9F5] text-[#427A5B] border-[#8FBFA0]/40",
    degraded: "bg-[#FDF9F0] text-[#9E814D] border-[#E6C07B]/40",
  };
  return <span className={cn(`inline-flex items-center px-2 py-0.5 rounded-sm-custom text-[11px] font-medium border`, variants[variant], className)}>{children}</span>;
};

const Button = React.forwardRef<any, any>(({ className, variant = "primary", size = "md", isLoading, disabled, children, ...props }, ref) => {
  const variants = {
    primary: "bg-[var(--primary-gold)] text-[var(--text-primary)] hover:bg-[var(--primary-gold-dark)] active:scale-[0.98] shadow-soft-sm border border-transparent",
    secondary: "border border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-primary)] hover:bg-[var(--bg-app)] active:scale-[0.98] shadow-sm",
    tertiary: "bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-color)]/30 active:scale-[0.98]",
    destructive: "bg-[var(--state-error)] text-white hover:bg-[#C26B6B] active:scale-[0.98] shadow-soft-sm border border-transparent",
    "destructive-soft": "border border-[var(--border-color)] bg-transparent text-[var(--text-primary)] hover:border-[var(--state-error)]/40 hover:bg-[var(--state-error)]/10 hover:text-[#9B5050] active:scale-[0.98]",
  };
  const sizes = { sm: "h-8 px-3 text-xs rounded-sm-custom", md: "h-10 px-4 py-2 text-sm rounded-md-custom", lg: "h-12 px-6 py-3 text-base rounded-md-custom", icon: "h-10 w-10 rounded-md-custom" };
  return (
    <button ref={ref} disabled={isLoading || disabled} className={cn("inline-flex items-center justify-center font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50 disabled:opacity-50 disabled:pointer-events-none", variants[variant], sizes[size], className)} {...props}>
      {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
});
Button.displayName = "Button";

const Switch = ({  checked, onChange, disabled  }: any) => (
  <button
    type="button"
    disabled={disabled}
    role="switch"
    aria-checked={checked}
    onClick={() => onChange(!checked)}
    className={cn(
      "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/50 disabled:opacity-50 disabled:cursor-not-allowed",
      checked ? "bg-[#5C856A]" : "bg-[#E9E7E2]"
    )}
  >
    <span className={cn(
      "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
      checked ? "translate-x-4" : "translate-x-0"
    )} />
  </button>
);

const Label = React.forwardRef<any, any>(({ className, ...props }, ref) => (
  <label ref={ref} className={cn("text-sm font-medium leading-none text-[var(--text-primary)] peer-disabled:cursor-not-allowed peer-disabled:opacity-70", className)} {...props} />
));
Label.displayName = "Label";

const Input = React.forwardRef<any, any>(({ className, label, error, helperText, multiline, ...props }, ref) => {
  return (
    <div className="space-y-2 w-full">
      {label && <Label>{label}</Label>}
      {multiline ? (
        <textarea ref={ref} className={cn("flex min-h-[80px] w-full rounded-md-custom border bg-white px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 transition-all duration-200 resize-y focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/30 focus-visible:border-[var(--primary-gold)] disabled:cursor-not-allowed disabled:opacity-50 shadow-soft-sm disabled:bg-[var(--bg-app)]", error ? "border-[var(--state-error)] focus-visible:ring-[var(--state-error)]/30 focus-visible:border-[var(--state-error)]" : "border-[var(--border-color)]", className)} {...props} />
      ) : (
        <input ref={ref} className={cn("flex h-10 w-full rounded-md-custom border bg-white px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/30 focus-visible:border-[var(--primary-gold)] disabled:cursor-not-allowed disabled:opacity-50 shadow-soft-sm disabled:bg-[var(--bg-app)]", error ? "border-[var(--state-error)] focus-visible:ring-[var(--state-error)]/30 focus-visible:border-[var(--state-error)]" : "border-[var(--border-color)]", className)} {...props} />
      )}
      {error && <p className="text-xs font-medium text-[var(--state-error)]">{error}</p>}
      {helperText && !error && <p className="text-xs text-[var(--text-secondary)]">{helperText}</p>}
    </div>
  );
});
Input.displayName = "Input";

const Select = ({  label, placeholder, options = [], value, onChange, error, disabled  }: any) => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<any>(null);
  useEffect(() => {
    const handleClickOutside = (event) => { if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false); };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  const selectedOption = options.find(opt => opt.value === value);

  return (
    <div className="space-y-2 w-full relative" ref={dropdownRef}>
      {label && <Label className={disabled ? "opacity-50" : ""}>{label}</Label>}
      <button type="button" disabled={disabled} onClick={() => setIsOpen(!isOpen)} className={cn("flex h-10 w-full items-center justify-between rounded-md-custom border bg-white px-3 py-2 text-sm shadow-soft-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-50 disabled:bg-[var(--bg-app)] disabled:cursor-not-allowed", error ? "border-[var(--state-error)]" : "border-[var(--border-color)] hover:border-[var(--primary-gold)]/50", !selectedOption ? "text-[var(--text-secondary)]/60" : "text-[var(--text-primary)]")}>
        {selectedOption ? selectedOption.label : (placeholder || t('templates30PlatformHealthCustomize.selectDefaultPlaceholder'))}
        <ChevronDown className="h-4 w-4 opacity-50" />
      </button>
      {isOpen && !disabled && (
        <div className="absolute top-full left-0 z-50 w-full mt-1 bg-white rounded-md-custom border border-[var(--border-color)] shadow-soft-md animate-in fade-in zoom-in-95 duration-150 overflow-hidden py-1">
          {options.map((opt) => (
            <div key={opt.value} onClick={() => { onChange(opt.value); setIsOpen(false); }} className={cn("relative flex w-full cursor-pointer select-none items-center rounded-sm py-2 pl-8 pr-2 text-sm outline-none hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)] transition-colors", value === opt.value ? "bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)] font-medium" : "text-[var(--text-primary)]")}>
              {value === opt.value && <Check className="absolute left-2 h-4 w-4" />}
              {opt.label}
            </div>
          ))}
        </div>
      )}
      {error && <p className="text-xs font-medium text-[var(--state-error)]">{error}</p>}
    </div>
  );
};

const DatePicker = ({  label, placeholder, date, setDate  }: any) => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<any>(null);
  useEffect(() => {
    const handleClickOutside = (e) => { if (ref.current && !ref.current.contains(e.target)) setIsOpen(false); };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  return (
    <div className="space-y-2 w-full relative" ref={ref}>
      {label && <Label>{label}</Label>}
      <button type="button" onClick={() => setIsOpen(!isOpen)} className={cn("flex h-10 w-full items-center justify-start text-left rounded-md-custom border border-[var(--border-color)] bg-white px-3 py-2 text-sm shadow-soft-sm transition-all duration-200 hover:border-[var(--primary-gold)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30", !date ? "text-[var(--text-secondary)]/60" : "text-[var(--text-primary)]")}>
        <CalendarIcon className="mr-2 h-4 w-4 opacity-50" />
        {date ? date : (placeholder || t('templates30PlatformHealthCustomize.datePickerDefaultPlaceholder'))}
      </button>
      {isOpen && (
        <div className="absolute top-full left-0 z-50 mt-1 p-3 bg-white rounded-md-custom border border-[var(--border-color)] shadow-soft-md animate-in fade-in zoom-in-95 duration-150 w-[280px]">
           <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-semibold text-[var(--text-primary)]">October 2026</span>
              <div className="flex gap-1">
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronLeft className="w-4 h-4 text-[var(--text-secondary)]"/></button>
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronRight className="w-4 h-4 text-[var(--text-secondary)]"/></button>
              </div>
           </div>
           <div className="grid grid-cols-7 gap-1 text-center text-xs text-[var(--text-secondary)] mb-2">
             {['Su','Mo','Tu','We','Th','Fr','Sa'].map(d => <div key={d}>{d}</div>)}
           </div>
           <div className="grid grid-cols-7 gap-1 text-sm">
             {Array.from({length: 31}).map((_, i) => (
                <button key={i} onClick={() => { setDate(`Oct ${i + 1}, 2026`); setIsOpen(false); }} className={cn("h-8 w-8 rounded flex items-center justify-center hover:bg-[var(--bg-app)] transition-colors", date === `Oct ${i + 1}, 2026` ? "bg-[var(--primary-gold)] text-white hover:bg-[var(--primary-gold-dark)]" : "text-[var(--text-primary)]")}>{i + 1}</button>
             ))}
           </div>
        </div>
      )}
    </div>
  );
};

const Card = ({  className, ...props  }: any) => (
  <div className={cn("bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm", className)} {...props} />
);

const MetricCard = ({  title, value, trend, isUp, inverseGood = false, className  }: any) => {
  const t = useT();
  const isPositive = (isUp && !inverseGood) || (!isUp && inverseGood);
  const trendColor = trend === '0%' ? 'text-[var(--text-secondary)]' : isPositive ? 'text-[#5C856A]' : 'text-[#9B5050]';
  return (
    <Card className={cn("transition-shadow hover:shadow-soft-md p-5 flex flex-col justify-between", className)}>
      <div className="text-sm font-medium text-[var(--text-secondary)] mb-3">{title}</div>
      <div>
        <div className="flex items-baseline gap-3">
          <div className="text-3xl font-semibold text-[var(--text-primary)]">{value}</div>
          {trend && trend !== '0%' && (
            <div className={`flex items-center text-xs font-medium ${trendColor}`}>
              {isUp ? <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" /> : <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" />}
              {trend}
            </div>
          )}
        </div>
        <div className="text-xs text-[var(--text-secondary)] mt-1 opacity-75">{t('templates30PlatformHealthCustomize.vsYesterday')}</div>
      </div>
    </Card>
  );
};

const Table = ({  className, ...props  }: any) => <div className="w-full overflow-auto"><table className={cn("w-full caption-bottom text-sm", className)} {...props} /></div>;
const TableHeader = ({  className, ...props  }: any) => <thead className={cn("bg-[var(--bg-app)] border-b border-[var(--border-color)]", className)} {...props} />;
const TableBody = ({  className, ...props  }: any) => <tbody className={cn("[&_tr:last-child]:border-0 divide-y divide-[var(--border-color)]", className)} {...props} />;
const TableRow = ({  className, ...props  }: any) => <tr className={cn("border-b border-[var(--border-color)] transition-colors hover:bg-[var(--bg-app)]/50", className)} {...props} />;
const TableHead = ({  className, ...props  }: any) => <th className={cn("h-12 px-4 text-left align-middle font-medium text-[var(--text-secondary)] text-xs uppercase tracking-wider", className)} {...props} />;
const TableCell = ({  className, ...props  }: any) => <td className={cn("p-4 align-middle text-[var(--text-primary)]", className)} {...props} />;

const DataTable = ({  columns, data, loading, pagination = true, onRowClick  }: any) => {
  const t = useT();
  return (
    <div className="rounded-lg-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm overflow-hidden w-full">
      <Table>
        <TableHeader><TableRow>{columns.map((col, i) => <TableHead key={i}>{col}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {loading ? (
             Array.from({length: 3}).map((_, i) => (
                <TableRow key={i}>{columns.map((_, j) => <TableCell key={j}><div className="h-4 bg-[var(--bg-app)] rounded animate-pulse w-3/4"></div></TableCell>)}</TableRow>
             ))
          ) : data.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-32 text-center">
                <div className="flex flex-col items-center justify-center space-y-1">
                  <div className="w-10 h-10 rounded-full bg-[var(--bg-app)] flex items-center justify-center mb-2"><Search className="w-5 h-5 text-[var(--text-secondary)]" /></div>
                  <span className="text-sm font-medium text-[var(--text-primary)]">{t('templates30PlatformHealthCustomize.noResultsFound')}</span>
                  <span className="text-xs text-[var(--text-secondary)]">{t('templates30PlatformHealthCustomize.tryAdjustingFilters')}</span>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, i) => (
              <TableRow key={i} className={onRowClick ? "cursor-pointer hover:bg-[#FAF7F2]/50" : ""} onClick={() => onRowClick && onRowClick(row)}>
                {row.map((cell, j) => <TableCell key={j}>{cell}</TableCell>)}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      {pagination && data.length > 0 && (
        <div className="border-t border-[var(--border-color)] px-4 py-3 flex items-center justify-between bg-[#FCFBF9]">
          <span className="text-xs text-[var(--text-secondary)]">{t('templates30PlatformHealthCustomize.showingResults', { count: data.length })}</span>
          <div className="flex gap-2"><Button variant="outline" size="sm" disabled>{t('templates30PlatformHealthCustomize.previous')}</Button><Button variant="outline" size="sm">{t('templates30PlatformHealthCustomize.next')}</Button></div>
        </div>
      )}
    </div>
  );
};

const Modal = ({  isOpen, onClose, title, description, children, footer, widthClass = "max-w-lg"  }: any) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-0">
      <div className="absolute inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className={cn("relative bg-[var(--bg-card)] rounded-lg-custom shadow-soft-lg border border-[var(--border-color)] w-full overflow-hidden animate-slide-up-fade", widthClass)}>
        <div className="p-6 pb-4">
           <h2 className="text-lg font-semibold text-[var(--text-primary)] leading-none mb-2">{title}</h2>
           {description && <p className="text-sm text-[var(--text-secondary)]">{description}</p>}
        </div>
        <div className="px-6 py-4">{children}</div>
        {footer && <div className="px-6 py-4 bg-[var(--bg-app)] border-t border-[var(--border-color)] flex justify-end gap-3">{footer}</div>}
      </div>
    </div>
  );
};

const Drawer = ({  isOpen, onClose, title, children, footer, widthClass = "max-w-md"  }: any) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className={cn("relative bg-[var(--bg-card)] w-full h-full shadow-soft-lg border-l border-[var(--border-color)] flex flex-col animate-slide-in-right", widthClass)}>
        <div className="px-6 py-5 border-b border-[var(--border-color)] flex justify-between items-center">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
          <button onClick={onClose} className="p-2 -mr-2 rounded-md hover:bg-[var(--bg-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"><X className="w-5 h-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
        {footer && <div className="p-6 border-t border-[var(--border-color)] bg-[#FCFBF9]">{footer}</div>}
      </div>
    </div>
  );
};

const Alert = ({  variant = "info", title, children, className  }: any) => {
  const variants = {
    info: "bg-[#F4F7FB] border-[#A5B4CB]/40 text-[#4A648A] [&>svg]:text-[#4A648A]",
    success: "bg-[#F3F9F5] border-[#8FBFA0]/40 text-[#427A5B] [&>svg]:text-[#427A5B]",
    warning: "bg-[#FDF9F0] border-[#E6C07B]/40 text-[#9E814D] [&>svg]:text-[#9E814D]",
    error: "bg-[#FDF8F8] border-[#D97C7C]/40 text-[#9B5050] [&>svg]:text-[#9B5050]",
  };
  const icons = { info: Info, success: CheckCircle2, warning: AlertCircle, error: ShieldAlert, danger: AlertTriangle };
  const Icon = icons[variant] || Info;
  return (
    <div className={cn("relative w-full rounded-md-custom border p-4 shadow-soft-sm flex gap-3 items-start", variants[variant], className)}>
      <Icon className="w-5 h-5 shrink-0 mt-0.5" />
      <div className="flex flex-col gap-1">
        {title && <h5 className="mb-1 font-medium leading-none tracking-tight">{title}</h5>}
        <div className="text-sm opacity-90">{children}</div>
      </div>
    </div>
  );
};

const Tabs = ({  defaultValue, tabs, className  }: any) => {
  const [activeTab, setActiveTab] = useState(defaultValue);
  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-6 border-b border-[var(--border-color)] overflow-x-auto no-scrollbar">
        {tabs.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={cn("h-10 text-sm font-medium transition-colors border-b-2 -mb-[1px] whitespace-nowrap", activeTab === tab.id ? "border-[var(--primary-gold)] text-[var(--primary-gold)]" : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-color)]")}>
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-6 animate-in fade-in duration-300">{tabs.find(t => t.id === activeTab)?.content}</div>
    </div>
  );
};

const CopyButton = ({  text, className  }: any) => {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={handleCopy} className={cn("p-1 hover:bg-[var(--bg-app)] rounded transition-colors text-[var(--text-secondary)] hover:text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/50", className)} aria-label={t('templates30PlatformHealthCustomize.copyToClipboard')}>
      {copied ? <Check className="w-3.5 h-3.5 text-[#5C856A]" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

const PageContainer = ({  children, maxWidth = 'default', className = ''  }: any) => {
  const maxWidthClasses = { narrow: 'max-w-[720px]', default: 'max-w-[1280px]', wide: 'max-w-[1440px]' };
  return <div className={`mx-auto w-full animate-in fade-in duration-300 pb-12 ${maxWidthClasses[maxWidth]} ${className}`}>{children}</div>;
};

const PageHeader = ({  title, subtitle, actions, className = '', showBack, onBack  }: any) => (
  <div className={`flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6 sm:mb-8 ${className}`}>
    <div className="flex items-start gap-4">
      {showBack && (
        <button onClick={onBack} className="mt-1 p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]"><ArrowLeft className="w-5 h-5" /></button>
      )}
      <div>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-1">{title}</h1>
        {subtitle && <p className="text-sm text-[var(--text-secondary)]">{subtitle}</p>}
      </div>
    </div>
    {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
  </div>
);

const Section = ({  title, description, actions, children, className = ''  }: any) => (
  <section className={`mb-6 sm:mb-8 ${className}`}>
    {(title || description || actions) && (
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-4 pl-1">
        <div>
          {title && <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{title}</h2>}
          {description && <p className="text-xs text-[var(--text-secondary)] mt-1">{description}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    )}
    {children}
  </section>
);

const NAVIGATION_CONFIG = [
  { groupKey: 'templates30PlatformHealthCustomize.navGroupMain', items: [{ id: 'overview', labelKey: 'templates30PlatformHealthCustomize.navPlatformHealth', icon: LayoutDashboard, route: '/platform' }, { id: 'workspaces', labelKey: 'templates30PlatformHealthCustomize.navWorkspaces', icon: Briefcase, route: '/platform/workspaces', badge: '4' }] },
  { groupKey: 'templates30PlatformHealthCustomize.navGroupManagement', items: [{ id: 'keys', labelKey: 'templates30PlatformHealthCustomize.navApiKeys', icon: Key, route: '/platform/keys' }, { id: 'billing', labelKey: 'templates30PlatformHealthCustomize.navBilling', icon: CreditCard, route: '/platform/billing' }, { id: 'admin', labelKey: 'templates30PlatformHealthCustomize.navAdmins', icon: Shield, route: '/platform/admins', role: 'admin' }] },
  { groupKey: 'templates30PlatformHealthCustomize.navGroupSystem', items: [{ id: 'components', labelKey: 'templates30PlatformHealthCustomize.navComponentLibrary', icon: Component, route: '/platform/components' }, { id: 'sessions', labelKey: 'templates30PlatformHealthCustomize.navSecuritySessions', icon: Settings, route: '/p1/auth/sessions' }] }
];

const EnvBadge = ({  env = 'production'  }: any) => {
  const config = { production: "bg-[var(--primary-gold)]/15 text-[#9E814D] border-[var(--primary-gold)]/30", staging: "bg-white text-[var(--text-secondary)] border-[var(--border-color)]", development: "bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]" };
  return <span className={`hidden md:inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${config[env]}`}>{env}</span>;
};

const NotificationDropdown = () => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<any>(null);
  useEffect(() => {
    const handleClickOutside = (event) => { if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false); };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  const notifications = [{ id: 1, title: t('templates30PlatformHealthCustomize.notifDataSyncCompleted'), time: '10m ago', read: false }];
  return (
    <div className="relative" ref={dropdownRef}>
      <button onClick={() => setIsOpen(!isOpen)} className={`relative p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-full transition-colors border ${isOpen ? 'bg-[var(--bg-app)] border-[var(--border-color)]' : 'border-transparent hover:bg-[var(--bg-app)] hover:border-[var(--border-color)]'}`}>
        <Bell className="w-[18px] h-[18px]" /><span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--state-error)] border-2 border-[var(--bg-app)] animate-pulse"></span>
      </button>
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[320px] bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)] bg-[#FCFBF9]"><h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates30PlatformHealthCustomize.notifications')}</h3></div>
          <div className="max-h-[300px] overflow-y-auto">
            {notifications.map((n) => (
              <div key={n.id} className="px-4 py-3 border-b border-[var(--border-color)]/50 last:border-0 hover:bg-[var(--bg-app)]/50 transition-colors cursor-pointer flex gap-3 bg-[#FAF7F2]/30">
                <div className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 bg-[var(--primary-gold)]" />
                <div><p className="text-sm font-medium text-[var(--text-primary)]">{n.title}</p><p className="text-[11px] text-[var(--text-secondary)] mt-1">{n.time}</p></div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const HeaderUserMenu = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<any>(null);
  useEffect(() => {
    const handleClickOutside = (event) => { if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false); };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  return (
    <div className="relative" ref={dropdownRef}>
      <button onClick={() => setIsOpen(!isOpen)} className="w-[34px] h-[34px] rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center transition-all hover:shadow-soft-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50"><span className="text-sm font-semibold text-[var(--text-secondary)]">A</span></button>
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[240px] bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50">
          <div className="px-4 py-3 border-b border-[var(--border-color)] bg-[#FCFBF9]"><p className="text-sm font-semibold text-[var(--text-primary)] truncate">Admin User</p><p className="text-xs text-[var(--text-secondary)] truncate">admin@kaori.io</p></div>
          <div className="p-1.5"><button onClick={() => { setActiveRoute('sessions'); setIsOpen(false); }} className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors flex items-center gap-2"><Shield className="w-4 h-4 text-[var(--text-secondary)]" /> {t('templates30PlatformHealthCustomize.navSecuritySessions')}</button></div>
          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" />
          <div className="p-1.5"><button className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] transition-colors flex items-center gap-2 font-medium"><LogOut className="w-4 h-4" /> {t('templates30PlatformHealthCustomize.signOut')}</button></div>
        </div>
      )}
    </div>
  );
};

const GlobalHeader = ({  activeRoute, setActiveRoute, setIsMobileMenuOpen  }: any) => {
  const t = useT();
  let routeLabel = NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.labelKey;
  routeLabel = routeLabel ? t(routeLabel) : undefined;
  if (activeRoute === 'workspace-details') routeLabel = t('templates30PlatformHealthCustomize.routeWorkspacesOverview');
  else if (activeRoute === 'workspace-members') routeLabel = t('templates30PlatformHealthCustomize.routeWorkspacesMembers');
  else if (activeRoute === 'workspace-billing') routeLabel = t('templates30PlatformHealthCustomize.routeWorkspacesBilling');
  else if (activeRoute === 'audit-logs') routeLabel = t('templates30PlatformHealthCustomize.routeWorkspacesAuditLogs');
  else if (activeRoute === 'workspace-new') routeLabel = t('templates30PlatformHealthCustomize.routeWorkspacesNew');
  else if (activeRoute === 'workspace-edit') routeLabel = t('templates30PlatformHealthCustomize.routeWorkspacesSettings');
  else if (activeRoute === 'keys-new') routeLabel = t('templates30PlatformHealthCustomize.routeApiKeysCreate');
  else if (activeRoute === 'key-details') routeLabel = t('templates30PlatformHealthCustomize.routeApiKeysDetails');
  else if (activeRoute === 'admin-invite') routeLabel = t('templates30PlatformHealthCustomize.routeAdminsInvite');
  else if (activeRoute === 'admin-details') routeLabel = t('templates30PlatformHealthCustomize.routeAdminsDetails');
  else if (activeRoute === 'admin-reset-password') routeLabel = t('templates30PlatformHealthCustomize.routeAdminsResetPassword');
  else if (activeRoute === 'enterprise-billing-details') routeLabel = t('templates30PlatformHealthCustomize.routeBillingEnterpriseDetail');
  else if (activeRoute === 'quota') routeLabel = t('templates30PlatformHealthCustomize.routeBillingQuota');
  else if (activeRoute === 'billing-export') routeLabel = t('templates30PlatformHealthCustomize.routeBillingExport');
  else if (activeRoute === 'health-customize') routeLabel = t('templates30PlatformHealthCustomize.routePlatformCustomize');
  else if (!routeLabel) routeLabel = activeRoute;

  return (
    <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/90 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6 transition-all duration-300">
      <div className="flex items-center gap-4">
        <button className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]" onClick={() => setIsMobileMenuOpen(true)}><Menu className="w-5 h-5" /></button>
        <div className="hidden sm:flex items-center text-sm font-medium"><span className="text-[var(--text-secondary)]">{t('templates30PlatformHealthCustomize.breadcrumbPlatform')}</span><ChevronRight className="w-4 h-4 mx-2 text-[var(--border-color)] shrink-0 opacity-50" /><span className="text-[var(--text-primary)] capitalize">{routeLabel}</span></div>
      </div>
      <div className="flex items-center gap-3 sm:gap-4">
        <EnvBadge env="production" />
        <div className="w-[1px] h-5 bg-[var(--border-color)] hidden md:block mx-1"></div>
        <div className="hidden sm:flex items-center gap-2">
           <div className="relative group hidden lg:block">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-[14px] h-[14px] text-[var(--text-secondary)] group-focus-within:text-[var(--primary-gold)] transition-colors" />
              <input type="text" placeholder={t('templates30PlatformHealthCustomize.searchPlaceholder')} className="h-8 w-48 pl-8 pr-10 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm" />
            </div>
            <Button variant="outline" size="sm" onClick={() => setActiveRoute('workspace-new')} className="hidden md:flex"><Plus className="w-3.5 h-3.5 mr-1.5" /> {t('templates30PlatformHealthCustomize.quickCreateWorkspace')}</Button>
        </div>
        <NotificationDropdown />
        <HeaderUserMenu setActiveRoute={setActiveRoute} />
      </div>
    </header>
  );
};

const SidebarTooltip = ({  children, content, isCollapsed  }: any) => {
  if (!isCollapsed) return children;
  return (
    <div className="group relative flex w-full">
      {children}
      <div role="tooltip" className="absolute left-full top-1/2 -translate-y-1/2 ml-3 px-2.5 py-1.5 bg-[var(--text-primary)] text-white text-xs font-medium rounded shadow-soft-md opacity-0 group-hover:opacity-100 pointer-events-none z-50 whitespace-nowrap transition-opacity duration-200">
        {content}
        <div className="absolute top-1/2 -left-1 -translate-y-1/2 border-y-4 border-y-transparent border-r-4 border-r-[var(--text-primary)]"></div>
      </div>
    </div>
  );
};

const GlobalSidebar = ({  isMobile, activeRoute, setActiveRoute, isCollapsed, setIsCollapsed  }: any) => {
  const t = useT();
  const collapsed = isCollapsed && !isMobile;
  const currentHighlight =
    (activeRoute === 'workspace-details' || activeRoute === 'workspace-members' || activeRoute === 'workspace-billing' || activeRoute === 'audit-logs' || activeRoute === 'workspace-new' || activeRoute === 'workspace-edit') ? 'workspaces' :
    (activeRoute === 'keys-new' || activeRoute === 'key-details') ? 'keys' :
    (activeRoute === 'admin-invite' || activeRoute === 'admin-details' || activeRoute === 'admin-reset-password') ? 'admin' :
    (activeRoute === 'enterprise-billing-details' || activeRoute === 'quota' || activeRoute === 'billing-export') ? 'billing' :
    (activeRoute === 'health-customize') ? 'overview' :
    activeRoute;

  return (
    <aside className={cn("relative flex flex-col h-full bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] sidebar-transition z-30", isMobile ? 'w-[280px]' : collapsed ? 'w-[72px]' : 'w-[240px]')}>
      <div className={`flex items-center h-16 shrink-0 border-b border-[var(--border-color)]/50 sidebar-transition ${collapsed ? 'px-0 justify-center' : 'px-5 gap-3'}`}>
        <div className="flex h-8 w-8 items-center justify-center rounded-md-custom bg-white shadow-soft-sm border border-[var(--border-color)] shrink-0">
          <svg className="w-5 h-5 text-[var(--primary-gold)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z" fill="currentColor" fillOpacity="0.1"/><path d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z" fill="currentColor" fillOpacity="0.1"/>
          </svg>
        </div>
        {!collapsed && (
          <div className="flex flex-col overflow-hidden animate-in fade-in duration-300">
            <span className="font-serif text-[17px] leading-none font-semibold text-[var(--text-primary)] tracking-wide">Kaori</span>
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mt-0.5">{t('templates30PlatformHealthCustomize.sidebarTagline')}</span>
          </div>
        )}
      </div>

      <nav aria-label="Main Navigation" className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 space-y-6">
        {NAVIGATION_CONFIG.map((group, idx) => (
          <div key={idx} className="flex flex-col">
            {!collapsed ? <div className="px-3 mb-2 text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-[0.1em] opacity-70">{t(group.groupKey)}</div> : <div className="w-full h-[1px] bg-[var(--border-color)]/60 my-2 rounded-full" />}
            <div className="space-y-1">
              {group.items.map((item) => {
                const isActive = currentHighlight === item.id;
                const Icon = item.icon;
                return (
                  <SidebarTooltip key={item.id} content={t(item.labelKey)} isCollapsed={collapsed}>
                    <button onClick={() => setActiveRoute(item.id)} className={cn("relative flex items-center h-10 rounded-md-custom transition-all duration-200 group w-full", isActive ? "bg-[var(--primary-gold)]/10 text-[var(--text-primary)]" : "text-[var(--text-secondary)] hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)]", collapsed ? "justify-center px-0" : "px-3 gap-3")}>
                      {isActive && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[var(--primary-gold)] rounded-r-md transition-all" />}
                      <Icon className={`shrink-0 transition-colors ${isActive ? 'text-[var(--primary-gold)] w-5 h-5' : 'w-[18px] h-[18px] group-hover:text-[var(--text-primary)]'}`} />
                      {!collapsed && <span className="text-sm font-medium truncate flex-1 text-left">{t(item.labelKey)}</span>}
                      {!collapsed && item.badge && <span className="shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-[var(--primary-gold)] text-white text-[10px] font-bold shadow-sm ml-2">{item.badge}</span>}
                      {collapsed && item.badge && <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[var(--primary-gold)] border border-[var(--bg-sidebar)]" />}
                    </button>
                  </SidebarTooltip>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="shrink-0 p-3 flex justify-center">
        {!isMobile && (
          <button onClick={() => setIsCollapsed(!isCollapsed)} className={cn("w-full flex items-center h-8 rounded-md-custom text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors border border-transparent hover:border-[var(--border-color)]/50", collapsed ? 'justify-center' : 'px-3 gap-3')}>
            {collapsed ? <PanelLeftOpen className="w-[18px] h-[18px]" /> : <PanelLeftClose className="w-[18px] h-[18px]" />}
            {!collapsed && <span className="text-xs font-medium">{t('templates30PlatformHealthCustomize.collapseSidebar')}</span>}
          </button>
        )}
      </div>
    </aside>
  );
};

// ==========================================
// 4. VIEWS & PAGES
// ==========================================

const EnterpriseUsageCard = ({  title, current, max, unit, icon: Icon  }: any) => {
  const t = useT();
  const percent = Math.min((current / max) * 100, 100);
  const isWarning = percent >= 80;
  return (
    <Card className="p-5 flex flex-col justify-between">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center shrink-0"><Icon className="w-5 h-5 text-[var(--text-secondary)]" /></div>
        <div><h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3><p className="text-xs text-[var(--text-secondary)]">{current.toLocaleString()} / {max.toLocaleString()} {unit}</p></div>
      </div>
      <div className="w-full bg-[var(--bg-app)] rounded-full h-2 border border-[var(--border-color)] overflow-hidden"><div className={cn("h-2 rounded-full transition-all duration-500", isWarning ? "bg-[#D97C7C]" : "bg-[#5C856A]")} style={{ width: `${percent}%` }}></div></div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">{t('templates30PlatformHealthCustomize.usagePercentUsed', { percent: percent.toFixed(1) })}</span>
        {isWarning && <span className="text-[11px] text-[#9B5050] font-medium flex items-center"><AlertCircle className="w-3 h-3 mr-1" /> {t('templates30PlatformHealthCustomize.approachingLimit')}</span>}
      </div>
    </Card>
  );
};

// --- CUSTOMIZE DASHBOARD PAGE ---
const PlatformCustomizeDashboard = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isSaving, setIsSaving] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [draggedId, setDraggedId] = useState(null);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);

  const defaultWidgets = [
    { id: 'global-status', title: t('templates30PlatformHealthCustomize.widgetGlobalStatusTitle'), desc: t('templates30PlatformHealthCustomize.widgetGlobalStatusDesc'), visible: true },
    { id: 'key-metrics', title: t('templates30PlatformHealthCustomize.widgetKeyMetricsTitle'), desc: t('templates30PlatformHealthCustomize.widgetKeyMetricsDesc'), visible: true },
    { id: 'services-health', title: t('templates30PlatformHealthCustomize.widgetServicesHealthTitle'), desc: t('templates30PlatformHealthCustomize.widgetServicesHealthDesc'), visible: true },
    { id: 'active-alerts', title: t('templates30PlatformHealthCustomize.widgetActiveAlertsTitle'), desc: t('templates30PlatformHealthCustomize.widgetActiveAlertsDesc'), visible: true },
    { id: 'live-activity', title: t('templates30PlatformHealthCustomize.widgetLiveActivityTitle'), desc: t('templates30PlatformHealthCustomize.widgetLiveActivityDesc'), visible: true }
  ];

  const [widgets, setWidgets] = useState(defaultWidgets);

  const handleToggle = (id) => {
    setWidgets(widgets.map(w => w.id === id ? { ...w, visible: !w.visible } : w));
  };

  const handleDragStart = (e, id) => {
    e.dataTransfer.setData('text/plain', id);
    setDraggedId(id);
    e.currentTarget.style.opacity = '0.4';
  };

  const handleDragEnd = (e) => {
    e.currentTarget.style.opacity = '1';
    setDraggedId(null);
    const elements = document.querySelectorAll('.drop-zone');
    elements.forEach(el => el.classList.remove('drag-over'));
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('drag-over');
  };

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('drag-over');
  };

  const handleDrop = (e, targetId) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    const sourceId = e.dataTransfer.getData('text/plain');
    if (sourceId === targetId) return;

    const newWidgets = [...widgets];
    const sourceIndex = newWidgets.findIndex(w => w.id === sourceId);
    const targetIndex = newWidgets.findIndex(w => w.id === targetId);
    const [movedWidget] = newWidgets.splice(sourceIndex, 1);
    newWidgets.splice(targetIndex, 0, movedWidget);

    setWidgets(newWidgets);
  };

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise(r => setTimeout(r, 600));
    setIsSaving(false);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  const handleReset = async () => {
    setIsSaving(true);
    await new Promise(r => setTimeout(r, 400));
    setWidgets(defaultWidgets);
    setIsSaving(false);
    setIsResetModalOpen(false);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  const visibleWidgets = widgets.filter(w => w.visible);

  return (
    <PageContainer maxWidth="default" className="relative">
      {/* Toast */}
      {showToast && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="bg-[#F3F9F5] border border-[#8FBFA0] text-[#427A5B] px-4 py-2 rounded-full shadow-soft-md flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-4 h-4" /> {t('templates30PlatformHealthCustomize.toastLayoutSaved')}
          </div>
        </div>
      )}

      <PageHeader
        showBack
        onBack={() => setActiveRoute('overview')}
        title={t('templates30PlatformHealthCustomize.customizeDashboardTitle')}
        subtitle={t('templates30PlatformHealthCustomize.customizeDashboardSubtitle')}
        actions={
          <>
            <Button variant="tertiary" onClick={() => setIsResetModalOpen(true)} className="hidden sm:flex" disabled={isSaving}>{t('templates30PlatformHealthCustomize.resetToDefault')}</Button>
            <Button onClick={handleSave} isLoading={isSaving}>{t('templates30PlatformHealthCustomize.saveChanges')}</Button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">

        {/* WIDGET CONTROLS */}
        <div className="lg:col-span-1 space-y-6 lg:order-2">
          <Card className="p-6 shadow-soft-sm">
            <div className="flex items-center gap-2 mb-4 border-b border-[var(--border-color)] pb-3">
              <ListFilter className="w-4 h-4 text-[var(--text-secondary)]" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates30PlatformHealthCustomize.availableWidgets')}</h3>
            </div>
            <div className="space-y-4">
              {widgets.map(widget => (
                <div key={widget.id} className="flex items-start justify-between gap-4 p-3 rounded-lg-custom border border-[#E9E7E2] hover:bg-[#FAF7F2] transition-colors">
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-[var(--text-primary)] leading-none">{widget.title}</span>
                    <span className="text-xs text-[var(--text-secondary)] leading-tight">{widget.desc}</span>
                  </div>
                  <Switch checked={widget.visible} onChange={() => handleToggle(widget.id)} disabled={isSaving} />
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* LAYOUT PREVIEW */}
        <div className="lg:col-span-2 lg:order-1">
          <Section title={t('templates30PlatformHealthCustomize.livePreviewTitle')} description={t('templates30PlatformHealthCustomize.livePreviewDesc')}>
            <div className="bg-[var(--bg-app)] border-2 border-dashed border-[var(--border-color)] rounded-xl p-4 sm:p-6 min-h-[400px] flex flex-col gap-3">
              {visibleWidgets.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-[var(--text-secondary)] opacity-50">
                  <LayoutTemplate className="w-8 h-8 mb-2" />
                  <p className="text-sm">{t('templates30PlatformHealthCustomize.noWidgetsVisible')}</p>
                </div>
              ) : (
                visibleWidgets.map((widget: any, index: number) => (
                  <div
                    key={widget.id}
                    draggable
                    onDragStart={(e: any) => handleDragStart(e, widget.id)}
                    onDragEnd={handleDragEnd}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={(e: any) => handleDrop(e, widget.id)}
                    className={cn(
                      "drop-zone relative flex items-center gap-4 bg-white border border-[#E9E7E2] rounded-lg-custom p-4 shadow-sm cursor-grab active:cursor-grabbing transition-all duration-200",
                      draggedId === widget.id ? "opacity-40 scale-[0.98]" : "hover:border-[var(--primary-gold)]/50 hover:shadow-soft-md"
                    )}
                  >
                    <GripVertical className="w-5 h-5 text-[#E9E7E2] shrink-0" />
                    <div className="flex-1 flex flex-col">
                      <span className="text-sm font-semibold text-[var(--text-primary)]">{widget.title}</span>
                      <span className="text-xs text-[var(--text-secondary)] mt-1 opacity-70">
                        {widget.id === 'global-status' && t('templates30PlatformHealthCustomize.previewFullWidthBanner')}
                        {widget.id === 'key-metrics' && t('templates30PlatformHealthCustomize.previewFourColumnGrid')}
                        {widget.id === 'services-health' && t('templates30PlatformHealthCustomize.previewDataTable')}
                        {widget.id === 'active-alerts' && t('templates30PlatformHealthCustomize.previewHighlightList')}
                        {widget.id === 'live-activity' && t('templates30PlatformHealthCustomize.previewTimelineStream')}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Section>
        </div>

      </div>

      <Modal
        isOpen={isResetModalOpen}
        onClose={() => !isSaving && setIsResetModalOpen(false)}
        title={t('templates30PlatformHealthCustomize.resetDashboardTitle')}
        description={t('templates30PlatformHealthCustomize.resetDashboardDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsResetModalOpen(false)} disabled={isSaving}>{t('templates30PlatformHealthCustomize.cancel')}</Button>
            <Button variant="destructive" onClick={handleReset} isLoading={isSaving}>{t('templates30PlatformHealthCustomize.confirmReset')}</Button>
          </>
        }
      />
    </PageContainer>
  );
};


// --- COMPONENTS PAGE ---
const ComponentsPage = () => {
  const t = useT();
  const [date, setDate] = useState("");
  const [selectVal, setSelectVal] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates30PlatformHealthCustomize.navComponentLibrary')} subtitle={t('templates30PlatformHealthCustomize.componentLibrarySubtitle')} actions={<Button>{t('templates30PlatformHealthCustomize.deploySystem')}</Button>} />
      <Tabs defaultValue="form" tabs={[
        { id: 'form', label: t('templates30PlatformHealthCustomize.tabFormsInputs'), content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title={t('templates30PlatformHealthCustomize.sectionButtons')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)]">
               <div className="flex flex-wrap gap-4 mb-4"><Button variant="primary">{t('templates30PlatformHealthCustomize.btnPrimary')}</Button><Button variant="secondary">{t('templates30PlatformHealthCustomize.btnSecondary')}</Button><Button variant="tertiary">{t('templates30PlatformHealthCustomize.btnGhost')}</Button></div>
               <div className="flex flex-wrap gap-4 items-center"><Button variant="primary" isLoading>{t('templates30PlatformHealthCustomize.btnLoading')}</Button><Button variant="destructive">{t('templates30PlatformHealthCustomize.btnDestructive')}</Button><Button variant="primary" size="icon"><Plus className="w-4 h-4"/></Button></div>
             </Section>
             <Section title={t('templates30PlatformHealthCustomize.sectionInputsSelects')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] space-y-4">
                <Input label={t('templates30PlatformHealthCustomize.labelEmailAddress')} placeholder="admin@kaori.io" helperText={t('templates30PlatformHealthCustomize.helperNeverShareEmail')} />
                <Select label={t('templates30PlatformHealthCustomize.labelEnvironment')} placeholder={t('templates30PlatformHealthCustomize.placeholderSelectEnvironment')} options={[{label: t('templates30PlatformHealthCustomize.optionProduction'), value: 'prod'}]} value={selectVal} onChange={setSelectVal} />
                <DatePicker label={t('templates30PlatformHealthCustomize.labelBillingCycleStart')} date={date} setDate={setDate} />
             </Section>
           </div>
        )},
        { id: 'data', label: t('templates30PlatformHealthCustomize.tabDataDisplay'), content: (<Alert variant="info" title={t('templates30PlatformHealthCustomize.alertDataComponentsTitle')}>{t('templates30PlatformHealthCustomize.alertDataComponentsBody')}</Alert>)},
        { id: 'feedback', label: t('templates30PlatformHealthCustomize.tabFeedbackOverlays'), content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title={t('templates30PlatformHealthCustomize.sectionModalsDrawers')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] flex flex-col gap-4 items-start">
               <Button variant="secondary" onClick={() => setIsModalOpen(true)}>{t('templates30PlatformHealthCustomize.openModal')}</Button>
               <Button variant="secondary" onClick={() => setIsDrawerOpen(true)}>{t('templates30PlatformHealthCustomize.openDrawer')}</Button>
               <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={t('templates30PlatformHealthCustomize.modalDeleteWorkspaceTitle')} footer={<><Button variant="outline" onClick={()=>setIsModalOpen(false)}>{t('templates30PlatformHealthCustomize.cancel')}</Button><Button variant="destructive">{t('templates30PlatformHealthCustomize.confirm')}</Button></>}><Input label={t('templates30PlatformHealthCustomize.labelTypeToConfirm')} /></Modal>
               <Drawer isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} title={t('templates30PlatformHealthCustomize.drawerEditProfileTitle')} footer={<Button className="w-full">{t('templates30PlatformHealthCustomize.saveChanges')}</Button>}><Input label={t('templates30PlatformHealthCustomize.labelFullName')} placeholder="Admin User" /></Drawer>
             </Section>
           </div>
        )}
      ]} />
    </PageContainer>
  );
};

// --- ENHANCED HEALTH DASHBOARD ---
const PlatformOverview = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isAutoRefresh, setIsAutoRefresh] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date().toLocaleTimeString());

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await new Promise(r => setTimeout(r, 600));
    setLastUpdated(new Date().toLocaleTimeString());
    setIsRefreshing(false);
  };

  useEffect(() => {
    let interval;
    if (isAutoRefresh) { interval = setInterval(() => { setLastUpdated(new Date().toLocaleTimeString()); }, 5000); }
    return () => clearInterval(interval);
  }, [isAutoRefresh]);

  const SERVICES_DATA = [
    ["API Gateway", <Badge key="1" variant="operational">{t('templates30PlatformHealthCustomize.statusOperational')}</Badge>, "42ms", "0.01%", "32 days ago"],
    ["Auth Service", <Badge key="2" variant="operational">{t('templates30PlatformHealthCustomize.statusOperational')}</Badge>, "18ms", "0.00%", "45 days ago"],
    ["Insights Engine", <Badge key="4" variant="warning">{t('templates30PlatformHealthCustomize.statusDegraded')}</Badge>, "850ms", "1.20%", t('templates30PlatformHealthCustomize.incidentCurrently')],
  ];

  const ACTIVITY_STREAM = [
    { id: 1, type: 'alert', message: t('templates30PlatformHealthCustomize.activityHighLatency'), time: '2 mins ago', icon: ShieldAlert, color: 'text-[var(--state-error)]', bg: 'bg-[var(--state-error)]/10', border: 'border-[var(--state-error)]/20' },
    { id: 2, type: 'deploy', message: t('templates30PlatformHealthCustomize.activityDeploySuccess', { id: 1402 }), time: '1 hour ago', icon: Server, color: 'text-[var(--state-success)]', bg: 'bg-[var(--state-success)]/10', border: 'border-[var(--state-success)]/20' },
  ];

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        title={t('templates30PlatformHealthCustomize.navPlatformHealth')} subtitle={t('templates30PlatformHealthCustomize.platformHealthSubtitle')}
        actions={
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 mr-2">
              <span className="text-xs text-[var(--text-secondary)] font-medium">{t('templates30PlatformHealthCustomize.autoRefresh')}</span>
              <Switch checked={isAutoRefresh} onChange={setIsAutoRefresh} />
            </div>
            <Button variant="outline" onClick={handleRefresh} isLoading={isRefreshing} className="hidden sm:flex h-9 px-3"><RefreshCw className="w-4 h-4 mr-2" /> {t('templates30PlatformHealthCustomize.refresh')}</Button>
            <Button variant="tertiary" size="sm" className="h-9 px-3" onClick={() => setActiveRoute('health-customize')}>
              <LayoutTemplate className="w-4 h-4 mr-2" /> {t('templates30PlatformHealthCustomize.customize')}
            </Button>
          </div>
        }
      />
      <Section>
        <Card className="p-6 overflow-hidden relative border-[#8FBFA0]/40 bg-[#F3F9F5]">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[#5C856A]/5 to-transparent pointer-events-none" />
           <div className="flex items-center gap-4 relative z-10">
             <div className="w-12 h-12 rounded-full bg-white flex items-center justify-center shadow-sm border border-[#8FBFA0]/30 shrink-0"><CheckCircle2 className="w-6 h-6 text-[#5C856A]" /></div>
             <div>
               <h2 className="text-lg font-semibold text-[#2F2F2F]">{t('templates30PlatformHealthCustomize.allSystemsOperational')}</h2>
               <p className="text-sm text-[#5C856A] mt-0.5 flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[#5C856A] animate-pulse" /> {t('templates30PlatformHealthCustomize.updatedAt', { time: lastUpdated })}</p>
             </div>
           </div>
        </Card>
      </Section>
      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates30PlatformHealthCustomize.metricApiLatency')} value="42ms" trend="-2ms" isUp={false} inverseGood={true} />
          <MetricCard title={t('templates30PlatformHealthCustomize.metricErrorRate')} value="0.01%" trend="-0.01%" isUp={false} inverseGood={true} />
          <MetricCard title={t('templates30PlatformHealthCustomize.metricThroughput')} value="12.4k" trend="+5%" isUp={true} />
          <MetricCard title={t('templates30PlatformHealthCustomize.metricActiveUsers')} value="4,892" trend="+12" isUp={true} />
        </div>
      </Section>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
        <div className="lg:col-span-2 space-y-4">
          <Section title={t('templates30PlatformHealthCustomize.widgetServicesHealthTitle')}><DataTable columns={[t('templates30PlatformHealthCustomize.colService'), t('templates30PlatformHealthCustomize.colStatus'), t('templates30PlatformHealthCustomize.colLatency'), t('templates30PlatformHealthCustomize.metricErrorRate'), t('templates30PlatformHealthCustomize.colLastIncident')]} data={SERVICES_DATA} loading={false} pagination={false}/></Section>
        </div>
        <div className="space-y-6 sm:space-y-8">
           <Section title={t('templates30PlatformHealthCustomize.widgetActiveAlertsTitle')}>
               <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm space-y-3">
                  <Alert variant="warning" title={t('templates30PlatformHealthCustomize.alertDegradedPerformanceTitle')}>{t('templates30PlatformHealthCustomize.alertDegradedPerformanceBody')}</Alert>
               </div>
           </Section>
           <Section title={t('templates30PlatformHealthCustomize.widgetLiveActivityTitle')}>
             <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm space-y-4">
                  {ACTIVITY_STREAM.map((item, idx) => (
                    <div key={item.id} className="flex gap-3 relative">
                      {idx !== ACTIVITY_STREAM.length - 1 && <div className="absolute left-[15px] top-8 bottom-[-16px] w-[1px] bg-[var(--border-color)]" />}
                      <div className={cn("w-8 h-8 rounded-full flex items-center justify-center shrink-0 border z-10", item.bg, item.border)}><item.icon className={cn("w-4 h-4", item.color)} /></div>
                      <div className="pt-1.5 pb-2"><p className="text-sm font-medium text-[var(--text-primary)] leading-none mb-1">{item.message}</p><p className="text-xs text-[var(--text-secondary)]">{item.time}</p></div>
                    </div>
                  ))}
             </div>
           </Section>
        </div>
      </div>
    </PageContainer>
  );
};

// --- WORKSPACES PAGE ---
const MOCK_WORKSPACES = [
  { id: 'ws_prod_01', name: 'Production AI', ownerName: 'Admin User', ownerEmail: 'admin@kaori.io', plan: 'Enterprise', members: 14, usage: '2.4M reqs', status: 'Active', created: 'Oct 12, 2026' },
  { id: 'ws_stage_02', name: 'Staging Environment', ownerName: 'Sarah Jenkins', ownerEmail: 'sarah@kaori.io', plan: 'Pro', members: 8, usage: '850K reqs', status: 'Active', created: 'Oct 14, 2026' }
];

const RowActionsDropdown = ({  workspaceId, onViewDetails, onEdit  }: any) => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<any>(null);
  useEffect(() => { const handleClickOutside = (e) => { if (ref.current && !ref.current.contains(e.target)) setIsOpen(false); }; document.addEventListener('mousedown', handleClickOutside); return () => document.removeEventListener('mousedown', handleClickOutside); }, []);
  return (
    <div className="relative flex justify-end" ref={ref}>
      <button onClick={() => setIsOpen(!isOpen)} className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors"><MoreVertical className="w-4 h-4"/></button>
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 animate-in fade-in zoom-in-95 duration-100">
          <button onClick={() => { onViewDetails(); setIsOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2"><Eye className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates30PlatformHealthCustomize.actionViewDetails')}</button>
          <button onClick={() => { onEdit(); setIsOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2"><Edit2 className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates30PlatformHealthCustomize.actionEditWorkspace')}</button>
        </div>
      )}
    </div>
  );
};

const WorkspacesPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [isLoading, setIsLoading] = useState(false);
  const mappedData = MOCK_WORKSPACES.map(ws => [
    <div key="name"><div className="font-medium text-[var(--text-primary)]">{ws.name}</div></div>,
    <div key="owner"><div className="text-sm text-[var(--text-primary)]">{ws.ownerName}</div></div>,
    <Badge key="plan" variant="current">{ws.plan}</Badge>,
    <div key="members" className="flex items-center gap-1.5 text-[var(--text-secondary)]"><Users className="w-3.5 h-3.5"/> {ws.members}</div>,
    <span key="usage" className="tabular-nums text-[var(--text-secondary)]">{ws.usage}</span>,
    <Badge key="status" variant="operational">{ws.status}</Badge>,
    <span key="created" className="text-[var(--text-secondary)] whitespace-nowrap">{ws.created}</span>,
    <RowActionsDropdown key="actions" workspaceId={ws.id} onViewDetails={() => setActiveRoute('workspace-details')} onEdit={() => setActiveRoute('workspace-edit')} />
  ]);
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates30PlatformHealthCustomize.navWorkspaces')} actions={<Button onClick={() => setActiveRoute('workspace-new')}><Plus className="w-4 h-4 mr-2"/> {t('templates30PlatformHealthCustomize.createWorkspace')}</Button>} />
      <Section><DataTable columns={[t('templates30PlatformHealthCustomize.colWorkspace'), t('templates30PlatformHealthCustomize.colOwner'), t('templates30PlatformHealthCustomize.colPlan'), t('templates30PlatformHealthCustomize.colMembers'), t('templates30PlatformHealthCustomize.colUsage'), t('templates30PlatformHealthCustomize.colStatus'), t('templates30PlatformHealthCustomize.colCreated'), ""]} data={mappedData} loading={isLoading} /></Section>
    </PageContainer>
  );
};

// --- WORKSPACE NEW PAGE ---
const Stepper = ({  currentStep  }: any) => {
  const t = useT();
  const steps = [{ num: 1, label: t('templates30PlatformHealthCustomize.stepWorkspaceInfo') }, { num: 2, label: t('templates30PlatformHealthCustomize.stepPlanSelection') }, { num: 3, label: t('templates30PlatformHealthCustomize.stepReviewCreate') }];
  return (
    <div className="flex items-center w-full mb-10 max-w-md mx-auto">
      {steps.map((step, idx) => {
        const isCompleted = currentStep > step.num;
        const isActive = currentStep === step.num;
        return (
          <React.Fragment key={step.num}>
            <div className="flex flex-col items-center relative z-10">
              <div className={cn("w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors duration-300 shadow-sm border", isCompleted ? "bg-[var(--primary-gold)] text-white border-transparent" : isActive ? "bg-[var(--bg-card)] border-[var(--primary-gold)] text-[var(--primary-gold-dark)] shadow-soft-md" : "bg-[var(--bg-app)] border-[var(--border-color)] text-[var(--text-secondary)]")}>
                {isCompleted ? <Check className="w-4 h-4" /> : step.num}
              </div>
            </div>
            {idx < steps.length - 1 && <div className="flex-1 h-px bg-[var(--border-color)] mx-4 relative"><div className="absolute left-0 top-0 h-full bg-[var(--primary-gold)] transition-all duration-500 ease-in-out" style={{ width: currentStep > step.num ? '100%' : '0%' }}/></div>}
          </React.Fragment>
        );
      })}
    </div>
  );
};

const WorkspaceNewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [step, setStep] = useState(1);
  const handleCreate = async () => { setActiveRoute('workspace-details'); };
  return (
    <PageContainer maxWidth="narrow" className="pt-8">
      <div className="mb-10 text-center animate-in fade-in slide-in-from-bottom-4 duration-500"><h1 className="text-3xl font-serif font-semibold text-[var(--text-primary)] mb-2">{t('templates30PlatformHealthCustomize.createWorkspaceHeading')}</h1></div>
      <Stepper currentStep={step} />
      <Card className="p-6 sm:p-8 mt-12 shadow-soft-md animate-in fade-in zoom-in-[0.98] duration-300">
        {step === 1 && <div className="space-y-6"><Input label={t('templates30PlatformHealthCustomize.labelWorkspaceName')} /><Select label={t('templates30PlatformHealthCustomize.labelDataRegion')} options={[{label: 'US East', value: 'us'}]} value="us" onChange={()=>{}}/></div>}
        {step === 2 && <div className="space-y-6"><Select label={t('templates30PlatformHealthCustomize.labelPlanTier')} options={[{label: 'Pro', value: 'pro'}]} value="pro" onChange={()=>{}}/></div>}
        {step === 3 && <Alert variant="info" title={t('templates30PlatformHealthCustomize.alertReadyToProvisionTitle')}>{t('templates30PlatformHealthCustomize.alertReadyToProvisionBody')}</Alert>}
        <div className="mt-8 pt-6 border-t border-[var(--border-color)] flex items-center justify-between">
          <Button variant="tertiary" onClick={() => step === 1 ? setActiveRoute('workspaces') : setStep(s => s - 1)}>{t('templates30PlatformHealthCustomize.back')}</Button>
          {step < 3 ? <Button onClick={() => setStep(s => s + 1)}>{t('templates30PlatformHealthCustomize.continueBtn')}</Button> : <Button onClick={handleCreate}>{t('templates30PlatformHealthCustomize.createWorkspace')}</Button>}
        </div>
      </Card>
    </PageContainer>
  );
};

const WorkspaceOverviewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('workspaces')} title="Production AI" subtitle="Enterprise Plan" actions={<Button variant="outline" onClick={() => setActiveRoute('workspace-edit')}>{t('templates30PlatformHealthCustomize.editDetails')}</Button>} />
      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates30PlatformHealthCustomize.metricApiRequestsToday')} value="124.5K" trend="+5.2%" isUp={true} />
          <MetricCard title={t('templates30PlatformHealthCustomize.metricActiveUsers')} value="14" trend="0%" />
        </div>
      </Section>
    </PageContainer>
  );
};

const WorkspaceSettingsPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="narrow">
      <PageHeader showBack onBack={() => setActiveRoute('workspace-details')} title={t('templates30PlatformHealthCustomize.workspaceSettingsTitle')} actions={<Button>{t('templates30PlatformHealthCustomize.saveChanges')}</Button>} />
      <Section><Card className="p-6"><Input label={t('templates30PlatformHealthCustomize.labelWorkspaceName')} value="Production AI" /></Card></Section>
    </PageContainer>
  );
};

const WorkspaceMembersPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('workspace-details')} title={t('templates30PlatformHealthCustomize.membersTitle')} actions={<Button><UserPlus className="w-4 h-4 mr-2"/> {t('templates30PlatformHealthCustomize.inviteMember')}</Button>} />
      <Section><DataTable columns={[t('templates30PlatformHealthCustomize.colName'), t('templates30PlatformHealthCustomize.colRole'), t('templates30PlatformHealthCustomize.colStatus')]} data={[["Admin User", <Badge key="1">{t('templates30PlatformHealthCustomize.roleOwner')}</Badge>, t('templates30PlatformHealthCustomize.statusActive')]]} loading={false} /></Section>
    </PageContainer>
  );
};

const WorkspaceBillingPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('workspace-details')} title={t('templates30PlatformHealthCustomize.billingUsageTitle')} />
      <Section title={t('templates30PlatformHealthCustomize.currentUsageTitle')}><div className="grid grid-cols-1 md:grid-cols-2 gap-6"><EnterpriseUsageCard title={t('templates30PlatformHealthCustomize.apiRequestsTitle')} icon={Zap} current={42150} max={50000} unit="reqs" /></div></Section>
    </PageContainer>
  );
};

const WorkspaceAuditLogPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('workspace-details')} title={t('templates30PlatformHealthCustomize.auditLogTitle')} />
      <Section><DataTable columns={[t('templates30PlatformHealthCustomize.colTimestamp'), t('templates30PlatformHealthCustomize.colActor'), t('templates30PlatformHealthCustomize.colAction')]} data={[["Oct 25", "Admin User", t('templates30PlatformHealthCustomize.actionCreatedApiKey')]]} loading={false} /></Section>
    </PageContainer>
  );
};

const ApiKeysPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates30PlatformHealthCustomize.navApiKeys')} actions={<Button onClick={() => setActiveRoute('keys-new')}><Plus className="w-4 h-4 mr-2" /> {t('templates30PlatformHealthCustomize.createKey')}</Button>} />
      <Section><DataTable columns={[t('templates30PlatformHealthCustomize.colKeyName'), t('templates30PlatformHealthCustomize.colSecretKey'), t('templates30PlatformHealthCustomize.colStatus')]} data={[["Production Backend", "sk_live_••••abcd", t('templates30PlatformHealthCustomize.statusActive')]]} loading={false} onRowClick={() => setActiveRoute('key-details')} /></Section>
    </PageContainer>
  );
};

const ApiKeyNewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="narrow" className="pt-8">
      <PageHeader showBack onBack={() => setActiveRoute('keys')} title={t('templates30PlatformHealthCustomize.createApiKeyTitle')} />
      <Card className="p-6"><Input label={t('templates30PlatformHealthCustomize.labelKeyName')} /><Button className="mt-4" onClick={() => setActiveRoute('keys')}>{t('templates30PlatformHealthCustomize.create')}</Button></Card>
    </PageContainer>
  );
};

const ApiKeyDetailPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('keys')} title="Production Backend" subtitle="sk_live_••••abcd" actions={<Button variant="destructive-soft">{t('templates30PlatformHealthCustomize.revoke')}</Button>} />
      <Section><MetricCard title={t('templates30PlatformHealthCustomize.metricRequests24h')} value="18,492" trend="+1.2%" isUp={true} /></Section>
    </PageContainer>
  );
};

const PlatformAdminsPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates30PlatformHealthCustomize.platformAdminsTitle')} actions={<Button onClick={() => setActiveRoute('admin-invite')}><UserPlus className="w-4 h-4 mr-2"/> {t('templates30PlatformHealthCustomize.inviteAdmin')}</Button>} />
      <Section><DataTable columns={[t('templates30PlatformHealthCustomize.colNameEmail'), t('templates30PlatformHealthCustomize.colRole'), t('templates30PlatformHealthCustomize.colStatus')]} data={[["Admin User", t('templates30PlatformHealthCustomize.roleSuperAdmin'), t('templates30PlatformHealthCustomize.statusActive')]]} loading={false} onRowClick={() => setActiveRoute('admin-details')} /></Section>
    </PageContainer>
  );
};

const PlatformAdminInvitePage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="narrow" className="pt-8">
      <PageHeader showBack onBack={() => setActiveRoute('admin')} title={t('templates30PlatformHealthCustomize.invitePlatformAdminTitle')} />
      <Card className="p-6"><Input label={t('templates30PlatformHealthCustomize.labelEmailAddress')} /><Button className="mt-4" onClick={() => setActiveRoute('admin')}>{t('templates30PlatformHealthCustomize.sendInvite')}</Button></Card>
    </PageContainer>
  );
};

const PlatformAdminDetailPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('admin')} title="Admin User" subtitle="admin@kaori.io" actions={<Button variant="outline" onClick={() => setActiveRoute('admin-reset-password')}>{t('templates30PlatformHealthCustomize.resetPassword')}</Button>} />
      <Section><MetricCard title={t('templates30PlatformHealthCustomize.metricLastActive')} value={t('templates30PlatformHealthCustomize.valueNow')} trend="" /></Section>
    </PageContainer>
  );
};

const PlatformAdminResetPasswordPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="narrow" className="pt-8">
      <PageHeader showBack onBack={() => setActiveRoute('admin-details')} title={t('templates30PlatformHealthCustomize.resetAdminPasswordTitle')} />
      <Card className="p-6"><Alert variant="warning" title={t('templates30PlatformHealthCustomize.warningTitle')}>{t('templates30PlatformHealthCustomize.warningInvalidateSessions')}</Alert><Button className="mt-4" onClick={() => setActiveRoute('admin-details')}>{t('templates30PlatformHealthCustomize.confirmReset')}</Button></Card>
    </PageContainer>
  );
};

const PlatformBillingOverviewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates30PlatformHealthCustomize.billingOverviewTitle')} actions={<Button variant="outline" onClick={() => setActiveRoute('billing-export')}><Download className="w-4 h-4 mr-2"/> {t('templates30PlatformHealthCustomize.exportData')}</Button>} />
      <Section><div className="grid grid-cols-2 gap-4"><MetricCard title={t('templates30PlatformHealthCustomize.metricMRR')} value="$124,500" trend="+8.4%" isUp={true} /><MetricCard title={t('templates30PlatformHealthCustomize.metricActiveSubs')} value="1,892" trend="+42" isUp={true} /></div></Section>
    </PageContainer>
  );
};

const PlatformEnterpriseBillingDetailPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('billing')} title="Production AI Billing" />
      <Section><MetricCard title={t('templates30PlatformHealthCustomize.metricMonthlyRevenue')} value="$2,400" trend="0%" /></Section>
    </PageContainer>
  );
};

const PlatformQuotaManagementPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates30PlatformHealthCustomize.quotaManagementTitle')} />
      <Section><DataTable columns={[t('templates30PlatformHealthCustomize.colWorkspace'), t('templates30PlatformHealthCustomize.colApiUsage'), t('templates30PlatformHealthCustomize.colStatus')]} data={[["Production AI", "2.4M / 10M", t('templates30PlatformHealthCustomize.statusNormal')]]} loading={false} /></Section>
    </PageContainer>
  );
};

const PlatformBillingExportPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader showBack onBack={() => setActiveRoute('billing')} title={t('templates30PlatformHealthCustomize.exportBillingDataTitle')} />
      <Section><Card className="p-6"><Button onClick={() => {}}>{t('templates30PlatformHealthCustomize.generateExport')}</Button></Card></Section>
    </PageContainer>
  );
};

const SessionsPage = () => {
  const t = useT();
  return (
    <PageContainer maxWidth="narrow">
      <PageHeader title={t('templates30PlatformHealthCustomize.activeSessionsTitle')} subtitle={t('templates30PlatformHealthCustomize.activeSessionsSubtitle')} actions={<Button variant="outline">{t('templates30PlatformHealthCustomize.signOutAll')}</Button>} />
      <Section title={t('templates30PlatformHealthCustomize.navSecuritySessions')}>
        <Card className="p-8 text-center flex flex-col items-center">
          <Shield className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
          <h3 className="text-sm font-medium text-[var(--text-primary)]">{t('templates30PlatformHealthCustomize.navSecuritySessions')}</h3>
        </Card>
      </Section>
    </PageContainer>
  );
};

export default function KaoriPlatformShell() {
  const t = useT();
  const [activeRoute, setActiveRoute] = useState('health-customize');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <>
      <GlobalStyles />
      <div className="flex h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
        <div className="hidden md:block shrink-0 z-30">
          <GlobalSidebar isMobile={false} activeRoute={activeRoute} setActiveRoute={setActiveRoute} isCollapsed={isCollapsed} setIsCollapsed={setIsCollapsed} />
        </div>
        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative">
          <GlobalHeader activeRoute={activeRoute} setActiveRoute={setActiveRoute} setIsMobileMenuOpen={setIsMobileMenuOpen} />
          <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-[var(--bg-app)]">
            {activeRoute === 'components' ? <ComponentsPage /> :
             activeRoute === 'workspaces' ? <WorkspacesPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-details' ? <WorkspaceOverviewPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-members' ? <WorkspaceMembersPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-billing' ? <WorkspaceBillingPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'audit-logs' ? <WorkspaceAuditLogPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-new' ? <WorkspaceNewPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-edit' ? <WorkspaceSettingsPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'keys' ? <ApiKeysPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'keys-new' ? <ApiKeyNewPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'key-details' ? <ApiKeyDetailPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'admin' ? <PlatformAdminsPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'admin-invite' ? <PlatformAdminInvitePage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'admin-details' ? <PlatformAdminDetailPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'admin-reset-password' ? <PlatformAdminResetPasswordPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'billing' ? <PlatformBillingOverviewPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'enterprise-billing-details' ? <PlatformEnterpriseBillingDetailPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'quota' ? <PlatformQuotaManagementPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'billing-export' ? <PlatformBillingExportPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'health-customize' ? <PlatformCustomizeDashboard setActiveRoute={setActiveRoute} /> :
             activeRoute === 'overview' ? <PlatformOverview setActiveRoute={setActiveRoute} /> :
             activeRoute === 'sessions' ? <SessionsPage /> : (
              <PageContainer maxWidth="narrow">
                <PageHeader title={t('templates30PlatformHealthCustomize.comingSoonTitle')} subtitle={t('templates30PlatformHealthCustomize.comingSoonSubtitle')} />
              </PageContainer>
            )}
          </main>
        </div>
      </div>
    </>
  );
}

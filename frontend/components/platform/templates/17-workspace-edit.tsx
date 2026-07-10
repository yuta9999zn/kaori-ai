// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 17Workspace Id Edit.jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState, useEffect, useRef } from 'react';
import { useT } from '@/lib/i18n/provider';
import {
  LayoutDashboard, 
  Briefcase, 
  Key, 
  CreditCard, 
  Shield, 
  Activity, 
  Search, 
  Bell, 
  Menu, 
  X, 
  ChevronRight,
  ChevronLeft,
  MoreVertical,
  ArrowUpRight,
  ArrowDownRight,
  Settings,
  Laptop,
  Smartphone,
  MapPin,
  Globe,
  Clock,
  LogOut,
  AlertCircle,
  Loader2,
  Plus,
  ChevronsUpDown,
  User,
  Check,
  Calendar as CalendarIcon,
  ChevronDown,
  Info,
  CheckCircle2,
  Component,
  ShieldAlert,
  RefreshCw,
  PanelLeftOpen,
  PanelLeftClose,
  Eye,
  Edit2,
  Users,
  Ban,
  Trash2,
  ArrowLeft,
  Server,
  Zap,
  UserPlus,
  Mail,
  Send,
  Download,
  Receipt,
  HardDrive,
  FileText,
  FileJson,
  Save,
  AlertTriangle
} from 'lucide-react';

// --- UTILS ---
const cn = (...classes) => classes.filter(Boolean).join(' ');

// --- DESIGN TOKENS & STYLES ---
const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400&display=swap');

    :root {
      /* Colors */
      --primary-gold: #D4B88A;
      --primary-gold-dark: #BFA88C;
      
      --bg-app: #FAF7F2;
      --bg-sidebar: #F5F1EA;
      --bg-card: #FFFFFF;
      
      --border-color: #E9E7E2;
      
      --text-primary: #2F2F2F;
      --text-secondary: #8C8173;
      
      /* State Colors */
      --state-success: #8FBFA0;
      --state-warning: #E6C07B;
      --state-error: #D97C7C;
      --state-info: #A5B4CB;

      /* Shadows */
      --shadow-soft-sm: 0 2px 8px -2px rgba(47, 47, 47, 0.04), 0 1px 3px -1px rgba(47, 47, 47, 0.02);
      --shadow-soft-md: 0 6px 16px -4px rgba(47, 47, 47, 0.06), 0 4px 8px -2px rgba(47, 47, 47, 0.03);
      --shadow-soft-lg: 0 12px 24px -4px rgba(47, 47, 47, 0.08), 0 8px 12px -4px rgba(47, 47, 47, 0.04);
      
      /* Radii */
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
    }

    body {
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-app);
      color: var(--text-primary);
      margin: 0;
      -webkit-font-smoothing: antialiased;
    }

    .font-serif {
      font-family: 'Playfair Display', serif;
    }

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

    @keyframes slideUpFade {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .animate-slide-up-fade {
      animation: slideUpFade 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    @keyframes slideInRight {
      from { transform: translateX(100%); }
      to { transform: translateX(0); }
    }
    .animate-slide-in-right {
      animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    @keyframes fadeInSlide {
      from { opacity: 0; transform: translateX(10px); }
      to { opacity: 1; transform: translateX(0); }
    }
    .animate-step {
      animation: fadeInSlide 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    
    /* Sidebar Transitions */
    .sidebar-transition {
      transition: width 0.3s cubic-bezier(0.2, 0, 0, 1), padding 0.3s ease, opacity 0.2s ease;
    }
  `}</style>
);

// ==========================================
// 1. COMPONENT FOUNDATION (UI LIBRARY)
// ==========================================

// --- BADGE ---
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
  return (
    <span className={cn(`inline-flex items-center px-2 py-0.5 rounded-sm-custom text-[11px] font-medium border`, variants[variant], className)}>
      {children}
    </span>
  );
};

// --- BUTTON ---
const Button = React.forwardRef<any, any>(({ className, variant = "primary", size = "md", isLoading, disabled, children, ...props }, ref) => {
  const variants = {
    primary: "bg-[var(--primary-gold)] text-[var(--text-primary)] hover:bg-[var(--primary-gold-dark)] active:scale-[0.98] shadow-soft-sm border border-transparent",
    secondary: "border border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-primary)] hover:bg-[var(--bg-app)] active:scale-[0.98] shadow-sm",
    tertiary: "bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-color)]/30 active:scale-[0.98]",
    destructive: "bg-[var(--state-error)] text-white hover:bg-[#C26B6B] active:scale-[0.98] shadow-soft-sm border border-transparent",
    "destructive-soft": "border border-[var(--border-color)] bg-transparent text-[var(--text-primary)] hover:border-[var(--state-error)]/40 hover:bg-[var(--state-error)]/10 hover:text-[#9B5050] active:scale-[0.98]",
  };
  const sizes = {
    sm: "h-8 px-3 text-xs rounded-sm-custom",
    md: "h-10 px-4 py-2 text-sm rounded-md-custom",
    lg: "h-12 px-6 py-3 text-base rounded-md-custom",
    icon: "h-10 w-10 rounded-md-custom",
  };

  return (
    <button
      ref={ref}
      disabled={isLoading || disabled}
      className={cn(
        "inline-flex items-center justify-center font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50 disabled:opacity-50 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
});
Button.displayName = "Button";

// --- INPUT & LABEL ---
const Label = React.forwardRef<any, any>(({ className, ...props }, ref) => (
  <label ref={ref} className={cn("text-sm font-medium leading-none text-[var(--text-primary)] peer-disabled:cursor-not-allowed peer-disabled:opacity-70", className)} {...props} />
));
Label.displayName = "Label";

const Input = React.forwardRef<any, any>(({ className, label, error, helperText, ...props }, ref) => {
  return (
    <div className="space-y-2 w-full">
      {label && <Label>{label}</Label>}
      <input
        ref={ref}
        className={cn(
          "flex h-10 w-full rounded-md-custom border bg-white px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 transition-all duration-200",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/30 focus-visible:border-[var(--primary-gold)]",
          "disabled:cursor-not-allowed disabled:opacity-50 shadow-soft-sm disabled:bg-[var(--bg-app)]",
          error ? "border-[var(--state-error)] focus-visible:ring-[var(--state-error)]/30 focus-visible:border-[var(--state-error)]" : "border-[var(--border-color)]",
          className
        )}
        {...props}
      />
      {error && <p className="text-xs font-medium text-[var(--state-error)]">{error}</p>}
      {helperText && !error && <p className="text-xs text-[var(--text-secondary)]">{helperText}</p>}
    </div>
  );
});
Input.displayName = "Input";

// --- SELECT (Simulated Radix Select) ---
const Select = ({  label, placeholder, options = [], value, onChange, error, disabled  }: any) => {
  const t = useT();
  const effectivePlaceholder = placeholder || t('templates17WorkspaceEdit.selectDefaultPlaceholder');
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<any>(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedOption = options.find(opt => opt.value === value);

  return (
    <div className="space-y-2 w-full relative" ref={dropdownRef}>
      {label && <Label className={disabled ? "opacity-50" : ""}>{label}</Label>}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md-custom border bg-white px-3 py-2 text-sm shadow-soft-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-50 disabled:bg-[var(--bg-app)] disabled:cursor-not-allowed",
          error ? "border-[var(--state-error)]" : "border-[var(--border-color)] hover:border-[var(--primary-gold)]/50",
          !selectedOption ? "text-[var(--text-secondary)]/60" : "text-[var(--text-primary)]"
        )}
      >
        {selectedOption ? selectedOption.label : effectivePlaceholder}
        <ChevronDown className="h-4 w-4 opacity-50" />
      </button>
      {isOpen && !disabled && (
        <div className="absolute top-full left-0 z-50 w-full mt-1 bg-white rounded-md-custom border border-[var(--border-color)] shadow-soft-md animate-in fade-in zoom-in-95 duration-150 overflow-hidden py-1">
          {options.map((opt) => (
            <div
              key={opt.value}
              onClick={() => { onChange(opt.value); setIsOpen(false); }}
              className={cn(
                "relative flex w-full cursor-pointer select-none items-center rounded-sm py-2 pl-8 pr-2 text-sm outline-none hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)] transition-colors",
                value === opt.value ? "bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)] font-medium" : "text-[var(--text-primary)]"
              )}
            >
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

// --- DATEPICKER (Simulated) ---
const DatePicker = ({  label, placeholder, date, setDate  }: any) => {
  const t = useT();
  const effectivePlaceholder = placeholder || t('templates17WorkspaceEdit.datePickerDefaultPlaceholder');
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
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex h-10 w-full items-center justify-start text-left rounded-md-custom border border-[var(--border-color)] bg-white px-3 py-2 text-sm shadow-soft-sm transition-all duration-200 hover:border-[var(--primary-gold)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30",
          !date ? "text-[var(--text-secondary)]/60" : "text-[var(--text-primary)]"
        )}
      >
        <CalendarIcon className="mr-2 h-4 w-4 opacity-50" />
        {date ? date : effectivePlaceholder}
      </button>
      {isOpen && (
        <div className="absolute top-full left-0 z-50 mt-1 p-3 bg-white rounded-md-custom border border-[var(--border-color)] shadow-soft-md animate-in fade-in zoom-in-95 duration-150 w-[280px]">
           <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.calendarMonthLabel')}</span>
              <div className="flex gap-1">
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronLeft className="w-4 h-4 text-[var(--text-secondary)]"/></button>
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronRight className="w-4 h-4 text-[var(--text-secondary)]"/></button>
              </div>
           </div>
           <div className="grid grid-cols-7 gap-1 text-center text-xs text-[var(--text-secondary)] mb-2">
             {[
               ['Su', 'templates17WorkspaceEdit.weekdaySu'],
               ['Mo', 'templates17WorkspaceEdit.weekdayMo'],
               ['Tu', 'templates17WorkspaceEdit.weekdayTu'],
               ['We', 'templates17WorkspaceEdit.weekdayWe'],
               ['Th', 'templates17WorkspaceEdit.weekdayTh'],
               ['Fr', 'templates17WorkspaceEdit.weekdayFr'],
               ['Sa', 'templates17WorkspaceEdit.weekdaySa'],
             ].map(([d, key]) => <div key={d}>{t(key)}</div>)}
           </div>
           <div className="grid grid-cols-7 gap-1 text-sm">
             {Array.from({length: 31}).map((_, i) => (
                <button 
                  key={i} 
                  onClick={() => { setDate(`Oct ${i + 1}, 2026`); setIsOpen(false); }}
                  className={cn("h-8 w-8 rounded flex items-center justify-center hover:bg-[var(--bg-app)] transition-colors", date === `Oct ${i + 1}, 2026` ? "bg-[var(--primary-gold)] text-white hover:bg-[var(--primary-gold-dark)]" : "text-[var(--text-primary)]")}
                >
                  {i + 1}
                </button>
             ))}
           </div>
        </div>
      )}
    </div>
  );
};

// --- CARD SYSTEM ---
const Card = ({  className, ...props  }: any) => (
  <div className={cn("bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm", className)} {...props} />
);

const MetricCard = ({  title, value, trend, isUp, inverseGood = false, className  }: any) => {
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
        <div className="text-xs text-[var(--text-secondary)] mt-1 opacity-75">vs yesterday</div>
      </div>
    </Card>
  );
};

// --- TABLE ---
const Table = ({  className, ...props  }: any) => (
  <div className="w-full overflow-auto">
    <table className={cn("w-full caption-bottom text-sm", className)} {...props} />
  </div>
);
const TableHeader = ({  className, ...props  }: any) => <thead className={cn("bg-[var(--bg-app)] border-b border-[var(--border-color)]", className)} {...props} />;
const TableBody = ({  className, ...props  }: any) => <tbody className={cn("[&_tr:last-child]:border-0 divide-y divide-[var(--border-color)]", className)} {...props} />;
const TableRow = ({  className, ...props  }: any) => <tr className={cn("border-b border-[var(--border-color)] transition-colors hover:bg-[var(--bg-app)]/50", className)} {...props} />;
const TableHead = ({  className, ...props  }: any) => <th className={cn("h-12 px-4 text-left align-middle font-medium text-[var(--text-secondary)] text-xs uppercase tracking-wider", className)} {...props} />;
const TableCell = ({  className, ...props  }: any) => <td className={cn("p-4 align-middle text-[var(--text-primary)]", className)} {...props} />;

const DataTable = ({  columns, data, loading, pagination = true  }: any) => {
  const t = useT();
  return (
    <div className="rounded-lg-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm overflow-hidden w-full">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col, i) => <TableHead key={i}>{col}</TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
             Array.from({length: 3}).map((_, i) => (
                <TableRow key={i}>
                  {columns.map((_, j) => (
                     <TableCell key={j}><div className="h-4 bg-[var(--bg-app)] rounded animate-pulse w-3/4"></div></TableCell>
                  ))}
                </TableRow>
             ))
          ) : data.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-32 text-center">
                <div className="flex flex-col items-center justify-center space-y-1">
                  <div className="w-10 h-10 rounded-full bg-[var(--bg-app)] flex items-center justify-center mb-2">
                    <Search className="w-5 h-5 text-[var(--text-secondary)]" />
                  </div>
                  <span className="text-sm font-medium text-[var(--text-primary)]">{t('templates17WorkspaceEdit.noResultsFound')}</span>
                  <span className="text-xs text-[var(--text-secondary)]">{t('templates17WorkspaceEdit.tryAdjustingFilters')}</span>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, i) => (
              <TableRow key={i}>
                {row.map((cell, j) => <TableCell key={j}>{cell}</TableCell>)}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      {pagination && data.length > 0 && (
        <div className="border-t border-[var(--border-color)] px-4 py-3 flex items-center justify-between bg-[#FCFBF9]">
          <span className="text-xs text-[var(--text-secondary)]">{t('templates17WorkspaceEdit.showingResults', { count: data.length })}</span>
          <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled>{t('templates17WorkspaceEdit.previous')}</Button>
              <Button variant="outline" size="sm">{t('templates17WorkspaceEdit.next')}</Button>
          </div>
        </div>
      )}
    </div>
  );
};

// --- MODAL ---
const Modal = ({  isOpen, onClose, title, description, children, footer  }: any) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-0">
      <div className="absolute inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className="relative bg-[var(--bg-card)] rounded-lg-custom shadow-soft-lg border border-[var(--border-color)] w-full max-w-lg overflow-hidden animate-slide-up-fade">
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

// --- DRAWER ---
const Drawer = ({  isOpen, onClose, title, children, footer, widthClass = "max-w-md"  }: any) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className={cn("relative bg-[var(--bg-card)] w-full h-full shadow-soft-lg border-l border-[var(--border-color)] flex flex-col animate-slide-in-right", widthClass)}>
        <div className="px-6 py-5 border-b border-[var(--border-color)] flex justify-between items-center">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
          <button onClick={onClose} className="p-2 -mr-2 rounded-md hover:bg-[var(--bg-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
        {footer && <div className="p-6 border-t border-[var(--border-color)] bg-[#FCFBF9]">{footer}</div>}
      </div>
    </div>
  );
};

// --- ALERT & TOAST ---
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

// --- TABS ---
const Tabs = ({  defaultValue, tabs, className  }: any) => {
  const [activeTab, setActiveTab] = useState(defaultValue);
  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-6 border-b border-[var(--border-color)] overflow-x-auto no-scrollbar">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "h-10 text-sm font-medium transition-colors border-b-2 -mb-[1px] whitespace-nowrap",
              activeTab === tab.id 
                ? "border-[var(--primary-gold)] text-[var(--primary-gold)]" 
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-color)]"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-6 animate-in fade-in duration-300">
        {tabs.find(t => t.id === activeTab)?.content}
      </div>
    </div>
  );
};

// ==========================================
// 2. LAYOUT SYSTEM
// ==========================================

const PageContainer = ({  children, maxWidth = 'default', className = ''  }: any) => {
  const maxWidthClasses = {
    narrow: 'max-w-[720px]',
    default: 'max-w-[1280px]',
    wide: 'max-w-[1440px]'
  };
  return (
    <div className={`mx-auto w-full animate-in fade-in duration-300 pb-12 ${maxWidthClasses[maxWidth]} ${className}`}>
      {children}
    </div>
  );
};

const PageHeader = ({  title, subtitle, actions, className = '', showBack, onBack  }: any) => (
  <div className={`flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6 sm:mb-8 ${className}`}>
    <div className="flex items-start gap-4">
      {showBack && (
        <button onClick={onBack} className="mt-1 p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]">
          <ArrowLeft className="w-5 h-5" />
        </button>
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


// ==========================================
// 3. APPLICATION SHELL COMPONENTS
// ==========================================

// --- CONFIG ---
const NAVIGATION_CONFIG = [
  {
    group: 'Main',
    items: [
      { id: 'overview', label: 'Platform Health', icon: LayoutDashboard, route: '/platform' },
      { id: 'workspaces', label: 'Workspaces', icon: Briefcase, route: '/platform/workspaces', badge: '4' },
    ]
  },
  {
    group: 'Management',
    items: [
      { id: 'keys', label: 'API Keys', icon: Key, route: '/platform/keys' },
      { id: 'billing', label: 'Billing', icon: CreditCard, route: '/platform/billing' },
      { id: 'admin', label: 'Admins', icon: Shield, route: '/platform/admins', role: 'admin' },
    ]
  },
  {
    group: 'System',
    items: [
      { id: 'components', label: 'Component Library', icon: Component, route: '/platform/components' },
      { id: 'sessions', label: 'Security & Sessions', icon: Settings, route: '/p1/auth/sessions' },
    ]
  }
];

// i18n label lookups for NAVIGATION_CONFIG (module-scope config can't call useT() directly)
const NAV_GROUP_LABEL_KEYS: Record<string, string> = {
  Main: 'templates17WorkspaceEdit.navGroupMain',
  Management: 'templates17WorkspaceEdit.navGroupManagement',
  System: 'templates17WorkspaceEdit.navGroupSystem',
};
const NAV_ITEM_LABEL_KEYS: Record<string, string> = {
  overview: 'templates17WorkspaceEdit.navPlatformHealth',
  workspaces: 'templates17WorkspaceEdit.navWorkspaces',
  keys: 'templates17WorkspaceEdit.navApiKeys',
  billing: 'templates17WorkspaceEdit.navBilling',
  admin: 'templates17WorkspaceEdit.navAdmins',
  components: 'templates17WorkspaceEdit.navComponentLibrary',
  sessions: 'templates17WorkspaceEdit.securitySessions',
};

// --- HEADER SUB-COMPONENTS ---
const EnvBadge = ({  env = 'production'  }: any) => {
  const config = {
    production: "bg-[var(--primary-gold)]/15 text-[#9E814D] border-[var(--primary-gold)]/30",
    staging: "bg-white text-[var(--text-secondary)] border-[var(--border-color)]",
    development: "bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]"
  };
  return (
    <span className={`hidden md:inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${config[env]}`}>
      {env}
    </span>
  );
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

  const notifications = [{ id: 1, title: 'Data sync completed successfully', time: '10m ago', read: false }];

  return (
    <div className="relative" ref={dropdownRef}>
      <button onClick={() => setIsOpen(!isOpen)} className={`relative p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-full transition-colors border ${isOpen ? 'bg-[var(--bg-app)] border-[var(--border-color)]' : 'border-transparent hover:bg-[var(--bg-app)] hover:border-[var(--border-color)]'}`}>
        <Bell className="w-[18px] h-[18px]" />
        <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--state-error)] border-2 border-[var(--bg-app)] animate-pulse"></span>
      </button>
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[320px] bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)] bg-[#FCFBF9]">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.notifications')}</h3>
          </div>
          <div className="max-h-[300px] overflow-y-auto">
            {notifications.map((n) => (
              <div key={n.id} className="px-4 py-3 border-b border-[var(--border-color)]/50 last:border-0 hover:bg-[var(--bg-app)]/50 transition-colors cursor-pointer flex gap-3 bg-[#FAF7F2]/30">
                <div className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 bg-[var(--primary-gold)]" />
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">{n.title}</p>
                  <p className="text-[11px] text-[var(--text-secondary)] mt-1">{n.time}</p>
                </div>
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
      <button onClick={() => setIsOpen(!isOpen)} className="w-[34px] h-[34px] rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center transition-all hover:shadow-soft-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50">
        <span className="text-sm font-semibold text-[var(--text-secondary)]">A</span>
      </button>
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[240px] bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50">
          <div className="px-4 py-3 border-b border-[var(--border-color)] bg-[#FCFBF9]">
            <p className="text-sm font-semibold text-[var(--text-primary)] truncate">Admin User</p>
            <p className="text-xs text-[var(--text-secondary)] truncate">admin@kaori.io</p>
          </div>
          <div className="p-1.5">
            <button onClick={() => { setActiveRoute('sessions'); setIsOpen(false); }} className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors flex items-center gap-2">
              <Shield className="w-4 h-4 text-[var(--text-secondary)]" /> {t('templates17WorkspaceEdit.securitySessions')}
            </button>
          </div>
          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" />
          <div className="p-1.5">
            <button className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] transition-colors flex items-center gap-2 font-medium">
              <LogOut className="w-4 h-4" /> {t('templates17WorkspaceEdit.signOut')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const GlobalHeader = ({  activeRoute, setActiveRoute, setIsMobileMenuOpen  }: any) => {
  const t = useT();
  const navItemMatch = NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute);
  let routeLabel = navItemMatch ? t(NAV_ITEM_LABEL_KEYS[navItemMatch.id] ?? navItemMatch.label) : undefined;
  if (activeRoute === 'workspace-details') routeLabel = t('templates17WorkspaceEdit.breadcrumbWorkspaceOverview');
  else if (activeRoute === 'workspace-members') routeLabel = t('templates17WorkspaceEdit.breadcrumbWorkspaceMembers');
  else if (activeRoute === 'billing') routeLabel = t('templates17WorkspaceEdit.breadcrumbWorkspaceBilling');
  else if (activeRoute === 'audit-logs') routeLabel = t('templates17WorkspaceEdit.breadcrumbWorkspaceAuditLogs');
  else if (activeRoute === 'workspace-new') routeLabel = t('templates17WorkspaceEdit.breadcrumbWorkspaceNew');
  else if (activeRoute === 'workspace-edit') routeLabel = t('templates17WorkspaceEdit.breadcrumbWorkspaceSettings');
  else if (!routeLabel) routeLabel = activeRoute;

  return (
    <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/90 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6 transition-all duration-300">
      <div className="flex items-center gap-4">
        <button className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]" onClick={() => setIsMobileMenuOpen(true)}>
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:flex items-center text-sm font-medium">
          <span className="text-[var(--text-secondary)]">{t('templates17WorkspaceEdit.breadcrumbPlatform')}</span>
          <ChevronRight className="w-4 h-4 mx-2 text-[var(--border-color)] shrink-0 opacity-50" />
          <span className="text-[var(--text-primary)] capitalize">{routeLabel}</span>
        </div>
      </div>
      <div className="flex items-center gap-3 sm:gap-4">
        <EnvBadge env="production" />
        <div className="w-[1px] h-5 bg-[var(--border-color)] hidden md:block mx-1"></div>
        <div className="hidden sm:flex items-center gap-2">
           <div className="relative group hidden lg:block">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-[14px] h-[14px] text-[var(--text-secondary)] group-focus-within:text-[var(--primary-gold)] transition-colors" />
              <input type="text" placeholder={t('templates17WorkspaceEdit.searchPlaceholder')} className="h-8 w-48 pl-8 pr-10 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm" />
            </div>
            <Button variant="outline" size="sm" onClick={() => setActiveRoute('workspace-new')} className="hidden md:flex"><Plus className="w-3.5 h-3.5 mr-1.5" /> {t('templates17WorkspaceEdit.newWorkspaceButton')}</Button>
        </div>
        <NotificationDropdown />
        <HeaderUserMenu setActiveRoute={setActiveRoute} />
      </div>
    </header>
  );
};

// --- SIDEBAR COMPONENTS ---
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
  // Keep Workspaces highlighted for any workspace sub-route or billing
  const currentHighlight = (activeRoute === 'workspace-details' || activeRoute === 'workspace-members' || activeRoute === 'billing' || activeRoute === 'audit-logs' || activeRoute === 'workspace-new' || activeRoute === 'workspace-edit') ? 'workspaces' : activeRoute;

  return (
    <aside className={cn("relative flex flex-col h-full bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] sidebar-transition z-30", isMobile ? 'w-[280px]' : collapsed ? 'w-[72px]' : 'w-[240px]')}>
      <div className={`flex items-center h-16 shrink-0 border-b border-[var(--border-color)]/50 sidebar-transition ${collapsed ? 'px-0 justify-center' : 'px-5 gap-3'}`}>
        <div className="flex h-8 w-8 items-center justify-center rounded-md-custom bg-white shadow-soft-sm border border-[var(--border-color)] shrink-0">
          <svg className="w-5 h-5 text-[var(--primary-gold)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z" fill="currentColor" fillOpacity="0.1"/>
            <path d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z" fill="currentColor" fillOpacity="0.1"/>
          </svg>
        </div>
        {!collapsed && (
          <div className="flex flex-col overflow-hidden animate-in fade-in duration-300">
            <span className="font-serif text-[17px] leading-none font-semibold text-[var(--text-primary)] tracking-wide">Kaori</span>
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mt-0.5">{t('templates17WorkspaceEdit.breadcrumbPlatform')}</span>
          </div>
        )}
      </div>

      <nav aria-label={t('templates17WorkspaceEdit.mainNavigationAriaLabel')} className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 space-y-6">
        {NAVIGATION_CONFIG.map((group, idx) => (
          <div key={idx} className="flex flex-col">
            {!collapsed ? (
              <div className="px-3 mb-2 text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-[0.1em] opacity-70">{t(NAV_GROUP_LABEL_KEYS[group.group] ?? group.group)}</div>
            ) : (
              <div className="w-full h-[1px] bg-[var(--border-color)]/60 my-2 rounded-full" />
            )}
            <div className="space-y-1">
              {group.items.map((item) => {
                const isActive = currentHighlight === item.id;
                const Icon = item.icon;
                const itemLabel = t(NAV_ITEM_LABEL_KEYS[item.id] ?? item.label);
                return (
                  <SidebarTooltip key={item.id} content={itemLabel} isCollapsed={collapsed}>
                    <button
                      onClick={() => setActiveRoute(item.id)}
                      className={cn(
                        "relative flex items-center h-10 rounded-md-custom transition-all duration-200 group w-full",
                        isActive ? "bg-[var(--primary-gold)]/10 text-[var(--text-primary)]" : "text-[var(--text-secondary)] hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)]",
                        collapsed ? "justify-center px-0" : "px-3 gap-3"
                      )}
                    >
                      {isActive && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[var(--primary-gold)] rounded-r-md transition-all" />}
                      <Icon className={`shrink-0 transition-colors ${isActive ? 'text-[var(--primary-gold)] w-5 h-5' : 'w-[18px] h-[18px] group-hover:text-[var(--text-primary)]'}`} />
                      {!collapsed && <span className="text-sm font-medium truncate flex-1 text-left">{itemLabel}</span>}
                      {!collapsed && item.badge && (
                        <span className="shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-[var(--primary-gold)] text-white text-[10px] font-bold shadow-sm ml-2">
                          {item.badge}
                        </span>
                      )}
                      {collapsed && item.badge && (
                        <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[var(--primary-gold)] border border-[var(--bg-sidebar)]" />
                      )}
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
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={cn("w-full flex items-center h-8 rounded-md-custom text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors border border-transparent hover:border-[var(--border-color)]/50", collapsed ? 'justify-center' : 'px-3 gap-3')}
          >
            {collapsed ? <PanelLeftOpen className="w-[18px] h-[18px]" /> : <PanelLeftClose className="w-[18px] h-[18px]" />}
            {!collapsed && <span className="text-xs font-medium">{t('templates17WorkspaceEdit.collapseSidebar')}</span>}
          </button>
        )}
      </div>
    </aside>
  );
};


// ==========================================
// 4. VIEWS & PAGES
// ==========================================

// --- EDIT WORKSPACE SETTINGS PAGE ---
const WorkspaceSettingsPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isSaving, setIsSaving] = useState(false);
  const [showSavedToast, setShowSavedToast] = useState(false);
  
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  
  // Form State
  const initialData = {
    name: 'Production AI',
    description: 'Main production environment for ML models',
    region: 'us-east',
    timezone: 'UTC',
    rateLimit: '1000',
    storageQuota: '500'
  };
  const [formData, setFormData] = useState(initialData);

  const isDirty = JSON.stringify(formData) !== JSON.stringify(initialData);

  const handleSave = async () => {
    if (!isDirty) return;
    setIsSaving(true);
    await new Promise(r => setTimeout(r, 1000));
    setIsSaving(false);
    setShowSavedToast(true);
    setTimeout(() => setShowSavedToast(false), 3000);
    // In real app: setInitialData to formData to reset isDirty
  };

  const handleDelete = async () => {
    // Perform delete logic
    await new Promise(r => setTimeout(r, 800));
    setIsDeleteModalOpen(false);
    setActiveRoute('workspaces');
  };

  return (
    <PageContainer maxWidth="narrow" className="relative">
      
      {/* Success Toast */}
      {showSavedToast && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="bg-[#F3F9F5] border border-[#8FBFA0] text-[#427A5B] px-4 py-2 rounded-full shadow-soft-md flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-4 h-4" /> {t('templates17WorkspaceEdit.changesSavedToast')}
          </div>
        </div>
      )}

      <PageHeader
        showBack
        onBack={() => setActiveRoute('workspace-details')}
        title={t('templates17WorkspaceEdit.workspaceSettingsTitle')}
        subtitle={t('templates17WorkspaceEdit.workspaceSettingsSubtitle')}
        actions={
          <>
            <Button variant="tertiary" onClick={() => setActiveRoute('workspace-details')} className="hidden sm:flex">{t('templates17WorkspaceEdit.cancel')}</Button>
            <Button onClick={handleSave} disabled={!isDirty} isLoading={isSaving}>
              <Save className="w-4 h-4 mr-2" /> {t('templates17WorkspaceEdit.saveChanges')}
            </Button>
          </>
        }
      />

      <Tabs defaultValue="general" tabs={[
        {
          id: 'general',
          label: t('templates17WorkspaceEdit.tabGeneral'),
          content: (
            <div className="space-y-8 animate-step">
              <Section>
                <Card className="p-6">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates17WorkspaceEdit.basicInformation')}</h3>
                  <div className="space-y-5">
                    <Input
                      label={t('templates17WorkspaceEdit.workspaceNameLabel')}
                      value={formData.name}
                      onChange={(e: any) => setFormData({...formData, name: e.target.value})}
                    />
                    <Input
                      label={t('templates17WorkspaceEdit.descriptionLabel')}
                      value={formData.description}
                      onChange={(e: any) => setFormData({...formData, description: e.target.value})}
                    />
                    <Input
                      label={t('templates17WorkspaceEdit.deploymentRegionLabel')}
                      value={t('templates17WorkspaceEdit.regionUsEast')}
                      disabled
                      helperText={t('templates17WorkspaceEdit.regionChangeHelper')}
                    />
                  </div>
                </Card>
              </Section>
              <Section>
                <Card className="p-6">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates17WorkspaceEdit.displaySettings')}</h3>
                  <div className="space-y-5">
                    <Select
                      label={t('templates17WorkspaceEdit.defaultTimezoneLabel')}
                      value={formData.timezone}
                      onChange={(v: any) => setFormData({...formData, timezone: v})}
                      options={[
                        {label: t('templates17WorkspaceEdit.tzUtc'), value: 'UTC'},
                        {label: t('templates17WorkspaceEdit.tzPst'), value: 'PST'},
                        {label: t('templates17WorkspaceEdit.tzEst'), value: 'EST'},
                        {label: t('templates17WorkspaceEdit.tzCet'), value: 'CET'}
                      ]}
                    />
                  </div>
                </Card>
              </Section>
            </div>
          )
        },
        {
          id: 'advanced',
          label: t('templates17WorkspaceEdit.tabAdvanced'),
          content: (
            <div className="space-y-8 animate-step">
              <Section>
                <Card className="p-6">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates17WorkspaceEdit.resourceLimits')}</h3>
                  <p className="text-xs text-[var(--text-secondary)] mb-5">{t('templates17WorkspaceEdit.resourceLimitsDesc')}</p>
                  <div className="space-y-5">
                    <Input
                      label={t('templates17WorkspaceEdit.apiRateLimitLabel')}
                      type="number"
                      value={formData.rateLimit}
                      onChange={(e: any) => setFormData({...formData, rateLimit: e.target.value})}
                    />
                    <Input
                      label={t('templates17WorkspaceEdit.storageQuotaLabel')}
                      type="number"
                      value={formData.storageQuota}
                      onChange={(e: any) => setFormData({...formData, storageQuota: e.target.value})}
                    />
                  </div>
                </Card>
              </Section>
              <Section>
                 <Card className="p-6 opacity-60 pointer-events-none">
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3 flex items-center justify-between">
                      {t('templates17WorkspaceEdit.integrations')} <Badge>{t('templates17WorkspaceEdit.comingSoon')}</Badge>
                    </h3>
                    <p className="text-xs text-[var(--text-secondary)]">{t('templates17WorkspaceEdit.integrationsDesc')}</p>
                 </Card>
              </Section>
            </div>
          )
        },
        {
          id: 'danger',
          label: t('templates17WorkspaceEdit.tabDangerZone'),
          content: (
            <div className="space-y-8 animate-step">
              <Section>
                <Card className="p-6 border-[#D97C7C]/40 bg-[#FDF8F8]">
                  <h3 className="text-sm font-semibold text-[#9B5050] mb-4 border-b border-[#D97C7C]/30 pb-3 flex items-center">
                    <AlertTriangle className="w-4 h-4 mr-2" /> {t('templates17WorkspaceEdit.tabDangerZone')}
                  </h3>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-4 border-b border-[#D97C7C]/20">
                    <div>
                      <h4 className="text-sm font-medium text-[var(--text-primary)]">{t('templates17WorkspaceEdit.suspendWorkspaceHeading')}</h4>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates17WorkspaceEdit.suspendWorkspaceDesc')}</p>
                    </div>
                    <Button variant="secondary" className="shrink-0 text-[#9B5050] hover:bg-[#D97C7C]/10 border-[#D97C7C]/40">{t('templates17WorkspaceEdit.suspend')}</Button>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-4">
                    <div>
                      <h4 className="text-sm font-medium text-[var(--text-primary)]">{t('templates17WorkspaceEdit.deleteWorkspace')}</h4>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates17WorkspaceEdit.deleteWorkspaceDesc')}</p>
                    </div>
                    <Button variant="destructive" className="shrink-0" onClick={() => setIsDeleteModalOpen(true)}>{t('templates17WorkspaceEdit.deleteWorkspace')}</Button>
                  </div>
                </Card>
              </Section>
            </div>
          )
        }
      ]} />

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title={t('templates17WorkspaceEdit.deleteWorkspace')}
        description={t('templates17WorkspaceEdit.deleteWorkspaceModalDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsDeleteModalOpen(false)}>{t('templates17WorkspaceEdit.cancel')}</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteConfirmText !== formData.name}>{t('templates17WorkspaceEdit.deleteWorkspaceConfirmButton')}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Alert variant="error" title={t('templates17WorkspaceEdit.warning')}>
            {t('templates17WorkspaceEdit.deleteWorkspaceAlertMsg')}
          </Alert>
          <div className="space-y-2 mt-4">
            <Label>{t('templates17WorkspaceEdit.deleteConfirmPrefix')} <strong className="font-bold text-[var(--text-primary)]">{formData.name}</strong> {t('templates17WorkspaceEdit.deleteConfirmSuffix')}</Label>
            <Input
              value={deleteConfirmText}
              onChange={(e: any) => setDeleteConfirmText(e.target.value)}
              placeholder={t('templates17WorkspaceEdit.workspaceNamePlaceholder')}
            />
          </div>
        </div>
      </Modal>

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
      <PageHeader
        title={t('templates17WorkspaceEdit.componentLibraryTitle')}
        subtitle={t('templates17WorkspaceEdit.componentLibrarySubtitle')}
        actions={<Button>{t('templates17WorkspaceEdit.deploySystem')}</Button>}
      />

      <Tabs defaultValue="form" tabs={[
        { id: 'form', label: t('templates17WorkspaceEdit.tabFormsInputs'), content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title={t('templates17WorkspaceEdit.sectionButtons')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)]">
               <div className="flex flex-wrap gap-4 mb-4">
                 <Button variant="primary">{t('templates17WorkspaceEdit.primaryButton')}</Button>
                 <Button variant="secondary">{t('templates17WorkspaceEdit.secondaryButton')}</Button>
                 <Button variant="tertiary">{t('templates17WorkspaceEdit.tertiaryGhost')}</Button>
               </div>
               <div className="flex flex-wrap gap-4 items-center">
                 <Button variant="primary" isLoading>{t('templates17WorkspaceEdit.loading')}</Button>
                 <Button variant="destructive">{t('templates17WorkspaceEdit.destructiveAction')}</Button>
                 <Button variant="primary" size="icon"><Plus className="w-4 h-4"/></Button>
               </div>
             </Section>

             <Section title={t('templates17WorkspaceEdit.sectionInputsSelects')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] space-y-4">
                <Input label={t('templates17WorkspaceEdit.emailAddressLabel')} placeholder="admin@kaori.io" helperText={t('templates17WorkspaceEdit.emailHelperText')} />
                <Input label={t('templates17WorkspaceEdit.workspaceNameLabel')} placeholder={t('templates17WorkspaceEdit.workspaceNamePlaceholderExample')} error={t('templates17WorkspaceEdit.workspaceNameTakenError')} />
                <Select
                  label={t('templates17WorkspaceEdit.environmentLabel')}
                  placeholder={t('templates17WorkspaceEdit.selectEnvironmentPlaceholder')}
                  options={[{label: t('templates17WorkspaceEdit.production'), value: 'prod'}, {label: t('templates17WorkspaceEdit.staging'), value: 'stage'}]}
                  value={selectVal}
                  onChange={setSelectVal}
                />
                <DatePicker label={t('templates17WorkspaceEdit.billingCycleStartLabel')} date={date} setDate={setDate} />
             </Section>
           </div>
        )},
        { id: 'data', label: t('templates17WorkspaceEdit.tabDataDisplay'), content: (
           <div className="space-y-8">
             <Section title={t('templates17WorkspaceEdit.sectionMetricCards')}>
               <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                 <MetricCard title={t('templates17WorkspaceEdit.totalRevenue')} value="$45,231" trend="+20.1%" isUp={true} />
                 <MetricCard title={t('templates17WorkspaceEdit.activeWorkspaces')} value="12" trend="0%" />
                 <MetricCard title={t('templates17WorkspaceEdit.errorRate')} value="1.2%" trend="+0.4%" isUp={false} inverseGood={true} />
               </div>
             </Section>

             <Section title={t('templates17WorkspaceEdit.sectionDataTable')}>
                <DataTable
                  columns={[t('templates17WorkspaceEdit.colWorkspace'), t('templates17WorkspaceEdit.colEnvironment'), t('templates17WorkspaceEdit.colStatus'), t('templates17WorkspaceEdit.colCreated')]}
                  data={[
                    ["Production AI", t('templates17WorkspaceEdit.production'), <Badge variant="operational" key="1">{t('templates17WorkspaceEdit.healthy')}</Badge>, "Oct 12, 2026"],
                    ["Staging Data", t('templates17WorkspaceEdit.staging'), <Badge variant="degraded" key="2">{t('templates17WorkspaceEdit.degraded')}</Badge>, "Oct 14, 2026"],
                    ["Dev Cluster", "Development", <Badge variant="operational" key="3">{t('templates17WorkspaceEdit.healthy')}</Badge>, "Oct 15, 2026"]
                  ]}
                  loading={false}
                />
             </Section>
           </div>
        )},
        { id: 'feedback', label: t('templates17WorkspaceEdit.tabFeedbackOverlays'), content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title={t('templates17WorkspaceEdit.sectionAlerts')} className="space-y-4">
               <Alert variant="info" title={t('templates17WorkspaceEdit.alertSystemUpdateTitle')}>{t('templates17WorkspaceEdit.alertSystemUpdateMsg')}</Alert>
               <Alert variant="success" title={t('templates17WorkspaceEdit.alertBackupCompleteTitle')}>{t('templates17WorkspaceEdit.alertBackupCompleteMsg')}</Alert>
               <Alert variant="warning" title={t('templates17WorkspaceEdit.alertHighLatencyTitle')}>{t('templates17WorkspaceEdit.alertHighLatencyMsg')}</Alert>
               <Alert variant="error" title={t('templates17WorkspaceEdit.alertPaymentFailedTitle')}>{t('templates17WorkspaceEdit.alertPaymentFailedMsg')}</Alert>
             </Section>

             <Section title={t('templates17WorkspaceEdit.sectionModalsDrawers')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] flex flex-col gap-4 items-start">
               <Button variant="secondary" onClick={() => setIsModalOpen(true)}>{t('templates17WorkspaceEdit.openModal')}</Button>
               <Button variant="secondary" onClick={() => setIsDrawerOpen(true)}>{t('templates17WorkspaceEdit.openDrawer')}</Button>

               <Modal
                 isOpen={isModalOpen}
                 onClose={() => setIsModalOpen(false)}
                 title={t('templates17WorkspaceEdit.deleteWorkspace')}
                 description={t('templates17WorkspaceEdit.deleteWorkspaceConfirmDesc')}
                 footer={<><Button variant="outline" onClick={()=>setIsModalOpen(false)}>{t('templates17WorkspaceEdit.cancel')}</Button><Button variant="destructive">{t('templates17WorkspaceEdit.confirmDelete')}</Button></>}
               >
                 <div className="space-y-4">
                    <Input label={t('templates17WorkspaceEdit.typeWorkspaceNameConfirmLabel')} placeholder="Production AI" />
                 </div>
               </Modal>

               <Drawer
                 isOpen={isDrawerOpen}
                 onClose={() => setIsDrawerOpen(false)}
                 title={t('templates17WorkspaceEdit.editProfile')}
                 footer={<><Button variant="outline" className="w-full" onClick={()=>setIsDrawerOpen(false)}>{t('templates17WorkspaceEdit.cancel')}</Button><Button className="w-full">{t('templates17WorkspaceEdit.saveChangesCapital')}</Button></>}
               >
                 <div className="space-y-4">
                    <Input label={t('templates17WorkspaceEdit.fullNameLabel')} placeholder="Admin User" />
                    <Input label={t('templates17WorkspaceEdit.emailLabel')} placeholder="admin@kaori.io" disabled />
                    <Select label={t('templates17WorkspaceEdit.roleLabel')} options={[{label: t('templates17WorkspaceEdit.admin'), value:'admin'}, {label: t('templates17WorkspaceEdit.member'), value:'member'}]} value="admin" onChange={()=>{}} />
                 </div>
               </Drawer>
             </Section>
           </div>
        )}
      ]} />
    </PageContainer>
  );
};

// --- PLATFORM OVERVIEW PAGE ---
const PlatformOverview = () => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates17WorkspaceEdit.platformOverviewTitle')} subtitle={t('templates17WorkspaceEdit.platformOverviewSubtitle')} actions={<Button variant="outline"><RefreshCw className="w-4 h-4 mr-2" /> {t('templates17WorkspaceEdit.refreshData')}</Button>} />
      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates17WorkspaceEdit.totalWorkspaces')} value="124" trend="+4" isUp={true} />
          <MetricCard title={t('templates17WorkspaceEdit.activeUsers')} value="1,892" trend="+12.5%" isUp={true} />
          <MetricCard title={t('templates17WorkspaceEdit.apiRequests')} value="2.4M" trend="+5.2%" isUp={true} />
          <MetricCard title={t('templates17WorkspaceEdit.failedRequests')} value="482" trend="-18%" isUp={false} inverseGood={true} />
        </div>
      </Section>
      <Section title={t('templates17WorkspaceEdit.recentActivity')}>
         <DataTable
            columns={[t('templates17WorkspaceEdit.colEvent'), t('templates17WorkspaceEdit.colWorkspace'), t('templates17WorkspaceEdit.colTime')]}
            data={[
              ["API Key Generated", "Production AI", "2 mins ago"],
              ["Workspace Created", "Staging Env", "1 hour ago"],
              ["User Invited", "Design System", "Yesterday"]
            ]}
            loading={false}
          />
      </Section>
    </PageContainer>
  );
};

// --- SESSIONS PAGE ---
const SessionsPage = () => {
  const t = useT();
  return (
    <PageContainer maxWidth="narrow">
      <PageHeader title={t('templates17WorkspaceEdit.activeSessionsTitle')} subtitle={t('templates17WorkspaceEdit.activeSessionsSubtitle')} actions={<Button variant="outline">{t('templates17WorkspaceEdit.signOutAll')}</Button>} />
      <Section title={t('templates17WorkspaceEdit.securitySessions')}>
        <Card className="p-8 text-center flex flex-col items-center">
          <Shield className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
          <h3 className="text-sm font-medium text-[var(--text-primary)]">{t('templates17WorkspaceEdit.securitySessions')}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates17WorkspaceEdit.manageActiveLoginsText')}</p>
        </Card>
      </Section>
    </PageContainer>
  );
};

// --- CREATE WORKSPACE WIZARD ---
const Stepper = ({  currentStep  }: any) => {
  const t = useT();
  const steps = [
    { num: 1, label: t('templates17WorkspaceEdit.stepWorkspaceInfo') },
    { num: 2, label: t('templates17WorkspaceEdit.stepPlanSelection') },
    { num: 3, label: t('templates17WorkspaceEdit.stepReviewCreate') }
  ];

  return (
    <div className="flex items-center w-full mb-10 max-w-md mx-auto">
      {steps.map((step, idx) => {
        const isCompleted = currentStep > step.num;
        const isActive = currentStep === step.num;

        return (
          <React.Fragment key={step.num}>
            <div className="flex flex-col items-center relative z-10">
              <div 
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors duration-300 shadow-sm border",
                  isCompleted ? "bg-[var(--primary-gold)] text-white border-transparent" : 
                  isActive ? "bg-[var(--bg-card)] border-[var(--primary-gold)] text-[var(--primary-gold-dark)] shadow-soft-md" : 
                  "bg-[var(--bg-app)] border-[var(--border-color)] text-[var(--text-secondary)]"
                )}
              >
                {isCompleted ? <Check className="w-4 h-4" /> : step.num}
              </div>
              <span className={cn(
                "absolute top-10 text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap",
                isActive ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)] opacity-70"
              )}>
                {step.label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div className="flex-1 h-px bg-[var(--border-color)] mx-4 relative">
                <div 
                  className="absolute left-0 top-0 h-full bg-[var(--primary-gold)] transition-all duration-500 ease-in-out" 
                  style={{ width: currentStep > step.num ? '100%' : '0%' }}
                />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

const WorkspaceNewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [step, setStep] = useState(1);
  const [isCreating, setIsCreating] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    region: '',
    plan: 'pro'
  });
  const [errors, setErrors] = useState({});

  const validateStep1 = () => {
    const newErrors = {};
    if (!formData.name.trim()) newErrors.name = t('templates17WorkspaceEdit.errWorkspaceNameRequired');
    else if (formData.name.length < 3) newErrors.name = t('templates17WorkspaceEdit.errWorkspaceNameMinLength');

    if (!formData.region) newErrors.region = t('templates17WorkspaceEdit.errRegionRequired');
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (step === 1 && !validateStep1()) return;
    setStep(s => Math.min(s + 1, 3));
  };

  const handleBack = () => setStep(s => Math.max(s - 1, 1));

  const handleCreate = async () => {
    setIsCreating(true);
    await new Promise(r => setTimeout(r, 1200));
    setActiveRoute('workspace-details');
  };

  return (
    <PageContainer maxWidth="narrow" className="pt-8">
      <div className="mb-10 text-center animate-in fade-in slide-in-from-bottom-4 duration-500">
        <h1 className="text-3xl font-serif font-semibold text-[var(--text-primary)] mb-2">{t('templates17WorkspaceEdit.createWorkspaceTitle')}</h1>
        <p className="text-sm text-[var(--text-secondary)]">{t('templates17WorkspaceEdit.createWorkspaceSubtitle')}</p>
      </div>

      <Stepper currentStep={step} />

      <Card className="p-6 sm:p-8 mt-12 shadow-soft-md animate-in fade-in zoom-in-[0.98] duration-300">
        {step === 1 && (
          <div className="space-y-6 animate-step">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.workspaceDetailsHeading')}</h2>
              <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates17WorkspaceEdit.workspaceDetailsDesc')}</p>
            </div>
            <div className="space-y-5">
              <Input label={t('templates17WorkspaceEdit.workspaceNameLabel')} placeholder={t('templates17WorkspaceEdit.workspaceNamePlaceholderAcme')} value={formData.name} onChange={(e: any) => { setFormData({...formData, name: e.target.value}); if (errors.name) setErrors({...errors, name: ''}); }} error={errors.name} autoFocus />
              <Input label={t('templates17WorkspaceEdit.descriptionOptionalLabel')} placeholder={t('templates17WorkspaceEdit.descriptionPlaceholder')} value={formData.description} onChange={(e: any) => setFormData({...formData, description: e.target.value})} />
              <Select label={t('templates17WorkspaceEdit.dataRegionLabel')} placeholder={t('templates17WorkspaceEdit.selectRegionPlaceholder')} options={[{label: t('templates17WorkspaceEdit.regionUsEast'), value: 'us-east'}, {label: t('templates17WorkspaceEdit.regionEuCentral'), value: 'eu-central'}, {label: t('templates17WorkspaceEdit.regionApSoutheast'), value: 'ap-southeast'}]} value={formData.region} onChange={(v: any) => { setFormData({...formData, region: v}); if (errors.region) setErrors({...errors, region: ''}); }} error={errors.region} />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6 animate-step">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.selectPlanHeading')}</h2>
              <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates17WorkspaceEdit.selectPlanDesc')}</p>
            </div>
            <div className="grid grid-cols-1 gap-4">
              {[
                { id: 'free', name: t('templates17WorkspaceEdit.freeTier'), price: '$0', desc: t('templates17WorkspaceEdit.freeTierDesc') },
                { id: 'pro', name: t('templates17WorkspaceEdit.proTierName'), price: '$49', desc: t('templates17WorkspaceEdit.proTierDesc'), recommended: true },
                { id: 'enterprise', name: t('templates17WorkspaceEdit.enterpriseTierName'), price: '$249', desc: t('templates17WorkspaceEdit.enterpriseTierDesc') }
              ].map(plan => (
                <div key={plan.id} onClick={() => setFormData({...formData, plan: plan.id})} className={cn("relative flex items-center p-4 rounded-md-custom border cursor-pointer transition-all duration-200", formData.plan === plan.id ? "border-[var(--primary-gold)] bg-[var(--primary-gold)]/5 shadow-soft-sm" : "border-[var(--border-color)] bg-white hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]")}>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-semibold text-[var(--text-primary)]">{plan.name}</h4>
                      {plan.recommended && <Badge variant="current">{t('templates17WorkspaceEdit.recommended')}</Badge>}
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] mt-1">{plan.desc}</p>
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-lg font-bold text-[var(--text-primary)]">{plan.price}<span className="text-[10px] font-normal text-[var(--text-secondary)]">/mo</span></div>
                  </div>
                  <div className={cn("absolute -right-2 -top-2 w-5 h-5 rounded-full flex items-center justify-center border shadow-sm transition-opacity duration-200", formData.plan === plan.id ? "opacity-100 bg-[var(--primary-gold)] border-[var(--bg-card)]" : "opacity-0")}>
                    <Check className="w-3 h-3 text-white" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6 animate-step">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.reviewCreateHeading')}</h2>
              <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates17WorkspaceEdit.reviewCreateDesc')}</p>
            </div>
            <div className="bg-[var(--bg-app)] rounded-md-custom border border-[var(--border-color)] p-5 space-y-4">
              <div className="flex justify-between items-center border-b border-[var(--border-color)] pb-3">
                <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{t('templates17WorkspaceEdit.workspaceNameLabel')}</span>
                <span className="text-sm font-medium text-[var(--text-primary)]">{formData.name}</span>
              </div>
              <div className="flex justify-between items-center border-b border-[var(--border-color)] pb-3">
                <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{t('templates17WorkspaceEdit.descriptionLabel')}</span>
                <span className="text-sm text-[var(--text-primary)] text-right truncate max-w-[200px]">{formData.description || t('templates17WorkspaceEdit.noneProvided')}</span>
              </div>
              <div className="flex justify-between items-center border-b border-[var(--border-color)] pb-3">
                <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{t('templates17WorkspaceEdit.regionLabel')}</span>
                <span className="text-sm font-medium text-[var(--text-primary)]">{formData.region === 'us-east' ? t('templates17WorkspaceEdit.regionUsEast') : formData.region === 'eu-central' ? t('templates17WorkspaceEdit.regionEuCentral') : formData.region === 'ap-southeast' ? t('templates17WorkspaceEdit.regionApSoutheast') : t('templates17WorkspaceEdit.none')}</span>
              </div>
              <div className="flex justify-between items-center pt-1">
                <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{t('templates17WorkspaceEdit.selectedPlanLabel')}</span>
                <Badge variant={formData.plan === 'pro' ? 'current' : 'operational'} className="capitalize">{formData.plan} {t('templates17WorkspaceEdit.tierSuffix')}</Badge>
              </div>
            </div>
            <Alert variant="info" title={t('templates17WorkspaceEdit.readyToProvisionTitle')}>{t('templates17WorkspaceEdit.readyToProvisionMsg')}</Alert>
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-[var(--border-color)] flex items-center justify-between">
          <Button variant="tertiary" onClick={step === 1 ? () => setActiveRoute('workspaces') : handleBack} disabled={isCreating}>{step === 1 ? t('templates17WorkspaceEdit.cancel') : t('templates17WorkspaceEdit.back')}</Button>
          {step < 3 ? (
            <Button onClick={handleNext}>{t('templates17WorkspaceEdit.continueBtn')} <ChevronRight className="w-4 h-4 ml-1" /></Button>
          ) : (
            <Button onClick={handleCreate} isLoading={isCreating}>{t('templates17WorkspaceEdit.createWorkspaceBtn')}</Button>
          )}
        </div>
      </Card>
    </PageContainer>
  );
};

// --- WORKSPACE OVERVIEW PAGE ---
const WorkspaceOverviewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<any>(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setIsDropdownOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <PageContainer maxWidth="default">
      <PageHeader 
        showBack 
        onBack={() => setActiveRoute('workspaces')}
        title="Production AI" 
        subtitle="ws_prod_01 • Main production environment for ML models" 
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex" onClick={() => setActiveRoute('workspace-edit')}><Edit2 className="w-4 h-4 mr-2"/> {t('templates17WorkspaceEdit.editDetails')}</Button>
            <Button variant="outline" className="hidden sm:flex" onClick={() => setActiveRoute('workspace-members')}><Users className="w-4 h-4 mr-2"/> {t('templates17WorkspaceEdit.manageMembers')}</Button>
            <div className="relative" ref={dropdownRef}>
               <Button variant="tertiary" size="icon" onClick={() => setIsDropdownOpen(!isDropdownOpen)}>
                 <MoreVertical className="w-4 h-4" />
               </Button>
               {isDropdownOpen && (
                  <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 animate-in fade-in zoom-in-95 duration-100">
                    <button
                      onClick={() => { setActiveRoute('audit-logs'); setIsDropdownOpen(false); }}
                      className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
                    >
                      <Activity className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates17WorkspaceEdit.auditLogs')}
                    </button>
                    <button
                      onClick={() => { setActiveRoute('billing'); setIsDropdownOpen(false); }}
                      className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
                    >
                      <CreditCard className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates17WorkspaceEdit.navBilling')}
                    </button>
                  </div>
               )}
            </div>
          </>
        } 
      />

      <Section>
        <Card className="p-5 sm:p-6 overflow-hidden relative">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
           <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6 relative z-10">
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates17WorkspaceEdit.statusLabel')}</p>
                <Badge variant="operational" className="py-1">{t('templates17WorkspaceEdit.active')}</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates17WorkspaceEdit.planLabel')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{t('templates17WorkspaceEdit.enterpriseTierName')}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates17WorkspaceEdit.regionLabel')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">US-East</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates17WorkspaceEdit.createdLabel')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">Oct 12, 2026</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates17WorkspaceEdit.ownerLabel')}</p>
                <div className="flex items-center gap-2">
                   <div className="w-5 h-5 rounded bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center text-[10px] font-bold text-[var(--primary-gold)]">A</div>
                   <div className="text-sm font-medium text-[var(--text-primary)]">Admin User</div>
                </div>
             </div>
           </div>
        </Card>
      </Section>

      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates17WorkspaceEdit.apiRequestsToday')} value="124.5K" trend="+5.2%" isUp={true} />
          <MetricCard title={t('templates17WorkspaceEdit.activeUsers')} value="14" trend="0%" />
          <MetricCard title={t('templates17WorkspaceEdit.errorRate')} value="0.01%" trend="-0.04%" isUp={false} inverseGood={true} />
          <MetricCard title={t('templates17WorkspaceEdit.storageUsed')} value="84 GB" trend="+2.1%" isUp={true} />
        </div>
      </Section>

      <Section>
        <Tabs defaultValue="overview" tabs={[
          {
            id: 'overview',
            label: t('templates17WorkspaceEdit.tabOverview'),
            content: (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.recentActivity')}</h3>
                     <Button variant="tertiary" size="sm" onClick={() => setActiveRoute('audit-logs')}>{t('templates17WorkspaceEdit.viewAllLogs')}</Button>
                  </div>
                  <DataTable
                    pagination={false}
                    columns={[t('templates17WorkspaceEdit.colEvent'), t('templates17WorkspaceEdit.colActor'), t('templates17WorkspaceEdit.colTime')]}
                    data={[
                      ["Billing updated to Enterprise", "Admin User", "2 days ago"],
                      ["API Key 'Prod Token' generated", "System", "Oct 18, 2026"],
                      ["User 'Sarah Jenkins' invited", "Admin User", "Oct 15, 2026"]
                    ]}
                    loading={false}
                  />
                </div>
                <div className="space-y-6 sm:space-y-8">
                   <div className="space-y-4">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.alertsHeading')}</h3>
                     <Alert variant="success" title={t('templates17WorkspaceEdit.healthy')}>{t('templates17WorkspaceEdit.noIssuesMsg')}</Alert>
                   </div>
                   <div className="space-y-4">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.quickActionsHeading')}</h3>
                     <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm flex flex-col gap-2">
                        <Button variant="outline" className="w-full justify-start"><Key className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> {t('templates17WorkspaceEdit.generateApiKey')}</Button>
                        <Button variant="outline" className="w-full justify-start" onClick={() => setActiveRoute('workspace-members')}><UserPlus className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> {t('templates17WorkspaceEdit.inviteUser')}</Button>
                        <Button variant="outline" className="w-full justify-start" onClick={() => setActiveRoute('billing')}><CreditCard className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> {t('templates17WorkspaceEdit.manageBilling')}</Button>
                     </div>
                   </div>
                </div>
              </div>
            )
          },
          {
            id: 'activity',
            label: t('templates17WorkspaceEdit.tabActivity'),
            content: (
               <DataTable
                columns={[t('templates17WorkspaceEdit.colEvent'), t('templates17WorkspaceEdit.colResource'), t('templates17WorkspaceEdit.colActor'), t('templates17WorkspaceEdit.colTime')]}
                data={[
                  ["Billing updated", "Plan: Enterprise", "Admin User", "2 days ago"],
                  ["Key generated", "Prod Token", "System", "Oct 18, 2026"],
                  ["User invited", "sarah@kaori.io", "Admin User", "Oct 15, 2026"],
                  ["Workspace created", "Production AI", "Admin User", "Oct 12, 2026"],
                ]}
                loading={false}
              />
            )
          },
          {
            id: 'usage',
            label: t('templates17WorkspaceEdit.tabUsage'),
            content: (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center shrink-0">
                      <Zap className="w-5 h-5 text-[var(--text-secondary)]" />
                    </div>
                    <div>
                       <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.apiCallsHeading')}</h3>
                       <p className="text-xs text-[var(--text-secondary)]">{t('templates17WorkspaceEdit.last30Days')}</p>
                    </div>
                  </div>
                  <div className="text-3xl font-semibold text-[var(--text-primary)]">2.4M</div>
                  <div className="text-sm text-[var(--text-secondary)] mt-2">{t('templates17WorkspaceEdit.enterpriseLimit20m')}</div>
                  <div className="w-full bg-[var(--bg-app)] rounded-full h-2 mt-4 border border-[var(--border-color)] overflow-hidden">
                     <div className="bg-[var(--primary-gold)] h-2 rounded-full" style={{width: '12%'}}></div>
                  </div>
                </Card>
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center shrink-0">
                      <Server className="w-5 h-5 text-[var(--text-secondary)]" />
                    </div>
                    <div>
                       <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.storageHeading')}</h3>
                       <p className="text-xs text-[var(--text-secondary)]">{t('templates17WorkspaceEdit.currentUsage')}</p>
                    </div>
                  </div>
                  <div className="text-3xl font-semibold text-[var(--text-primary)]">84 GB</div>
                  <div className="text-sm text-[var(--text-secondary)] mt-2">{t('templates17WorkspaceEdit.enterpriseLimit500gb')}</div>
                  <div className="w-full bg-[var(--bg-app)] rounded-full h-2 mt-4 border border-[var(--border-color)] overflow-hidden">
                     <div className="bg-[#5C856A] h-2 rounded-full" style={{width: '16%'}}></div>
                  </div>
                </Card>
              </div>
            )
          },
          { id: 'keys', label: t('templates17WorkspaceEdit.navApiKeys'), content: <Alert variant="info" title={t('templates17WorkspaceEdit.keysAlertTitle')}>{t('templates17WorkspaceEdit.manageApiKeysHereMsg')}</Alert> },
          { id: 'members', label: t('templates17WorkspaceEdit.tabMembers'), content: (
            <Card className="p-8 text-center flex flex-col items-center">
              <Users className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
              <h3 className="text-sm font-medium text-[var(--text-primary)]">{t('templates17WorkspaceEdit.workspaceMembersHeading')}</h3>
              <p className="text-xs text-[var(--text-secondary)] mt-1 mb-4">{t('templates17WorkspaceEdit.manageActiveMembersDesc')}</p>
              <Button onClick={() => setActiveRoute('workspace-members')}>{t('templates17WorkspaceEdit.openMembersManagement')}</Button>
            </Card>
          )}
        ]} />
      </Section>
    </PageContainer>
  );
};

// --- WORKSPACES PAGE ---
const MOCK_WORKSPACES = [
  { id: 'ws_prod_01', name: 'Production AI', ownerName: 'Admin User', ownerEmail: 'admin@kaori.io', plan: 'Enterprise', members: 14, usage: '2.4M reqs', status: 'Active', created: 'Oct 12, 2026' },
  { id: 'ws_stage_02', name: 'Staging Environment', ownerName: 'Sarah Jenkins', ownerEmail: 'sarah@kaori.io', plan: 'Pro', members: 8, usage: '850K reqs', status: 'Active', created: 'Oct 14, 2026' },
  { id: 'ws_dev_03', name: 'Dev Cluster Alpha', ownerName: 'Mike Chen', ownerEmail: 'mike@kaori.io', plan: 'Free', members: 3, usage: '12K reqs', status: 'Suspended', created: 'Oct 15, 2026' },
  { id: 'ws_analytics_04', name: 'Data Analytics Core', ownerName: 'Admin User', ownerEmail: 'admin@kaori.io', plan: 'Enterprise', members: 22, usage: '5.1M reqs', status: 'Active', created: 'Nov 01, 2026' },
];

const RowActionsDropdown = ({  workspaceId, onViewDetails, onEdit  }: any) => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<any>(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative flex justify-end" ref={ref}>
      <button onClick={() => setIsOpen(!isOpen)} className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors">
        <MoreVertical className="w-4 h-4"/>
      </button>
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 animate-in fade-in zoom-in-95 duration-100">
          <button onClick={() => { onViewDetails(); setIsOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Eye className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates17WorkspaceEdit.viewDetails')}
          </button>
          <button onClick={() => { onEdit(); setIsOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Edit2 className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates17WorkspaceEdit.editWorkspace')}
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Users className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates17WorkspaceEdit.manageMembers')}
          </button>
          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium">
            <Ban className="w-4 h-4 opacity-80"/> {t('templates17WorkspaceEdit.suspend')}
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium">
            <Trash2 className="w-4 h-4 opacity-80"/> {t('templates17WorkspaceEdit.delete')}
          </button>
        </div>
      )}
    </div>
  );
};

const WorkspacesPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [plan, setPlan] = useState('all');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const filteredData = MOCK_WORKSPACES.filter(ws => {
    const matchesSearch = ws.name.toLowerCase().includes(search.toLowerCase()) || ws.id.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = status === 'all' || ws.status === status;
    const matchesPlan = plan === 'all' || ws.plan === plan;
    return matchesSearch && matchesStatus && matchesPlan;
  });

  const getPlanBadgeVariant = (p) => {
    if (p === 'Free') return 'default';
    if (p === 'Pro') return 'operational';
    return 'current';
  };

  const mappedData = filteredData.map(ws => [
    <div key="ws-name">
      <div className="font-medium text-[var(--text-primary)]">{ws.name}</div>
      <div className="text-xs text-[var(--text-secondary)] font-mono mt-0.5">{ws.id}</div>
    </div>,
    <div key="ws-owner">
      <div className="text-sm text-[var(--text-primary)]">{ws.ownerName}</div>
      <div className="text-xs text-[var(--text-secondary)] mt-0.5">{ws.ownerEmail}</div>
    </div>,
    <Badge key="ws-plan" variant={getPlanBadgeVariant(ws.plan)}>{ws.plan}</Badge>,
    <div key="ws-members" className="flex items-center gap-1.5 text-[var(--text-secondary)]">
      <Users className="w-3.5 h-3.5"/> {ws.members}
    </div>,
    <span key="ws-usage" className="tabular-nums text-[var(--text-secondary)]">{ws.usage}</span>,
    <Badge key="ws-status" variant={ws.status === 'Active' ? 'operational' : 'warning'}>{ws.status}</Badge>,
    <span key="ws-created" className="text-[var(--text-secondary)] whitespace-nowrap">{ws.created}</span>,
    <RowActionsDropdown key="ws-actions" workspaceId={ws.id} onViewDetails={() => setActiveRoute('workspace-details')} onEdit={() => setActiveRoute('workspace-edit')} />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        title={t('templates17WorkspaceEdit.navWorkspaces')}
        subtitle={t('templates17WorkspaceEdit.workspacesSubtitle')}
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Search className="w-4 h-4 mr-2"/> {t('templates17WorkspaceEdit.import')}</Button>
            <Button onClick={() => setActiveRoute('workspace-new')}><Plus className="w-4 h-4 mr-2"/> {t('templates17WorkspaceEdit.createWorkspaceAction')}</Button>
          </>
        }
      />

      <Section>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 bg-[var(--bg-card)] p-4 rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm">
          <div className="relative w-full sm:w-72 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              className="h-10 w-full pl-9 pr-3 rounded-md-custom border border-[var(--border-color)] bg-white text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
              placeholder={t('templates17WorkspaceEdit.searchWorkspacesPlaceholder')}
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex w-full sm:w-auto gap-3 shrink-0">
            <div className="w-full sm:w-36">
              <Select value={status} onChange={setStatus} options={[{label: t('templates17WorkspaceEdit.allStatuses'), value: 'all'}, {label: t('templates17WorkspaceEdit.active'), value: 'Active'}, {label: t('templates17WorkspaceEdit.suspended'), value: 'Suspended'}]} placeholder={t('templates17WorkspaceEdit.statusPlaceholder')} />
            </div>
            <div className="w-full sm:w-36">
              <Select value={plan} onChange={setPlan} options={[{label: t('templates17WorkspaceEdit.allPlans'), value: 'all'}, {label: t('templates17WorkspaceEdit.free'), value: 'Free'}, {label: t('templates17WorkspaceEdit.pro'), value: 'Pro'}, {label: t('templates17WorkspaceEdit.enterpriseTierName'), value: 'Enterprise'}]} placeholder={t('templates17WorkspaceEdit.planPlaceholder')} />
            </div>
          </div>
          {(search || status !== 'all' || plan !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setStatus('all'); setPlan('all');}} className="px-3">{t('templates17WorkspaceEdit.clearFilters')}</Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable columns={[t('templates17WorkspaceEdit.colWorkspace'), t('templates17WorkspaceEdit.colOwner'), t('templates17WorkspaceEdit.planLabel'), t('templates17WorkspaceEdit.colMembers'), t('templates17WorkspaceEdit.colUsage'), t('templates17WorkspaceEdit.colStatus'), t('templates17WorkspaceEdit.colCreated'), ""]} data={mappedData} loading={isLoading} />
      </Section>
    </PageContainer>
  );
};

// --- WORKSPACE BILLING PAGE ---
const UsageCard = ({  title, current, max, unit, icon: Icon  }: any) => {
  const t = useT();
  const percent = Math.min((current / max) * 100, 100);
  const isWarning = percent >= 80;

  return (
    <Card className="p-5 flex flex-col justify-between">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-[var(--text-secondary)]" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
          <p className="text-xs text-[var(--text-secondary)]">{current.toLocaleString()} / {max.toLocaleString()} {unit}</p>
        </div>
      </div>
      <div className="w-full bg-[var(--bg-app)] rounded-full h-2 border border-[var(--border-color)] overflow-hidden">
         <div className={cn("h-2 rounded-full transition-all duration-500", isWarning ? "bg-[#D97C7C]" : "bg-[#5C856A]")} style={{ width: `${percent}%` }}></div>
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">{percent.toFixed(1)}% {t('templates17WorkspaceEdit.percentUsedSuffix')}</span>
        {isWarning && <span className="text-[11px] text-[#9B5050] font-medium flex items-center"><AlertCircle className="w-3 h-3 mr-1" /> {t('templates17WorkspaceEdit.approachingLimit')}</span>}
      </div>
    </Card>
  );
};

const WorkspaceBillingPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isUpgradeOpen, setIsUpgradeOpen] = useState(false);
  const [isCancelOpen, setIsCancelOpen] = useState(false);
  const [isLoadingInvoices, setIsLoadingInvoices] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoadingInvoices(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const MOCK_INVOICES = [
    { id: 'INV-2026-004', date: 'Oct 01, 2026', amount: '$49.00', status: 'Paid' },
    { id: 'INV-2026-003', date: 'Sep 01, 2026', amount: '$49.00', status: 'Paid' },
    { id: 'INV-2026-002', date: 'Aug 01, 2026', amount: '$49.00', status: 'Paid' },
    { id: 'INV-2026-001', date: 'Jul 01, 2026', amount: '$0.00', status: 'Paid' },
  ];

  const invoiceData = MOCK_INVOICES.map(inv => [
    <span key="id" className="font-medium text-[var(--text-primary)]">{inv.id}</span>,
    <span key="date" className="text-[var(--text-secondary)]">{inv.date}</span>,
    <span key="amount" className="tabular-nums text-[var(--text-primary)]">{inv.amount}</span>,
    <Badge key="status" variant={inv.status === 'Paid' ? 'operational' : 'default'}>{inv.status}</Badge>,
    <Button key="download" variant="tertiary" size="sm" className="h-8 px-2"><Download className="w-4 h-4 text-[var(--text-secondary)] hover:text-[var(--text-primary)]" /></Button>
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        showBack
        onBack={() => setActiveRoute('workspace-details')}
        title={t('templates17WorkspaceEdit.billingUsageTitle')}
        subtitle={t('templates17WorkspaceEdit.billingUsageSubtitle')}
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Download className="w-4 h-4 mr-2" /> {t('templates17WorkspaceEdit.downloadAll')}</Button>
            <Button onClick={() => setIsUpgradeOpen(true)}>{t('templates17WorkspaceEdit.upgradePlan')}</Button>
          </>
        }
      />

      <Section title={t('templates17WorkspaceEdit.currentPlanSection')}>
        <Card className="p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 border-[var(--primary-gold)]/40 bg-[#FAF7F2]/30 relative overflow-hidden">
          <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
          <div className="relative z-10 flex flex-col gap-1">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-[var(--text-primary)]">{t('templates17WorkspaceEdit.proTierHeading')}</h3>
              <Badge variant="current">{t('templates17WorkspaceEdit.active')}</Badge>
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              $49.00 / month, billed monthly.
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-2">
              {t('templates17WorkspaceEdit.nextBillingDatePrefix')} <strong className="font-medium text-[var(--text-primary)]">Nov 01, 2026</strong>.
            </p>
          </div>
          <div className="relative z-10 flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
            <Button variant="outline" onClick={() => setIsCancelOpen(true)}>{t('templates17WorkspaceEdit.cancelPlan')}</Button>
            <Button onClick={() => setIsUpgradeOpen(true)}>{t('templates17WorkspaceEdit.changePlan')}</Button>
          </div>
        </Card>
      </Section>

      <Section title={t('templates17WorkspaceEdit.currentUsageSection')}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
           <UsageCard title={t('templates17WorkspaceEdit.apiRequests')} icon={Zap} current={42150} max={50000} unit="reqs" />
           <UsageCard title={t('templates17WorkspaceEdit.storageUsed')} icon={HardDrive} current={8.4} max={50} unit="GB" />
           <UsageCard title={t('templates17WorkspaceEdit.activeUsers')} icon={Users} current={8} max={10} unit="seats" />
        </div>
      </Section>

      <Section title={t('templates17WorkspaceEdit.invoicesSection')} actions={
        <div className="w-32">
          <Select value="2026" onChange={() => {}} options={[{label: '2026', value: '2026'}, {label: '2025', value: '2025'}]} placeholder={t('templates17WorkspaceEdit.yearPlaceholder')} />
        </div>
      }>
        <DataTable
          columns={[t('templates17WorkspaceEdit.colInvoiceId'), t('templates17WorkspaceEdit.colDate'), t('templates17WorkspaceEdit.colAmount'), t('templates17WorkspaceEdit.colStatus'), ""]}
          data={invoiceData}
          loading={isLoadingInvoices}
          pagination={false}
        />
      </Section>

      {/* Upgrade Modal */}
      <Modal
        isOpen={isUpgradeOpen}
        onClose={() => setIsUpgradeOpen(false)}
        title={t('templates17WorkspaceEdit.upgradePlanModalTitle')}
        description={t('templates17WorkspaceEdit.upgradePlanModalDesc')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* Free Tier */}
          <div className="border border-[var(--border-color)] rounded-lg-custom p-4 bg-[var(--bg-app)] flex flex-col">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t('templates17WorkspaceEdit.free')}</h4>
              <div className="text-2xl font-bold text-[var(--text-primary)]">$0<span className="text-sm text-[var(--text-secondary)] font-normal">/mo</span></div>
            </div>
            <ul className="text-xs text-[var(--text-secondary)] space-y-2 mb-6 flex-1">
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--state-info)] mt-0.5" /> {t('templates17WorkspaceEdit.featureApiReqs10k')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--state-info)] mt-0.5" /> {t('templates17WorkspaceEdit.feature5gbStorage')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--state-info)] mt-0.5" /> {t('templates17WorkspaceEdit.feature3TeamMembers')}</li>
            </ul>
            <Button variant="outline" className="w-full" disabled>{t('templates17WorkspaceEdit.downgrade')}</Button>
          </div>

          {/* Pro Tier (Current) */}
          <div className="border-2 border-[var(--primary-gold)] rounded-lg-custom p-4 bg-white flex flex-col relative shadow-soft-md scale-[1.02]">
            <div className="absolute top-0 right-0 bg-[var(--primary-gold)] text-[var(--bg-card)] text-[9px] font-bold uppercase tracking-widest px-2 py-1 rounded-bl-lg rounded-tr-[14px]">
              {t('templates17WorkspaceEdit.current')}
            </div>
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t('templates17WorkspaceEdit.pro')}</h4>
              <div className="text-2xl font-bold text-[var(--text-primary)]">$49<span className="text-sm text-[var(--text-secondary)] font-normal">/mo</span></div>
            </div>
            <ul className="text-xs text-[var(--text-secondary)] space-y-2 mb-6 flex-1">
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates17WorkspaceEdit.featureApiReqs50k')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates17WorkspaceEdit.feature50gbStorage')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates17WorkspaceEdit.feature10TeamMembers')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates17WorkspaceEdit.featureEmailSupport')}</li>
            </ul>
            <Button variant="outline" className="w-full border-[var(--primary-gold)] text-[#9E814D]" disabled>{t('templates17WorkspaceEdit.currentPlanBtn')}</Button>
          </div>

          {/* Enterprise Tier */}
          <div className="border border-[var(--border-color)] rounded-lg-custom p-4 bg-white flex flex-col">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t('templates17WorkspaceEdit.enterpriseTierName')}</h4>
              <div className="text-2xl font-bold text-[var(--text-primary)]">$249<span className="text-sm text-[var(--text-secondary)] font-normal">/mo</span></div>
            </div>
            <ul className="text-xs text-[var(--text-secondary)] space-y-2 mb-6 flex-1">
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates17WorkspaceEdit.featureUnlimitedApiReqs')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates17WorkspaceEdit.feature500gbStorage')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates17WorkspaceEdit.featureUnlimitedMembers')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates17WorkspaceEdit.featurePrioritySupport')}</li>
            </ul>
            <Button className="w-full">{t('templates17WorkspaceEdit.upgrade')}</Button>
          </div>
        </div>
      </Modal>

      {/* Cancel Plan Modal */}
      <Modal
        isOpen={isCancelOpen}
        onClose={() => setIsCancelOpen(false)}
        title={t('templates17WorkspaceEdit.cancelSubscriptionTitle')}
        description={t('templates17WorkspaceEdit.cancelSubscriptionDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsCancelOpen(false)}>{t('templates17WorkspaceEdit.keepPlan')}</Button>
            <Button variant="destructive" onClick={() => setIsCancelOpen(false)}>{t('templates17WorkspaceEdit.confirmCancellation')}</Button>
          </>
        }
      >
         <Alert variant="warning" title={t('templates17WorkspaceEdit.warning')}>
           {t('templates17WorkspaceEdit.downgradeWarningMsg')}
         </Alert>
      </Modal>

    </PageContainer>
  );
};


// ==========================================
// MAIN PLATFORM SHELL COMPONENT
// ==========================================

export default function KaoriPlatformShell() {
  const t = useT();
  const [activeRoute, setActiveRoute] = useState('workspace-edit');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try { return localStorage.getItem('kaori_sidebar_collapsed') === 'true'; } 
    catch { return false; }
  });

  useEffect(() => {
    try { localStorage.setItem('kaori_sidebar_collapsed', isCollapsed); } 
    catch (e) { /* ignore */ }
  }, [isCollapsed]);

  return (
    <>
      <GlobalStyles />
      <div className="flex h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
        
        <div className="hidden md:block shrink-0 z-30">
          <GlobalSidebar isMobile={false} activeRoute={activeRoute} setActiveRoute={setActiveRoute} isCollapsed={isCollapsed} setIsCollapsed={setIsCollapsed} />
        </div>

        {isMobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            <div className="fixed inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity" onClick={() => setIsMobileMenuOpen(false)} />
            <div className="relative flex flex-col shadow-2xl animate-in slide-in-from-left h-full">
              <button onClick={() => setIsMobileMenuOpen(false)} className="absolute top-4 -right-12 p-2 text-white hover:text-white/80 bg-[var(--text-primary)] rounded-full shadow-md z-50">
                <X className="w-5 h-5" />
              </button>
              <GlobalSidebar isMobile={true} activeRoute={activeRoute} setActiveRoute={(r: any) => { setActiveRoute(r); setIsMobileMenuOpen(false); }} isCollapsed={false} setIsCollapsed={() => {}} />
            </div>
          </div>
        )}

        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative">
          <GlobalHeader activeRoute={activeRoute} setActiveRoute={setActiveRoute} setIsMobileMenuOpen={setIsMobileMenuOpen} />

          <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-[var(--bg-app)]">
            {activeRoute === 'components' ? <ComponentsPage /> :
             activeRoute === 'workspaces' ? <WorkspacesPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-details' ? <WorkspaceOverviewPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-members' ? <WorkspaceMembersPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'billing' ? <WorkspaceBillingPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'audit-logs' ? <WorkspaceAuditLogPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-new' ? <WorkspaceNewPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'workspace-edit' ? <WorkspaceSettingsPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'overview' ? <PlatformOverview /> : 
             activeRoute === 'sessions' ? <SessionsPage /> : (
              <PageContainer maxWidth="narrow">
                <PageHeader title={`${t(NAV_ITEM_LABEL_KEYS[activeRoute] ?? (NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label ?? activeRoute))} ${t('templates17WorkspaceEdit.moduleSuffix')}`} subtitle={t('templates17WorkspaceEdit.moduleDesignSubtitle')} />
                <Section>
                  <Card className="flex flex-col items-center justify-center py-20 px-4 text-center border-dashed bg-[var(--bg-card)]/50 mx-auto w-full animate-in fade-in duration-300">
                    <div className="w-12 h-12 rounded-lg-custom bg-[var(--bg-sidebar)] flex items-center justify-center border border-[var(--border-color)] mb-4">
                      {React.createElement(NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.icon || LayoutDashboard, { className: 'w-6 h-6 text-[var(--text-secondary)]' })}
                    </div>
                    <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">{t('templates17WorkspaceEdit.workInProgress')}</h3>
                    <p className="text-sm text-[var(--text-secondary)] max-w-sm">{t('templates17WorkspaceEdit.contentForRoutePrefix')} {activeRoute} {t('templates17WorkspaceEdit.contentForRouteSuffix')}</p>
                  </Card>
                </Section>
              </PageContainer>
            )}
          </main>
        </div>
      </div>
    </>
  );
}
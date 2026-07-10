// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 14Workspace Id Billing.jsx by convert_jsx_to_tsx.py.
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
  HardDrive
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
          "disabled:cursor-not-allowed disabled:opacity-50 shadow-soft-sm",
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
const Select = ({  label, placeholder, options = [], value, onChange, error  }: any) => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<any>(null);
  const resolvedPlaceholder = placeholder ?? t('templates14WorkspaceBilling.selectAnOption');

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
      {label && <Label>{label}</Label>}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md-custom border bg-white px-3 py-2 text-sm shadow-soft-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30",
          error ? "border-[var(--state-error)]" : "border-[var(--border-color)] hover:border-[var(--primary-gold)]/50",
          !selectedOption ? "text-[var(--text-secondary)]/60" : "text-[var(--text-primary)]"
        )}
      >
        {selectedOption ? selectedOption.label : resolvedPlaceholder}
        <ChevronDown className="h-4 w-4 opacity-50" />
      </button>
      {isOpen && (
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
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<any>(null);
  const resolvedPlaceholder = placeholder ?? t('templates14WorkspaceBilling.pickADate');
  const weekdayLabels = [
    t('templates14WorkspaceBilling.dayShortSun'),
    t('templates14WorkspaceBilling.dayShortMon'),
    t('templates14WorkspaceBilling.dayShortTue'),
    t('templates14WorkspaceBilling.dayShortWed'),
    t('templates14WorkspaceBilling.dayShortThu'),
    t('templates14WorkspaceBilling.dayShortFri'),
    t('templates14WorkspaceBilling.dayShortSat'),
  ];
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
        {date ? date : resolvedPlaceholder}
      </button>
      {isOpen && (
        <div className="absolute top-full left-0 z-50 mt-1 p-3 bg-white rounded-md-custom border border-[var(--border-color)] shadow-soft-md animate-in fade-in zoom-in-95 duration-150 w-[280px]">
           <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.calendarMonthDemo')}</span>
              <div className="flex gap-1">
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronRight className="w-4 h-4 rotate-180 text-[var(--text-secondary)]"/></button>
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronRight className="w-4 h-4 text-[var(--text-secondary)]"/></button>
              </div>
           </div>
           <div className="grid grid-cols-7 gap-1 text-center text-xs text-[var(--text-secondary)] mb-2">
             {weekdayLabels.map(d => <div key={d}>{d}</div>)}
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
        <div className="text-xs text-[var(--text-secondary)] mt-1 opacity-75">{t('templates14WorkspaceBilling.vsYesterday')}</div>
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
                  <span className="text-sm font-medium text-[var(--text-primary)]">{t('templates14WorkspaceBilling.noResultsFound')}</span>
                  <span className="text-xs text-[var(--text-secondary)]">{t('templates14WorkspaceBilling.tryAdjustingFilters')}</span>
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
          <span className="text-xs text-[var(--text-secondary)]">{t('templates14WorkspaceBilling.showingResults', { count: data.length })}</span>
          <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled>{t('templates14WorkspaceBilling.previous')}</Button>
              <Button variant="outline" size="sm">{t('templates14WorkspaceBilling.next')}</Button>
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
const Drawer = ({  isOpen, onClose, title, children, footer  }: any) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className="relative bg-[var(--bg-card)] w-full max-w-md h-full shadow-soft-lg border-l border-[var(--border-color)] flex flex-col animate-slide-in-right">
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
  const icons = { info: Info, success: CheckCircle2, warning: AlertCircle, error: ShieldAlert };
  const Icon = icons[variant];
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
      <div className="flex items-center gap-6 border-b border-[var(--border-color)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "h-10 text-sm font-medium transition-colors border-b-2 -mb-[1px]",
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
const getNavigationConfig = (t: any) => [
  {
    group: t('templates14WorkspaceBilling.navGroupMain'),
    items: [
      { id: 'overview', label: t('templates14WorkspaceBilling.navPlatformHealth'), icon: LayoutDashboard, route: '/platform' },
      { id: 'workspaces', label: t('templates14WorkspaceBilling.navWorkspaces'), icon: Briefcase, route: '/platform/workspaces', badge: '4' },
    ]
  },
  {
    group: t('templates14WorkspaceBilling.navGroupManagement'),
    items: [
      { id: 'keys', label: t('templates14WorkspaceBilling.navApiKeys'), icon: Key, route: '/platform/keys' },
      { id: 'billing', label: t('templates14WorkspaceBilling.navBilling'), icon: CreditCard, route: '/platform/billing' },
      { id: 'admin', label: t('templates14WorkspaceBilling.navAdmins'), icon: Shield, route: '/platform/admins', role: 'admin' },
    ]
  },
  {
    group: t('templates14WorkspaceBilling.navGroupSystem'),
    items: [
      { id: 'components', label: t('templates14WorkspaceBilling.navComponentLibrary'), icon: Component, route: '/platform/components' },
      { id: 'sessions', label: t('templates14WorkspaceBilling.navSecuritySessions'), icon: Settings, route: '/p1/auth/sessions' },
    ]
  }
];

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
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.notifications')}</h3>
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
              <Shield className="w-4 h-4 text-[var(--text-secondary)]" /> {t('templates14WorkspaceBilling.navSecuritySessions')}
            </button>
          </div>
          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" />
          <div className="p-1.5">
            <button className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] transition-colors flex items-center gap-2 font-medium">
              <LogOut className="w-4 h-4" /> {t('templates14WorkspaceBilling.signOut')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const GlobalHeader = ({  activeRoute, setActiveRoute, setIsMobileMenuOpen  }: any) => {
  const t = useT();
  const NAVIGATION_CONFIG = getNavigationConfig(t);
  // If the route is a detail route, show custom label.
  let routeLabel = NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label;
  if (activeRoute === 'workspace-details') routeLabel = t('templates14WorkspaceBilling.routeWorkspacesOverview');
  else if (activeRoute === 'workspace-members') routeLabel = t('templates14WorkspaceBilling.routeWorkspacesMembers');
  else if (activeRoute === 'billing') routeLabel = t('templates14WorkspaceBilling.routeWorkspacesBilling');
  else if (!routeLabel) routeLabel = activeRoute;

  return (
    <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/90 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6 transition-all duration-300">
      <div className="flex items-center gap-4">
        <button className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]" onClick={() => setIsMobileMenuOpen(true)}>
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:flex items-center text-sm font-medium">
          <span className="text-[var(--text-secondary)]">{t('templates14WorkspaceBilling.platformLabel')}</span>
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
              <input type="text" placeholder={t('templates14WorkspaceBilling.headerSearchPlaceholder')} className="h-8 w-48 pl-8 pr-10 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm" />
            </div>
            <Button variant="outline" size="sm" className="hidden md:flex"><Plus className="w-3.5 h-3.5 mr-1.5" /> {t('templates14WorkspaceBilling.colWorkspace')}</Button>
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
  const NAVIGATION_CONFIG = getNavigationConfig(t);
  const collapsed = isCollapsed && !isMobile;
  // Keep Workspaces highlighted for any workspace sub-route or billing
  const currentHighlight = (activeRoute === 'workspace-details' || activeRoute === 'workspace-members' || activeRoute === 'billing') ? 'workspaces' : activeRoute;

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
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mt-0.5">{t('templates14WorkspaceBilling.platformLabel')}</span>
          </div>
        )}
      </div>

      <nav aria-label={t('templates14WorkspaceBilling.ariaMainNavigation')} className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 space-y-6">
        {NAVIGATION_CONFIG.map((group, idx) => (
          <div key={idx} className="flex flex-col">
            {!collapsed ? (
              <div className="px-3 mb-2 text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-[0.1em] opacity-70">{group.group}</div>
            ) : (
              <div className="w-full h-[1px] bg-[var(--border-color)]/60 my-2 rounded-full" />
            )}
            <div className="space-y-1">
              {group.items.map((item) => {
                const isActive = currentHighlight === item.id;
                const Icon = item.icon;
                return (
                  <SidebarTooltip key={item.id} content={item.label} isCollapsed={collapsed}>
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
                      {!collapsed && <span className="text-sm font-medium truncate flex-1 text-left">{item.label}</span>}
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
            {!collapsed && <span className="text-xs font-medium">{t('templates14WorkspaceBilling.collapseSidebar')}</span>}
          </button>
        )}
      </div>
    </aside>
  );
};


// ==========================================
// 4. VIEWS & PAGES
// ==========================================

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
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">{t('templates14WorkspaceBilling.percentUsed', { percent: percent.toFixed(1) })}</span>
        {isWarning && <span className="text-[11px] text-[#9B5050] font-medium flex items-center"><AlertCircle className="w-3 h-3 mr-1" /> {t('templates14WorkspaceBilling.approachingLimit')}</span>}
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
        title={t('templates14WorkspaceBilling.billingTitle')}
        subtitle={t('templates14WorkspaceBilling.billingSubtitle')}
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Download className="w-4 h-4 mr-2" /> {t('templates14WorkspaceBilling.downloadAll')}</Button>
            <Button onClick={() => setIsUpgradeOpen(true)}>{t('templates14WorkspaceBilling.upgradePlan')}</Button>
          </>
        }
      />

      <Section title={t('templates14WorkspaceBilling.currentPlanSectionTitle')}>
        <Card className="p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 border-[var(--primary-gold)]/40 bg-[#FAF7F2]/30 relative overflow-hidden">
          <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
          <div className="relative z-10 flex flex-col gap-1">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.proTier')}</h3>
              <Badge variant="current">{t('templates14WorkspaceBilling.statusActive')}</Badge>
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              {t('templates14WorkspaceBilling.planPriceMonthly')}
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-2">
              {t('templates14WorkspaceBilling.nextBillingDateLead')} <strong className="font-medium text-[var(--text-primary)]">Nov 01, 2026</strong>.
            </p>
          </div>
          <div className="relative z-10 flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
            <Button variant="outline" onClick={() => setIsCancelOpen(true)}>{t('templates14WorkspaceBilling.cancelPlan')}</Button>
            <Button onClick={() => setIsUpgradeOpen(true)}>{t('templates14WorkspaceBilling.changePlan')}</Button>
          </div>
        </Card>
      </Section>

      <Section title={t('templates14WorkspaceBilling.currentUsageSectionTitle')}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
           <UsageCard title={t('templates14WorkspaceBilling.apiRequestsTitle')} icon={Zap} current={42150} max={50000} unit={t('templates14WorkspaceBilling.unitReqs')} />
           <UsageCard title={t('templates14WorkspaceBilling.storageUsedTitle')} icon={HardDrive} current={8.4} max={50} unit="GB" />
           <UsageCard title={t('templates14WorkspaceBilling.activeUsersTitle')} icon={Users} current={8} max={10} unit={t('templates14WorkspaceBilling.unitSeats')} />
        </div>
      </Section>

      <Section title={t('templates14WorkspaceBilling.invoicesSectionTitle')} actions={
        <div className="w-32">
          <Select value="2026" onChange={() => {}} options={[{label: '2026', value: '2026'}, {label: '2025', value: '2025'}]} placeholder={t('templates14WorkspaceBilling.yearSelectPlaceholder')} />
        </div>
      }>
        <DataTable
          columns={[t('templates14WorkspaceBilling.colInvoiceId'), t('templates14WorkspaceBilling.colDate'), t('templates14WorkspaceBilling.colAmount'), t('templates14WorkspaceBilling.labelStatus'), ""]}
          data={invoiceData}
          loading={isLoadingInvoices}
          pagination={false}
        />
      </Section>

      {/* Upgrade Modal */}
      <Modal
        isOpen={isUpgradeOpen}
        onClose={() => setIsUpgradeOpen(false)}
        title={t('templates14WorkspaceBilling.upgradePlanModalTitle')}
        description={t('templates14WorkspaceBilling.upgradePlanModalDesc')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* Free Tier */}
          <div className="border border-[var(--border-color)] rounded-lg-custom p-4 bg-[var(--bg-app)] flex flex-col">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t('templates14WorkspaceBilling.planFree')}</h4>
              <div className="text-2xl font-bold text-[var(--text-primary)]">$0<span className="text-sm text-[var(--text-secondary)] font-normal">/mo</span></div>
            </div>
            <ul className="text-xs text-[var(--text-secondary)] space-y-2 mb-6 flex-1">
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--state-info)] mt-0.5" /> {t('templates14WorkspaceBilling.featureFreeReqs')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--state-info)] mt-0.5" /> {t('templates14WorkspaceBilling.featureFreeStorage')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--state-info)] mt-0.5" /> {t('templates14WorkspaceBilling.featureFreeMembers')}</li>
            </ul>
            <Button variant="outline" className="w-full" disabled>{t('templates14WorkspaceBilling.downgrade')}</Button>
          </div>

          {/* Pro Tier (Current) */}
          <div className="border-2 border-[var(--primary-gold)] rounded-lg-custom p-4 bg-white flex flex-col relative shadow-soft-md scale-[1.02]">
            <div className="absolute top-0 right-0 bg-[var(--primary-gold)] text-[var(--bg-card)] text-[9px] font-bold uppercase tracking-widest px-2 py-1 rounded-bl-lg rounded-tr-[14px]">
              {t('templates14WorkspaceBilling.currentBadge')}
            </div>
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t('templates14WorkspaceBilling.planPro')}</h4>
              <div className="text-2xl font-bold text-[var(--text-primary)]">$49<span className="text-sm text-[var(--text-secondary)] font-normal">/mo</span></div>
            </div>
            <ul className="text-xs text-[var(--text-secondary)] space-y-2 mb-6 flex-1">
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates14WorkspaceBilling.featureProReqs')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates14WorkspaceBilling.featureProStorage')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates14WorkspaceBilling.featureProMembers')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mt-0.5" /> {t('templates14WorkspaceBilling.featureProSupport')}</li>
            </ul>
            <Button variant="outline" className="w-full border-[var(--primary-gold)] text-[#9E814D]" disabled>{t('templates14WorkspaceBilling.currentPlanButton')}</Button>
          </div>

          {/* Enterprise Tier */}
          <div className="border border-[var(--border-color)] rounded-lg-custom p-4 bg-white flex flex-col">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t('templates14WorkspaceBilling.planEnterprise')}</h4>
              <div className="text-2xl font-bold text-[var(--text-primary)]">$249<span className="text-sm text-[var(--text-secondary)] font-normal">/mo</span></div>
            </div>
            <ul className="text-xs text-[var(--text-secondary)] space-y-2 mb-6 flex-1">
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates14WorkspaceBilling.featureEntReqs')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates14WorkspaceBilling.featureEntStorage')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates14WorkspaceBilling.featureEntMembers')}</li>
              <li className="flex items-start gap-2"><Check className="w-3.5 h-3.5 text-[#5C856A] mt-0.5" /> {t('templates14WorkspaceBilling.featureEntSupport')}</li>
            </ul>
            <Button className="w-full">{t('templates14WorkspaceBilling.upgradeButton')}</Button>
          </div>
        </div>
      </Modal>

      {/* Cancel Plan Modal */}
      <Modal
        isOpen={isCancelOpen}
        onClose={() => setIsCancelOpen(false)}
        title={t('templates14WorkspaceBilling.cancelSubscriptionTitle')}
        description={t('templates14WorkspaceBilling.cancelSubscriptionDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsCancelOpen(false)}>{t('templates14WorkspaceBilling.keepPlan')}</Button>
            <Button variant="destructive" onClick={() => setIsCancelOpen(false)}>{t('templates14WorkspaceBilling.confirmCancellation')}</Button>
          </>
        }
      >
         <Alert variant="warning" title={t('templates14WorkspaceBilling.warningTitle')}>
           {t('templates14WorkspaceBilling.downgradeWarningBody')}
         </Alert>
      </Modal>

    </PageContainer>
  );
};


// --- WORKSPACE MEMBERS PAGE ---
const MOCK_MEMBERS = [
  { id: 'm1', name: 'Admin User', email: 'admin@kaori.io', role: 'Owner', status: 'Active', lastActive: 'Now', joinedAt: 'Oct 12, 2026' },
  { id: 'm2', name: 'Sarah Jenkins', email: 'sarah@kaori.io', role: 'Admin', status: 'Active', lastActive: '2 hours ago', joinedAt: 'Oct 15, 2026' },
  { id: 'm3', name: 'Mike Chen', email: 'mike@kaori.io', role: 'Member', status: 'Pending', lastActive: '-', joinedAt: 'Oct 20, 2026' },
  { id: 'm4', name: 'Emily Davis', email: 'emily@kaori.io', role: 'Viewer', status: 'Active', lastActive: '1 day ago', joinedAt: 'Oct 22, 2026' },
];

const MemberActionsDropdown = ({  member, onRemove  }: any) => {
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
      <button 
        onClick={() => setIsOpen(!isOpen)} 
        className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors"
      >
        <MoreVertical className="w-4 h-4"/>
      </button>
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 animate-in fade-in zoom-in-95 duration-100">
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Shield className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates14WorkspaceBilling.changeRole')}
          </button>

          {member.status === 'Pending' && (
            <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
              <Send className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates14WorkspaceBilling.resendInvite')}
            </button>
          )}

          {member.role === 'Owner' && (
            <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
              <Key className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates14WorkspaceBilling.transferOwnership')}
            </button>
          )}

          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          <button
            onClick={() => { onRemove(member); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium"
          >
            <Trash2 className="w-4 h-4 opacity-80"/> {t('templates14WorkspaceBilling.removeMemberAction')}
          </button>
        </div>
      )}
    </div>
  );
};

const WorkspaceMembersPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  
  const [members, setMembers] = useState(MOCK_MEMBERS);
  const [isLoading, setIsLoading] = useState(true);
  
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  
  const [memberToRemove, setMemberToRemove] = useState(null);
  const [removeError, setRemoveError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const handleRemove = () => {
    if (memberToRemove?.role === 'Owner') {
      const ownerCount = members.filter(m => m.role === 'Owner').length;
      if (ownerCount <= 1) {
        setRemoveError(t('templates14WorkspaceBilling.errCannotRemoveLastOwner'));
        return;
      }
    }
    setMembers(prev => prev.filter(m => m.id !== memberToRemove.id));
    setMemberToRemove(null);
    setRemoveError('');
  };

  const handleInvite = () => {
    if (!inviteEmail) return;
    const newMember = {
      id: `m${Date.now()}`,
      name: inviteEmail.split('@')[0],
      email: inviteEmail,
      role: 'Member',
      status: 'Pending',
      lastActive: '-',
      joinedAt: 'Just now'
    };
    setMembers([newMember, ...members]);
    setIsInviteOpen(false);
    setInviteEmail('');
  };

  const filteredMembers = members.filter(m => {
    const matchesSearch = m.name.toLowerCase().includes(search.toLowerCase()) || m.email.toLowerCase().includes(search.toLowerCase());
    const matchesRole = roleFilter === 'all' || m.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || m.status === statusFilter;
    return matchesSearch && matchesRole && matchesStatus;
  });

  const getRoleBadgeVariant = (role) => {
    if (role === 'Owner') return 'current';
    if (role === 'Admin') return 'operational';
    if (role === 'Member') return 'default';
    return 'default';
  };

  const mappedData = filteredMembers.map(m => [
    <div key="member-info" className="flex items-center gap-3">
       <div className="w-8 h-8 rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center text-xs font-medium text-[var(--primary-gold)]">
         {m.name.charAt(0).toUpperCase()}
       </div>
       <div>
         <div className="font-medium text-[var(--text-primary)] flex items-center gap-2">
           {m.name} 
           {m.id === 'm1' && <span className="text-[10px] bg-[var(--bg-app)] border border-[var(--border-color)] px-1.5 py-0.5 rounded text-[var(--text-secondary)]">{t('templates14WorkspaceBilling.youBadge')}</span>}
         </div>
         <div className="text-xs text-[var(--text-secondary)] mt-0.5">{m.email}</div>
       </div>
    </div>,
    <Badge key="member-role" variant={getRoleBadgeVariant(m.role)}>{m.role}</Badge>,
    <Badge key="member-status" variant={m.status === 'Active' ? 'operational' : 'warning'}>{m.status}</Badge>,
    <span key="member-last" className="text-[var(--text-secondary)] whitespace-nowrap">{m.lastActive}</span>,
    <span key="member-joined" className="text-[var(--text-secondary)] whitespace-nowrap">{m.joinedAt}</span>,
    <MemberActionsDropdown key="member-actions" member={m} onRemove={setMemberToRemove} />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        showBack
        onBack={() => setActiveRoute('workspace-details')}
        title={t('templates14WorkspaceBilling.membersTitle')}
        subtitle={t('templates14WorkspaceBilling.membersSubtitle', { workspace: 'Production AI' })}
        actions={
          <Button onClick={() => setIsInviteOpen(true)}>
            <UserPlus className="w-4 h-4 mr-2"/> {t('templates14WorkspaceBilling.inviteMember')}
          </Button>
        }
      />

      <Section>
        {/* Filters Bar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 bg-[var(--bg-card)] p-4 rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm">
          <div className="relative w-full sm:w-72 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              className="h-10 w-full pl-9 pr-3 rounded-md-custom border border-[var(--border-color)] bg-white text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
              placeholder={t('templates14WorkspaceBilling.searchByNameEmail')}
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex w-full sm:w-auto gap-3 shrink-0">
            <div className="w-full sm:w-36">
              <Select
                value={roleFilter}
                onChange={setRoleFilter}
                options={[
                  {label: t('templates14WorkspaceBilling.allRoles'), value: 'all'},
                  {label: t('templates14WorkspaceBilling.roleOwner'), value: 'Owner'},
                  {label: t('templates14WorkspaceBilling.roleAdmin'), value: 'Admin'},
                  {label: t('templates14WorkspaceBilling.roleMember'), value: 'Member'},
                  {label: t('templates14WorkspaceBilling.roleViewer'), value: 'Viewer'}
                ]}
                placeholder={t('templates14WorkspaceBilling.rolePlaceholder')}
              />
            </div>
            <div className="w-full sm:w-36">
              <Select
                value={statusFilter}
                onChange={setStatusFilter}
                options={[{label: t('templates14WorkspaceBilling.allStatuses'), value: 'all'}, {label: t('templates14WorkspaceBilling.statusActive'), value: 'Active'}, {label: t('templates14WorkspaceBilling.statusPending'), value: 'Pending'}]}
                placeholder={t('templates14WorkspaceBilling.statusPlaceholder')}
              />
            </div>
          </div>
          {(search || roleFilter !== 'all' || statusFilter !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setRoleFilter('all'); setStatusFilter('all');}} className="px-3">
              {t('templates14WorkspaceBilling.clearFilters')}
            </Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable
          columns={[t('templates14WorkspaceBilling.colName'), t('templates14WorkspaceBilling.rolePlaceholder'), t('templates14WorkspaceBilling.labelStatus'), t('templates14WorkspaceBilling.colLastActive'), t('templates14WorkspaceBilling.colJoined'), ""]}
          data={mappedData}
          loading={isLoading}
        />
      </Section>

      {/* Invite Modal */}
      <Modal
        isOpen={isInviteOpen}
        onClose={() => setIsInviteOpen(false)}
        title={t('templates14WorkspaceBilling.inviteMemberModalTitle')}
        description={t('templates14WorkspaceBilling.inviteMemberModalDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsInviteOpen(false)}>{t('templates14WorkspaceBilling.cancel')}</Button>
            <Button onClick={handleInvite}><Mail className="w-4 h-4 mr-2"/> {t('templates14WorkspaceBilling.sendInvite')}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label={t('templates14WorkspaceBilling.emailAddress')}
            placeholder="colleague@company.com"
            value={inviteEmail}
            onChange={e => setInviteEmail(e.target.value)}
          />
          <Select
            label={t('templates14WorkspaceBilling.workspaceRole')}
            placeholder={t('templates14WorkspaceBilling.selectARole')}
            options={[
              {label: t('templates14WorkspaceBilling.roleAdmin'), value: 'admin'},
              {label: t('templates14WorkspaceBilling.roleMember'), value: 'member'},
              {label: t('templates14WorkspaceBilling.roleViewer'), value: 'viewer'}
            ]}
            value="member"
            onChange={() => {}}
          />
          <Alert variant="info" className="mt-2">
            {t('templates14WorkspaceBilling.inviteInfoAlert')}
          </Alert>
        </div>
      </Modal>

      {/* Remove Confirmation Modal */}
      <Modal
        isOpen={!!memberToRemove}
        onClose={() => { setMemberToRemove(null); setRemoveError(''); }}
        title={t('templates14WorkspaceBilling.removeMemberTitle')}
        description={t('templates14WorkspaceBilling.removeMemberDesc', { name: memberToRemove?.name })}
        footer={
          <>
            <Button variant="outline" onClick={() => { setMemberToRemove(null); setRemoveError(''); }}>{t('templates14WorkspaceBilling.cancel')}</Button>
            <Button variant="destructive" onClick={handleRemove}>{t('templates14WorkspaceBilling.removeMemberTitle')}</Button>
          </>
        }
      >
        {removeError && (
          <Alert variant="error" className="mb-4">
            {removeError}
          </Alert>
        )}
        <div className="text-sm text-[var(--text-secondary)]">
          {t('templates14WorkspaceBilling.removeMemberUndoNotice')}
        </div>
      </Modal>

    </PageContainer>
  );
};

// --- WORKSPACE OVERVIEW PAGE ---
const WorkspaceOverviewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader
        showBack
        onBack={() => setActiveRoute('workspaces')}
        title="Production AI"
        subtitle={t('templates14WorkspaceBilling.workspaceOverviewSubtitle', { wsId: 'ws_prod_01' })}
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Edit2 className="w-4 h-4 mr-2"/> {t('templates14WorkspaceBilling.editDetails')}</Button>
            <Button variant="outline" className="hidden sm:flex" onClick={() => setActiveRoute('workspace-members')}><Users className="w-4 h-4 mr-2"/> {t('templates14WorkspaceBilling.manageMembers')}</Button>
            <Button variant="tertiary" size="icon"><MoreVertical className="w-4 h-4" /></Button>
          </>
        }
      />

      <Section>
        <Card className="p-5 sm:p-6 overflow-hidden relative">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
           <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6 relative z-10">
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates14WorkspaceBilling.labelStatus')}</p>
                <Badge variant="operational" className="py-1">{t('templates14WorkspaceBilling.statusActive')}</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates14WorkspaceBilling.labelPlan')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{t('templates14WorkspaceBilling.planEnterprise')}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates14WorkspaceBilling.labelRegion')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">US-East</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates14WorkspaceBilling.labelCreated')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">Oct 12, 2026</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates14WorkspaceBilling.labelOwner')}</p>
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
          <MetricCard title={t('templates14WorkspaceBilling.metricApiRequestsToday')} value="124.5K" trend="+5.2%" isUp={true} />
          <MetricCard title={t('templates14WorkspaceBilling.activeUsersTitle')} value="14" trend="0%" />
          <MetricCard title={t('templates14WorkspaceBilling.metricErrorRate')} value="0.01%" trend="-0.04%" isUp={false} inverseGood={true} />
          <MetricCard title={t('templates14WorkspaceBilling.storageUsedTitle')} value="84 GB" trend="+2.1%" isUp={true} />
        </div>
      </Section>

      <Section>
        <Tabs defaultValue="overview" tabs={[
          {
            id: 'overview',
            label: t('templates14WorkspaceBilling.tabOverview'),
            content: (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.recentActivity')}</h3>
                     <Button variant="tertiary" size="sm">{t('templates14WorkspaceBilling.viewAll')}</Button>
                  </div>
                  <DataTable
                    pagination={false}
                    columns={[t('templates14WorkspaceBilling.colEvent'), t('templates14WorkspaceBilling.colActor'), t('templates14WorkspaceBilling.colTime')]}
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
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.alertsHeading')}</h3>
                     <Alert variant="success" title={t('templates14WorkspaceBilling.healthyTitle')}>{t('templates14WorkspaceBilling.noIssuesDetected')}</Alert>
                   </div>
                   <div className="space-y-4">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.quickActionsHeading')}</h3>
                     <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm flex flex-col gap-2">
                        <Button variant="outline" className="w-full justify-start"><Key className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> {t('templates14WorkspaceBilling.generateApiKey')}</Button>
                        <Button variant="outline" className="w-full justify-start" onClick={() => setActiveRoute('workspace-members')}><UserPlus className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> {t('templates14WorkspaceBilling.inviteUser')}</Button>
                        <Button variant="outline" className="w-full justify-start" onClick={() => setActiveRoute('billing')}><CreditCard className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> {t('templates14WorkspaceBilling.manageBilling')}</Button>
                     </div>
                   </div>
                </div>
              </div>
            )
          },
          {
            id: 'activity',
            label: t('templates14WorkspaceBilling.tabActivity'),
            content: (
               <DataTable
                columns={[t('templates14WorkspaceBilling.colEvent'), t('templates14WorkspaceBilling.colResource'), t('templates14WorkspaceBilling.colActor'), t('templates14WorkspaceBilling.colTime')]}
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
            label: t('templates14WorkspaceBilling.tabUsage'),
            content: (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center shrink-0">
                      <Zap className="w-5 h-5 text-[var(--text-secondary)]" />
                    </div>
                    <div>
                       <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.apiCallsTitle')}</h3>
                       <p className="text-xs text-[var(--text-secondary)]">{t('templates14WorkspaceBilling.last30Days')}</p>
                    </div>
                  </div>
                  <div className="text-3xl font-semibold text-[var(--text-primary)]">2.4M</div>
                  <div className="text-sm text-[var(--text-secondary)] mt-2">{t('templates14WorkspaceBilling.enterpriseLimitPercent20M')}</div>
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
                       <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates14WorkspaceBilling.storageTitle')}</h3>
                       <p className="text-xs text-[var(--text-secondary)]">{t('templates14WorkspaceBilling.currentUsageLabel')}</p>
                    </div>
                  </div>
                  <div className="text-3xl font-semibold text-[var(--text-primary)]">84 GB</div>
                  <div className="text-sm text-[var(--text-secondary)] mt-2">{t('templates14WorkspaceBilling.enterpriseLimitPercent500GB')}</div>
                  <div className="w-full bg-[var(--bg-app)] rounded-full h-2 mt-4 border border-[var(--border-color)] overflow-hidden">
                     <div className="bg-[#5C856A] h-2 rounded-full" style={{width: '16%'}}></div>
                  </div>
                </Card>
              </div>
            )
          },
          { id: 'keys', label: t('templates14WorkspaceBilling.navApiKeys'), content: <Alert variant="info" title={t('templates14WorkspaceBilling.keysTabTitle')}>{t('templates14WorkspaceBilling.manageApiKeysHere')}</Alert> },
          { id: 'members', label: t('templates14WorkspaceBilling.membersTitle'), content: (
            <Card className="p-8 text-center flex flex-col items-center">
              <Users className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
              <h3 className="text-sm font-medium text-[var(--text-primary)]">{t('templates14WorkspaceBilling.workspaceMembersHeading')}</h3>
              <p className="text-xs text-[var(--text-secondary)] mt-1 mb-4">{t('templates14WorkspaceBilling.manageActiveMembersRoles')}</p>
              <Button onClick={() => setActiveRoute('workspace-members')}>{t('templates14WorkspaceBilling.openMembersManagement')}</Button>
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

const RowActionsDropdown = ({  workspaceId, onViewDetails  }: any) => {
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
            <Eye className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates14WorkspaceBilling.viewDetails')}
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Edit2 className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates14WorkspaceBilling.editWorkspace')}
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Users className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates14WorkspaceBilling.manageMembers')}
          </button>
          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium">
            <Ban className="w-4 h-4 opacity-80"/> {t('templates14WorkspaceBilling.suspend')}
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium">
            <Trash2 className="w-4 h-4 opacity-80"/> {t('templates14WorkspaceBilling.deleteAction')}
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
  const [isCreateOpen, setIsCreateOpen] = useState(false);

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
    <RowActionsDropdown key="ws-actions" workspaceId={ws.id} onViewDetails={() => setActiveRoute('workspace-details')} />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        title={t('templates14WorkspaceBilling.navWorkspaces')}
        subtitle={t('templates14WorkspaceBilling.workspacesSubtitle')}
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Search className="w-4 h-4 mr-2"/> {t('templates14WorkspaceBilling.importAction')}</Button>
            <Button onClick={() => setIsCreateOpen(true)}><Plus className="w-4 h-4 mr-2"/> {t('templates14WorkspaceBilling.createWorkspace')}</Button>
          </>
        }
      />

      <Section>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 bg-[var(--bg-card)] p-4 rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm">
          <div className="relative w-full sm:w-72 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              className="h-10 w-full pl-9 pr-3 rounded-md-custom border border-[var(--border-color)] bg-white text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
              placeholder={t('templates14WorkspaceBilling.searchWorkspacesPlaceholder')}
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex w-full sm:w-auto gap-3 shrink-0">
            <div className="w-full sm:w-36">
              <Select value={status} onChange={setStatus} options={[{label: t('templates14WorkspaceBilling.allStatuses'), value: 'all'}, {label: t('templates14WorkspaceBilling.statusActive'), value: 'Active'}, {label: t('templates14WorkspaceBilling.statusSuspended'), value: 'Suspended'}]} placeholder={t('templates14WorkspaceBilling.statusPlaceholder')} />
            </div>
            <div className="w-full sm:w-36">
              <Select value={plan} onChange={setPlan} options={[{label: t('templates14WorkspaceBilling.allPlans'), value: 'all'}, {label: t('templates14WorkspaceBilling.planFree'), value: 'Free'}, {label: t('templates14WorkspaceBilling.planPro'), value: 'Pro'}, {label: t('templates14WorkspaceBilling.planEnterprise'), value: 'Enterprise'}]} placeholder={t('templates14WorkspaceBilling.labelPlan')} />
            </div>
          </div>
          {(search || status !== 'all' || plan !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setStatus('all'); setPlan('all');}} className="px-3">{t('templates14WorkspaceBilling.clearFilters')}</Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable columns={[t('templates14WorkspaceBilling.colWorkspace'), t('templates14WorkspaceBilling.labelOwner'), t('templates14WorkspaceBilling.labelPlan'), t('templates14WorkspaceBilling.membersTitle'), t('templates14WorkspaceBilling.colUsage'), t('templates14WorkspaceBilling.labelStatus'), t('templates14WorkspaceBilling.labelCreated'), ""]} data={mappedData} loading={isLoading} />
      </Section>

      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title={t('templates14WorkspaceBilling.createWorkspaceModalTitle')}
        description={t('templates14WorkspaceBilling.createWorkspaceModalDesc')}
        footer={<><Button variant="outline" onClick={() => setIsCreateOpen(false)}>{t('templates14WorkspaceBilling.cancel')}</Button><Button onClick={() => setIsCreateOpen(false)}>{t('templates14WorkspaceBilling.createEnvironment')}</Button></>}
      >
        <div className="space-y-4">
          <Input label={t('templates14WorkspaceBilling.workspaceNameLabel')} placeholder={t('templates14WorkspaceBilling.workspaceNamePlaceholder', { example: 'Acme Corp Production' })} />
          <Select label={t('templates14WorkspaceBilling.planTierLabel')} placeholder={t('templates14WorkspaceBilling.selectPlanPlaceholder')} options={[{label: t('templates14WorkspaceBilling.planFreeTier'), value: 'free'}, {label: t('templates14WorkspaceBilling.planPro'), value: 'pro'}, {label: t('templates14WorkspaceBilling.planEnterprise'), value: 'enterprise'}]} value="free" onChange={() => {}} />
          <Input label={t('templates14WorkspaceBilling.adminEmailLabel')} placeholder="owner@company.com" helperText={t('templates14WorkspaceBilling.adminEmailHelper')} />
        </div>
      </Modal>

    </PageContainer>
  );
};

// --- REMAINING PREVIOUS PAGES ---
const ComponentsPage = () => {
  const t = useT();
  const [date, setDate] = useState("");
  const [selectVal, setSelectVal] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates14WorkspaceBilling.navComponentLibrary')} subtitle={t('templates14WorkspaceBilling.componentLibrarySubtitle')} actions={<Button>{t('templates14WorkspaceBilling.deploySystem')}</Button>} />
      <Tabs defaultValue="form" tabs={[
        { id: 'form', label: t('templates14WorkspaceBilling.tabFormsInputs'), content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title={t('templates14WorkspaceBilling.buttonsSectionTitle')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)]">
               <div className="flex flex-wrap gap-4 mb-4"><Button variant="primary">{t('templates14WorkspaceBilling.demoPrimary')}</Button><Button variant="secondary">{t('templates14WorkspaceBilling.demoSecondary')}</Button><Button variant="tertiary">{t('templates14WorkspaceBilling.demoGhost')}</Button></div>
               <div className="flex flex-wrap gap-4 items-center"><Button variant="primary" isLoading>{t('templates14WorkspaceBilling.demoLoading')}</Button><Button variant="destructive">{t('templates14WorkspaceBilling.demoDestructive')}</Button><Button variant="primary" size="icon"><Plus className="w-4 h-4"/></Button></div>
             </Section>
             <Section title={t('templates14WorkspaceBilling.inputsSelectsSectionTitle')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] space-y-4">
                <Input label={t('templates14WorkspaceBilling.emailAddress')} placeholder="admin@kaori.io" helperText={t('templates14WorkspaceBilling.neverShareEmailHelper')} />
                <Select label={t('templates14WorkspaceBilling.environmentLabel')} placeholder={t('templates14WorkspaceBilling.selectEnvironmentPlaceholder')} options={[{label: t('templates14WorkspaceBilling.optionProduction'), value: 'prod'}]} value={selectVal} onChange={setSelectVal} />
             </Section>
           </div>
        )},
        { id: 'data', label: t('templates14WorkspaceBilling.tabDataDisplay'), content: ( <Alert variant="info" title={t('templates14WorkspaceBilling.dataComponentsTitle')}>{t('templates14WorkspaceBilling.dataComponentsBody')}</Alert> )},
        { id: 'feedback', label: t('templates14WorkspaceBilling.tabFeedbackOverlays'), content: ( <Alert variant="info" title={t('templates14WorkspaceBilling.feedbackComponentsTitle')}>{t('templates14WorkspaceBilling.feedbackComponentsBody')}</Alert> )}
      ]} />
    </PageContainer>
  );
};

const PlatformOverview = () => {
  const t = useT();
  return (
    <PageContainer maxWidth="default">
      <PageHeader title={t('templates14WorkspaceBilling.platformOverviewTitle')} subtitle={t('templates14WorkspaceBilling.platformOverviewSubtitle')} actions={<Button variant="outline"><RefreshCw className="w-4 h-4 mr-2" /> {t('templates14WorkspaceBilling.refreshData')}</Button>} />
      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates14WorkspaceBilling.metricTotalWorkspaces')} value="124" trend="+4" isUp={true} />
          <MetricCard title={t('templates14WorkspaceBilling.activeUsersTitle')} value="1,892" trend="+12.5%" isUp={true} />
          <MetricCard title={t('templates14WorkspaceBilling.apiRequestsTitle')} value="2.4M" trend="+5.2%" isUp={true} />
          <MetricCard title={t('templates14WorkspaceBilling.metricFailedRequests')} value="482" trend="-18%" isUp={false} inverseGood={true} />
        </div>
      </Section>
      <Section title={t('templates14WorkspaceBilling.recentActivity')}>
         <DataTable
            columns={[t('templates14WorkspaceBilling.colEvent'), t('templates14WorkspaceBilling.colWorkspace'), t('templates14WorkspaceBilling.colTime')]}
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

const SessionsPage = () => {
  const t = useT();
  return (
    <PageContainer maxWidth="narrow">
      <PageHeader title={t('templates14WorkspaceBilling.activeSessionsTitle')} subtitle={t('templates14WorkspaceBilling.activeSessionsSubtitle')} actions={<Button variant="outline">{t('templates14WorkspaceBilling.signOutAll')}</Button>} />
      <Section title={t('templates14WorkspaceBilling.navSecuritySessions')}>
        <Card className="p-8 text-center flex flex-col items-center">
          <Shield className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
          <h3 className="text-sm font-medium text-[var(--text-primary)]">{t('templates14WorkspaceBilling.navSecuritySessions')}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates14WorkspaceBilling.manageActiveLoginsHere')}</p>
        </Card>
      </Section>
    </PageContainer>
  );
};


// ==========================================
// MAIN PLATFORM SHELL COMPONENT
// ==========================================

export default function KaoriPlatformShell() {
  const t = useT();
  const NAVIGATION_CONFIG = getNavigationConfig(t);
  const [activeRoute, setActiveRoute] = useState('billing');
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
             activeRoute === 'overview' ? <PlatformOverview /> : 
             activeRoute === 'sessions' ? <SessionsPage /> : (
              <PageContainer maxWidth="narrow">
                <PageHeader title={t('templates14WorkspaceBilling.moduleSuffix', { label: NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label })} subtitle={t('templates14WorkspaceBilling.moduleBuildingSubtitle')} />
                <Section>
                  <Card className="flex flex-col items-center justify-center py-20 px-4 text-center border-dashed bg-[var(--bg-card)]/50 mx-auto w-full animate-in fade-in duration-300">
                    <div className="w-12 h-12 rounded-lg-custom bg-[var(--bg-sidebar)] flex items-center justify-center border border-[var(--border-color)] mb-4">
                      {React.createElement(NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.icon || LayoutDashboard, { className: 'w-6 h-6 text-[var(--text-secondary)]' })}
                    </div>
                    <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">{t('templates14WorkspaceBilling.workInProgress')}</h3>
                    <p className="text-sm text-[var(--text-secondary)] max-w-sm">{t('templates14WorkspaceBilling.contentWillPopulate', { route: activeRoute })}</p>
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
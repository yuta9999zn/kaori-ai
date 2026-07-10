// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 19Key Id New .jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState, useEffect, useRef } from 'react';
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
  AlertTriangle,
  Copy,
  RefreshCcw
} from 'lucide-react';
import { useT } from '@/lib/i18n/provider';

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
  const resolvedPlaceholder = placeholder || t('templates19PlatformKeyNew.selectDefaultPlaceholder');
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
        {selectedOption ? selectedOption.label : resolvedPlaceholder}
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
  const resolvedPlaceholder = placeholder || t('templates19PlatformKeyNew.datePickerDefaultPlaceholder');
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
        {date ? date : resolvedPlaceholder}
      </button>
      {isOpen && (
        <div className="absolute top-full left-0 z-50 mt-1 p-3 bg-white rounded-md-custom border border-[var(--border-color)] shadow-soft-md animate-in fade-in zoom-in-95 duration-150 w-[280px]">
           <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-semibold text-[var(--text-primary)]">{t('templates19PlatformKeyNew.calendarMonthYear')}</span>
              <div className="flex gap-1">
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronLeft className="w-4 h-4 text-[var(--text-secondary)]"/></button>
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronRight className="w-4 h-4 text-[var(--text-secondary)]"/></button>
              </div>
           </div>
           <div className="grid grid-cols-7 gap-1 text-center text-xs text-[var(--text-secondary)] mb-2">
             {[
               t('templates19PlatformKeyNew.weekdaySun'),
               t('templates19PlatformKeyNew.weekdayMon'),
               t('templates19PlatformKeyNew.weekdayTue'),
               t('templates19PlatformKeyNew.weekdayWed'),
               t('templates19PlatformKeyNew.weekdayThu'),
               t('templates19PlatformKeyNew.weekdayFri'),
               t('templates19PlatformKeyNew.weekdaySat'),
             ].map(d => <div key={d}>{d}</div>)}
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
        <div className="text-xs text-[var(--text-secondary)] mt-1 opacity-75">{t('templates19PlatformKeyNew.vsYesterday')}</div>
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
                  <span className="text-sm font-medium text-[var(--text-primary)]">{t('templates19PlatformKeyNew.noResultsFound')}</span>
                  <span className="text-xs text-[var(--text-secondary)]">{t('templates19PlatformKeyNew.tryAdjustingFilters')}</span>
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
          <span className="text-xs text-[var(--text-secondary)]">{t('templates19PlatformKeyNew.showingResults', { count: data.length })}</span>
          <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled>{t('templates19PlatformKeyNew.previous')}</Button>
              <Button variant="outline" size="sm">{t('templates19PlatformKeyNew.next')}</Button>
          </div>
        </div>
      )}
    </div>
  );
};

// --- MODAL ---
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

// --- COPY BUTTON HELPER ---
const CopyButton = ({  text, className  }: any) => {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button 
      onClick={handleCopy} 
      className={cn("p-1 hover:bg-[var(--bg-app)] rounded transition-colors text-[var(--text-secondary)] hover:text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/50", className)}
      aria-label={t('templates19PlatformKeyNew.copyToClipboard')}
    >
      {copied ? <Check className="w-3.5 h-3.5 text-[#5C856A]" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

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
    group: t('templates19PlatformKeyNew.navGroupMain'),
    items: [
      { id: 'overview', label: t('templates19PlatformKeyNew.navPlatformHealth'), icon: LayoutDashboard, route: '/platform' },
      { id: 'workspaces', label: t('templates19PlatformKeyNew.navWorkspaces'), icon: Briefcase, route: '/platform/workspaces', badge: '4' },
    ]
  },
  {
    group: t('templates19PlatformKeyNew.navGroupManagement'),
    items: [
      { id: 'keys', label: t('templates19PlatformKeyNew.navApiKeys'), icon: Key, route: '/platform/keys' },
      { id: 'billing', label: t('templates19PlatformKeyNew.navBilling'), icon: CreditCard, route: '/platform/billing' },
      { id: 'admin', label: t('templates19PlatformKeyNew.navAdmins'), icon: Shield, route: '/platform/admins', role: 'admin' },
    ]
  },
  {
    group: t('templates19PlatformKeyNew.navGroupSystem'),
    items: [
      { id: 'components', label: t('templates19PlatformKeyNew.navComponentLibrary'), icon: Component, route: '/platform/components' },
      { id: 'sessions', label: t('templates19PlatformKeyNew.navSecuritySessions'), icon: Settings, route: '/p1/auth/sessions' },
    ]
  }
];

// --- HEADER SUB-COMPONENTS ---
const EnvBadge = ({  env = 'production'  }: any) => {
  const t = useT();
  const config = {
    production: "bg-[var(--primary-gold)]/15 text-[#9E814D] border-[var(--primary-gold)]/30",
    staging: "bg-white text-[var(--text-secondary)] border-[var(--border-color)]",
    development: "bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]"
  };
  const labels = {
    production: t('templates19PlatformKeyNew.envProduction'),
    staging: t('templates19PlatformKeyNew.envStaging'),
    development: t('templates19PlatformKeyNew.envDevelopment'),
  };
  return (
    <span className={`hidden md:inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${config[env]}`}>
      {labels[env] || env}
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
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates19PlatformKeyNew.notifications')}</h3>
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
              <Shield className="w-4 h-4 text-[var(--text-secondary)]" /> {t('templates19PlatformKeyNew.navSecuritySessions')}
            </button>
          </div>
          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" />
          <div className="p-1.5">
            <button className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] transition-colors flex items-center gap-2 font-medium">
              <LogOut className="w-4 h-4" /> {t('templates19PlatformKeyNew.signOut')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const GlobalHeader = ({  activeRoute, setActiveRoute, setIsMobileMenuOpen  }: any) => {
  const t = useT();
  let routeLabel = getNavigationConfig(t).flatMap(g => g.items).find(n => n.id === activeRoute)?.label;
  if (activeRoute === 'workspace-details') routeLabel = t('templates19PlatformKeyNew.breadcrumbWorkspacesOverview');
  else if (activeRoute === 'workspace-members') routeLabel = t('templates19PlatformKeyNew.breadcrumbWorkspacesMembers');
  else if (activeRoute === 'billing') routeLabel = t('templates19PlatformKeyNew.breadcrumbWorkspacesBilling');
  else if (activeRoute === 'audit-logs') routeLabel = t('templates19PlatformKeyNew.breadcrumbWorkspacesAuditLogs');
  else if (activeRoute === 'workspace-new') routeLabel = t('templates19PlatformKeyNew.breadcrumbWorkspacesNewWorkspace');
  else if (activeRoute === 'workspace-edit') routeLabel = t('templates19PlatformKeyNew.breadcrumbWorkspacesSettings');
  else if (activeRoute === 'keys-new') routeLabel = t('templates19PlatformKeyNew.breadcrumbApiKeysCreateKey');
  else if (!routeLabel) routeLabel = activeRoute;

  return (
    <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/90 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6 transition-all duration-300">
      <div className="flex items-center gap-4">
        <button className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]" onClick={() => setIsMobileMenuOpen(true)}>
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:flex items-center text-sm font-medium">
          <span className="text-[var(--text-secondary)]">{t('templates19PlatformKeyNew.breadcrumbPlatform')}</span>
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
              <input type="text" placeholder={t('templates19PlatformKeyNew.searchPlaceholder')} className="h-8 w-48 pl-8 pr-10 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm" />
            </div>
            <Button variant="outline" size="sm" onClick={() => setActiveRoute('workspace-new')} className="hidden md:flex"><Plus className="w-3.5 h-3.5 mr-1.5" /> {t('templates19PlatformKeyNew.headerWorkspaceBtn')}</Button>
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
  const navigationConfig = getNavigationConfig(t);
  const collapsed = isCollapsed && !isMobile;
  const currentHighlight = (activeRoute === 'workspace-details' || activeRoute === 'workspace-members' || activeRoute === 'billing' || activeRoute === 'audit-logs' || activeRoute === 'workspace-new' || activeRoute === 'workspace-edit') ? 'workspaces' : (activeRoute === 'keys-new' ? 'keys' : activeRoute);

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
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mt-0.5">{t('templates19PlatformKeyNew.breadcrumbPlatform')}</span>
          </div>
        )}
      </div>

      <nav aria-label={t('templates19PlatformKeyNew.mainNavigationAriaLabel')} className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 space-y-6">
        {navigationConfig.map((group, idx) => (
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
            {!collapsed && <span className="text-xs font-medium">{t('templates19PlatformKeyNew.collapseSidebar')}</span>}
          </button>
        )}
      </div>
    </aside>
  );
};


// ==========================================
// 4. VIEWS & PAGES
// ==========================================

// --- API KEYS PAGE ---

const MOCK_API_KEYS = [
  { id: 'key_1', name: 'Production Backend', keyHash: '982b3a1c8f0e4d5a', scope: 'Full Access', status: 'Active', created: 'Oct 01, 2026', lastUsed: '2 mins ago' },
  { id: 'key_2', name: 'Read-only Analytics', keyHash: '1122334455667788', scope: 'Read-only', status: 'Active', created: 'Oct 10, 2026', lastUsed: '5 hours ago' },
  { id: 'key_3', name: 'Old Staging Key', keyHash: 'abcdef1234567890', scope: 'Full Access', status: 'Revoked', created: 'Jan 15, 2026', lastUsed: 'Sep 30, 2026' },
];

const maskKey = (hash) => {
  return `sk_live_••••••••${hash.substring(hash.length - 4)}`;
};

const KeyActionsDropdown = ({  apiKey, onRevoke, onRotate  }: any) => {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<any>(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative flex justify-end" ref={dropdownRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)} 
        className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50"
        aria-label={t('templates19PlatformKeyNew.keyActions')}
      >
        <MoreVertical className="w-4 h-4"/>
      </button>
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-44 bg-[var(--bg-card)] border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 animate-in fade-in zoom-in-95 duration-100">
          <button
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
          >
            <Eye className="w-4 h-4 text-[var(--text-secondary)]" /> {t('templates19PlatformKeyNew.viewDetails')}
          </button>

          {apiKey.status === 'Active' && (
            <>
              <button
                onClick={() => { onRotate(apiKey); setIsOpen(false); }}
                className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
              >
                <RefreshCcw className="w-4 h-4 text-[var(--text-secondary)]" /> {t('templates19PlatformKeyNew.rotateKeyLower')}
              </button>

              <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />

              <button
                onClick={() => { onRevoke(apiKey); setIsOpen(false); }}
                className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium"
              >
                <Ban className="w-4 h-4 opacity-80" /> {t('templates19PlatformKeyNew.revokeKeyLower')}
              </button>
            </>
          )}

          {apiKey.status === 'Revoked' && (
            <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium mt-1">
              <Trash2 className="w-4 h-4 opacity-80" /> {t('templates19PlatformKeyNew.deleteAction')}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

const ApiKeysPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [keys, setKeys] = useState(MOCK_API_KEYS);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isLoading, setIsLoading] = useState(true);

  // Modal States
  const [isRevokeOpen, setIsRevokeOpen] = useState(false);
  const [isRotateOpen, setIsRotateOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState(null);
  
  // Rotate State
  const [generatedKey, setGeneratedKey] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const handleRevokeConfirm = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 600));
    setKeys(prev => prev.map(k => k.id === selectedKey.id ? { ...k, status: 'Revoked' } : k));
    setIsProcessing(false);
    setIsRevokeOpen(false);
    setSelectedKey(null);
  };

  const handleRotateConfirm = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 800));
    
    const fullSecret = `sk_live_${Math.random().toString(36).substring(2, 18)}`;
    
    setKeys(prev => prev.map(k => {
      if (k.id === selectedKey.id) {
         return { ...k, keyHash: fullSecret.substring(fullSecret.length - 16), created: 'Just now', lastUsed: 'Never' };
      }
      return k;
    }));
    
    setGeneratedKey(fullSecret);
    setIsProcessing(false);
  };

  const filteredKeys = keys.filter(k => {
    const matchesSearch = k.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || k.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const tableData = filteredKeys.map(k => [
    <span key="name" className="font-medium text-[var(--text-primary)]">{k.name}</span>,
    <div key="key" className="flex items-center gap-2">
      <span className="font-mono text-xs bg-[var(--bg-app)] px-2 py-1 rounded border border-[var(--border-color)] text-[var(--text-secondary)]">
        {maskKey(k.keyHash)}
      </span>
      <CopyButton text={maskKey(k.keyHash)} />
    </div>,
    <span key="scope" className="text-[var(--text-secondary)]">{k.scope}</span>,
    <span key="created" className="text-[var(--text-secondary)] whitespace-nowrap">{k.created}</span>,
    <span key="lastUsed" className="text-[var(--text-secondary)] whitespace-nowrap">{k.lastUsed}</span>,
    <Badge key="status" variant={k.status === 'Active' ? 'success' : 'default'}>{k.status}</Badge>,
    <KeyActionsDropdown 
      key="actions" 
      apiKey={k} 
      onRevoke={(key: any) => { setSelectedKey(key); setIsRevokeOpen(true); }}
      onRotate={(key: any) => { setSelectedKey(key); setIsRotateOpen(true); }}
    />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        title={t('templates19PlatformKeyNew.apiKeysTitle')}
        subtitle={t('templates19PlatformKeyNew.apiKeysSubtitle')}
        actions={
          <Button onClick={() => setActiveRoute('keys-new')}>
            <Plus className="w-4 h-4 mr-2" /> {t('templates19PlatformKeyNew.createKey')}
          </Button>
        }
      />

      <Section>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 bg-[var(--bg-card)] p-4 rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm">
          <div className="relative w-full sm:w-72 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              className="h-10 w-full pl-9 pr-3 rounded-md-custom border border-[var(--border-color)] bg-white text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
              placeholder={t('templates19PlatformKeyNew.searchKeyNamePlaceholder')}
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex w-full sm:w-auto gap-3 shrink-0">
            <div className="w-full sm:w-40">
              <Select 
                value={statusFilter} 
                onChange={setStatusFilter} 
                options={[{label: t('templates19PlatformKeyNew.allStatuses'), value: 'all'}, {label: t('templates19PlatformKeyNew.statusActive'), value: 'Active'}, {label: t('templates19PlatformKeyNew.statusRevoked'), value: 'Revoked'}]}
                placeholder={t('templates19PlatformKeyNew.statusPlaceholder')}
              />
            </div>
          </div>
          {(search || statusFilter !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setStatusFilter('all');}} className="px-3">{t('templates19PlatformKeyNew.clearFilters')}</Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable
          columns={[
            t('templates19PlatformKeyNew.colKeyName'),
            t('templates19PlatformKeyNew.colSecretKey'),
            t('templates19PlatformKeyNew.colScope'),
            t('templates19PlatformKeyNew.colCreatedAt'),
            t('templates19PlatformKeyNew.colLastUsed'),
            t('templates19PlatformKeyNew.colStatus'),
            ""
          ]}
          data={tableData}
          loading={isLoading}
        />
      </Section>

      {/* Revoke Key Modal */}
      <Modal
        isOpen={isRevokeOpen}
        onClose={() => !isProcessing && setIsRevokeOpen(false)}
        title={t('templates19PlatformKeyNew.revokeApiKeyTitle')}
        description={t('templates19PlatformKeyNew.revokeConfirmDesc', { name: selectedKey?.name })}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsRevokeOpen(false)} disabled={isProcessing}>{t('templates19PlatformKeyNew.cancel')}</Button>
            <Button variant="destructive" onClick={handleRevokeConfirm} isLoading={isProcessing}>{t('templates19PlatformKeyNew.revokeKeyUpper')}</Button>
          </>
        }
      >
        <Alert variant="error" className="mb-2">
          {t('templates19PlatformKeyNew.revokeIrreversibleWarning')}
        </Alert>
      </Modal>

      {/* Rotate Key Modal */}
      <Modal
        isOpen={isRotateOpen}
        onClose={() => { if(!generatedKey && !isProcessing) setIsRotateOpen(false); }}
        title={generatedKey ? t('templates19PlatformKeyNew.saveNewApiKeyTitle') : t('templates19PlatformKeyNew.rotateApiKeyTitle')}
        description={generatedKey ? t('templates19PlatformKeyNew.rotateSuccessDesc') : t('templates19PlatformKeyNew.rotateConfirmDesc', { name: selectedKey?.name })}
        footer={
          generatedKey ? (
            <Button onClick={() => { setIsRotateOpen(false); setGeneratedKey(null); }} className="w-full">{t('templates19PlatformKeyNew.done')}</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => setIsRotateOpen(false)} disabled={isProcessing}>{t('templates19PlatformKeyNew.cancel')}</Button>
              <Button onClick={handleRotateConfirm} isLoading={isProcessing}>{t('templates19PlatformKeyNew.rotateKeyUpper')}</Button>
            </>
          )
        }
      >
        {!generatedKey ? (
          <Alert variant="warning">
            {t('templates19PlatformKeyNew.rotateInvalidateWarning')}
          </Alert>
        ) : (
          <div className="space-y-4">
            <Alert variant="success" title={t('templates19PlatformKeyNew.keyRotatedSuccessTitle')}>
              {t('templates19PlatformKeyNew.keyRotatedSuccessDesc')}
            </Alert>
            <div className="flex items-center gap-2 p-3 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom">
              <span className="font-mono text-sm text-[var(--text-primary)] flex-1 overflow-x-auto whitespace-nowrap scrollbar-hide select-all">
                {generatedKey}
              </span>
              <CopyButton text={generatedKey} className="shrink-0 bg-white border border-[var(--border-color)] shadow-sm" />
            </div>
          </div>
        )}
      </Modal>

    </PageContainer>
  );
};

const ApiKeyNewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [step, setStep] = useState(1);
  const [isCreating, setIsCreating] = useState(false);
  const [generatedKey, setGeneratedKey] = useState(null);
  const [formData, setFormData] = useState({ name: '', scope: 'Full Access', expiration: 'never' });
  const [errors, setErrors] = useState({});

  const handleCreate = async () => {
    if (!formData.name) {
      setErrors({ name: t('templates19PlatformKeyNew.keyNameRequired') });
      return;
    }
    setIsCreating(true);
    // Simulate API call
    await new Promise(r => setTimeout(r, 1000));
    const fullSecret = `sk_live_${Math.random().toString(36).substring(2, 18)}${Math.random().toString(36).substring(2, 18)}`;
    setGeneratedKey(fullSecret);
    setIsCreating(false);
    setStep(2);
  };

  return (
    <PageContainer maxWidth="narrow" className="pt-8">
       {/* Step 1 */}
       {step === 1 && (
         <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
           <PageHeader
             showBack
             onBack={() => setActiveRoute('keys')}
             title={t('templates19PlatformKeyNew.createApiKeyTitle')}
             subtitle={t('templates19PlatformKeyNew.createApiKeySubtitle')}
           />
           <Card className="p-6 sm:p-8 mt-8 shadow-soft-md">
             <div className="space-y-6">
                <Input
                  label={t('templates19PlatformKeyNew.keyNameLabel')}
                  placeholder={t('templates19PlatformKeyNew.keyNamePlaceholder')}
                  value={formData.name}
                  onChange={e => { setFormData({...formData, name: e.target.value}); setErrors({}); }}
                  error={errors.name}
                  autoFocus
                />
                <Select
                  label={t('templates19PlatformKeyNew.scopeLabel')}
                  options={[{label: t('templates19PlatformKeyNew.scopeFullAccess'), value: 'Full Access'}, {label: t('templates19PlatformKeyNew.scopeReadOnly'), value: 'Read-only'}]}
                  value={formData.scope}
                  onChange={v => setFormData({...formData, scope: v})}
                />
                <Select
                  label={t('templates19PlatformKeyNew.expirationLabel')}
                  options={[{label: t('templates19PlatformKeyNew.expirationNever'), value: 'never'}, {label: t('templates19PlatformKeyNew.expiration30Days'), value: '30'}, {label: t('templates19PlatformKeyNew.expiration90Days'), value: '90'}]}
                  value={formData.expiration}
                  onChange={v => setFormData({...formData, expiration: v})}
                />
             </div>
             <div className="mt-8 pt-6 border-t border-[var(--border-color)] flex items-center justify-between">
                <Button variant="tertiary" onClick={() => setActiveRoute('keys')}>{t('templates19PlatformKeyNew.cancel')}</Button>
                <Button onClick={handleCreate} isLoading={isCreating}>{t('templates19PlatformKeyNew.createKey')}</Button>
             </div>
           </Card>
         </div>
       )}

       {/* Step 2 */}
       {step === 2 && (
         <div className="animate-in fade-in zoom-in-[0.98] duration-500">
           <PageHeader
             title={t('templates19PlatformKeyNew.keyCreatedTitle')}
             subtitle={t('templates19PlatformKeyNew.keyCreatedSubtitle')}
           />
           <Card className="p-6 sm:p-8 mt-8 shadow-soft-md border-[var(--primary-gold)]/30">
             <Alert variant="warning" className="mb-6 bg-[#FDF9F0] border-[#E6C07B]/40">
               <div className="flex items-start gap-2">
                 <div>
                   <h4 className="text-sm font-semibold text-[#9E814D] mb-1">{t('templates19PlatformKeyNew.copyKeyNowTitle')}</h4>
                   <p className="text-xs text-[#9E814D]/90">{t('templates19PlatformKeyNew.copyKeyNowDesc')}</p>
                 </div>
               </div>
             </Alert>

             <div className="space-y-2 mb-8">
               <Label>{t('templates19PlatformKeyNew.secretApiKeyLabel')}</Label>
               <div className="flex items-center gap-3 p-3 sm:p-4 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom shadow-inner">
                 <span className="font-mono text-sm sm:text-base text-[var(--text-primary)] flex-1 overflow-x-auto whitespace-nowrap scrollbar-hide select-all">
                   {generatedKey}
                 </span>
                 <CopyButton text={generatedKey} className="shrink-0 bg-white border border-[var(--border-color)] shadow-sm w-8 h-8 flex items-center justify-center" />
               </div>
             </div>

             <div className="pt-6 border-t border-[var(--border-color)] flex justify-end">
                <Button onClick={() => setActiveRoute('keys')}>{t('templates19PlatformKeyNew.done')}</Button>
             </div>
           </Card>
         </div>
       )}
    </PageContainer>
  )
}

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
            <CheckCircle2 className="w-4 h-4" /> {t('templates19PlatformKeyNew.changesSaved')}
          </div>
        </div>
      )}

      <PageHeader
        showBack
        onBack={() => setActiveRoute('workspace-details')}
        title={t('templates19PlatformKeyNew.workspaceSettingsTitle')}
        subtitle={t('templates19PlatformKeyNew.workspaceSettingsSubtitle')}
        actions={
          <>
            <Button variant="tertiary" onClick={() => setActiveRoute('workspace-details')} className="hidden sm:flex">{t('templates19PlatformKeyNew.cancel')}</Button>
            <Button onClick={handleSave} disabled={!isDirty} isLoading={isSaving}>
              <Save className="w-4 h-4 mr-2" /> {t('templates19PlatformKeyNew.saveChangesLower')}
            </Button>
          </>
        }
      />

      <Tabs defaultValue="general" tabs={[
        {
          id: 'general',
          label: t('templates19PlatformKeyNew.tabGeneral'),
          content: (
            <div className="space-y-8 animate-step">
              <Section>
                <Card className="p-6">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates19PlatformKeyNew.basicInformation')}</h3>
                  <div className="space-y-5">
                    <Input
                      label={t('templates19PlatformKeyNew.workspaceNameLabel')}
                      value={formData.name}
                      onChange={(e: any) => setFormData({...formData, name: e.target.value})}
                    />
                    <Input
                      label={t('templates19PlatformKeyNew.descriptionLabel')}
                      value={formData.description}
                      onChange={(e: any) => setFormData({...formData, description: e.target.value})}
                    />
                    <Input
                      label={t('templates19PlatformKeyNew.deploymentRegionLabel')}
                      value="US East (N. Virginia)"
                      disabled
                      helperText={t('templates19PlatformKeyNew.regionHelperText')}
                    />
                  </div>
                </Card>
              </Section>
              <Section>
                <Card className="p-6">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates19PlatformKeyNew.displaySettings')}</h3>
                  <div className="space-y-5">
                    <Select
                      label={t('templates19PlatformKeyNew.defaultTimezoneLabel')}
                      value={formData.timezone}
                      onChange={(v: any) => setFormData({...formData, timezone: v})}
                      options={[
                        {label: t('templates19PlatformKeyNew.timezoneUtc'), value: 'UTC'},
                        {label: t('templates19PlatformKeyNew.timezonePst'), value: 'PST'},
                        {label: t('templates19PlatformKeyNew.timezoneEst'), value: 'EST'},
                        {label: t('templates19PlatformKeyNew.timezoneCet'), value: 'CET'}
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
          label: t('templates19PlatformKeyNew.tabAdvanced'),
          content: (
            <div className="space-y-8 animate-step">
              <Section>
                <Card className="p-6">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates19PlatformKeyNew.resourceLimits')}</h3>
                  <p className="text-xs text-[var(--text-secondary)] mb-5">{t('templates19PlatformKeyNew.resourceLimitsDesc')}</p>
                  <div className="space-y-5">
                    <Input
                      label={t('templates19PlatformKeyNew.apiRateLimitLabel')}
                      type="number"
                      value={formData.rateLimit}
                      onChange={(e: any) => setFormData({...formData, rateLimit: e.target.value})}
                    />
                    <Input
                      label={t('templates19PlatformKeyNew.storageQuotaLabel')}
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
                      {t('templates19PlatformKeyNew.integrations')} <Badge>{t('templates19PlatformKeyNew.comingSoon')}</Badge>
                    </h3>
                    <p className="text-xs text-[var(--text-secondary)]">{t('templates19PlatformKeyNew.integrationsDesc')}</p>
                 </Card>
              </Section>
            </div>
          )
        },
        {
          id: 'danger',
          label: t('templates19PlatformKeyNew.tabDangerZone'),
          content: (
            <div className="space-y-8 animate-step">
              <Section>
                <Card className="p-6 border-[#D97C7C]/40 bg-[#FDF8F8]">
                  <h3 className="text-sm font-semibold text-[#9B5050] mb-4 border-b border-[#D97C7C]/30 pb-3 flex items-center">
                    <AlertTriangle className="w-4 h-4 mr-2" /> {t('templates19PlatformKeyNew.tabDangerZone')}
                  </h3>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-4 border-b border-[#D97C7C]/20">
                    <div>
                      <h4 className="text-sm font-medium text-[var(--text-primary)]">{t('templates19PlatformKeyNew.suspendWorkspace')}</h4>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates19PlatformKeyNew.suspendWorkspaceDesc')}</p>
                    </div>
                    <Button variant="secondary" className="shrink-0 text-[#9B5050] hover:bg-[#D97C7C]/10 border-[#D97C7C]/40">{t('templates19PlatformKeyNew.suspend')}</Button>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-4">
                    <div>
                      <h4 className="text-sm font-medium text-[var(--text-primary)]">{t('templates19PlatformKeyNew.deleteWorkspace')}</h4>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates19PlatformKeyNew.deleteWorkspaceDesc')}</p>
                    </div>
                    <Button variant="destructive" className="shrink-0" onClick={() => setIsDeleteModalOpen(true)}>{t('templates19PlatformKeyNew.deleteWorkspace')}</Button>
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
        title={t('templates19PlatformKeyNew.deleteWorkspace')}
        description={t('templates19PlatformKeyNew.deleteWorkspaceModalDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsDeleteModalOpen(false)}>{t('templates19PlatformKeyNew.cancel')}</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteConfirmText !== formData.name}>{t('templates19PlatformKeyNew.understandDeleteWorkspace')}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Alert variant="error" title={t('templates19PlatformKeyNew.warning')}>
            {t('templates19PlatformKeyNew.deleteWorkspaceAlertDesc')}
          </Alert>
          <div className="space-y-2 mt-4">
            <Label>{t('templates19PlatformKeyNew.pleaseType')} <strong className="font-bold text-[var(--text-primary)]">{formData.name}</strong> {t('templates19PlatformKeyNew.toConfirm')}</Label>
            <Input
              value={deleteConfirmText}
              onChange={(e: any) => setDeleteConfirmText(e.target.value)}
              placeholder={t('templates19PlatformKeyNew.workspaceNamePlaceholder')}
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
        title={t('templates19PlatformKeyNew.componentLibraryTitle')}
        subtitle={t('templates19PlatformKeyNew.componentLibrarySubtitle')}
        actions={<Button>{t('templates19PlatformKeyNew.deploySystem')}</Button>}
      />

      <Tabs defaultValue="form" tabs={[
        { id: 'form', label: t('templates19PlatformKeyNew.tabFormsInputs'), content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title={t('templates19PlatformKeyNew.sectionButtons')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)]">
               <div className="flex flex-wrap gap-4 mb-4">
                 <Button variant="primary">{t('templates19PlatformKeyNew.primaryButton')}</Button>
                 <Button variant="secondary">{t('templates19PlatformKeyNew.secondaryButton')}</Button>
                 <Button variant="tertiary">{t('templates19PlatformKeyNew.tertiaryGhost')}</Button>
               </div>
               <div className="flex flex-wrap gap-4 items-center">
                 <Button variant="primary" isLoading>{t('templates19PlatformKeyNew.loading')}</Button>
                 <Button variant="destructive">{t('templates19PlatformKeyNew.destructiveAction')}</Button>
                 <Button variant="primary" size="icon"><Plus className="w-4 h-4"/></Button>
               </div>
             </Section>

             <Section title={t('templates19PlatformKeyNew.sectionInputsSelects')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] space-y-4">
                <Input label={t('templates19PlatformKeyNew.emailAddressLabel')} placeholder="admin@kaori.io" helperText={t('templates19PlatformKeyNew.emailHelperText')} />
                <Input label={t('templates19PlatformKeyNew.workspaceNameLabel')} placeholder={t('templates19PlatformKeyNew.workspaceNameExamplePlaceholder')} error={t('templates19PlatformKeyNew.workspaceNameTakenError')} />
                <Select
                  label={t('templates19PlatformKeyNew.environmentLabel')}
                  placeholder={t('templates19PlatformKeyNew.selectEnvironmentPlaceholder')}
                  options={[{label: t('templates19PlatformKeyNew.envProduction'), value: 'prod'}, {label: t('templates19PlatformKeyNew.envStaging'), value: 'stage'}]}
                  value={selectVal}
                  onChange={setSelectVal}
                />
                <DatePicker label={t('templates19PlatformKeyNew.billingCycleStartLabel')} date={date} setDate={setDate} />
             </Section>
           </div>
        )},
        { id: 'data', label: t('templates19PlatformKeyNew.tabDataDisplay'), content: (
           <div className="space-y-8">
             <Section title={t('templates19PlatformKeyNew.sectionMetricCards')}>
               <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                 <MetricCard title={t('templates19PlatformKeyNew.metricTotalRevenue')} value="$45,231" trend="+20.1%" isUp={true} />
                 <MetricCard title={t('templates19PlatformKeyNew.metricActiveWorkspaces')} value="12" trend="0%" />
                 <MetricCard title={t('templates19PlatformKeyNew.metricErrorRate')} value="1.2%" trend="+0.4%" isUp={false} inverseGood={true} />
               </div>
             </Section>

             <Section title={t('templates19PlatformKeyNew.sectionDataTable')}>
                <DataTable
                  columns={[
                    t('templates19PlatformKeyNew.colWorkspace'),
                    t('templates19PlatformKeyNew.colEnvironment'),
                    t('templates19PlatformKeyNew.colStatus'),
                    t('templates19PlatformKeyNew.colCreated')
                  ]}
                  data={[
                    ["Production AI", "Production", <Badge variant="operational" key="1">Healthy</Badge>, "Oct 12, 2026"],
                    ["Staging Data", "Staging", <Badge variant="degraded" key="2">Degraded</Badge>, "Oct 14, 2026"],
                    ["Dev Cluster", "Development", <Badge variant="operational" key="3">Healthy</Badge>, "Oct 15, 2026"]
                  ]}
                  loading={false}
                />
             </Section>
           </div>
        )},
        { id: 'feedback', label: t('templates19PlatformKeyNew.tabFeedbackOverlays'), content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title={t('templates19PlatformKeyNew.sectionAlerts')} className="space-y-4">
               <Alert variant="info" title={t('templates19PlatformKeyNew.alertSystemUpdateTitle')}>{t('templates19PlatformKeyNew.alertSystemUpdateDesc')}</Alert>
               <Alert variant="success" title={t('templates19PlatformKeyNew.alertBackupCompleteTitle')}>{t('templates19PlatformKeyNew.alertBackupCompleteDesc')}</Alert>
               <Alert variant="warning" title={t('templates19PlatformKeyNew.alertHighLatencyTitle')}>{t('templates19PlatformKeyNew.alertHighLatencyDesc')}</Alert>
               <Alert variant="error" title={t('templates19PlatformKeyNew.alertPaymentFailedTitle')}>{t('templates19PlatformKeyNew.alertPaymentFailedDesc')}</Alert>
             </Section>

             <Section title={t('templates19PlatformKeyNew.sectionModalsDrawers')} className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] flex flex-col gap-4 items-start">
               <Button variant="secondary" onClick={() => setIsModalOpen(true)}>{t('templates19PlatformKeyNew.openModal')}</Button>
               <Button variant="secondary" onClick={() => setIsDrawerOpen(true)}>{t('templates19PlatformKeyNew.openDrawer')}</Button>

               <Modal
                 isOpen={isModalOpen}
                 onClose={() => setIsModalOpen(false)}
                 title={t('templates19PlatformKeyNew.deleteWorkspace')}
                 description={t('templates19PlatformKeyNew.deleteWorkspaceModalDescGeneric')}
                 footer={<><Button variant="outline" onClick={()=>setIsModalOpen(false)}>{t('templates19PlatformKeyNew.cancel')}</Button><Button variant="destructive">{t('templates19PlatformKeyNew.confirmDelete')}</Button></>}
               >
                 <div className="space-y-4">
                    <Input label={t('templates19PlatformKeyNew.typeWorkspaceNameToConfirmLabel')} placeholder="Production AI" />
                 </div>
               </Modal>

               <Drawer
                 isOpen={isDrawerOpen}
                 onClose={() => setIsDrawerOpen(false)}
                 title={t('templates19PlatformKeyNew.editProfile')}
                 footer={<><Button variant="outline" className="w-full" onClick={()=>setIsDrawerOpen(false)}>{t('templates19PlatformKeyNew.cancel')}</Button><Button className="w-full">{t('templates19PlatformKeyNew.saveChangesUpper')}</Button></>}
               >
                 <div className="space-y-4">
                    <Input label={t('templates19PlatformKeyNew.fullNameLabel')} placeholder="Admin User" />
                    <Input label={t('templates19PlatformKeyNew.emailLabel')} placeholder="admin@kaori.io" disabled />
                    <Select label={t('templates19PlatformKeyNew.roleLabel')} options={[{label:t('templates19PlatformKeyNew.roleAdmin'), value:'admin'}, {label:t('templates19PlatformKeyNew.roleMember'), value:'member'}]} value="admin" onChange={()=>{}} />
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
      <PageHeader title={t('templates19PlatformKeyNew.platformOverviewTitle')} subtitle={t('templates19PlatformKeyNew.platformOverviewSubtitle')} actions={<Button variant="outline"><RefreshCw className="w-4 h-4 mr-2" /> {t('templates19PlatformKeyNew.refreshData')}</Button>} />
      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates19PlatformKeyNew.metricTotalWorkspaces')} value="124" trend="+4" isUp={true} />
          <MetricCard title={t('templates19PlatformKeyNew.metricActiveUsers')} value="1,892" trend="+12.5%" isUp={true} />
          <MetricCard title={t('templates19PlatformKeyNew.metricApiRequests')} value="2.4M" trend="+5.2%" isUp={true} />
          <MetricCard title={t('templates19PlatformKeyNew.metricFailedRequests')} value="482" trend="-18%" isUp={false} inverseGood={true} />
        </div>
      </Section>
      <Section title={t('templates19PlatformKeyNew.sectionRecentActivity')}>
         <DataTable
            columns={[t('templates19PlatformKeyNew.colEvent'), t('templates19PlatformKeyNew.colWorkspace'), t('templates19PlatformKeyNew.colTime')]}
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
      <PageHeader title={t('templates19PlatformKeyNew.activeSessionsTitle')} subtitle={t('templates19PlatformKeyNew.activeSessionsSubtitle')} actions={<Button variant="outline">{t('templates19PlatformKeyNew.signOutAll')}</Button>} />
      <Section title={t('templates19PlatformKeyNew.navSecuritySessions')}>
        <Card className="p-8 text-center flex flex-col items-center">
          <Shield className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
          <h3 className="text-sm font-medium text-[var(--text-primary)]">{t('templates19PlatformKeyNew.navSecuritySessions')}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates19PlatformKeyNew.manageActiveLoginsHere')}</p>
        </Card>
      </Section>
    </PageContainer>
  );
};

// --- MAIN PLATFORM SHELL COMPONENT ---

export default function KaoriPlatformShell() {
  const t = useT();
  const navigationConfig = getNavigationConfig(t);
  const [activeRoute, setActiveRoute] = useState('keys'); // Setting default to API Keys for demo
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
             activeRoute === 'keys' ? <ApiKeysPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'keys-new' ? <ApiKeyNewPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'overview' ? <PlatformOverview /> : 
             activeRoute === 'sessions' ? <SessionsPage /> : (
              <PageContainer maxWidth="narrow">
                <PageHeader title={t('templates19PlatformKeyNew.moduleTitle', { label: navigationConfig.flatMap(g => g.items).find(n => n.id === activeRoute)?.label })} subtitle={t('templates19PlatformKeyNew.moduleSubtitle')} />
                <Section>
                  <Card className="flex flex-col items-center justify-center py-20 px-4 text-center border-dashed bg-[var(--bg-card)]/50 mx-auto w-full animate-in fade-in duration-300">
                    <div className="w-12 h-12 rounded-lg-custom bg-[var(--bg-sidebar)] flex items-center justify-center border border-[var(--border-color)] mb-4">
                      {React.createElement(navigationConfig.flatMap(g => g.items).find(n => n.id === activeRoute)?.icon || LayoutDashboard, { className: 'w-6 h-6 text-[var(--text-secondary)]' })}
                    </div>
                    <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">{t('templates19PlatformKeyNew.workInProgress')}</h3>
                    <p className="text-sm text-[var(--text-secondary)] max-w-sm">{t('templates19PlatformKeyNew.moduleContentPlaceholder', { route: activeRoute })}</p>
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
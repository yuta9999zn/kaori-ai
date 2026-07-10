// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 28Billing Export.jsx by convert_jsx_to_tsx.py.
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
  AlertTriangle,
  Copy,
  RefreshCcw,
  BarChart3,
  Lock,
  Unlock,
  ShieldCheck,
  AlertOctagon,
  ExternalLink,
  SlidersHorizontal
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

const Input = React.forwardRef<any, any>(({ className, label, error, helperText, multiline, ...props }, ref) => {
  return (
    <div className="space-y-2 w-full">
      {label && <Label>{label}</Label>}
      {multiline ? (
        <textarea
          ref={ref}
          className={cn(
            "flex min-h-[80px] w-full rounded-md-custom border bg-white px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 transition-all duration-200 resize-y",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/30 focus-visible:border-[var(--primary-gold)]",
            "disabled:cursor-not-allowed disabled:opacity-50 shadow-soft-sm disabled:bg-[var(--bg-app)]",
            error ? "border-[var(--state-error)] focus-visible:ring-[var(--state-error)]/30 focus-visible:border-[var(--state-error)]" : "border-[var(--border-color)]",
            className
          )}
          {...props}
        />
      ) : (
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
      )}
      {error && <p className="text-xs font-medium text-[var(--state-error)]">{error}</p>}
      {helperText && !error && <p className="text-xs text-[var(--text-secondary)]">{helperText}</p>}
    </div>
  );
});
Input.displayName = "Input";

// --- SELECT (Simulated Radix Select) ---
const Select = ({  label, placeholder, options = [], value, onChange, error, disabled  }: any) => {
  const t = useT();
  const resolvedPlaceholder = placeholder || t('templates28BillingExport.selectPlaceholder');
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
  const resolvedPlaceholder = placeholder || t('templates28BillingExport.datePickerPlaceholder');
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
              <span className="text-sm font-semibold text-[var(--text-primary)]">{t('templates28BillingExport.calendarMonthDemo')}</span>
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

const DataTable = ({  columns, data, loading, pagination = true, onRowClick  }: any) => {
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
                  <span className="text-sm font-medium text-[var(--text-primary)]">{t('templates28BillingExport.noResultsFound')}</span>
                  <span className="text-xs text-[var(--text-secondary)]">{t('templates28BillingExport.tryAdjustingFilters')}</span>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, i) => (
              <TableRow 
                key={i} 
                className={onRowClick ? "cursor-pointer hover:bg-[#FAF7F2]/50" : ""}
                onClick={() => onRowClick && onRowClick(row)}
              >
                {row.map((cell, j) => <TableCell key={j}>{cell}</TableCell>)}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      {pagination && data.length > 0 && (
        <div className="border-t border-[var(--border-color)] px-4 py-3 flex items-center justify-between bg-[#FCFBF9]">
          <span className="text-xs text-[var(--text-secondary)]">{t('templates28BillingExport.showingResults', { count: data.length })}</span>
          <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled>{t('templates28BillingExport.previous')}</Button>
              <Button variant="outline" size="sm">{t('templates28BillingExport.next')}</Button>
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
      aria-label={t('templates28BillingExport.copyToClipboard')}
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
const NAVIGATION_CONFIG = [
  {
    group: 'templates28BillingExport.navGroupMain',
    items: [
      { id: 'overview', label: 'templates28BillingExport.navPlatformHealth', icon: LayoutDashboard, route: '/platform' },
      { id: 'workspaces', label: 'templates28BillingExport.navWorkspaces', icon: Briefcase, route: '/platform/workspaces', badge: '4' },
    ]
  },
  {
    group: 'templates28BillingExport.navGroupManagement',
    items: [
      { id: 'keys', label: 'templates28BillingExport.navApiKeys', icon: Key, route: '/platform/keys' },
      { id: 'billing', label: 'templates28BillingExport.navBilling', icon: CreditCard, route: '/platform/billing' },
      { id: 'admin', label: 'templates28BillingExport.navAdmins', icon: Shield, route: '/platform/admins', role: 'admin' },
    ]
  },
  {
    group: 'templates28BillingExport.navGroupSystem',
    items: [
      { id: 'components', label: 'templates28BillingExport.navComponentLibrary', icon: Component, route: '/platform/components' },
      { id: 'sessions', label: 'templates28BillingExport.navSecuritySessions', icon: Settings, route: '/p1/auth/sessions' },
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

  const notifications = [{ id: 1, title: t('templates28BillingExport.notifDataSync'), time: '10m ago', read: false }];

  return (
    <div className="relative" ref={dropdownRef}>
      <button onClick={() => setIsOpen(!isOpen)} className={`relative p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-full transition-colors border ${isOpen ? 'bg-[var(--bg-app)] border-[var(--border-color)]' : 'border-transparent hover:bg-[var(--bg-app)] hover:border-[var(--border-color)]'}`}>
        <Bell className="w-[18px] h-[18px]" />
        <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--state-error)] border-2 border-[var(--bg-app)] animate-pulse"></span>
      </button>
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[320px] bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)] bg-[#FCFBF9]">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates28BillingExport.notifications')}</h3>
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
              <Shield className="w-4 h-4 text-[var(--text-secondary)]" /> {t('templates28BillingExport.navSecuritySessions')}
            </button>
          </div>
          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" />
          <div className="p-1.5">
            <button className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] transition-colors flex items-center gap-2 font-medium">
              <LogOut className="w-4 h-4" /> {t('templates28BillingExport.signOut')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const GlobalHeader = ({  activeRoute, setActiveRoute, setIsMobileMenuOpen  }: any) => {
  const t = useT();
  let routeLabel = NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label;
  routeLabel = routeLabel ? t(routeLabel) : routeLabel;
  if (activeRoute === 'workspace-details') routeLabel = t('templates28BillingExport.crumbWorkspacesOverview');
  else if (activeRoute === 'workspace-members') routeLabel = t('templates28BillingExport.crumbWorkspacesMembers');
  else if (activeRoute === 'workspace-billing') routeLabel = t('templates28BillingExport.crumbWorkspacesBilling');
  else if (activeRoute === 'audit-logs') routeLabel = t('templates28BillingExport.crumbWorkspacesAuditLogs');
  else if (activeRoute === 'workspace-new') routeLabel = t('templates28BillingExport.crumbWorkspacesNew');
  else if (activeRoute === 'workspace-edit') routeLabel = t('templates28BillingExport.crumbWorkspacesSettings');
  else if (activeRoute === 'keys-new') routeLabel = t('templates28BillingExport.crumbApiKeysCreate');
  else if (activeRoute === 'key-details') routeLabel = t('templates28BillingExport.crumbApiKeysDetails');
  else if (activeRoute === 'admin-invite') routeLabel = t('templates28BillingExport.crumbAdminsInvite');
  else if (activeRoute === 'admin-details') routeLabel = t('templates28BillingExport.crumbAdminsDetails');
  else if (activeRoute === 'admin-reset-password') routeLabel = t('templates28BillingExport.crumbAdminsResetPassword');
  else if (activeRoute === 'enterprise-billing-details') routeLabel = t('templates28BillingExport.crumbBillingEnterpriseDetail');
  else if (activeRoute === 'quota') routeLabel = t('templates28BillingExport.crumbBillingQuota');
  else if (activeRoute === 'billing-export') routeLabel = t('templates28BillingExport.crumbBillingExport');
  else if (!routeLabel) routeLabel = activeRoute;

  return (
    <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/90 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6 transition-all duration-300">
      <div className="flex items-center gap-4">
        <button className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]" onClick={() => setIsMobileMenuOpen(true)}>
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:flex items-center text-sm font-medium">
          <span className="text-[var(--text-secondary)]">{t('templates28BillingExport.platformLabel')}</span>
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
              <input type="text" placeholder={t('templates28BillingExport.searchPlaceholder')} className="h-8 w-48 pl-8 pr-10 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm" />
            </div>
            <Button variant="outline" size="sm" onClick={() => setActiveRoute('workspace-new')} className="hidden md:flex"><Plus className="w-3.5 h-3.5 mr-1.5" /> {t('templates28BillingExport.newWorkspaceButton')}</Button>
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
  const currentHighlight = 
    (activeRoute === 'workspace-details' || activeRoute === 'workspace-members' || activeRoute === 'workspace-billing' || activeRoute === 'audit-logs' || activeRoute === 'workspace-new' || activeRoute === 'workspace-edit') ? 'workspaces' : 
    (activeRoute === 'keys-new' || activeRoute === 'key-details') ? 'keys' : 
    (activeRoute === 'admin-invite' || activeRoute === 'admin-details' || activeRoute === 'admin-reset-password') ? 'admin' : 
    (activeRoute === 'enterprise-billing-details' || activeRoute === 'quota' || activeRoute === 'billing-export') ? 'billing' :
    activeRoute;

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
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mt-0.5">{t('templates28BillingExport.platformLabel')}</span>
          </div>
        )}
      </div>

      <nav aria-label={t('templates28BillingExport.mainNavigationAriaLabel')} className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 space-y-6">
        {NAVIGATION_CONFIG.map((group, idx) => (
          <div key={idx} className="flex flex-col">
            {!collapsed ? (
              <div className="px-3 mb-2 text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-[0.1em] opacity-70">{t(group.group)}</div>
            ) : (
              <div className="w-full h-[1px] bg-[var(--border-color)]/60 my-2 rounded-full" />
            )}
            <div className="space-y-1">
              {group.items.map((item) => {
                const isActive = currentHighlight === item.id;
                const Icon = item.icon;
                return (
                  <SidebarTooltip key={item.id} content={t(item.label)} isCollapsed={collapsed}>
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
                      {!collapsed && <span className="text-sm font-medium truncate flex-1 text-left">{t(item.label)}</span>}
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
            {!collapsed && <span className="text-xs font-medium">{t('templates28BillingExport.collapseSidebar')}</span>}
          </button>
        )}
      </div>
    </aside>
  );
};


// ==========================================
// 4. VIEWS & PAGES
// ==========================================

// --- PLATFORM BILLING EXPORT PAGE ---
const PlatformBillingExportPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [startDate, setStartDate] = useState('Oct 01, 2026');
  const [endDate, setEndDate] = useState('Oct 31, 2026');
  const [dataType, setDataType] = useState('all');
  const [workspace, setWorkspace] = useState('all');
  const [planFilter, setPlanFilter] = useState('all');
  const [format, setFormat] = useState('csv');

  const [isExporting, setIsExporting] = useState(false);

  const [history, setHistory] = useState([
    { id: 'exp_0982', date: 'Oct 25, 2026 14:30', filters: 'All Data • All Workspaces • Oct 2026', status: 'Ready', format: 'CSV' },
    { id: 'exp_0981', date: 'Oct 20, 2026 09:15', filters: 'Invoices • Enterprise • Q3 2026', status: 'Failed', format: 'XLSX' }
  ]);

  const handleExport = async () => {
    setIsExporting(true);
    await new Promise(r => setTimeout(r, 1200));

    const newId = `exp_${Math.floor(Math.random() * 10000).toString().padStart(4, '0')}`;
    const newExport = {
      id: newId,
      date: 'Just now',
      filters: `${dataType === 'all' ? t('templates28BillingExport.allData') : dataType} • ${workspace === 'all' ? t('templates28BillingExport.allWorkspaces') : workspace} • ${t('templates28BillingExport.customRangeLabel')}`,
      status: 'Processing',
      format: format.toUpperCase()
    };

    setHistory([newExport, ...history]);
    setIsExporting(false);

    // Simulate processing completion
    setTimeout(() => {
      setHistory(prev => prev.map(h => h.id === newId ? { ...h, status: 'Ready' } : h));
    }, 4000);
  };

  const handleReset = () => {
    setStartDate('');
    setEndDate('');
    setDataType('all');
    setWorkspace('all');
    setPlanFilter('all');
    setFormat('csv');
  };

  const mappedHistory = history.map(h => [
    <span key="id" className="font-mono text-[var(--text-primary)] text-xs">{h.id}</span>,
    <span key="date" className="text-[var(--text-secondary)] whitespace-nowrap">{h.date}</span>,
    <span key="filters" className="text-[var(--text-primary)]">{h.filters}</span>,
    <Badge key="status" variant={h.status === 'Ready' ? 'success' : h.status === 'Processing' ? 'operational' : 'error'}>
      {h.status === 'Processing' ? <span className="flex items-center gap-1.5"><Loader2 className="w-3 h-3 animate-spin" /> Processing</span> : h.status}
    </Badge>,
    <Button 
      key="action" 
      variant="tertiary" 
      size="sm" 
      disabled={h.status !== 'Ready'}
      className="h-8 px-2"
    >
      <Download className="w-4 h-4 text-[var(--text-secondary)]" />
    </Button>
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        showBack
        onBack={() => setActiveRoute('billing')}
        title={t('templates28BillingExport.exportBillingDataTitle')}
        subtitle={t('templates28BillingExport.exportBillingDataSubtitle')}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
        <div className="lg:col-span-1 space-y-6">
          <Card className="p-6 shadow-soft-sm">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates28BillingExport.exportConfiguration')}</h3>
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <DatePicker label={t('templates28BillingExport.startDate')} date={startDate} setDate={setStartDate} placeholder={t('templates28BillingExport.fromPlaceholder')} />
                <DatePicker label={t('templates28BillingExport.endDate')} date={endDate} setDate={setEndDate} placeholder={t('templates28BillingExport.toPlaceholder')} />
              </div>

              <Select
                label={t('templates28BillingExport.dataTypeLabel')}
                value={dataType}
                onChange={setDataType}
                options={[
                  {label: t('templates28BillingExport.allData'), value: 'all'},
                  {label: t('templates28BillingExport.revenue'), value: 'Revenue'},
                  {label: t('templates28BillingExport.usage'), value: 'Usage'},
                  {label: t('templates28BillingExport.invoices'), value: 'Invoices'}
                ]}
              />

              <Select
                label={t('templates28BillingExport.workspaceLabel')}
                value={workspace}
                onChange={setWorkspace}
                options={[
                  {label: t('templates28BillingExport.allWorkspaces'), value: 'all'},
                  {label: 'Production AI (ws_prod_01)', value: 'ws_prod_01'},
                  {label: 'Staging Env (ws_stage_02)', value: 'ws_stage_02'}
                ]}
              />

              <Select
                label={t('templates28BillingExport.planFilterLabel')}
                value={planFilter}
                onChange={setPlanFilter}
                options={[
                  {label: t('templates28BillingExport.allPlans'), value: 'all'},
                  {label: t('templates28BillingExport.enterprisePlanLabel'), value: 'Enterprise'},
                  {label: t('templates28BillingExport.proPlanLabel'), value: 'Pro'},
                  {label: t('templates28BillingExport.freePlanLabel'), value: 'Free'}
                ]}
              />

              <div className="h-[1px] bg-[var(--border-color)]/50 my-2" />

              <Select
                label={t('templates28BillingExport.formatLabel')}
                value={format}
                onChange={setFormat}
                options={[
                  {label: t('templates28BillingExport.csvFormat'), value: 'csv'},
                  {label: t('templates28BillingExport.excelFormat'), value: 'xlsx'}
                ]}
              />

              <div className="pt-4 flex flex-col gap-3">
                <Button onClick={handleExport} isLoading={isExporting} className="w-full">
                  {t('templates28BillingExport.generateExport')}
                </Button>
                <Button variant="tertiary" onClick={handleReset} disabled={isExporting} className="w-full">
                  {t('templates28BillingExport.resetFilters')}
                </Button>
              </div>
            </div>
          </Card>
          <Alert variant="info" title={t('templates28BillingExport.largeDatasetsTitle')}>
            {t('templates28BillingExport.largeDatasetsBody')}
          </Alert>
        </div>

        <div className="lg:col-span-2">
          <Section title={t('templates28BillingExport.exportHistoryTitle')}>
            <DataTable
              columns={[t('templates28BillingExport.colExportId'), t('templates28BillingExport.colDate'), t('templates28BillingExport.colConfiguration'), t('templates28BillingExport.colStatus'), ""]}
              data={mappedHistory}
              loading={false}
            />
          </Section>
        </div>
      </div>

    </PageContainer>
  );
};

// --- PLATFORM QUOTA MANAGEMENT PAGE ---
const MOCK_QUOTAS = [
  { id: 'ws_prod_01', name: 'Production AI', plan: 'Enterprise', apiCurrent: 2400, apiMax: 10000, storageCurrent: 84, storageMax: 500, status: 'Normal', lastUpdated: 'Oct 20, 2026' },
  { id: 'ws_stage_02', name: 'Staging Environment', plan: 'Pro', apiCurrent: 45, apiMax: 50, storageCurrent: 48, storageMax: 50, status: 'Warning', lastUpdated: 'Oct 22, 2026' },
  { id: 'ws_dev_03', name: 'Dev Cluster Alpha', plan: 'Free', apiCurrent: 12, apiMax: 10, storageCurrent: 6, storageMax: 5, status: 'Over Quota', lastUpdated: 'Oct 25, 2026' },
  { id: 'ws_analytics_04', name: 'Data Analytics Core', plan: 'Enterprise', apiCurrent: 4900, apiMax: 5000, storageCurrent: 490, storageMax: 500, status: 'Warning', lastUpdated: 'Oct 24, 2026' },
];

const QuotaActionsDropdown = ({  workspace, onAdjustQuota, onViewDetails  }: any) => {
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
          <button onClick={() => { onViewDetails(); setIsOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Eye className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates28BillingExport.viewWorkspaceAction')}
          </button>
          <button onClick={() => { onAdjustQuota(workspace); setIsOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <SlidersHorizontal className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates28BillingExport.adjustQuotaAction')}
          </button>
          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium">
            <Ban className="w-4 h-4 opacity-80"/> {t('templates28BillingExport.suspendAction')}
          </button>
        </div>
      )}
    </div>
  );
};

const PlatformQuotaManagementPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [planFilter, setPlanFilter] = useState('all');
  const [isLoading, setIsLoading] = useState(true);
  const [quotas, setQuotas] = useState(MOCK_QUOTAS);
  
  // Modal state
  const [isAdjustOpen, setIsAdjustOpen] = useState(false);
  const [selectedWs, setSelectedWs] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [apiLimit, setApiLimit] = useState('');
  const [storageLimit, setStorageLimit] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const openAdjustModal = (ws) => {
    setSelectedWs(ws);
    setApiLimit(ws.apiMax.toString());
    setStorageLimit(ws.storageMax.toString());
    setIsAdjustOpen(true);
  };

  const handleAdjustSave = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 800));
    
    setQuotas(prev => prev.map(q => {
      if (q.id === selectedWs.id) {
        const newApiMax = parseInt(apiLimit, 10) || q.apiMax;
        const newStorageMax = parseInt(storageLimit, 10) || q.storageMax;
        
        let newStatus = 'Normal';
        if (q.apiCurrent >= newApiMax || q.storageCurrent >= newStorageMax) newStatus = 'Over Quota';
        else if (q.apiCurrent / newApiMax >= 0.8 || q.storageCurrent / newStorageMax >= 0.8) newStatus = 'Warning';

        return { ...q, apiMax: newApiMax, storageMax: newStorageMax, status: newStatus, lastUpdated: 'Just now' };
      }
      return q;
    }));
    
    setIsProcessing(false);
    setIsAdjustOpen(false);
  };

  const filteredQuotas = quotas.filter(q => {
    const matchesSearch = q.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || q.status === statusFilter;
    const matchesPlan = planFilter === 'all' || q.plan === planFilter;
    return matchesSearch && matchesStatus && matchesPlan;
  });

  const renderProgressBar = (current, max, isWarning, isOver) => {
    const pct = Math.min((current / max) * 100, 100);
    let colorClass = "bg-[#5C856A]";
    if (isOver) colorClass = "bg-[#D97C7C]";
    else if (isWarning || pct >= 80) colorClass = "bg-[#E6C07B]";

    return (
      <div className="flex flex-col gap-1.5 w-full min-w-[120px] max-w-[160px]">
        <div className="flex justify-between text-[11px] font-medium text-[var(--text-secondary)]">
          <span>{current.toLocaleString()}{max > 1000 ? 'k' : ''}</span>
          <span>{max.toLocaleString()}{max > 1000 ? 'k' : ''}</span>
        </div>
        <div className="w-full bg-[#E9E7E2]/50 rounded-full h-1.5 border border-[#E9E7E2] overflow-hidden">
          <div className={cn("h-full rounded-full transition-all duration-500", colorClass)} style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  };

  const mappedData = filteredQuotas.map(q => [
    <span key="ws" className="font-medium text-[var(--text-primary)] cursor-pointer hover:underline" onClick={() => setActiveRoute('workspace-details')}>{q.name}</span>,
    <Badge key="plan" variant={q.plan === 'Enterprise' ? 'current' : q.plan === 'Pro' ? 'operational' : 'default'}>{q.plan}</Badge>,
    <div key="api">{renderProgressBar(q.apiCurrent, q.apiMax, q.status === 'Warning', q.status === 'Over Quota')}</div>,
    <div key="storage">{renderProgressBar(q.storageCurrent, q.storageMax, q.status === 'Warning', q.status === 'Over Quota')}</div>,
    <Badge key="status" variant={q.status === 'Normal' ? 'success' : q.status === 'Warning' ? 'warning' : 'error'}>{q.status}</Badge>,
    <span key="updated" className="text-[var(--text-secondary)] whitespace-nowrap">{q.lastUpdated}</span>,
    <QuotaActionsDropdown key="actions" workspace={q} onAdjustQuota={openAdjustModal} onViewDetails={() => setActiveRoute('workspace-details')} />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        title={t('templates28BillingExport.quotaManagementTitle')}
        subtitle={t('templates28BillingExport.quotaManagementSubtitle')}
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Download className="w-4 h-4 mr-2" /> {t('templates28BillingExport.exportDataButton')}</Button>
            <Button variant="outline"><Settings className="w-4 h-4 mr-2"/> {t('templates28BillingExport.adjustDefaultQuota')}</Button>
          </>
        }
      />

      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates28BillingExport.totalApiCapacity')} value="150M reqs" trend="0%" />
          <MetricCard title={t('templates28BillingExport.totalUsageMonth')} value="82.4M reqs" trend="+5.2%" isUp={true} />
          <MetricCard title={t('templates28BillingExport.overQuotaWorkspaces')} value="14" trend="+2" isUp={false} inverseGood={true} />
          <MetricCard title={t('templates28BillingExport.warningLevelWorkspaces')} value="32" trend="-5" isUp={true} inverseGood={true} />
        </div>
      </Section>

      <Section>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 bg-[var(--bg-card)] p-4 rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm">
          <div className="relative w-full sm:w-72 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              className="h-10 w-full pl-9 pr-3 rounded-md-custom border border-[var(--border-color)] bg-white text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
              placeholder={t('templates28BillingExport.searchWorkspacesPlaceholder')}
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex w-full sm:w-auto gap-3 shrink-0">
            <div className="w-full sm:w-40">
              <Select
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  {label: t('templates28BillingExport.allStatuses'), value: 'all'},
                  {label: t('templates28BillingExport.normalStatus'), value: 'Normal'},
                  {label: t('templates28BillingExport.warningStatus'), value: 'Warning'},
                  {label: t('templates28BillingExport.overQuotaStatus'), value: 'Over Quota'}
                ]}
                placeholder={t('templates28BillingExport.statusFieldLabel')}
              />
            </div>
            <div className="w-full sm:w-32">
              <Select
                value={planFilter}
                onChange={setPlanFilter}
                options={[
                  {label: t('templates28BillingExport.allPlans'), value: 'all'},
                  {label: t('templates28BillingExport.freePlanLabel'), value: 'Free'},
                  {label: t('templates28BillingExport.proPlanLabel'), value: 'Pro'},
                  {label: t('templates28BillingExport.enterprisePlanLabel'), value: 'Enterprise'}
                ]}
                placeholder={t('templates28BillingExport.planFieldLabel')}
              />
            </div>
          </div>
          {(search || statusFilter !== 'all' || planFilter !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setStatusFilter('all'); setPlanFilter('all');}} className="px-3">{t('templates28BillingExport.clearFiltersButton')}</Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable
          columns={[t('templates28BillingExport.colWorkspace'), t('templates28BillingExport.colPlan'), t('templates28BillingExport.colApiUsage'), t('templates28BillingExport.colStorageUsage'), t('templates28BillingExport.colStatus'), t('templates28BillingExport.colLastUpdated'), ""]}
          data={mappedData}
          loading={isLoading}
        />
      </Section>

      {/* Adjust Quota Modal */}
      <Modal
        isOpen={isAdjustOpen}
        onClose={() => !isProcessing && setIsAdjustOpen(false)}
        title={t('templates28BillingExport.adjustQuotaTitle')}
        description={selectedWs ? t('templates28BillingExport.adjustQuotaDesc', { name: selectedWs.name }) : ''}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsAdjustOpen(false)} disabled={isProcessing}>{t('templates28BillingExport.cancelButton')}</Button>
            <Button onClick={handleAdjustSave} isLoading={isProcessing}>{t('templates28BillingExport.saveChangesButton')}</Button>
          </>
        }
      >
        <div className="space-y-5">
           <Alert variant="warning">
             {t('templates28BillingExport.quotaWarningBody')}
           </Alert>
           <div className="space-y-4">
             <Input
               label={t('templates28BillingExport.apiLimitLabel')}
               type="number"
               value={apiLimit}
               onChange={e => setApiLimit(e.target.value)}
             />
             <Input
               label={t('templates28BillingExport.storageLimitLabel')}
               type="number"
               value={storageLimit}
               onChange={e => setStorageLimit(e.target.value)}
             />
           </div>
        </div>
      </Modal>

    </PageContainer>
  );
};


// --- SHARED USAGE CARD ---
const EnterpriseUsageCard = ({  title, current, max, unit, icon: Icon  }: any) => {
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
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">{t('templates28BillingExport.percentUsedSuffix', { percent: percent.toFixed(1) })}</span>
        {isWarning && <span className="text-[11px] text-[#9B5050] font-medium flex items-center"><AlertCircle className="w-3 h-3 mr-1" /> {t('templates28BillingExport.approachingLimitText')}</span>}
      </div>
    </Card>
  );
};

// --- PLATFORM ENTERPRISE BILLING DETAIL PAGE ---

const PlatformEnterpriseBillingDetailPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isLoading, setIsLoading] = useState(true);
  const [isAdjustPlanModalOpen, setIsAdjustPlanModalOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [newPlan, setNewPlan] = useState('Enterprise');
  const [customPrice, setCustomPrice] = useState('2400');

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const handleAdjustPlan = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 1000));
    setIsProcessing(false);
    setIsAdjustPlanModalOpen(false);
  };

  const MOCK_INVOICES = [
    { id: 'INV-2026-004', date: 'Oct 01, 2026', amount: '$2,400.00', status: 'Failed' },
    { id: 'INV-2026-003', date: 'Sep 01, 2026', amount: '$2,400.00', status: 'Paid' },
    { id: 'INV-2026-002', date: 'Aug 01, 2026', amount: '$2,400.00', status: 'Paid' },
    { id: 'INV-2026-001', date: 'Jul 01, 2026', amount: '$2,400.00', status: 'Paid' },
  ];

  const MOCK_ACTIVITY = [
    { timestamp: 'Oct 15, 2026 14:32:01', event: 'Payment method updated', actor: 'Admin User' },
    { timestamp: 'Sep 01, 2026 10:05:11', event: 'Invoice INV-2026-003 paid successfully', actor: 'System' },
    { timestamp: 'Aug 12, 2026 09:22:10', event: 'Plan upgraded to Enterprise', actor: 'Sales Team' },
  ];

  const invoiceData = MOCK_INVOICES.map(inv => [
    <span key="id" className="font-medium text-[var(--text-primary)]">{inv.id}</span>,
    <span key="date" className="text-[var(--text-secondary)]">{inv.date}</span>,
    <span key="amount" className="tabular-nums text-[var(--text-primary)]">{inv.amount}</span>,
    <Badge key="status" variant={inv.status === 'Paid' ? 'operational' : 'error'}>{inv.status}</Badge>,
    <Button key="download" variant="tertiary" size="sm" className="h-8 px-2"><Download className="w-4 h-4 text-[var(--text-secondary)] hover:text-[var(--text-primary)]" /></Button>
  ]);

  const activityData = MOCK_ACTIVITY.map((act, i) => [
    <span key="ts" className="text-[var(--text-secondary)]">{act.timestamp}</span>,
    <span key="ev" className="font-medium text-[var(--text-primary)]">{act.event}</span>,
    <span key="actor" className="text-[var(--text-secondary)]">{act.actor}</span>
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        showBack
        onBack={() => setActiveRoute('billing')}
        title="Production AI"
        subtitle="ws_prod_01 • Enterprise Plan"
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex" onClick={() => setActiveRoute('workspace-details')}>
              <ExternalLink className="w-4 h-4 mr-2" /> {t('templates28BillingExport.viewWorkspaceAction')}
            </Button>
            <Button onClick={() => setIsAdjustPlanModalOpen(true)}>{t('templates28BillingExport.adjustPlanButton')}</Button>
            <Button variant="tertiary" size="icon"><MoreVertical className="w-4 h-4" /></Button>
          </>
        }
      />

      <Section>
         <Alert variant="error" title={t('templates28BillingExport.actionRequiredTitle')}>
            {t('templates28BillingExport.invoiceFailedBody')}
         </Alert>
      </Section>

      <Section title={t('templates28BillingExport.enterpriseSummaryTitle')}>
        <Card className="p-5 sm:p-6 overflow-hidden relative">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
           <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 relative z-10 items-start">
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.statusFieldLabel')}</p>
                <Badge variant="operational" className="py-1">{t('templates28BillingExport.activeStatusLabel')}</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.planFieldLabel')}</p>
                <Badge variant="current" className="py-1">{t('templates28BillingExport.enterprisePlanLabel')}</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.billingCycleLabel')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{t('templates28BillingExport.billingCycleMonthly')}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.renewalDateLabel')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">Nov 01, 2026</div>
             </div>
             <div className="lg:col-span-2">
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.ownerBillingContactLabel')}</p>
                <div className="flex items-center gap-2">
                   <div className="w-6 h-6 rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center text-[10px] font-bold text-[var(--primary-gold)]">A</div>
                   <div className="flex flex-col">
                     <span className="text-sm font-medium text-[var(--text-primary)] leading-tight">Admin User</span>
                     <span className="text-xs text-[var(--text-secondary)] leading-tight">admin@kaori.io</span>
                   </div>
                </div>
             </div>
           </div>
        </Card>
      </Section>

      <Section title={t('templates28BillingExport.metricsOverviewTitle')}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates28BillingExport.monthlyRevenueTitle')} value="$2,400" trend="0%" />
          <MetricCard title={t('templates28BillingExport.apiRequestsMoTitle')} value="2.4M" trend="+12%" isUp={true} />
          <MetricCard title={t('templates28BillingExport.storageUsedTitle')} value="84 GB" trend="+5%" isUp={true} />
          <MetricCard title={t('templates28BillingExport.activeUsersTitle')} value="14" trend="+2" isUp={true} />
        </div>
      </Section>

      <Section>
        <Tabs defaultValue="invoices" tabs={[
          {
            id: 'usage',
            label: t('templates28BillingExport.usageDetailsTab'),
            content: (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <EnterpriseUsageCard title={t('templates28BillingExport.apiRequestsTitle')} icon={Zap} current={2400000} max={10000000} unit="reqs" />
                 <EnterpriseUsageCard title={t('templates28BillingExport.storageUsedTitle')} icon={HardDrive} current={84} max={500} unit="GB" />
              </div>
            )
          },
          {
            id: 'invoices',
            label: t('templates28BillingExport.invoicesTab'),
            content: (
              <DataTable
                columns={[t('templates28BillingExport.colInvoiceId'), t('templates28BillingExport.colDate'), t('templates28BillingExport.colAmount'), t('templates28BillingExport.colStatus'), ""]}
                data={invoiceData}
                loading={isLoading}
                pagination={false}
              />
            )
          },
          {
            id: 'activity',
            label: t('templates28BillingExport.activityTab'),
            content: (
              <DataTable
                columns={[t('templates28BillingExport.colTimestamp'), t('templates28BillingExport.colEvent'), t('templates28BillingExport.colActor')]}
                data={activityData}
                loading={isLoading}
                pagination={false}
              />
            )
          },
          {
            id: 'settings',
            label: t('templates28BillingExport.billingSettingsTab'),
            content: (
              <div className="max-w-2xl space-y-6">
                <Card className="p-6">
                   <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">{t('templates28BillingExport.contractDetailsTitle')}</h3>
                   <div className="space-y-5">
                     <Select
                       label={t('templates28BillingExport.currentPlanLabel')}
                       value="Enterprise"
                       disabled
                       options={[{label: t('templates28BillingExport.enterprisePlanLabel'), value: 'Enterprise'}]}
                       helperText={t('templates28BillingExport.currentPlanHelper')}
                     />
                     <Input
                       label={t('templates28BillingExport.billingNotesLabel')}
                       value="Net 30 terms. Send copy to finance@acme.com."
                       onChange={() => {}}
                       multiline
                     />
                     <div className="pt-4 flex justify-end">
                       <Button>{t('templates28BillingExport.saveNotesButton')}</Button>
                     </div>
                   </div>
                </Card>
              </div>
            )
          }
        ]} />
      </Section>

      {/* Adjust Plan Modal */}
      <Modal
        isOpen={isAdjustPlanModalOpen}
        onClose={() => !isProcessing && setIsAdjustPlanModalOpen(false)}
        title={t('templates28BillingExport.adjustSubscriptionPlanTitle')}
        description={t('templates28BillingExport.adjustSubscriptionPlanDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsAdjustPlanModalOpen(false)} disabled={isProcessing}>{t('templates28BillingExport.cancelButton')}</Button>
            <Button onClick={handleAdjustPlan} isLoading={isProcessing}>{t('templates28BillingExport.updatePlanButton')}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select
            label={t('templates28BillingExport.planTierLabel')}
            options={[
              {label: t('templates28BillingExport.freeTierOption'), value: 'Free'},
              {label: t('templates28BillingExport.proPlanLabel'), value: 'Pro'},
              {label: t('templates28BillingExport.enterprisePlanLabel'), value: 'Enterprise'}
            ]}
            value={newPlan}
            onChange={setNewPlan}
          />
          
          <div className="space-y-2 w-full">
            <Label>{t('templates28BillingExport.customMrrOverrideLabel')}</Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]">$</span>
              <Input 
                type="number"
                value={customPrice} 
                onChange={e => setCustomPrice(e.target.value)} 
                className="pl-7"
              />
            </div>
            <p className="text-xs text-[var(--text-secondary)]">{t('templates28BillingExport.blankPricingHint')}</p>
          </div>

          <Alert variant="warning" className="mt-2">
            {t('templates28BillingExport.prorationNote')}
          </Alert>
        </div>
      </Modal>

    </PageContainer>
  );
};


// --- PLATFORM BILLING OVERVIEW PAGE ---
const PlatformBillingOverviewPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isLoading, setIsLoading] = useState(true);
  const [dateRange, setDateRange] = useState('30d');

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const MOCK_TOP_WORKSPACES = [
    { name: 'Production AI', plan: 'Enterprise', revenue: '$2,400', usage: '2.4M reqs', status: 'Active' },
    { name: 'Staging Environment', plan: 'Pro', revenue: '$49', usage: '850K reqs', status: 'Active' },
    { name: 'Data Analytics Core', plan: 'Enterprise', revenue: '$1,200', usage: '5.1M reqs', status: 'Active' },
    { name: 'Dev Cluster Alpha', plan: 'Free', revenue: '$0', usage: '12K reqs', status: 'Suspended' },
  ];

  const tableData = MOCK_TOP_WORKSPACES.map((ws, i) => [
    <span key="name" className="font-medium text-[var(--text-primary)] cursor-pointer hover:underline" onClick={() => setActiveRoute('enterprise-billing-details')}>{ws.name}</span>,
    <Badge key="plan" variant={ws.plan === 'Enterprise' ? 'current' : ws.plan === 'Pro' ? 'operational' : 'default'}>{ws.plan}</Badge>,
    <span key="rev" className="tabular-nums text-[var(--text-primary)]">{ws.revenue}</span>,
    <span key="usage" className="text-[var(--text-secondary)]">{ws.usage}</span>,
    <Badge key="status" variant={ws.status === 'Active' ? 'success' : 'warning'}>{ws.status}</Badge>,
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        title={t('templates28BillingExport.billingOverviewTitle')}
        subtitle={t('templates28BillingExport.billingOverviewSubtitle')}
        actions={
          <>
            <div className="hidden sm:block w-36">
              <Select
                value={dateRange}
                onChange={setDateRange}
                options={[{label: t('templates28BillingExport.last30DaysOption'), value: '30d'}, {label: t('templates28BillingExport.thisQuarterOption'), value: '90d'}, {label: t('templates28BillingExport.thisYearOption'), value: '365d'}]}
                placeholder={t('templates28BillingExport.dateRangeLabel')}
              />
            </div>
            <Button variant="outline" onClick={() => setActiveRoute('billing-export')}><Download className="w-4 h-4 mr-2"/> {t('templates28BillingExport.exportDataButton')}</Button>
          </>
        }
      />

      <Section title={t('templates28BillingExport.revenueMetricsTitle')}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates28BillingExport.mrrTitle')} value="$124,500" trend="+8.4%" isUp={true} />
          <MetricCard title={t('templates28BillingExport.totalRevenueTitle')} value="$132,100" trend="+12.1%" isUp={true} />
          <MetricCard title={t('templates28BillingExport.activeSubscriptionsTitle')} value="1,892" trend="+42" isUp={true} />
          <MetricCard title={t('templates28BillingExport.churnRateTitle')} value="1.2%" trend="-0.4%" isUp={false} inverseGood={true} />
        </div>
      </Section>

      <Section title={t('templates28BillingExport.platformUsageTitle')}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title={t('templates28BillingExport.totalApiRequestsTitle')} value="45.2M" trend="+14%" isUp={true} />
          <MetricCard title={t('templates28BillingExport.storageUsageTitle')} value="12.4 TB" trend="+8%" isUp={true} />
          <MetricCard title={t('templates28BillingExport.activeWorkspacesTitle')} value="1,204" trend="+12" isUp={true} />
          <MetricCard title={t('templates28BillingExport.overQuotaWorkspaces')} value="14" trend="-2" isUp={false} inverseGood={true} />
        </div>
      </Section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
        <div className="lg:col-span-2 space-y-4">
          <Section title={t('templates28BillingExport.topWorkspacesTitle')}>
            <DataTable
              columns={[t('templates28BillingExport.colWorkspace'), t('templates28BillingExport.colPlan'), t('templates28BillingExport.colRevenue'), t('templates28BillingExport.colUsage'), t('templates28BillingExport.colStatus')]}
              data={tableData}
              loading={isLoading}
              pagination={false}
            />
          </Section>
        </div>

        <div className="space-y-6 sm:space-y-8">
           <Section title={t('templates28BillingExport.alertsRisksTitle')}>
             <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm space-y-3">
                <Alert variant="error" title={t('templates28BillingExport.paymentFailedTitle')}>
                  {t('templates28BillingExport.paymentFailedBodyPrefix')} <span className="font-semibold cursor-pointer hover:underline" onClick={() => setActiveRoute('enterprise-billing-details')}>Dev Cluster Alpha</span>.
                </Alert>
                <Alert variant="warning" title={t('templates28BillingExport.quotaWarningTitle')}>
                  <span className="font-semibold cursor-pointer hover:underline" onClick={() => setActiveRoute('enterprise-billing-details')}>Data Analytics Core</span> {t('templates28BillingExport.quotaWarningBodySuffix')}
                </Alert>
                <Alert variant="info" title={t('templates28BillingExport.suspendedAccountTitle')}>
                  {t('templates28BillingExport.suspendedAccountBodyPrefix')} <span className="font-semibold">Legacy Systems</span> {t('templates28BillingExport.suspendedAccountBodySuffix')}
                </Alert>
             </div>
           </Section>
        </div>
      </div>
    </PageContainer>
  );
};

// --- PLATFORM ADMIN RESET PASSWORD PAGE ---

const PlatformAdminResetPasswordPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [step, setStep] = useState('form');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [countdown, setCountdown] = useState(0);

  // Mock data for the target admin
  const adminData = {
    name: 'Sarah Jenkins',
    email: 'sarah@kaori.io',
    role: 'Admin',
    status: 'Active'
  };

  useEffect(() => {
    if (countdown > 0) {
      const timerId = setInterval(() => setCountdown((prev) => prev - 1), 1000);
      return () => clearInterval(timerId);
    }
  }, [countdown]);

  const handleSendReset = async () => {
    setIsSubmitting(true);
    await new Promise(r => setTimeout(r, 1200));
    setIsSubmitting(false);
    setIsConfirmModalOpen(false);
    setStep('success');
    setCountdown(30); // Prevent spamming
  };

  const handleResend = async () => {
    setIsSubmitting(true);
    await new Promise(r => setTimeout(r, 800));
    setIsSubmitting(false);
    setCountdown(30);
  };

  return (
    <PageContainer maxWidth="narrow" className="pt-8">
      {step === 'form' && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
          <PageHeader
            showBack
            onBack={() => setActiveRoute('admin-details')}
            title={t('templates28BillingExport.resetAdminPasswordTitle')}
            subtitle={t('templates28BillingExport.resetAdminPasswordSubtitle')}
          />

          <div className="space-y-6 mt-8">
            <Card className="p-6 border-[var(--border-color)] shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                 <div className="w-12 h-12 rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center text-lg font-medium text-[var(--primary-gold)] shrink-0">
                   {adminData.name.charAt(0).toUpperCase()}
                 </div>
                 <div>
                   <div className="font-medium text-[var(--text-primary)]">{adminData.name}</div>
                   <div className="text-sm text-[var(--text-secondary)]">{adminData.email}</div>
                 </div>
                 <div className="sm:ml-auto flex gap-2">
                   <Badge variant="operational">{adminData.role}</Badge>
                   <Badge variant={adminData.status === 'Active' ? 'success' : 'default'}>{adminData.status}</Badge>
                 </div>
              </div>
            </Card>

            <Alert variant="warning" className="bg-[#FDF9F0] border-[#E6C07B]/40">
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-[#9E814D]">{t('templates28BillingExport.importantSecurityNoticeTitle')}</h4>
                <p className="text-xs text-[#9E814D]/90 leading-relaxed">
                  {t('templates28BillingExport.securityNoticeBody')}
                </p>
                <p className="text-[11px] text-[#9E814D]/70 font-mono mt-2">{t('templates28BillingExport.auditLoggedNote')}</p>
              </div>
            </Alert>

            <div className="pt-6 border-t border-[var(--border-color)] flex items-center justify-end gap-3">
               <Button variant="tertiary" onClick={() => setActiveRoute('admin-details')}>{t('templates28BillingExport.cancelButton')}</Button>
               <Button onClick={() => setIsConfirmModalOpen(true)} disabled={adminData.status === 'Suspended'}>
                 <Mail className="w-4 h-4 mr-2"/> {t('templates28BillingExport.sendResetEmailButton')}
               </Button>
            </div>
          </div>
        </div>
      )}

      {step === 'success' && (
        <div className="animate-in fade-in zoom-in-[0.98] duration-500">
           <PageHeader
             showBack
             onBack={() => setActiveRoute('admin-details')}
             title={t('templates28BillingExport.resetEmailSentTitle')}
           />
           <Card className="p-8 mt-8 shadow-soft-md flex flex-col items-center text-center">
             <div className="w-16 h-16 rounded-full bg-[#F3F9F5] border border-[#8FBFA0]/40 flex items-center justify-center mb-6">
               <CheckCircle2 className="w-8 h-8 text-[#5C856A]" />
             </div>
             <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">{t('templates28BillingExport.resetEmailDispatchedHeading')}</h2>
             <p className="text-sm text-[var(--text-secondary)] mb-8 max-w-sm">
               {t('templates28BillingExport.emailSentToPrefix')} <strong className="text-[var(--text-primary)]">{adminData.email}</strong> {t('templates28BillingExport.resetEmailSentSuffix')}
             </p>
             <div className="flex gap-3">
               <Button variant="outline" onClick={() => setActiveRoute('admin-details')}>{t('templates28BillingExport.backToAdminDetailsButton')}</Button>
               <Button onClick={handleResend} disabled={countdown > 0} isLoading={isSubmitting}>
                 {countdown > 0 ? t('templates28BillingExport.resendInSeconds', { seconds: countdown }) : t('templates28BillingExport.resendEmailButton')}
               </Button>
             </div>
           </Card>
        </div>
      )}

      {/* Confirmation Modal */}
      <Modal
        isOpen={isConfirmModalOpen}
        onClose={() => !isSubmitting && setIsConfirmModalOpen(false)}
        title={t('templates28BillingExport.resetPasswordConfirmTitle')}
        description={t('templates28BillingExport.resetPasswordConfirmDesc')}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsConfirmModalOpen(false)} disabled={isSubmitting}>{t('templates28BillingExport.cancelButton')}</Button>
            <Button onClick={handleSendReset} isLoading={isSubmitting}>{t('templates28BillingExport.confirmResetButton')}</Button>
          </>
        }
      />
    </PageContainer>
  );
};


// --- PLATFORM ADMIN DETAILS PAGE ---
const PlatformAdminDetailPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [selectedEvent, setSelectedEvent] = useState(null);

  // Modals
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [isSuspendModalOpen, setIsSuspendModalOpen] = useState(false);
  const [isRemoveModalOpen, setIsRemoveModalOpen] = useState(false);

  // Form State
  const [adminData, setAdminData] = useState({
    id: 'adm_1',
    name: 'Admin User',
    email: 'admin@kaori.io',
    role: 'Super Admin',
    status: 'Active',
    created: 'Jan 01, 2026',
    lastActive: 'Now'
  });
  
  const [newRole, setNewRole] = useState(adminData.role);
  const [removeError, setRemoveError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const showSuccess = (msg) => {
    setToastMessage(msg);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  const handleRoleChange = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 600));
    setAdminData(prev => ({ ...prev, role: newRole }));
    setIsProcessing(false);
    setIsRoleModalOpen(false);
    showSuccess(t('templates28BillingExport.roleUpdatedToast'));
  };

  const handleSuspendToggle = async () => {
    if (adminData.role === 'Super Admin' && adminData.status === 'Active') {
      alert(t('templates28BillingExport.cannotSuspendPrimaryAlert'));
      setIsSuspendModalOpen(false);
      return;
    }
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 600));
    setAdminData(prev => ({ ...prev, status: prev.status === 'Active' ? 'Suspended' : 'Active' }));
    setIsProcessing(false);
    setIsSuspendModalOpen(false);
    showSuccess(adminData.status === 'Active' ? t('templates28BillingExport.adminSuspendedToast') : t('templates28BillingExport.adminActivatedToast'));
  };

  const handleRemove = async () => {
    if (adminData.role === 'Super Admin') {
      setRemoveError(t('templates28BillingExport.cannotRemovePrimaryError'));
      return;
    }
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 600));
    setIsProcessing(false);
    setIsRemoveModalOpen(false);
    setActiveRoute('admin');
  };

  const getRoleBadgeVariant = (role) => {
    if (role === 'Super Admin') return 'current';
    if (role === 'Admin') return 'operational';
    return 'default';
  };

  const MOCK_ACTIVITY = [
    { timestamp: 'Oct 26, 2026 09:12:45', action: 'Login', resource: 'Platform Dashboard', status: 'Success', ip: '103.142.12.33', detail: 'Successful authentication via SSO.' },
    { timestamp: 'Oct 25, 2026 16:05:00', action: 'Invited Admin', resource: 'mike@kaori.io', status: 'Success', ip: '103.142.12.33', detail: 'Sent invite for Support role.' },
    { timestamp: 'Oct 25, 2026 14:32:01', action: 'Created Workspace', resource: 'ws_test_99', status: 'Success', ip: '103.142.12.33', detail: 'Provisioned new staging environment.' },
    { timestamp: 'Oct 24, 2026 10:15:22', action: 'Failed Login', resource: 'Platform Dashboard', status: 'Failed', ip: '113.190.55.12', detail: 'Invalid credentials provided.' },
  ];

  const activityTableData = MOCK_ACTIVITY.map(log => [
    <span key="timestamp" className="text-[var(--text-secondary)] text-xs whitespace-nowrap">{log.timestamp}</span>,
    <span key="action" className="font-medium text-[var(--text-primary)]">{log.action}</span>,
    <span key="resource" className="text-xs font-mono bg-[var(--bg-app)] px-1.5 py-0.5 rounded border border-[var(--border-color)] text-[var(--text-secondary)]">{log.resource}</span>,
    <Badge key="status" variant={log.status === 'Success' ? 'operational' : 'error'}>{log.status}</Badge>,
    <span key="ip" className="text-[var(--text-secondary)] text-xs font-mono">{log.ip}</span>,
  ]);

  const permissionsList = adminData.role === 'Super Admin' ? [
    { title: t('templates28BillingExport.permTitleGlobalSettings'), desc: t('templates28BillingExport.permDescGlobalSettings') },
    { title: t('templates28BillingExport.permTitleBilling'), desc: t('templates28BillingExport.permDescBilling') },
    { title: t('templates28BillingExport.permTitleUserAdmin'), desc: t('templates28BillingExport.permDescUserAdmin') },
    { title: t('templates28BillingExport.permTitleWorkspaceOversight'), desc: t('templates28BillingExport.permDescWorkspaceOversight') }
  ] : adminData.role === 'Admin' ? [
    { title: t('templates28BillingExport.permTitleWorkspaceMgmt'), desc: t('templates28BillingExport.permDescWorkspaceMgmt') },
    { title: t('templates28BillingExport.permTitleUserMgmt'), desc: t('templates28BillingExport.permDescUserMgmt') },
    { title: t('templates28BillingExport.permTitleApiKeyMgmt'), desc: t('templates28BillingExport.permDescApiKeyMgmt') }
  ] : [
    { title: t('templates28BillingExport.permTitleReadOnly'), desc: t('templates28BillingExport.permDescReadOnly') },
    { title: t('templates28BillingExport.permTitleAuditLogs'), desc: t('templates28BillingExport.permDescAuditLogs') }
  ];

  return (
    <PageContainer maxWidth="default" className="relative">
      {/* Toast */}
      {showToast && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="bg-[#F3F9F5] border border-[#8FBFA0] text-[#427A5B] px-4 py-2 rounded-full shadow-soft-md flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-4 h-4" /> {toastMessage}
          </div>
        </div>
      )}

      <PageHeader 
        showBack 
        onBack={() => setActiveRoute('admin')}
        title={adminData.name} 
        subtitle={adminData.email}
        actions={
          <>
            <Button variant="outline" onClick={() => { setNewRole(adminData.role); setIsRoleModalOpen(true); }} className="hidden sm:flex">
              <Shield className="w-4 h-4 mr-2" /> {t('templates28BillingExport.changeRoleButton')}
            </Button>
            <Button variant="outline" onClick={() => setActiveRoute('admin-reset-password')} className="hidden sm:flex">
              <Lock className="w-4 h-4 mr-2" /> {t('templates28BillingExport.resetPasswordButton')}
            </Button>

            {/* Mobile / Dropdown Menu */}
            <div className="relative group">
              <Button variant="tertiary" size="icon"><MoreVertical className="w-4 h-4" /></Button>
              <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-100 focus-within:opacity-100 focus-within:visible">
                <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors sm:hidden" onClick={() => { setNewRole(adminData.role); setIsRoleModalOpen(true); }}>
                  <Shield className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates28BillingExport.changeRoleButton')}
                </button>
                <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors sm:hidden" onClick={() => setActiveRoute('admin-reset-password')}>
                  <Lock className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates28BillingExport.resetPasswordButton')}
                </button>
                <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2 sm:hidden" />
                <button onClick={() => setIsSuspendModalOpen(true)} className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium">
                  {adminData.status === 'Active' ? <Ban className="w-4 h-4 opacity-80"/> : <Unlock className="w-4 h-4 opacity-80"/>}
                  {adminData.status === 'Active' ? t('templates28BillingExport.suspendAccessLabel') : t('templates28BillingExport.restoreAccessLabel')}
                </button>
                <button onClick={() => setIsRemoveModalOpen(true)} className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium">
                  <Trash2 className="w-4 h-4 opacity-80"/> {t('templates28BillingExport.removeAdminButton')}
                </button>
              </div>
            </div>
          </>
        } 
      />

      {/* Summary Card */}
      <Section>
        <Card className="p-5 sm:p-6 overflow-hidden relative">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
           <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6 relative z-10 items-start">
             <div className="flex items-center gap-3 col-span-2 sm:col-span-1">
               <div className="w-12 h-12 rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center text-lg font-medium text-[var(--primary-gold)] shrink-0">
                 {adminData.name.charAt(0).toUpperCase()}
               </div>
               <div className="flex flex-col">
                 <Badge variant={getRoleBadgeVariant(adminData.role)} className="w-fit">{adminData.role}</Badge>
               </div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.statusFieldLabel')}</p>
                <Badge variant={adminData.status === 'Active' ? 'operational' : 'error'} className="py-1">{adminData.status}</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.createdFieldLabel')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{adminData.created}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">{t('templates28BillingExport.lastActiveFieldLabel')}</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{adminData.lastActive}</div>
             </div>
           </div>
        </Card>
      </Section>

      {/* Tabs */}
      <Section>
        <Tabs defaultValue="overview" tabs={[
          {
            id: 'overview',
            label: t('templates28BillingExport.overviewTab'),
            content: (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
                {/* Left col - Recent Activity */}
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates28BillingExport.recentActivityTitle')}</h3>
                     <Button variant="tertiary" size="sm" onClick={() => {}}>{t('templates28BillingExport.viewAllButton')}</Button>
                  </div>
                  <DataTable
                    pagination={false}
                    columns={[t('templates28BillingExport.colTimestamp'), t('templates28BillingExport.colAction'), t('templates28BillingExport.colResource'), t('templates28BillingExport.colStatus'), t('templates28BillingExport.colIp')]}
                    data={activityTableData.slice(0, 3)}
                    loading={isLoading}
                    onRowClick={(row: any) => setSelectedEvent(row)}
                  />
                </div>

                {/* Right col - Security Info */}
                <div className="space-y-6 sm:space-y-8">
                   <div className="space-y-4">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates28BillingExport.securityProfileTitle')}</h3>
                     <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-[#5C856A]" />
                            <span className="text-sm font-medium text-[var(--text-primary)]">{t('templates28BillingExport.mfaEnforcedLabel')}</span>
                          </div>
                          <Badge variant="operational">{t('templates28BillingExport.enabledLabel')}</Badge>
                        </div>
                        <div className="h-[1px] bg-[var(--border-color)]/50" />
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Laptop className="w-4 h-4 text-[var(--text-secondary)]" />
                            <span className="text-sm font-medium text-[var(--text-primary)]">{t('templates28BillingExport.activeSessionsLabel')}</span>
                          </div>
                          <span className="text-sm font-medium text-[var(--text-primary)]">2</span>
                        </div>
                     </div>
                   </div>
                </div>
              </div>
            )
          },
          {
            id: 'activity',
            label: t('templates28BillingExport.activityTab'),
            content: (
              <div className="space-y-4">
                <DataTable
                  columns={[t('templates28BillingExport.colTimestamp'), t('templates28BillingExport.colAction'), t('templates28BillingExport.colResource'), t('templates28BillingExport.colStatus'), t('templates28BillingExport.colIp')]}
                  data={activityTableData}
                  loading={isLoading}
                  onRowClick={(row: any) => setSelectedEvent(row)}
                />
              </div>
            )
          },
          {
            id: 'permissions',
            label: t('templates28BillingExport.permissionsTab'),
            content: (
              <div className="max-w-3xl space-y-6">
                <Alert variant="info">
                  {t('templates28BillingExport.permissionsInferredPrefix')} <strong>{adminData.role}</strong> {t('templates28BillingExport.permissionsInferredSuffix')}
                </Alert>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {permissionsList.map((perm, i) => (
                    <Card key={i} className="p-4 border-l-4 border-l-[var(--primary-gold)]">
                      <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{perm.title}</h4>
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{perm.desc}</p>
                    </Card>
                  ))}
                </div>
              </div>
            )
          }
        ]} />
      </Section>

      {/* Modals */}
      <Modal
        isOpen={isRoleModalOpen}
        onClose={() => !isProcessing && setIsRoleModalOpen(false)}
        title={t('templates28BillingExport.changeRoleModalTitle')}
        description={t('templates28BillingExport.updateAccessLevelPrefix', { name: adminData.name })}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsRoleModalOpen(false)} disabled={isProcessing}>{t('templates28BillingExport.cancelButton')}</Button>
            <Button onClick={handleRoleChange} isLoading={isProcessing} disabled={newRole === adminData.role}>{t('templates28BillingExport.updateRoleButton')}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select
            label={t('templates28BillingExport.platformRoleLabel')}
            options={[
              {label: t('templates28BillingExport.superAdminOption'), value: 'Super Admin'},
              {label: t('templates28BillingExport.adminOption'), value: 'Admin'},
              {label: t('templates28BillingExport.supportOption'), value: 'Support'}
            ]}
            value={newRole}
            onChange={setNewRole}
          />
          {newRole === 'Super Admin' && newRole !== adminData.role && (
            <Alert variant="warning" className="mt-2">
              {t('templates28BillingExport.grantingFullPrivilegesWarning')}
            </Alert>
          )}
          {adminData.role === 'Super Admin' && newRole !== 'Super Admin' && (
            <Alert variant="info" className="mt-2">
              {t('templates28BillingExport.downgradingSuperAdminInfo')}
            </Alert>
          )}
        </div>
      </Modal>

      <Modal
        isOpen={isSuspendModalOpen}
        onClose={() => !isProcessing && setIsSuspendModalOpen(false)}
        title={adminData.status === 'Active' ? t('templates28BillingExport.suspendAdminAccessTitle') : t('templates28BillingExport.restoreAdminAccessTitle')}
        description={adminData.status === 'Active' ? t('templates28BillingExport.confirmSuspendDesc', { name: adminData.name }) : t('templates28BillingExport.confirmRestoreDesc', { name: adminData.name })}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsSuspendModalOpen(false)} disabled={isProcessing}>{t('templates28BillingExport.cancelButton')}</Button>
            {adminData.status === 'Active' ? (
              <Button variant="destructive" onClick={handleSuspendToggle} isLoading={isProcessing}>{t('templates28BillingExport.suspendAccessButton')}</Button>
            ) : (
              <Button onClick={handleSuspendToggle} isLoading={isProcessing}>{t('templates28BillingExport.restoreAccessButton')}</Button>
            )}
          </>
        }
      >
        {adminData.status === 'Active' ? (
          <Alert variant="warning" className="mb-2">
            {t('templates28BillingExport.loseAccessWarningBody')}
          </Alert>
        ) : (
          <div className="text-sm text-[var(--text-secondary)]">
            {t('templates28BillingExport.restoreAccessBodyPrefix')} {adminData.role}.
          </div>
        )}
      </Modal>

      <Modal
        isOpen={isRemoveModalOpen}
        onClose={() => { setIsRemoveModalOpen(false); setRemoveError(''); }}
        title={t('templates28BillingExport.removeAdminModalTitle')}
        description={t('templates28BillingExport.confirmRemoveAdminDesc', { name: adminData.name })}
        footer={
          <>
            <Button variant="outline" onClick={() => { setIsRemoveModalOpen(false); setRemoveError(''); }} disabled={isProcessing}>{t('templates28BillingExport.cancelButton')}</Button>
            <Button variant="destructive" onClick={handleRemove} isLoading={isProcessing}>{t('templates28BillingExport.removeAdminModalTitle')}</Button>
          </>
        }
      >
        {removeError && <Alert variant="error" className="mb-4">{removeError}</Alert>}
        <Alert variant="error" className="mb-2">
          {t('templates28BillingExport.removeAdminIrreversibleBody')}
        </Alert>
      </Modal>

      {/* Detail Drawer (For Activity Row Click) */}
      <Drawer
        isOpen={!!selectedEvent}
        onClose={() => setSelectedEvent(null)}
        title={t('templates28BillingExport.eventDetailsTitle')}
      >
        {selectedEvent && (
          <div className="space-y-6">
            <div className="flex flex-col gap-2 bg-[var(--bg-app)] p-4 rounded-md-custom border border-[var(--border-color)]">
               <h3 className="text-base font-semibold text-[var(--text-primary)]">{selectedEvent[1]?.props?.children || selectedEvent[1]}</h3>
               <p className="text-xs text-[var(--text-secondary)]">{selectedEvent[0]?.props?.children || selectedEvent[0]}</p>
            </div>
            <div className="grid grid-cols-2 gap-y-4 gap-x-6 text-sm">
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">{t('templates28BillingExport.actorLabel')}</p>
                <p className="font-medium text-[var(--text-primary)]">{adminData.name}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">{t('templates28BillingExport.colResource')}</p>
                <p className="font-mono text-[var(--text-primary)] text-xs">{selectedEvent[2]?.props?.children || selectedEvent[2]}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">{t('templates28BillingExport.ipAddressLabel')}</p>
                <p className="font-mono text-[var(--text-primary)] text-xs">{selectedEvent[4]?.props?.children || selectedEvent[4]}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">{t('templates28BillingExport.statusFieldLabel')}</p>
                {selectedEvent[3]}
              </div>
            </div>
            <div className="h-[1px] bg-[var(--border-color)] w-full" />
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-[var(--text-primary)]">{t('templates28BillingExport.metadataContextTitle')}</h4>
              <div className="bg-[#1C1C1C] rounded-md-custom p-4 overflow-x-auto shadow-inner border border-[#2A2A2A]">
                <pre className="text-[11px] text-[#A5B4CB] font-mono leading-relaxed">
{JSON.stringify({
  event_id: `evt_${Math.random().toString(36).substr(2, 9)}`,
  session_id: "sess_desktop_2",
  user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
  risk_score: "low"
}, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </Drawer>

    </PageContainer>
  );
};


// --- PLATFORM ADMINS INVITE PAGE ---
const PlatformAdminInvitePage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [step, setStep] = useState('form');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    email: '',
    role: 'Admin',
    message: ''
  });
  
  const [errors, setErrors] = useState({});

  const validate = () => {
    const newErrors = {};
    if (!formData.email) newErrors.email = t('templates28BillingExport.emailRequiredError');
    else if (!/^\S+@\S+\.\S+$/.test(formData.email)) newErrors.email = t('templates28BillingExport.emailInvalidError');
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInvite = async () => {
    if (!validate()) return;
    setIsSubmitting(true);
    await new Promise(r => setTimeout(r, 1200));
    setIsSubmitting(false);
    setStep('success');
  };

  return (
    <PageContainer maxWidth="narrow" className="pt-8">
      
      {step === 'form' && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
          <PageHeader
            showBack
            onBack={() => setActiveRoute('admin')}
            title={t('templates28BillingExport.invitePlatformAdminTitle')}
            subtitle={t('templates28BillingExport.invitePlatformAdminSubtitle')}
          />

          <Card className="p-6 sm:p-8 mt-8 shadow-soft-md">
            <div className="space-y-6">

              <Input
                label={t('templates28BillingExport.emailAddressLabel')}
                placeholder="admin@company.com"
                value={formData.email}
                onChange={e => { setFormData({...formData, email: e.target.value}); setErrors({}); }}
                error={errors.email}
                autoFocus
              />

              <div className="space-y-2">
                <Select
                  label={t('templates28BillingExport.roleLabel')}
                  options={[
                    {label: t('templates28BillingExport.superAdminOption'), value: 'Super Admin'},
                    {label: t('templates28BillingExport.adminOption'), value: 'Admin'},
                    {label: t('templates28BillingExport.supportOption'), value: 'Support'}
                  ]}
                  value={formData.role}
                  onChange={v => setFormData({...formData, role: v})}
                />

                {/* Dynamic Role Description */}
                <div className="mt-2 text-xs text-[var(--text-secondary)] bg-[var(--bg-app)] p-3 rounded-md-custom border border-[var(--border-color)]">
                  {formData.role === 'Super Admin' && (
                    <div className="flex flex-col gap-2">
                      <span className="text-[#9B5050] font-medium flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" /> {t('templates28BillingExport.fullSystemAccessLabel')}
                      </span>
                      <span>{t('templates28BillingExport.superAdminDescLong')}</span>
                    </div>
                  )}
                  {formData.role === 'Admin' && t('templates28BillingExport.adminRoleDesc')}
                  {formData.role === 'Support' && t('templates28BillingExport.supportRoleDesc')}
                </div>
              </div>

              <Input
                label={t('templates28BillingExport.addMessageLabel')}
                placeholder={t('templates28BillingExport.addMessagePlaceholder')}
                value={formData.message}
                onChange={e => setFormData({...formData, message: e.target.value})}
                multiline
              />

            </div>

            <div className="mt-8 pt-6 border-t border-[var(--border-color)] flex items-center justify-between">
               <Button variant="tertiary" onClick={() => setActiveRoute('admin')} disabled={isSubmitting}>{t('templates28BillingExport.cancelButton')}</Button>
               <Button onClick={handleInvite} isLoading={isSubmitting}><Mail className="w-4 h-4 mr-2"/> {t('templates28BillingExport.sendInvitationButton')}</Button>
            </div>
          </Card>
        </div>
      )}

      {step === 'success' && (
        <div className="animate-in fade-in zoom-in-[0.98] duration-500">
           <PageHeader title={t('templates28BillingExport.invitationSentTitle')} />
           <Card className="p-8 mt-8 shadow-soft-md flex flex-col items-center text-center">
             <div className="w-16 h-16 rounded-full bg-[#F3F9F5] border border-[#8FBFA0]/40 flex items-center justify-center mb-6">
               <CheckCircle2 className="w-8 h-8 text-[#5C856A]" />
             </div>
             <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">{t('templates28BillingExport.invitationSuccessHeading')}</h2>
             <p className="text-sm text-[var(--text-secondary)] mb-8 max-w-sm">
               {t('templates28BillingExport.emailSentToPrefix')} <strong className="text-[var(--text-primary)]">{formData.email}</strong> {t('templates28BillingExport.invitationSentSuffix', { role: formData.role })}
             </p>
             <div className="flex gap-3">
               <Button variant="outline" onClick={() => { setFormData({email:'', role:'Admin', message:''}); setStep('form'); }}>{t('templates28BillingExport.inviteAnotherButton')}</Button>
               <Button onClick={() => setActiveRoute('admin')}>{t('templates28BillingExport.backToAdminsButton')}</Button>
             </div>
           </Card>
        </div>
      )}
    </PageContainer>
  );
};


// --- PLATFORM ADMINS PAGE ---
const MOCK_ADMINS = [
  { id: 'adm_1', name: 'Admin User', email: 'admin@kaori.io', role: 'Super Admin', status: 'Active', lastActive: 'Now', created: 'Jan 01, 2026' },
  { id: 'adm_2', name: 'Sarah Jenkins', email: 'sarah@kaori.io', role: 'Admin', status: 'Active', lastActive: '2 hours ago', created: 'Jan 15, 2026' },
  { id: 'adm_3', name: 'Mike Chen', email: 'mike@kaori.io', role: 'Support', status: 'Invited', lastActive: '-', created: 'Oct 20, 2026' },
  { id: 'adm_4', name: 'Emily Davis', email: 'emily@kaori.io', role: 'Admin', status: 'Suspended', lastActive: '1 month ago', created: 'Feb 22, 2026' },
];

const AdminActionsDropdown = ({  admin, onRemove, onSuspend, onActivate, onResetPassword, onViewDetails  }: any) => {
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
          
          <button 
            onClick={() => { onViewDetails(); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
          >
            <Eye className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates28BillingExport.viewDetailsAction')}
          </button>

          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Shield className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates28BillingExport.changeRoleButton')}
          </button>

          <button
            onClick={() => { onResetPassword(admin); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
          >
            <Lock className="w-4 h-4 text-[var(--text-secondary)]"/> {t('templates28BillingExport.resetPasswordButton')}
          </button>

          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />

          {admin.status === 'Active' || admin.status === 'Invited' ? (
            <button
              onClick={() => { onSuspend(admin); setIsOpen(false); }}
              className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium"
            >
              <Ban className="w-4 h-4 opacity-80"/> {t('templates28BillingExport.suspendAccessLabel')}
            </button>
          ) : (
            <button
              onClick={() => { onActivate(admin); setIsOpen(false); }}
              className="w-full text-left px-3 py-1.5 text-sm text-[#5C856A] hover:bg-[#F3F9F5] flex items-center gap-2 transition-colors font-medium"
            >
              <Unlock className="w-4 h-4 opacity-80"/> {t('templates28BillingExport.restoreAccessLabel')}
            </button>
          )}

          <button
            onClick={() => { onRemove(admin); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium"
          >
            <Trash2 className="w-4 h-4 opacity-80"/> {t('templates28BillingExport.removeAdminButton')}
          </button>
        </div>
      )}
    </div>
  );
};

const PlatformAdminsPage = ({  setActiveRoute  }: any) => {
  const t = useT();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  
  const [admins, setAdmins] = useState(MOCK_ADMINS);
  const [isLoading, setIsLoading] = useState(true);
  
  const [adminToRemove, setAdminToRemove] = useState(null);
  const [removeError, setRemoveError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const handleRemove = () => {
    if (adminToRemove?.role === 'Super Admin') {
      const superAdminCount = admins.filter(a => a.role === 'Super Admin').length;
      if (superAdminCount <= 1) {
        setRemoveError(t('templates28BillingExport.cannotRemoveLastSuperAdminError'));
        return;
      }
    }
    setAdmins(prev => prev.filter(a => a.id !== adminToRemove.id));
    setAdminToRemove(null);
    setRemoveError('');
  };

  const handleSuspend = (admin) => {
    if (admin.role === 'Super Admin') {
      const superAdminCount = admins.filter(a => a.role === 'Super Admin' && a.status === 'Active').length;
      if (superAdminCount <= 1) {
        alert(t('templates28BillingExport.cannotSuspendLastActiveError'));
        return;
      }
    }
    setAdmins(prev => prev.map(a => a.id === admin.id ? { ...a, status: 'Suspended' } : a));
  };

  const handleActivate = (admin) => {
    setAdmins(prev => prev.map(a => a.id === admin.id ? { ...a, status: 'Active' } : a));
  };

  const handleResetPassword = (admin) => {
     setActiveRoute('admin-reset-password');
  };

  const filteredAdmins = admins.filter(a => {
    const matchesSearch = a.name.toLowerCase().includes(search.toLowerCase()) || a.email.toLowerCase().includes(search.toLowerCase());
    const matchesRole = roleFilter === 'all' || a.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || a.status === statusFilter;
    return matchesSearch && matchesRole && matchesStatus;
  });

  const getRoleBadgeVariant = (role) => {
    if (role === 'Super Admin') return 'current';
    if (role === 'Admin') return 'operational';
    return 'default';
  };

  const mappedData = filteredAdmins.map(a => [
    <div key="admin-info" className="flex items-center gap-3">
       <div className="w-8 h-8 rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center text-xs font-medium text-[var(--primary-gold)]">
         {a.name.charAt(0).toUpperCase()}
       </div>
       <div>
         <div className="font-medium text-[var(--text-primary)] flex items-center gap-2">
           {a.name} 
           {a.id === 'adm_1' && <span className="text-[10px] bg-[var(--bg-app)] border border-[var(--border-color)] px-1.5 py-0.5 rounded text-[var(--text-secondary)]">{t('templates28BillingExport.youTag')}</span>}
         </div>
         <div className="text-xs text-[var(--text-secondary)] mt-0.5">{a.email}</div>
       </div>
    </div>,
    <Badge key="admin-role" variant={getRoleBadgeVariant(a.role)}>{a.role}</Badge>,
    <Badge key="admin-status" variant={a.status === 'Active' ? 'operational' : a.status === 'Suspended' ? 'error' : 'warning'}>{a.status}</Badge>,
    <span key="admin-last" className="text-[var(--text-secondary)] whitespace-nowrap">{a.lastActive}</span>,
    <span key="admin-joined" className="text-[var(--text-secondary)] whitespace-nowrap">{a.created}</span>,
    <AdminActionsDropdown 
      key="admin-actions" 
      admin={a} 
      onRemove={setAdminToRemove} 
      onSuspend={handleSuspend}
      onActivate={handleActivate}
      onResetPassword={handleResetPassword}
      onViewDetails={() => setActiveRoute('admin-details')}
    />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader
        title={t('templates28BillingExport.platformAdminsTitle')}
        subtitle={t('templates28BillingExport.platformAdminsSubtitle')}
        actions={
          <Button onClick={() => setActiveRoute('admin-invite')}>
            <UserPlus className="w-4 h-4 mr-2"/> {t('templates28BillingExport.inviteAdminButton')}
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
              placeholder={t('templates28BillingExport.searchByNameEmailPlaceholder')}
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex w-full sm:w-auto gap-3 shrink-0">
            <div className="w-full sm:w-40">
              <Select
                value={roleFilter}
                onChange={setRoleFilter}
                options={[
                  {label: t('templates28BillingExport.allRolesOption'), value: 'all'},
                  {label: t('templates28BillingExport.superAdminOption'), value: 'Super Admin'},
                  {label: t('templates28BillingExport.adminOption'), value: 'Admin'},
                  {label: t('templates28BillingExport.supportOption'), value: 'Support'}
                ]}
                placeholder={t('templates28BillingExport.roleLabel')}
              />
            </div>
            <div className="w-full sm:w-40">
              <Select
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  {label: t('templates28BillingExport.allStatuses'), value: 'all'},
                  {label: t('templates28BillingExport.activeStatusLabel'), value: 'Active'},
                  {label: t('templates28BillingExport.invitedStatusLabel'), value: 'Invited'},
                  {label: t('templates28BillingExport.suspendedStatusLabel'), value: 'Suspended'}
                ]}
                placeholder={t('templates28BillingExport.statusFieldLabel')}
              />
            </div>
          </div>
          {(search || roleFilter !== 'all' || statusFilter !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setRoleFilter('all'); setStatusFilter('all');}} className="px-3">
              {t('templates28BillingExport.clearFiltersButton')}
            </Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable
          columns={[t('templates28BillingExport.colNameEmail'), t('templates28BillingExport.colRole'), t('templates28BillingExport.colStatus'), t('templates28BillingExport.colLastActive'), t('templates28BillingExport.colCreatedAt'), ""]}
          data={mappedData}
          loading={isLoading}
        />
      </Section>

      {/* Remove Confirmation Modal */}
      <Modal
        isOpen={!!adminToRemove}
        onClose={() => { setAdminToRemove(null); setRemoveError(''); }}
        title={t('templates28BillingExport.removePlatformAdminTitle')}
        description={t('templates28BillingExport.confirmRemovePlatformAdminDesc', { name: adminToRemove?.name })}
        footer={
          <>
            <Button variant="outline" onClick={() => { setAdminToRemove(null); setRemoveError(''); }}>{t('templates28BillingExport.cancelButton')}</Button>
            <Button variant="destructive" onClick={handleRemove}>{t('templates28BillingExport.removeAdminModalTitle')}</Button>
          </>
        }
      >
        {removeError && (
          <Alert variant="error" className="mb-4">
            {removeError}
          </Alert>
        )}
        <div className="text-sm text-[var(--text-secondary)]">
          {t('templates28BillingExport.actionCannotBeUndoneNote')}
        </div>
      </Modal>

    </PageContainer>
  );
};

// ==========================================
// MAIN PLATFORM SHELL COMPONENT
// ==========================================

export default function KaoriPlatformShell() {
  const t = useT();
  const [activeRoute, setActiveRoute] = useState('billing-export'); // Set default to Billing Export for demo
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
             activeRoute === 'overview' ? <PlatformOverview /> : 
             activeRoute === 'sessions' ? <SessionsPage /> : (
              <PageContainer maxWidth="narrow">
                <PageHeader title={t('templates28BillingExport.moduleTitleTemplate', { label: t(NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label || '') })} subtitle={t('templates28BillingExport.sectionBeingDesignedSubtitle')} />
                <Section>
                  <Card className="flex flex-col items-center justify-center py-20 px-4 text-center border-dashed bg-[var(--bg-card)]/50 mx-auto w-full animate-in fade-in duration-300">
                    <div className="w-12 h-12 rounded-lg-custom bg-[var(--bg-sidebar)] flex items-center justify-center border border-[var(--border-color)] mb-4">
                      {React.createElement(NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.icon || LayoutDashboard, { className: 'w-6 h-6 text-[var(--text-secondary)]' })}
                    </div>
                    <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">{t('templates28BillingExport.workInProgressTitle')}</h3>
                    <p className="text-sm text-[var(--text-secondary)] max-w-sm">{t('templates28BillingExport.contentForRouteText', { route: activeRoute })}</p>
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
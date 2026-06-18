// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 22Plastform Admin Invate.jsx by convert_jsx_to_tsx.py.
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
  RefreshCcw,
  BarChart3,
  Lock,
  Unlock
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
const Select = ({  label, placeholder = "Select an option", options = [], value, onChange, error, disabled  }: any) => {
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
        {selectedOption ? selectedOption.label : placeholder}
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
const DatePicker = ({  label, placeholder = "Pick a date", date, setDate  }: any) => {
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
        {date ? date : placeholder}
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
                  <span className="text-sm font-medium text-[var(--text-primary)]">No results found</span>
                  <span className="text-xs text-[var(--text-secondary)]">Try adjusting your filters</span>
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
          <span className="text-xs text-[var(--text-secondary)]">Showing 1 to {data.length} of {data.length} results</span>
          <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled>Previous</Button>
              <Button variant="outline" size="sm">Next</Button>
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
      aria-label="Copy to clipboard"
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
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Notifications</h3>
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
              <Shield className="w-4 h-4 text-[var(--text-secondary)]" /> Security & Sessions
            </button>
          </div>
          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" />
          <div className="p-1.5">
            <button className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] transition-colors flex items-center gap-2 font-medium">
              <LogOut className="w-4 h-4" /> Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const GlobalHeader = ({  activeRoute, setActiveRoute, setIsMobileMenuOpen  }: any) => {
  let routeLabel = NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label;
  if (activeRoute === 'workspace-details') routeLabel = 'Workspaces / Overview';
  else if (activeRoute === 'workspace-members') routeLabel = 'Workspaces / Members';
  else if (activeRoute === 'billing') routeLabel = 'Workspaces / Billing';
  else if (activeRoute === 'audit-logs') routeLabel = 'Workspaces / Audit Logs';
  else if (activeRoute === 'workspace-new') routeLabel = 'Workspaces / New Workspace';
  else if (activeRoute === 'workspace-edit') routeLabel = 'Workspaces / Settings';
  else if (activeRoute === 'keys-new') routeLabel = 'API Keys / Create Key';
  else if (activeRoute === 'key-details') routeLabel = 'API Keys / Details';
  else if (activeRoute === 'admin-invite') routeLabel = 'Admins / Invite';
  else if (!routeLabel) routeLabel = activeRoute;

  return (
    <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/90 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6 transition-all duration-300">
      <div className="flex items-center gap-4">
        <button className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]" onClick={() => setIsMobileMenuOpen(true)}>
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:flex items-center text-sm font-medium">
          <span className="text-[var(--text-secondary)]">Platform</span>
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
              <input type="text" placeholder="Search..." className="h-8 w-48 pl-8 pr-10 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm" />
            </div>
            <Button variant="outline" size="sm" onClick={() => setActiveRoute('workspace-new')} className="hidden md:flex"><Plus className="w-3.5 h-3.5 mr-1.5" /> Workspace</Button>
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
  const collapsed = isCollapsed && !isMobile;
  const currentHighlight = 
    (activeRoute === 'workspace-details' || activeRoute === 'workspace-members' || activeRoute === 'billing' || activeRoute === 'audit-logs' || activeRoute === 'workspace-new' || activeRoute === 'workspace-edit') ? 'workspaces' : 
    (activeRoute === 'keys-new' || activeRoute === 'key-details') ? 'keys' : 
    (activeRoute === 'admin-invite') ? 'admin' : 
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
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mt-0.5">Platform</span>
          </div>
        )}
      </div>

      <nav aria-label="Main Navigation" className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 space-y-6">
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
            {!collapsed && <span className="text-xs font-medium">Collapse sidebar</span>}
          </button>
        )}
      </div>
    </aside>
  );
};


// ==========================================
// 4. VIEWS & PAGES
// ==========================================

// --- PLATFORM ADMINS INVITE PAGE ---
const PlatformAdminInvitePage = ({  setActiveRoute  }: any) => {
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
    if (!formData.email) newErrors.email = 'Email address is required';
    else if (!/^\S+@\S+\.\S+$/.test(formData.email)) newErrors.email = 'Please enter a valid email address';
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
            title="Invite Platform Admin" 
            subtitle="Grant administrative access to manage platform resources."
          />
          
          <Card className="p-6 sm:p-8 mt-8 shadow-soft-md">
            <div className="space-y-6">
              
              <Input 
                label="Email address" 
                placeholder="admin@company.com" 
                value={formData.email}
                onChange={e => { setFormData({...formData, email: e.target.value}); setErrors({}); }}
                error={errors.email}
                autoFocus
              />
              
              <div className="space-y-2">
                <Select 
                  label="Role" 
                  options={[
                    {label: 'Super Admin', value: 'Super Admin'}, 
                    {label: 'Admin', value: 'Admin'},
                    {label: 'Support', value: 'Support'}
                  ]}
                  value={formData.role}
                  onChange={v => setFormData({...formData, role: v})}
                />
                
                {/* Dynamic Role Description */}
                <div className="mt-2 text-xs text-[var(--text-secondary)] bg-[var(--bg-app)] p-3 rounded-md-custom border border-[var(--border-color)]">
                  {formData.role === 'Super Admin' && (
                    <div className="flex flex-col gap-2">
                      <span className="text-[#9B5050] font-medium flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" /> Full system access
                      </span>
                      <span>Super Admins have unrestricted access to all platform settings, billing, and global user management. Grant this role with caution.</span>
                    </div>
                  )}
                  {formData.role === 'Admin' && "Can manage workspaces, API keys, and platform-level users. Cannot access billing."}
                  {formData.role === 'Support' && "Read-only access to workspaces and logs. Useful for troubleshooting without operational risk."}
                </div>
              </div>
              
              <Input 
                label="Add a message (optional)" 
                placeholder="Include a personal note with the invitation..." 
                value={formData.message}
                onChange={e => setFormData({...formData, message: e.target.value})}
                multiline
              />

            </div>
            
            <div className="mt-8 pt-6 border-t border-[var(--border-color)] flex items-center justify-between">
               <Button variant="tertiary" onClick={() => setActiveRoute('admin')} disabled={isSubmitting}>Cancel</Button>
               <Button onClick={handleInvite} isLoading={isSubmitting}><Mail className="w-4 h-4 mr-2"/> Send invitation</Button>
            </div>
          </Card>
        </div>
      )}

      {step === 'success' && (
        <div className="animate-in fade-in zoom-in-[0.98] duration-500">
           <PageHeader title="Invitation sent" />
           <Card className="p-8 mt-8 shadow-soft-md flex flex-col items-center text-center">
             <div className="w-16 h-16 rounded-full bg-[#F3F9F5] border border-[#8FBFA0]/40 flex items-center justify-center mb-6">
               <CheckCircle2 className="w-8 h-8 text-[#5C856A]" />
             </div>
             <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">Invitation successfully sent</h2>
             <p className="text-sm text-[var(--text-secondary)] mb-8 max-w-sm">
               An email has been sent to <strong className="text-[var(--text-primary)]">{formData.email}</strong> with instructions to join the platform as {formData.role}.
             </p>
             <div className="flex gap-3">
               <Button variant="outline" onClick={() => { setFormData({email:'', role:'Admin', message:''}); setStep('form'); }}>Invite another</Button>
               <Button onClick={() => setActiveRoute('admin')}>Back to Admins</Button>
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

const AdminActionsDropdown = ({  admin, onRemove, onSuspend, onActivate, onResetPassword  }: any) => {
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
            <Shield className="w-4 h-4 text-[var(--text-secondary)]"/> Change role
          </button>
          
          <button 
            onClick={() => { onResetPassword(admin); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
          >
            <Lock className="w-4 h-4 text-[var(--text-secondary)]"/> Reset password
          </button>
          
          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          
          {admin.status === 'Active' || admin.status === 'Invited' ? (
            <button 
              onClick={() => { onSuspend(admin); setIsOpen(false); }}
              className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium"
            >
              <Ban className="w-4 h-4 opacity-80"/> Suspend access
            </button>
          ) : (
            <button 
              onClick={() => { onActivate(admin); setIsOpen(false); }}
              className="w-full text-left px-3 py-1.5 text-sm text-[#5C856A] hover:bg-[#F3F9F5] flex items-center gap-2 transition-colors font-medium"
            >
              <Unlock className="w-4 h-4 opacity-80"/> Restore access
            </button>
          )}

          <button 
            onClick={() => { onRemove(admin); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium"
          >
            <Trash2 className="w-4 h-4 opacity-80"/> Remove admin
          </button>
        </div>
      )}
    </div>
  );
};

const PlatformAdminsPage = ({  setActiveRoute  }: any) => {
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
        setRemoveError("You cannot remove the last Super Admin. Promote another user first.");
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
        alert("Cannot suspend the last active Super Admin."); 
        return;
      }
    }
    setAdmins(prev => prev.map(a => a.id === admin.id ? { ...a, status: 'Suspended' } : a));
  };

  const handleActivate = (admin) => {
    setAdmins(prev => prev.map(a => a.id === admin.id ? { ...a, status: 'Active' } : a));
  };

  const handleResetPassword = (admin) => {
     alert(`Password reset link sent to ${admin.email}`);
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
           {a.id === 'adm_1' && <span className="text-[10px] bg-[var(--bg-app)] border border-[var(--border-color)] px-1.5 py-0.5 rounded text-[var(--text-secondary)]">You</span>}
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
    />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader 
        title="Platform Admins" 
        subtitle="Manage global administrators and access permissions across the platform." 
        actions={
          <Button onClick={() => setActiveRoute('admin-invite')}>
            <UserPlus className="w-4 h-4 mr-2"/> Invite admin
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
              placeholder="Search by name or email..."
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
                  {label: 'All Roles', value: 'all'}, 
                  {label: 'Super Admin', value: 'Super Admin'}, 
                  {label: 'Admin', value: 'Admin'},
                  {label: 'Support', value: 'Support'}
                ]} 
                placeholder="Role" 
              />
            </div>
            <div className="w-full sm:w-40">
              <Select 
                value={statusFilter} 
                onChange={setStatusFilter} 
                options={[
                  {label: 'All Statuses', value: 'all'}, 
                  {label: 'Active', value: 'Active'}, 
                  {label: 'Invited', value: 'Invited'},
                  {label: 'Suspended', value: 'Suspended'}
                ]} 
                placeholder="Status" 
              />
            </div>
          </div>
          {(search || roleFilter !== 'all' || statusFilter !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setRoleFilter('all'); setStatusFilter('all');}} className="px-3">
              Clear filters
            </Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable 
          columns={["Name / Email", "Role", "Status", "Last Active", "Created At", ""]} 
          data={mappedData} 
          loading={isLoading} 
        />
      </Section>

      {/* Remove Confirmation Modal */}
      <Modal 
        isOpen={!!adminToRemove} 
        onClose={() => { setAdminToRemove(null); setRemoveError(''); }}
        title="Remove Platform Admin"
        description={`Are you sure you want to remove ${adminToRemove?.name} from platform administration? They will lose all access immediately.`}
        footer={
          <>
            <Button variant="outline" onClick={() => { setAdminToRemove(null); setRemoveError(''); }}>Cancel</Button>
            <Button variant="destructive" onClick={handleRemove}>Remove Admin</Button>
          </>
        }
      >
        {removeError && (
          <Alert variant="error" className="mb-4">
            {removeError}
          </Alert>
        )}
        <div className="text-sm text-[var(--text-secondary)]">
          This action cannot be undone. To restore access later, you will need to send a new invitation.
        </div>
      </Modal>

    </PageContainer>
  );
};


// --- API KEY DETAILS PAGE ---

const ApiKeyDetailPage = ({  setActiveRoute  }: any) => {
  const [isRotateOpen, setIsRotateOpen] = useState(false);
  const [isRevokeOpen, setIsRevokeOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [generatedKey, setGeneratedKey] = useState(null);
  const [showSavedToast, setShowSavedToast] = useState(false);
  
  // Mock Key Data
  const [keyData, setKeyData] = useState({
    id: 'key_1',
    name: 'Production Backend',
    keyHash: '982b3a1c8f0e4d5a',
    scope: 'Full Access',
    status: 'Active',
    created: 'Oct 01, 2026',
    lastUsed: '2 mins ago',
    expires: 'Never'
  });
  
  const [editName, setEditName] = useState(keyData.name);

  const handleRotateConfirm = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 800));
    
    const fullSecret = `sk_live_${Math.random().toString(36).substring(2, 18)}`;
    setKeyData(prev => ({ ...prev, keyHash: fullSecret.substring(fullSecret.length - 16), created: 'Just now', lastUsed: 'Never' }));
    setGeneratedKey(fullSecret);
    setIsProcessing(false);
  };

  const handleRevokeConfirm = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 600));
    setKeyData(prev => ({ ...prev, status: 'Revoked' }));
    setIsProcessing(false);
    setIsRevokeOpen(false);
  };

  const handleSaveSettings = async () => {
    if (editName === keyData.name) return;
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 600));
    setKeyData(prev => ({ ...prev, name: editName }));
    setIsProcessing(false);
    setShowSavedToast(true);
    setTimeout(() => setShowSavedToast(false), 3000);
  };

  return (
    <PageContainer maxWidth="default" className="relative">
      
      {/* Success Toast */}
      {showSavedToast && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="bg-[#F3F9F5] border border-[#8FBFA0] text-[#427A5B] px-4 py-2 rounded-full shadow-soft-md flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-4 h-4" /> Key settings updated
          </div>
        </div>
      )}

      <PageHeader 
        showBack 
        onBack={() => setActiveRoute('keys')}
        title={keyData.name} 
        subtitle={maskKey(keyData.keyHash)}
        actions={
          keyData.status === 'Active' ? (
            <>
              <Button variant="outline" onClick={() => setIsRotateOpen(true)} className="hidden sm:flex">
                <RefreshCcw className="w-4 h-4 mr-2" /> Rotate key
              </Button>
              <Button variant="destructive-soft" onClick={() => setIsRevokeOpen(true)}>
                <Ban className="w-4 h-4 mr-2" /> Revoke
              </Button>
            </>
          ) : (
            <Button variant="destructive" onClick={() => setActiveRoute('keys')}>
              <Trash2 className="w-4 h-4 mr-2" /> Delete
            </Button>
          )
        } 
      />

      {/* Summary Card */}
      <Section>
        <Card className="p-5 sm:p-6 overflow-hidden relative">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
           <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 relative z-10">
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Status</p>
                <Badge variant={keyData.status === 'Active' ? 'success' : 'default'} className="py-1">{keyData.status}</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Scope</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{keyData.scope}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Created</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{keyData.created}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Last Used</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{keyData.lastUsed}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Expiration</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{keyData.expires}</div>
             </div>
           </div>
        </Card>
      </Section>

      {/* Metrics */}
      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
          <MetricCard title="Requests (24h)" value="18,492" trend="+1.2%" isUp={true} />
          <MetricCard title="Error Rate (24h)" value="0.05%" trend="-0.01%" isUp={false} inverseGood={true} />
          <MetricCard title="Avg Latency (24h)" value="45ms" trend="0%" />
        </div>
      </Section>

      {/* Tabs */}
      <Section>
        <Tabs defaultValue="usage" tabs={[
          {
            id: 'usage',
            label: 'Usage',
            content: (
              <div className="space-y-6">
                <Card className="p-6">
                   <div className="flex items-center justify-between mb-4 border-b border-[var(--border-color)] pb-3">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">Top Endpoints</h3>
                     <span className="text-xs text-[var(--text-secondary)]">Last 30 days</span>
                   </div>
                   <DataTable 
                     columns={["Endpoint", "Requests", "Error Rate"]} 
                     data={[
                       ["POST /v1/completions", "45.2K", "0.01%"], 
                       ["GET /v1/workspaces", "12.0K", "0.00%"], 
                       ["POST /v1/embeddings", "8.2K", "0.08%"]
                     ]} 
                     pagination={false} 
                     loading={false} 
                   />
                </Card>
              </div>
            )
          },
          {
            id: 'activity',
            label: 'Activity Log',
            content: (
              <div className="space-y-6">
                 <DataTable 
                  columns={["Timestamp", "Action", "IP Address", "Status"]}
                  data={[
                    ["Oct 25, 2026 14:32:01", "Request made (POST /v1/completions)", "103.142.12.33", <Badge variant="operational" key="1">Success</Badge>],
                    ["Oct 25, 2026 14:31:45", "Request made (POST /v1/completions)", "103.142.12.33", <Badge variant="operational" key="2">Success</Badge>],
                    ["Oct 25, 2026 14:15:22", "Request made (GET /v1/workspaces)", "103.142.12.33", <Badge variant="operational" key="3">Success</Badge>],
                    ["Oct 25, 2026 10:05:11", "Request made (POST /v1/embeddings)", "202.168.1.99", <Badge variant="error" key="4">Rate Limited</Badge>],
                  ]}
                  loading={false}
                />
              </div>
            )
          },
          {
            id: 'settings',
            label: 'Settings',
            content: (
              <div className="max-w-2xl space-y-6">
                <Card className="p-6">
                   <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">Key Settings</h3>
                   <div className="space-y-5">
                     <Input 
                       label="Key Name" 
                       value={editName} 
                       onChange={e => setEditName(e.target.value)} 
                       helperText="A descriptive name to help you identify this key."
                     />
                     <Input 
                       label="Scope" 
                       value={keyData.scope} 
                       disabled 
                       helperText="Scope cannot be modified after creation. To change scopes, generate a new key."
                     />
                     <div className="pt-4 flex justify-end">
                       <Button onClick={handleSaveSettings} disabled={editName === keyData.name} isLoading={isProcessing}>Save changes</Button>
                     </div>
                   </div>
                </Card>
              </div>
            )
          }
        ]} />
      </Section>

      {/* Revoke Key Modal */}
      <Modal 
        isOpen={isRevokeOpen} 
        onClose={() => !isProcessing && setIsRevokeOpen(false)}
        title="Revoke API Key"
        description={`Are you sure you want to revoke "${keyData.name}"?`}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsRevokeOpen(false)} disabled={isProcessing}>Cancel</Button>
            <Button variant="destructive" onClick={handleRevokeConfirm} isLoading={isProcessing}>Revoke Key</Button>
          </>
        }
      >
        <Alert variant="error" className="mb-2">
          Any integrations currently using this key will immediately fail. This action cannot be undone.
        </Alert>
      </Modal>

      {/* Rotate Key Modal */}
      <Modal 
        isOpen={isRotateOpen} 
        onClose={() => { if(!generatedKey && !isProcessing) setIsRotateOpen(false); }}
        title={generatedKey ? "Save new API Key" : "Rotate API Key"}
        description={generatedKey ? "Please copy your new key. The old one is now invalid." : `Are you sure you want to rotate "${keyData.name}"?`}
        footer={
          generatedKey ? (
            <Button onClick={() => { setIsRotateOpen(false); setGeneratedKey(null); }} className="w-full">Done</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => setIsRotateOpen(false)} disabled={isProcessing}>Cancel</Button>
              <Button onClick={handleRotateConfirm} isLoading={isProcessing}>Rotate Key</Button>
            </>
          )
        }
      >
        {!generatedKey ? (
          <Alert variant="warning">
            This will immediately invalidate the current key and generate a new one. Applications using the old key will lose access until updated.
          </Alert>
        ) : (
          <div className="space-y-4">
            <Alert variant="success" title="Key Rotated Successfully">
              Your new key is ready. Remember to update your environments.
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

// --- API KEYS PAGE ---

const MOCK_API_KEYS = [
  { id: 'key_1', name: 'Production Backend', keyHash: '982b3a1c8f0e4d5a', scope: 'Full Access', status: 'Active', created: 'Oct 01, 2026', lastUsed: '2 mins ago' },
  { id: 'key_2', name: 'Read-only Analytics', keyHash: '1122334455667788', scope: 'Read-only', status: 'Active', created: 'Oct 10, 2026', lastUsed: '5 hours ago' },
  { id: 'key_3', name: 'Old Staging Key', keyHash: 'abcdef1234567890', scope: 'Full Access', status: 'Revoked', created: 'Jan 15, 2026', lastUsed: 'Sep 30, 2026' },
];

const maskKey = (hash) => {
  return `sk_live_••••••••${hash.substring(hash.length - 4)}`;
};

const KeyActionsDropdown = ({  apiKey, onRevoke, onRotate, onViewDetails  }: any) => {
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
        aria-label="Key Actions"
      >
        <MoreVertical className="w-4 h-4"/>
      </button>
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-44 bg-[var(--bg-card)] border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 animate-in fade-in zoom-in-95 duration-100">
          <button 
            onClick={() => { onViewDetails(); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
          >
            <Eye className="w-4 h-4 text-[var(--text-secondary)]" /> View details
          </button>
          
          {apiKey.status === 'Active' && (
            <>
              <button 
                onClick={() => { onRotate(apiKey); setIsOpen(false); }}
                className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors"
              >
                <RefreshCcw className="w-4 h-4 text-[var(--text-secondary)]" /> Rotate key
              </button>
              
              <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
              
              <button 
                onClick={() => { onRevoke(apiKey); setIsOpen(false); }}
                className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium"
              >
                <Ban className="w-4 h-4 opacity-80" /> Revoke key
              </button>
            </>
          )}

          {apiKey.status === 'Revoked' && (
            <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium mt-1">
              <Trash2 className="w-4 h-4 opacity-80" /> Delete
            </button>
          )}
        </div>
      )}
    </div>
  );
};

const ApiKeysPage = ({  setActiveRoute  }: any) => {
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
      onViewDetails={() => setActiveRoute('key-details')}
    />
  ]);

  return (
    <PageContainer maxWidth="default">
      <PageHeader 
        title="API Keys" 
        subtitle="Manage and secure programmatic access to your platform."
        actions={
          <Button onClick={() => setActiveRoute('keys-new')}>
            <Plus className="w-4 h-4 mr-2" /> Create key
          </Button>
        }
      />

      <Section>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 bg-[var(--bg-card)] p-4 rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm">
          <div className="relative w-full sm:w-72 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              className="h-10 w-full pl-9 pr-3 rounded-md-custom border border-[var(--border-color)] bg-white text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
              placeholder="Search key name..."
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex w-full sm:w-auto gap-3 shrink-0">
            <div className="w-full sm:w-40">
              <Select 
                value={statusFilter} 
                onChange={setStatusFilter} 
                options={[{label: 'All Statuses', value: 'all'}, {label: 'Active', value: 'Active'}, {label: 'Revoked', value: 'Revoked'}]} 
                placeholder="Status" 
              />
            </div>
          </div>
          {(search || statusFilter !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setStatusFilter('all');}} className="px-3">Clear filters</Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable 
          columns={["Key Name", "Secret Key", "Scope", "Created At", "Last Used", "Status", ""]}
          data={tableData}
          loading={isLoading}
        />
      </Section>

      {/* Revoke Key Modal */}
      <Modal 
        isOpen={isRevokeOpen} 
        onClose={() => !isProcessing && setIsRevokeOpen(false)}
        title="Revoke API Key"
        description={`Are you sure you want to revoke "${selectedKey?.name}"?`}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsRevokeOpen(false)} disabled={isProcessing}>Cancel</Button>
            <Button variant="destructive" onClick={handleRevokeConfirm} isLoading={isProcessing}>Revoke Key</Button>
          </>
        }
      >
        <Alert variant="error" className="mb-2">
          Any integrations currently using this key will immediately fail. This action cannot be undone.
        </Alert>
      </Modal>

      {/* Rotate Key Modal */}
      <Modal 
        isOpen={isRotateOpen} 
        onClose={() => { if(!generatedKey && !isProcessing) setIsRotateOpen(false); }}
        title={generatedKey ? "Save new API Key" : "Rotate API Key"}
        description={generatedKey ? "Please copy your new key. The old one is now invalid." : `Are you sure you want to rotate "${selectedKey?.name}"?`}
        footer={
          generatedKey ? (
            <Button onClick={() => { setIsRotateOpen(false); setGeneratedKey(null); }} className="w-full">Done</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => setIsRotateOpen(false)} disabled={isProcessing}>Cancel</Button>
              <Button onClick={handleRotateConfirm} isLoading={isProcessing}>Rotate Key</Button>
            </>
          )
        }
      >
        {!generatedKey ? (
          <Alert variant="warning">
            This will immediately invalidate the current key and generate a new one. Applications using the old key will lose access until updated.
          </Alert>
        ) : (
          <div className="space-y-4">
            <Alert variant="success" title="Key Rotated Successfully">
              Your new key is ready. Remember to update your environments.
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
  const [step, setStep] = useState(1);
  const [isCreating, setIsCreating] = useState(false);
  const [generatedKey, setGeneratedKey] = useState(null);
  const [formData, setFormData] = useState({ name: '', scope: 'Full Access', expiration: 'never' });
  const [errors, setErrors] = useState({});

  const handleCreate = async () => {
    if (!formData.name) {
      setErrors({ name: 'Key name is required' });
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
             title="Create API Key" 
             subtitle="Generate a secure key to allow programmatic access to your platform."
           />
           <Card className="p-6 sm:p-8 mt-8 shadow-soft-md">
             <div className="space-y-6">
                <Input 
                  label="Key Name" 
                  placeholder="e.g. Production Backend" 
                  value={formData.name}
                  onChange={e => { setFormData({...formData, name: e.target.value}); setErrors({}); }}
                  error={errors.name}
                  autoFocus
                />
                <Select 
                  label="Scope" 
                  options={[{label: 'Full Access', value: 'Full Access'}, {label: 'Read-only', value: 'Read-only'}]}
                  value={formData.scope}
                  onChange={v => setFormData({...formData, scope: v})}
                />
                <Select 
                  label="Expiration" 
                  options={[{label: 'Never', value: 'never'}, {label: '30 days', value: '30'}, {label: '90 days', value: '90'}]}
                  value={formData.expiration}
                  onChange={v => setFormData({...formData, expiration: v})}
                />
             </div>
             <div className="mt-8 pt-6 border-t border-[var(--border-color)] flex items-center justify-between">
                <Button variant="tertiary" onClick={() => setActiveRoute('keys')}>Cancel</Button>
                <Button onClick={handleCreate} isLoading={isCreating}>Create key</Button>
             </div>
           </Card>
         </div>
       )}

       {/* Step 2 */}
       {step === 2 && (
         <div className="animate-in fade-in zoom-in-[0.98] duration-500">
           <PageHeader 
             title="Your API key has been created" 
             subtitle="Please store this key securely. We cannot show it to you again."
           />
           <Card className="p-6 sm:p-8 mt-8 shadow-soft-md border-[var(--primary-gold)]/30">
             <Alert variant="warning" className="mb-6 bg-[#FDF9F0] border-[#E6C07B]/40">
               <div className="flex items-start gap-2">
                 <div>
                   <h4 className="text-sm font-semibold text-[#9E814D] mb-1">Make sure to copy your key now</h4>
                   <p className="text-xs text-[#9E814D]/90">You will not be able to see it again after you leave this page. If you lose it, you will need to generate a new one.</p>
                 </div>
               </div>
             </Alert>

             <div className="space-y-2 mb-8">
               <Label>Secret API Key</Label>
               <div className="flex items-center gap-3 p-3 sm:p-4 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom shadow-inner">
                 <span className="font-mono text-sm sm:text-base text-[var(--text-primary)] flex-1 overflow-x-auto whitespace-nowrap scrollbar-hide select-all">
                   {generatedKey}
                 </span>
                 <CopyButton text={generatedKey} className="shrink-0 bg-white border border-[var(--border-color)] shadow-sm w-8 h-8 flex items-center justify-center" />
               </div>
             </div>

             <div className="pt-6 border-t border-[var(--border-color)] flex justify-end">
                <Button onClick={() => setActiveRoute('keys')}>Done</Button>
             </div>
           </Card>
         </div>
       )}
    </PageContainer>
  )
}

// ==========================================
// MAIN PLATFORM SHELL COMPONENT
// ==========================================

export default function KaoriPlatformShell() {
  const [activeRoute, setActiveRoute] = useState('admin-invite'); // Set default to Admin Invite for demo
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
             activeRoute === 'key-details' ? <ApiKeyDetailPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'admin' ? <PlatformAdminsPage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'admin-invite' ? <PlatformAdminInvitePage setActiveRoute={setActiveRoute} /> :
             activeRoute === 'overview' ? <PlatformOverview /> : 
             activeRoute === 'sessions' ? <SessionsPage /> : (
              <PageContainer maxWidth="narrow">
                <PageHeader title={`${NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label} module`} subtitle="This section of the platform is currently being designed." />
                <Section>
                  <Card className="flex flex-col items-center justify-center py-20 px-4 text-center border-dashed bg-[var(--bg-card)]/50 mx-auto w-full animate-in fade-in duration-300">
                    <div className="w-12 h-12 rounded-lg-custom bg-[var(--bg-sidebar)] flex items-center justify-center border border-[var(--border-color)] mb-4">
                      {React.createElement(NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.icon || LayoutDashboard, { className: 'w-6 h-6 text-[var(--text-secondary)]' })}
                    </div>
                    <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">Work in Progress</h3>
                    <p className="text-sm text-[var(--text-secondary)] max-w-sm">Content for {activeRoute} will populate here inside the Shell Wrapper.</p>
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
// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 27Billing Quata manager.jsx by convert_jsx_to_tsx.py.
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

const DataTable = ({  columns, data, loading, pagination = true, onRowClick  }: any) => {
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
  else if (activeRoute === 'workspace-billing') routeLabel = 'Workspaces / Billing';
  else if (activeRoute === 'audit-logs') routeLabel = 'Workspaces / Audit Logs';
  else if (activeRoute === 'workspace-new') routeLabel = 'Workspaces / New Workspace';
  else if (activeRoute === 'workspace-edit') routeLabel = 'Workspaces / Settings';
  else if (activeRoute === 'keys-new') routeLabel = 'API Keys / Create Key';
  else if (activeRoute === 'key-details') routeLabel = 'API Keys / Details';
  else if (activeRoute === 'admin-invite') routeLabel = 'Admins / Invite';
  else if (activeRoute === 'admin-details') routeLabel = 'Admins / Details';
  else if (activeRoute === 'admin-reset-password') routeLabel = 'Admins / Reset Password';
  else if (activeRoute === 'enterprise-billing-details') routeLabel = 'Billing / Enterprise Detail';
  else if (activeRoute === 'quota') routeLabel = 'Billing / Quota Management';
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
    (activeRoute === 'workspace-details' || activeRoute === 'workspace-members' || activeRoute === 'workspace-billing' || activeRoute === 'audit-logs' || activeRoute === 'workspace-new' || activeRoute === 'workspace-edit') ? 'workspaces' : 
    (activeRoute === 'keys-new' || activeRoute === 'key-details') ? 'keys' : 
    (activeRoute === 'admin-invite' || activeRoute === 'admin-details' || activeRoute === 'admin-reset-password') ? 'admin' : 
    (activeRoute === 'enterprise-billing-details' || activeRoute === 'quota') ? 'billing' :
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

// --- PLATFORM QUOTA MANAGEMENT PAGE ---
const MOCK_QUOTAS = [
  { id: 'ws_prod_01', name: 'Production AI', plan: 'Enterprise', apiCurrent: 2400, apiMax: 10000, storageCurrent: 84, storageMax: 500, status: 'Normal', lastUpdated: 'Oct 20, 2026' },
  { id: 'ws_stage_02', name: 'Staging Environment', plan: 'Pro', apiCurrent: 45, apiMax: 50, storageCurrent: 48, storageMax: 50, status: 'Warning', lastUpdated: 'Oct 22, 2026' },
  { id: 'ws_dev_03', name: 'Dev Cluster Alpha', plan: 'Free', apiCurrent: 12, apiMax: 10, storageCurrent: 6, storageMax: 5, status: 'Over Quota', lastUpdated: 'Oct 25, 2026' },
  { id: 'ws_analytics_04', name: 'Data Analytics Core', plan: 'Enterprise', apiCurrent: 4900, apiMax: 5000, storageCurrent: 490, storageMax: 500, status: 'Warning', lastUpdated: 'Oct 24, 2026' },
];

const QuotaActionsDropdown = ({  workspace, onAdjustQuota, onViewDetails  }: any) => {
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
            <Eye className="w-4 h-4 text-[var(--text-secondary)]"/> View workspace
          </button>
          <button onClick={() => { onAdjustQuota(workspace); setIsOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <SlidersHorizontal className="w-4 h-4 text-[var(--text-secondary)]"/> Adjust quota
          </button>
          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium">
            <Ban className="w-4 h-4 opacity-80"/> Suspend
          </button>
        </div>
      )}
    </div>
  );
};

const PlatformQuotaManagementPage = ({  setActiveRoute  }: any) => {
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
        title="Quota Management" 
        subtitle="Monitor and enforce resource limits across all workspaces."
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Download className="w-4 h-4 mr-2" /> Export data</Button>
            <Button variant="outline"><Settings className="w-4 h-4 mr-2"/> Adjust default quota</Button>
          </>
        }
      />

      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title="Total API Capacity" value="150M reqs" trend="0%" />
          <MetricCard title="Total Usage (Mo)" value="82.4M reqs" trend="+5.2%" isUp={true} />
          <MetricCard title="Over-quota Workspaces" value="14" trend="+2" isUp={false} inverseGood={true} />
          <MetricCard title="Warning-level Workspaces" value="32" trend="-5" isUp={true} inverseGood={true} />
        </div>
      </Section>

      <Section>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 bg-[var(--bg-card)] p-4 rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm">
          <div className="relative w-full sm:w-72 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              className="h-10 w-full pl-9 pr-3 rounded-md-custom border border-[var(--border-color)] bg-white text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
              placeholder="Search workspaces..."
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
                  {label: 'All Statuses', value: 'all'}, 
                  {label: 'Normal', value: 'Normal'}, 
                  {label: 'Warning', value: 'Warning'},
                  {label: 'Over Quota', value: 'Over Quota'}
                ]} 
                placeholder="Status" 
              />
            </div>
            <div className="w-full sm:w-32">
              <Select 
                value={planFilter} 
                onChange={setPlanFilter} 
                options={[
                  {label: 'All Plans', value: 'all'}, 
                  {label: 'Free', value: 'Free'}, 
                  {label: 'Pro', value: 'Pro'},
                  {label: 'Enterprise', value: 'Enterprise'}
                ]} 
                placeholder="Plan" 
              />
            </div>
          </div>
          {(search || statusFilter !== 'all' || planFilter !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setStatusFilter('all'); setPlanFilter('all');}} className="px-3">Clear filters</Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable 
          columns={["Workspace", "Plan", "API Usage", "Storage Usage", "Status", "Last Updated", ""]}
          data={mappedData}
          loading={isLoading}
        />
      </Section>

      {/* Adjust Quota Modal */}
      <Modal 
        isOpen={isAdjustOpen} 
        onClose={() => !isProcessing && setIsAdjustOpen(false)}
        title="Adjust Quota"
        description={selectedWs ? `Modify resource limits for ${selectedWs.name}.` : ''}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsAdjustOpen(false)} disabled={isProcessing}>Cancel</Button>
            <Button onClick={handleAdjustSave} isLoading={isProcessing}>Save Changes</Button>
          </>
        }
      >
        <div className="space-y-5">
           <Alert variant="warning">
             Changing quota limits directly affects billing logic and customer SLAs. Ensure the customer has agreed to overage charges if applicable.
           </Alert>
           <div className="space-y-4">
             <Input 
               label="API Limit (thousands req/mo)" 
               type="number"
               value={apiLimit}
               onChange={e => setApiLimit(e.target.value)}
             />
             <Input 
               label="Storage Limit (GB)" 
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
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">{percent.toFixed(1)}% used</span>
        {isWarning && <span className="text-[11px] text-[#9B5050] font-medium flex items-center"><AlertCircle className="w-3 h-3 mr-1" /> Approaching limit</span>}
      </div>
    </Card>
  );
};

// --- PLATFORM ENTERPRISE BILLING DETAIL PAGE ---

const PlatformEnterpriseBillingDetailPage = ({  setActiveRoute  }: any) => {
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
              <ExternalLink className="w-4 h-4 mr-2" /> View workspace
            </Button>
            <Button onClick={() => setIsAdjustPlanModalOpen(true)}>Adjust plan</Button>
            <Button variant="tertiary" size="icon"><MoreVertical className="w-4 h-4" /></Button>
          </>
        }
      />

      <Section>
         <Alert variant="error" title="Action Required">
            The most recent invoice (INV-2026-004) failed to process. Services may be degraded if payment is not received within 3 days.
         </Alert>
      </Section>

      <Section title="Enterprise Summary">
        <Card className="p-5 sm:p-6 overflow-hidden relative">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
           <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 relative z-10 items-start">
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Status</p>
                <Badge variant="operational" className="py-1">Active</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Plan</p>
                <Badge variant="current" className="py-1">Enterprise</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Billing Cycle</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">Monthly</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Renewal Date</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">Nov 01, 2026</div>
             </div>
             <div className="lg:col-span-2">
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Owner / Billing Contact</p>
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

      <Section title="Metrics Overview">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title="Monthly Revenue" value="$2,400" trend="0%" />
          <MetricCard title="API Requests (Mo)" value="2.4M" trend="+12%" isUp={true} />
          <MetricCard title="Storage Used" value="84 GB" trend="+5%" isUp={true} />
          <MetricCard title="Active Users" value="14" trend="+2" isUp={true} />
        </div>
      </Section>

      <Section>
        <Tabs defaultValue="invoices" tabs={[
          { 
            id: 'usage', 
            label: 'Usage Details', 
            content: (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <EnterpriseUsageCard title="API Requests" icon={Zap} current={2400000} max={10000000} unit="reqs" />
                 <EnterpriseUsageCard title="Storage Used" icon={HardDrive} current={84} max={500} unit="GB" />
              </div>
            )
          },
          { 
            id: 'invoices', 
            label: 'Invoices', 
            content: (
              <DataTable 
                columns={["Invoice ID", "Date", "Amount", "Status", ""]}
                data={invoiceData}
                loading={isLoading}
                pagination={false}
              />
            )
          },
          { 
            id: 'activity', 
            label: 'Activity', 
            content: (
              <DataTable 
                columns={["Timestamp", "Event", "Actor"]}
                data={activityData}
                loading={isLoading}
                pagination={false}
              />
            )
          },
          { 
            id: 'settings', 
            label: 'Billing Settings', 
            content: (
              <div className="max-w-2xl space-y-6">
                <Card className="p-6">
                   <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 border-b border-[var(--border-color)] pb-3">Contract Details</h3>
                   <div className="space-y-5">
                     <Select 
                       label="Current Plan" 
                       value="Enterprise" 
                       disabled
                       options={[{label: 'Enterprise', value: 'Enterprise'}]}
                       helperText="To change plans, use the 'Adjust Plan' action above."
                     />
                     <Input 
                       label="Billing Notes" 
                       value="Net 30 terms. Send copy to finance@acme.com." 
                       onChange={() => {}}
                       multiline
                     />
                     <div className="pt-4 flex justify-end">
                       <Button>Save notes</Button>
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
        title="Adjust Subscription Plan"
        description="Modify the plan and custom pricing for this enterprise workspace."
        footer={
          <>
            <Button variant="outline" onClick={() => setIsAdjustPlanModalOpen(false)} disabled={isProcessing}>Cancel</Button>
            <Button onClick={handleAdjustPlan} isLoading={isProcessing}>Update Plan</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select 
            label="Plan Tier" 
            options={[
              {label: 'Free Tier', value: 'Free'}, 
              {label: 'Pro', value: 'Pro'}, 
              {label: 'Enterprise', value: 'Enterprise'}
            ]}
            value={newPlan}
            onChange={setNewPlan}
          />
          
          <div className="space-y-2 w-full">
            <Label>Custom MRR Override ($)</Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]">$</span>
              <Input 
                type="number"
                value={customPrice} 
                onChange={e => setCustomPrice(e.target.value)} 
                className="pl-7"
              />
            </div>
            <p className="text-xs text-[var(--text-secondary)]">Leave blank to use default plan pricing.</p>
          </div>

          <Alert variant="warning" className="mt-2">
            Proration will be automatically applied to the next invoice based on the change date.
          </Alert>
        </div>
      </Modal>

    </PageContainer>
  );
};


// --- PLATFORM BILLING OVERVIEW PAGE ---
const PlatformBillingOverviewPage = ({  setActiveRoute  }: any) => {
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
        title="Billing Overview" 
        subtitle="Monitor revenue, usage, and billing health across all workspaces."
        actions={
          <>
            <div className="hidden sm:block w-36">
              <Select 
                value={dateRange} 
                onChange={setDateRange} 
                options={[{label: 'Last 30 Days', value: '30d'}, {label: 'This Quarter', value: '90d'}, {label: 'This Year', value: '365d'}]} 
                placeholder="Date Range" 
              />
            </div>
            <Button variant="outline"><Download className="w-4 h-4 mr-2"/> Export data</Button>
          </>
        }
      />

      <Section title="Revenue Metrics">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title="MRR" value="$124,500" trend="+8.4%" isUp={true} />
          <MetricCard title="Total Revenue" value="$132,100" trend="+12.1%" isUp={true} />
          <MetricCard title="Active Subscriptions" value="1,892" trend="+42" isUp={true} />
          <MetricCard title="Churn Rate" value="1.2%" trend="-0.4%" isUp={false} inverseGood={true} />
        </div>
      </Section>

      <Section title="Platform Usage">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title="Total API Requests" value="45.2M" trend="+14%" isUp={true} />
          <MetricCard title="Storage Usage" value="12.4 TB" trend="+8%" isUp={true} />
          <MetricCard title="Active Workspaces" value="1,204" trend="+12" isUp={true} />
          <MetricCard title="Over-quota Workspaces" value="14" trend="-2" isUp={false} inverseGood={true} />
        </div>
      </Section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
        <div className="lg:col-span-2 space-y-4">
          <Section title="Top Workspaces">
            <DataTable 
              columns={["Workspace", "Plan", "Revenue", "Usage", "Status"]}
              data={tableData}
              loading={isLoading}
              pagination={false}
            />
          </Section>
        </div>
        
        <div className="space-y-6 sm:space-y-8">
           <Section title="Alerts & Risks">
             <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm space-y-3">
                <Alert variant="error" title="Payment Failed">
                  Invoice INV-2026-004 failed for <span className="font-semibold cursor-pointer hover:underline" onClick={() => setActiveRoute('enterprise-billing-details')}>Dev Cluster Alpha</span>.
                </Alert>
                <Alert variant="warning" title="Quota Warning">
                  <span className="font-semibold cursor-pointer hover:underline" onClick={() => setActiveRoute('enterprise-billing-details')}>Data Analytics Core</span> is at 95% of its API quota.
                </Alert>
                <Alert variant="info" title="Suspended Account">
                  Workspace <span className="font-semibold">Legacy Systems</span> was suspended due to policy violation.
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
            title="Reset Admin Password" 
            subtitle="Trigger a password reset for this administrator."
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
                <h4 className="text-sm font-semibold text-[#9E814D]">Important Security Notice</h4>
                <p className="text-xs text-[#9E814D]/90 leading-relaxed">
                  This action will send a password reset email to the admin. They will need to set a new password before accessing the platform again. Their active sessions will remain open until the password is officially changed.
                </p>
                <p className="text-[11px] text-[#9E814D]/70 font-mono mt-2">This action will be logged for audit purposes.</p>
              </div>
            </Alert>

            <div className="pt-6 border-t border-[var(--border-color)] flex items-center justify-end gap-3">
               <Button variant="tertiary" onClick={() => setActiveRoute('admin-details')}>Cancel</Button>
               <Button onClick={() => setIsConfirmModalOpen(true)} disabled={adminData.status === 'Suspended'}>
                 <Mail className="w-4 h-4 mr-2"/> Send reset email
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
             title="Reset email sent" 
           />
           <Card className="p-8 mt-8 shadow-soft-md flex flex-col items-center text-center">
             <div className="w-16 h-16 rounded-full bg-[#F3F9F5] border border-[#8FBFA0]/40 flex items-center justify-center mb-6">
               <CheckCircle2 className="w-8 h-8 text-[#5C856A]" />
             </div>
             <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">Reset email dispatched</h2>
             <p className="text-sm text-[var(--text-secondary)] mb-8 max-w-sm">
               An email has been sent to <strong className="text-[var(--text-primary)]">{adminData.email}</strong> with instructions to set a new password.
             </p>
             <div className="flex gap-3">
               <Button variant="outline" onClick={() => setActiveRoute('admin-details')}>Back to Admin Details</Button>
               <Button onClick={handleResend} disabled={countdown > 0} isLoading={isSubmitting}>
                 {countdown > 0 ? `Resend in ${countdown}s` : 'Resend email'}
               </Button>
             </div>
           </Card>
        </div>
      )}

      {/* Confirmation Modal */}
      <Modal 
        isOpen={isConfirmModalOpen} 
        onClose={() => !isSubmitting && setIsConfirmModalOpen(false)}
        title="Reset password for this admin?"
        description="This will send a reset link to the admin’s email address."
        footer={
          <>
            <Button variant="outline" onClick={() => setIsConfirmModalOpen(false)} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={handleSendReset} isLoading={isSubmitting}>Confirm Reset</Button>
          </>
        }
      />
    </PageContainer>
  );
};


// --- PLATFORM ADMIN DETAILS PAGE ---
const PlatformAdminDetailPage = ({  setActiveRoute  }: any) => {
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
    showSuccess("Role updated successfully.");
  };

  const handleSuspendToggle = async () => {
    if (adminData.role === 'Super Admin' && adminData.status === 'Active') {
      alert("Cannot suspend the primary Super Admin. Promote another user first.");
      setIsSuspendModalOpen(false);
      return;
    }
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 600));
    setAdminData(prev => ({ ...prev, status: prev.status === 'Active' ? 'Suspended' : 'Active' }));
    setIsProcessing(false);
    setIsSuspendModalOpen(false);
    showSuccess(`Admin ${adminData.status === 'Active' ? 'suspended' : 'activated'} successfully.`);
  };

  const handleRemove = async () => {
    if (adminData.role === 'Super Admin') {
      setRemoveError("Cannot remove the primary Super Admin. Please transfer ownership or change role first.");
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
    { title: 'Global Platform Settings', desc: 'Full access to read and write all platform configurations.' },
    { title: 'Billing & Subscriptions', desc: 'Manage payment methods, plans, and view all invoices.' },
    { title: 'User & Admin Management', desc: 'Invite, suspend, and remove platform administrators or workspace owners.' },
    { title: 'Workspace Oversight', desc: 'Full access to view and manage all tenant workspaces and resources.' }
  ] : adminData.role === 'Admin' ? [
    { title: 'Workspace Management', desc: 'Create, suspend, and manage all tenant workspaces.' },
    { title: 'User Management', desc: 'Invite and manage users within specific workspaces.' },
    { title: 'API Key Management', desc: 'View, rotate, and revoke platform API keys.' }
  ] : [
    { title: 'Read-only Oversight', desc: 'View workspace configurations and health metrics.' },
    { title: 'Audit Logs', desc: 'Access and export platform activity and security logs.' }
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
              <Shield className="w-4 h-4 mr-2" /> Change role
            </Button>
            <Button variant="outline" onClick={() => setActiveRoute('admin-reset-password')} className="hidden sm:flex">
              <Lock className="w-4 h-4 mr-2" /> Reset password
            </Button>
            
            {/* Mobile / Dropdown Menu */}
            <div className="relative group">
              <Button variant="tertiary" size="icon"><MoreVertical className="w-4 h-4" /></Button>
              <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-[var(--border-color)] shadow-soft-md rounded-lg-custom z-50 py-1.5 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-100 focus-within:opacity-100 focus-within:visible">
                <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors sm:hidden" onClick={() => { setNewRole(adminData.role); setIsRoleModalOpen(true); }}>
                  <Shield className="w-4 h-4 text-[var(--text-secondary)]"/> Change role
                </button>
                <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors sm:hidden" onClick={() => setActiveRoute('admin-reset-password')}>
                  <Lock className="w-4 h-4 text-[var(--text-secondary)]"/> Reset password
                </button>
                <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2 sm:hidden" />
                <button onClick={() => setIsSuspendModalOpen(true)} className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium">
                  {adminData.status === 'Active' ? <Ban className="w-4 h-4 opacity-80"/> : <Unlock className="w-4 h-4 opacity-80"/>}
                  {adminData.status === 'Active' ? 'Suspend access' : 'Restore access'}
                </button>
                <button onClick={() => setIsRemoveModalOpen(true)} className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium">
                  <Trash2 className="w-4 h-4 opacity-80"/> Remove admin
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
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Status</p>
                <Badge variant={adminData.status === 'Active' ? 'operational' : 'error'} className="py-1">{adminData.status}</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Created</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">{adminData.created}</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Last Active</p>
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
            label: 'Overview', 
            content: (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
                {/* Left col - Recent Activity */}
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">Recent Activity</h3>
                     <Button variant="tertiary" size="sm" onClick={() => {}}>View all</Button>
                  </div>
                  <DataTable 
                    pagination={false}
                    columns={["Timestamp", "Action", "Resource", "Status", "IP"]}
                    data={activityTableData.slice(0, 3)}
                    loading={isLoading}
                    onRowClick={(row: any) => setSelectedEvent(row)}
                  />
                </div>
                
                {/* Right col - Security Info */}
                <div className="space-y-6 sm:space-y-8">
                   <div className="space-y-4">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">Security Profile</h3>
                     <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-[#5C856A]" />
                            <span className="text-sm font-medium text-[var(--text-primary)]">MFA Enforced</span>
                          </div>
                          <Badge variant="operational">Enabled</Badge>
                        </div>
                        <div className="h-[1px] bg-[var(--border-color)]/50" />
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Laptop className="w-4 h-4 text-[var(--text-secondary)]" />
                            <span className="text-sm font-medium text-[var(--text-primary)]">Active Sessions</span>
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
            label: 'Activity', 
            content: (
              <div className="space-y-4">
                <DataTable 
                  columns={["Timestamp", "Action", "Resource", "Status", "IP"]}
                  data={activityTableData}
                  loading={isLoading}
                  onRowClick={(row: any) => setSelectedEvent(row)}
                />
              </div>
            )
          },
          { 
            id: 'permissions', 
            label: 'Permissions', 
            content: (
              <div className="max-w-3xl space-y-6">
                <Alert variant="info">
                  Permissions are inferred from the <strong>{adminData.role}</strong> role. Granular custom permissions are currently managed via the API.
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
        title="Change Role"
        description={`Update platform access level for ${adminData.name}.`}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsRoleModalOpen(false)} disabled={isProcessing}>Cancel</Button>
            <Button onClick={handleRoleChange} isLoading={isProcessing} disabled={newRole === adminData.role}>Update Role</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select 
            label="Platform Role" 
            options={[
              {label: 'Super Admin', value: 'Super Admin'}, 
              {label: 'Admin', value: 'Admin'}, 
              {label: 'Support', value: 'Support'}
            ]}
            value={newRole}
            onChange={setNewRole}
          />
          {newRole === 'Super Admin' && newRole !== adminData.role && (
            <Alert variant="warning" className="mt-2">
              You are granting full system privileges. Ensure this user is authorized for billing and global operations.
            </Alert>
          )}
          {adminData.role === 'Super Admin' && newRole !== 'Super Admin' && (
            <Alert variant="info" className="mt-2">
              Downgrading a Super Admin will immediately revoke their access to billing and global settings.
            </Alert>
          )}
        </div>
      </Modal>

      <Modal 
        isOpen={isSuspendModalOpen} 
        onClose={() => !isProcessing && setIsSuspendModalOpen(false)}
        title={adminData.status === 'Active' ? "Suspend Admin Access" : "Restore Admin Access"}
        description={adminData.status === 'Active' ? `Are you sure you want to suspend ${adminData.name}?` : `Are you sure you want to restore access for ${adminData.name}?`}
        footer={
          <>
            <Button variant="outline" onClick={() => setIsSuspendModalOpen(false)} disabled={isProcessing}>Cancel</Button>
            {adminData.status === 'Active' ? (
              <Button variant="destructive" onClick={handleSuspendToggle} isLoading={isProcessing}>Suspend Access</Button>
            ) : (
              <Button onClick={handleSuspendToggle} isLoading={isProcessing}>Restore Access</Button>
            )}
          </>
        }
      >
        {adminData.status === 'Active' ? (
          <Alert variant="warning" className="mb-2">
            The user will immediately lose access to the Kaori Platform Shell. No API keys or automated integrations will be affected.
          </Alert>
        ) : (
          <div className="text-sm text-[var(--text-secondary)]">
            Restoring access will allow the user to log in and resume their role as {adminData.role}.
          </div>
        )}
      </Modal>

      <Modal 
        isOpen={isRemoveModalOpen} 
        onClose={() => { setIsRemoveModalOpen(false); setRemoveError(''); }}
        title="Remove Admin"
        description={`Are you sure you want to permanently remove ${adminData.name} from the platform?`}
        footer={
          <>
            <Button variant="outline" onClick={() => { setIsRemoveModalOpen(false); setRemoveError(''); }} disabled={isProcessing}>Cancel</Button>
            <Button variant="destructive" onClick={handleRemove} isLoading={isProcessing}>Remove Admin</Button>
          </>
        }
      >
        {removeError && <Alert variant="error" className="mb-4">{removeError}</Alert>}
        <Alert variant="error" className="mb-2">
          This action is irreversible. The user's platform access will be destroyed. To restore access, a new invitation must be sent.
        </Alert>
      </Modal>

      {/* Detail Drawer (For Activity Row Click) */}
      <Drawer 
        isOpen={!!selectedEvent} 
        onClose={() => setSelectedEvent(null)} 
        title="Event Details"
      >
        {selectedEvent && (
          <div className="space-y-6">
            <div className="flex flex-col gap-2 bg-[var(--bg-app)] p-4 rounded-md-custom border border-[var(--border-color)]">
               <h3 className="text-base font-semibold text-[var(--text-primary)]">{selectedEvent[1]?.props?.children || selectedEvent[1]}</h3>
               <p className="text-xs text-[var(--text-secondary)]">{selectedEvent[0]?.props?.children || selectedEvent[0]}</p>
            </div>
            <div className="grid grid-cols-2 gap-y-4 gap-x-6 text-sm">
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">Actor</p>
                <p className="font-medium text-[var(--text-primary)]">{adminData.name}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">Resource</p>
                <p className="font-mono text-[var(--text-primary)] text-xs">{selectedEvent[2]?.props?.children || selectedEvent[2]}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">IP Address</p>
                <p className="font-mono text-[var(--text-primary)] text-xs">{selectedEvent[4]?.props?.children || selectedEvent[4]}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1">Status</p>
                {selectedEvent[3]}
              </div>
            </div>
            <div className="h-[1px] bg-[var(--border-color)] w-full" />
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-[var(--text-primary)]">Metadata Context</h4>
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

const AdminActionsDropdown = ({  admin, onRemove, onSuspend, onActivate, onResetPassword, onViewDetails  }: any) => {
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
            <Eye className="w-4 h-4 text-[var(--text-secondary)]"/> View details
          </button>

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
      onViewDetails={() => setActiveRoute('admin-details')}
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

// ==========================================
// MAIN PLATFORM SHELL COMPONENT
// ==========================================

export default function KaoriPlatformShell() {
  const [activeRoute, setActiveRoute] = useState('quota'); // Set default to Quota Management for demo
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
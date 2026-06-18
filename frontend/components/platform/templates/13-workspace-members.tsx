// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 13Workspace Id member.jsx by convert_jsx_to_tsx.py.
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
  Send
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
const Select = ({  label, placeholder = "Select an option", options = [], value, onChange, error  }: any) => {
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
        {selectedOption ? selectedOption.label : placeholder}
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
                <button className="p-1 hover:bg-[var(--bg-app)] rounded"><ChevronRight className="w-4 h-4 rotate-180 text-[var(--text-secondary)]"/></button>
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
      {pagination && (
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
  // If the route is a detail route, show custom label.
  let routeLabel = NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label;
  if (activeRoute === 'workspace-details') routeLabel = 'Workspaces / Overview';
  else if (activeRoute === 'workspace-members') routeLabel = 'Workspaces / Members';
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
            <Button variant="outline" size="sm" className="hidden md:flex"><Plus className="w-3.5 h-3.5 mr-1.5" /> Workspace</Button>
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
  // If activeRoute is a workspace sub-page, keep "Workspaces" highlighted.
  const currentHighlight = (activeRoute === 'workspace-details' || activeRoute === 'workspace-members') ? 'workspaces' : activeRoute;

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

// --- WORKSPACE MEMBERS PAGE ---
const MOCK_MEMBERS = [
  { id: 'm1', name: 'Admin User', email: 'admin@kaori.io', role: 'Owner', status: 'Active', lastActive: 'Now', joinedAt: 'Oct 12, 2026' },
  { id: 'm2', name: 'Sarah Jenkins', email: 'sarah@kaori.io', role: 'Admin', status: 'Active', lastActive: '2 hours ago', joinedAt: 'Oct 15, 2026' },
  { id: 'm3', name: 'Mike Chen', email: 'mike@kaori.io', role: 'Member', status: 'Pending', lastActive: '-', joinedAt: 'Oct 20, 2026' },
  { id: 'm4', name: 'Emily Davis', email: 'emily@kaori.io', role: 'Viewer', status: 'Active', lastActive: '1 day ago', joinedAt: 'Oct 22, 2026' },
];

const MemberActionsDropdown = ({  member, onRemove  }: any) => {
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
          
          {member.status === 'Pending' && (
            <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
              <Send className="w-4 h-4 text-[var(--text-secondary)]"/> Resend invite
            </button>
          )}

          {member.role === 'Owner' && (
            <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
              <Key className="w-4 h-4 text-[var(--text-secondary)]"/> Transfer ownership
            </button>
          )}

          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          <button 
            onClick={() => { onRemove(member); setIsOpen(false); }}
            className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium"
          >
            <Trash2 className="w-4 h-4 opacity-80"/> Remove member
          </button>
        </div>
      )}
    </div>
  );
};

const WorkspaceMembersPage = ({  setActiveRoute  }: any) => {
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
        setRemoveError("You cannot remove the last owner. Please transfer ownership first.");
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
           {m.id === 'm1' && <span className="text-[10px] bg-[var(--bg-app)] border border-[var(--border-color)] px-1.5 py-0.5 rounded text-[var(--text-secondary)]">You</span>}
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
        title="Members" 
        subtitle="Manage users and access levels for Production AI workspace." 
        actions={
          <Button onClick={() => setIsInviteOpen(true)}>
            <UserPlus className="w-4 h-4 mr-2"/> Invite member
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
            <div className="w-full sm:w-36">
              <Select 
                value={roleFilter} 
                onChange={setRoleFilter} 
                options={[
                  {label: 'All Roles', value: 'all'}, 
                  {label: 'Owner', value: 'Owner'}, 
                  {label: 'Admin', value: 'Admin'},
                  {label: 'Member', value: 'Member'},
                  {label: 'Viewer', value: 'Viewer'}
                ]} 
                placeholder="Role" 
              />
            </div>
            <div className="w-full sm:w-36">
              <Select 
                value={statusFilter} 
                onChange={setStatusFilter} 
                options={[{label: 'All Statuses', value: 'all'}, {label: 'Active', value: 'Active'}, {label: 'Pending', value: 'Pending'}]} 
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
          columns={["Name", "Role", "Status", "Last Active", "Joined", ""]} 
          data={mappedData} 
          loading={isLoading} 
        />
      </Section>

      {/* Invite Modal */}
      <Modal 
        isOpen={isInviteOpen} 
        onClose={() => setIsInviteOpen(false)}
        title="Invite Member"
        description="Send an email invitation to join this workspace."
        footer={
          <>
            <Button variant="outline" onClick={() => setIsInviteOpen(false)}>Cancel</Button>
            <Button onClick={handleInvite}><Mail className="w-4 h-4 mr-2"/> Send Invite</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input 
            label="Email Address" 
            placeholder="colleague@company.com" 
            value={inviteEmail}
            onChange={e => setInviteEmail(e.target.value)}
          />
          <Select 
            label="Workspace Role" 
            placeholder="Select a role..."
            options={[
              {label: 'Admin', value: 'admin'}, 
              {label: 'Member', value: 'member'}, 
              {label: 'Viewer', value: 'viewer'}
            ]}
            value="member"
            onChange={() => {}}
          />
          <Alert variant="info" className="mt-2">
            Members can view and interact with all resources, but cannot manage billing or workspace settings.
          </Alert>
        </div>
      </Modal>

      {/* Remove Confirmation Modal */}
      <Modal 
        isOpen={!!memberToRemove} 
        onClose={() => { setMemberToRemove(null); setRemoveError(''); }}
        title="Remove Member"
        description={`Are you sure you want to remove ${memberToRemove?.name} from this workspace? They will lose access immediately.`}
        footer={
          <>
            <Button variant="outline" onClick={() => { setMemberToRemove(null); setRemoveError(''); }}>Cancel</Button>
            <Button variant="destructive" onClick={handleRemove}>Remove Member</Button>
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

// --- WORKSPACE OVERVIEW PAGE ---
const WorkspaceOverviewPage = ({  setActiveRoute  }: any) => {
  return (
    <PageContainer maxWidth="default">
      <PageHeader 
        showBack 
        onBack={() => setActiveRoute('workspaces')}
        title="Production AI" 
        subtitle="ws_prod_01 • Main production environment for ML models" 
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Edit2 className="w-4 h-4 mr-2"/> Edit details</Button>
            <Button variant="outline" className="hidden sm:flex" onClick={() => setActiveRoute('workspace-members')}><Users className="w-4 h-4 mr-2"/> Manage members</Button>
            <Button variant="tertiary" size="icon"><MoreVertical className="w-4 h-4" /></Button>
          </>
        } 
      />

      <Section>
        <Card className="p-5 sm:p-6 overflow-hidden relative">
           <div className="absolute right-0 top-0 bottom-0 w-64 bg-gradient-to-l from-[var(--primary-gold)]/5 to-transparent pointer-events-none" />
           <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6 relative z-10">
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Status</p>
                <Badge variant="operational" className="py-1">Active</Badge>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Plan</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">Enterprise</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Region</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">US-East</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Created</p>
                <div className="text-sm font-medium text-[var(--text-primary)]">Oct 12, 2026</div>
             </div>
             <div>
                <p className="text-[11px] text-[var(--text-secondary)] font-semibold uppercase tracking-wider mb-2">Owner</p>
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
          <MetricCard title="API Requests (Today)" value="124.5K" trend="+5.2%" isUp={true} />
          <MetricCard title="Active Users" value="14" trend="0%" />
          <MetricCard title="Error Rate" value="0.01%" trend="-0.04%" isUp={false} inverseGood={true} />
          <MetricCard title="Storage Used" value="84 GB" trend="+2.1%" isUp={true} />
        </div>
      </Section>

      <Section>
        <Tabs defaultValue="overview" tabs={[
          { 
            id: 'overview', 
            label: 'Overview', 
            content: (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">Recent Activity</h3>
                     <Button variant="tertiary" size="sm">View all</Button>
                  </div>
                  <DataTable 
                    pagination={false}
                    columns={["Event", "Actor", "Time"]}
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
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">Alerts</h3>
                     <Alert variant="success" title="Healthy">No issues detected for this workspace.</Alert>
                   </div>
                   <div className="space-y-4">
                     <h3 className="text-sm font-semibold text-[var(--text-primary)]">Quick Actions</h3>
                     <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-4 shadow-soft-sm flex flex-col gap-2">
                        <Button variant="outline" className="w-full justify-start"><Key className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> Generate API Key</Button>
                        <Button variant="outline" className="w-full justify-start" onClick={() => setActiveRoute('workspace-members')}><UserPlus className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> Invite User</Button>
                        <Button variant="outline" className="w-full justify-start"><CreditCard className="w-4 h-4 mr-3 text-[var(--text-secondary)]" /> Upgrade Plan</Button>
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
               <DataTable 
                columns={["Event", "Resource", "Actor", "Time"]}
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
            label: 'Usage', 
            content: (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center shrink-0">
                      <Zap className="w-5 h-5 text-[var(--text-secondary)]" />
                    </div>
                    <div>
                       <h3 className="text-sm font-semibold text-[var(--text-primary)]">API Calls</h3>
                       <p className="text-xs text-[var(--text-secondary)]">Last 30 days</p>
                    </div>
                  </div>
                  <div className="text-3xl font-semibold text-[var(--text-primary)]">2.4M</div>
                  <div className="text-sm text-[var(--text-secondary)] mt-2">12% of Enterprise Limit (20M)</div>
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
                       <h3 className="text-sm font-semibold text-[var(--text-primary)]">Storage</h3>
                       <p className="text-xs text-[var(--text-secondary)]">Current usage</p>
                    </div>
                  </div>
                  <div className="text-3xl font-semibold text-[var(--text-primary)]">84 GB</div>
                  <div className="text-sm text-[var(--text-secondary)] mt-2">16% of Enterprise Limit (500 GB)</div>
                  <div className="w-full bg-[var(--bg-app)] rounded-full h-2 mt-4 border border-[var(--border-color)] overflow-hidden">
                     <div className="bg-[#5C856A] h-2 rounded-full" style={{width: '16%'}}></div>
                  </div>
                </Card>
              </div>
            )
          },
          { id: 'keys', label: 'API Keys', content: <Alert variant="info" title="Keys">Manage API keys here.</Alert> },
          { id: 'members', label: 'Members', content: (
            <Card className="p-8 text-center flex flex-col items-center">
              <Users className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
              <h3 className="text-sm font-medium text-[var(--text-primary)]">Workspace Members</h3>
              <p className="text-xs text-[var(--text-secondary)] mt-1 mb-4">Manage active members and roles.</p>
              <Button onClick={() => setActiveRoute('workspace-members')}>Open Members Management</Button>
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
            <Eye className="w-4 h-4 text-[var(--text-secondary)]"/> View details
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Edit2 className="w-4 h-4 text-[var(--text-secondary)]"/> Edit workspace
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] flex items-center gap-2 transition-colors">
            <Users className="w-4 h-4 text-[var(--text-secondary)]"/> Manage members
          </button>
          <div className="h-[1px] bg-[var(--border-color)]/50 my-1 mx-2" />
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-warning)] hover:bg-[#FDF9F0] flex items-center gap-2 transition-colors font-medium">
            <Ban className="w-4 h-4 opacity-80"/> Suspend
          </button>
          <button className="w-full text-left px-3 py-1.5 text-sm text-[var(--state-error)] hover:bg-[#FDF8F8] flex items-center gap-2 transition-colors font-medium">
            <Trash2 className="w-4 h-4 opacity-80"/> Delete
          </button>
        </div>
      )}
    </div>
  );
};

const WorkspacesPage = ({  setActiveRoute  }: any) => {
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
        title="Workspaces" 
        subtitle="Manage all tenant environments and access." 
        actions={
          <>
            <Button variant="outline" className="hidden sm:flex"><Search className="w-4 h-4 mr-2"/> Import</Button>
            <Button onClick={() => setIsCreateOpen(true)}><Plus className="w-4 h-4 mr-2"/> Create workspace</Button>
          </>
        } 
      />

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
            <div className="w-full sm:w-36">
              <Select value={status} onChange={setStatus} options={[{label: 'All Statuses', value: 'all'}, {label: 'Active', value: 'Active'}, {label: 'Suspended', value: 'Suspended'}]} placeholder="Status" />
            </div>
            <div className="w-full sm:w-36">
              <Select value={plan} onChange={setPlan} options={[{label: 'All Plans', value: 'all'}, {label: 'Free', value: 'Free'}, {label: 'Pro', value: 'Pro'}, {label: 'Enterprise', value: 'Enterprise'}]} placeholder="Plan" />
            </div>
          </div>
          {(search || status !== 'all' || plan !== 'all') && (
            <Button variant="tertiary" onClick={() => {setSearch(''); setStatus('all'); setPlan('all');}} className="px-3">Clear filters</Button>
          )}
        </div>
      </Section>

      <Section>
        <DataTable columns={["Workspace", "Owner", "Plan", "Members", "Usage", "Status", "Created", ""]} data={mappedData} loading={isLoading} />
      </Section>

      <Modal 
        isOpen={isCreateOpen} 
        onClose={() => setIsCreateOpen(false)}
        title="Create Workspace"
        description="Provision a new tenant environment."
        footer={<><Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button><Button onClick={() => setIsCreateOpen(false)}>Create Environment</Button></>}
      >
        <div className="space-y-4">
          <Input label="Workspace Name" placeholder="e.g. Acme Corp Production" />
          <Select label="Plan Tier" placeholder="Select plan..." options={[{label: 'Free Tier', value: 'free'}, {label: 'Pro', value: 'pro'}, {label: 'Enterprise', value: 'enterprise'}]} value="free" onChange={() => {}} />
          <Input label="Admin Email" placeholder="owner@company.com" helperText="An invitation will be sent to this email." />
        </div>
      </Modal>

    </PageContainer>
  );
};

// --- REMAINING PREVIOUS PAGES ---
const ComponentsPage = () => {
  const [date, setDate] = useState("");
  const [selectVal, setSelectVal] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  
  return (
    <PageContainer maxWidth="default">
      <PageHeader title="Component Library" subtitle="Foundational UI system for Kaori Platform following strict design tokens." actions={<Button>Deploy System</Button>} />
      <Tabs defaultValue="form" tabs={[
        { id: 'form', label: 'Forms & Inputs', content: (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <Section title="Buttons" className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)]">
               <div className="flex flex-wrap gap-4 mb-4"><Button variant="primary">Primary</Button><Button variant="secondary">Secondary</Button><Button variant="tertiary">Ghost</Button></div>
               <div className="flex flex-wrap gap-4 items-center"><Button variant="primary" isLoading>Loading</Button><Button variant="destructive">Destructive</Button><Button variant="primary" size="icon"><Plus className="w-4 h-4"/></Button></div>
             </Section>
             <Section title="Inputs & Selects" className="bg-[var(--bg-card)] p-6 rounded-lg-custom border border-[var(--border-color)] space-y-4">
                <Input label="Email Address" placeholder="admin@kaori.io" helperText="We will never share your email." />
                <Select label="Environment" placeholder="Select environment..." options={[{label: 'Production', value: 'prod'}]} value={selectVal} onChange={setSelectVal} />
             </Section>
           </div>
        )},
        { id: 'data', label: 'Data Display', content: ( <Alert variant="info" title="Data Components">Use Data Tables & Metric Cards for display.</Alert> )},
        { id: 'feedback', label: 'Feedback & Overlays', content: ( <Alert variant="info" title="Feedback Components">Modals, Drawers and Alerts provide user feedback.</Alert> )}
      ]} />
    </PageContainer>
  );
};

const PlatformOverview = () => {
  return (
    <PageContainer maxWidth="default">
      <PageHeader title="Platform Overview" subtitle="Monitor system health, usage, and recent activity." actions={<Button variant="outline"><RefreshCw className="w-4 h-4 mr-2" /> Refresh Data</Button>} />
      <Section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <MetricCard title="Total Workspaces" value="124" trend="+4" isUp={true} />
          <MetricCard title="Active Users" value="1,892" trend="+12.5%" isUp={true} />
          <MetricCard title="API Requests" value="2.4M" trend="+5.2%" isUp={true} />
          <MetricCard title="Failed Requests" value="482" trend="-18%" isUp={false} inverseGood={true} />
        </div>
      </Section>
      <Section title="Recent Activity">
         <DataTable 
            columns={["Event", "Workspace", "Time"]}
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
  return (
    <PageContainer maxWidth="narrow">
      <PageHeader title="Active Sessions" subtitle="Manage devices where your account is currently signed in." actions={<Button variant="outline">Sign out all</Button>} />
      <Section title="Security & Sessions">
        <Card className="p-8 text-center flex flex-col items-center">
          <Shield className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
          <h3 className="text-sm font-medium text-[var(--text-primary)]">Security & Sessions</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1">Manage active logins here.</p>
        </Card>
      </Section>
    </PageContainer>
  );
};


// ==========================================
// MAIN PLATFORM SHELL COMPONENT
// ==========================================

export default function KaoriPlatformShell() {
  const [activeRoute, setActiveRoute] = useState('workspace-members'); // Defaulted to members for review
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
// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 8Header user menu env badge.jsx by convert_jsx_to_tsx.py.
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
  ShieldAlert,
  RefreshCw,
  Plus,
  UserPlus,
  Server,
  Database,
  Cpu,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronsUpDown,
  User,
  Check
} from 'lucide-react';

// --- DESIGN TOKENS & STYLES ---
const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400&display=swap');

    :root {
      /* Colors */
      --primary-gold: #D4B88A;
      
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

      /* Shadows */
      --shadow-soft-sm: 0 2px 8px -2px rgba(47, 47, 47, 0.04), 0 1px 3px -1px rgba(47, 47, 47, 0.02);
      --shadow-soft-md: 0 6px 16px -4px rgba(47, 47, 47, 0.06), 0 4px 8px -2px rgba(47, 47, 47, 0.03);
      
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

    /* Sidebar Transitions */
    .sidebar-transition {
      transition: width 0.3s cubic-bezier(0.2, 0, 0, 1), padding 0.3s ease, opacity 0.2s ease;
    }
  `}</style>
);

// --- NAVIGATION CONFIGURATION ---
const NAVIGATION_CONFIG = [
  {
    group: 'Main',
    items: [
      { id: 'overview', label: 'Platform Health', icon: LayoutDashboard, route: '/platform' },
      { id: 'workspaces', label: 'Workspaces', icon: Briefcase, route: '/platform/workspaces', badge: '2' },
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
      { id: 'sessions', label: 'Security & Sessions', icon: Settings, route: '/p1/auth/sessions' },
    ]
  }
];

// --- SHARED UI COMPONENTS ---

const Badge = ({  variant = 'default', children  }: any) => {
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
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm-custom text-[11px] font-medium border ${variants[variant]}`}>
      {children}
    </span>
  );
};

const Button = React.forwardRef<any, any>(({ className, variant = "default", size = "default", isLoading, children, ...props }, ref) => {
  const variants = {
    default: "bg-[var(--primary-gold)] text-[var(--text-primary)] hover:bg-[#BFA88C] active:scale-[0.98] shadow-soft-sm",
    outline: "border border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-primary)] hover:bg-[var(--bg-app)] active:scale-[0.98] shadow-sm",
    ghost: "bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] active:scale-[0.98]",
    "destructive-soft": "border border-[var(--border-color)] bg-transparent text-[var(--text-primary)] hover:border-[var(--state-error)]/40 hover:bg-[var(--state-error)]/10 hover:text-[#9B5050] active:scale-[0.98]",
    destructive: "bg-[var(--state-error)] text-white hover:bg-[#C26B6B] active:scale-[0.98] shadow-soft-sm border border-transparent",
  };
  
  const sizes = {
    default: "h-9 px-4 py-2",
    sm: "h-8 rounded-sm-custom px-3 text-xs",
    icon: "h-9 w-9",
  };

  return (
    <button
      className={`inline-flex items-center justify-center rounded-md-custom text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50 disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className || ''}`}
      ref={ref}
      disabled={isLoading || props.disabled}
      {...props}
    >
      {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
});
Button.displayName = "Button";

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
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const notifications = [
    { id: 1, title: 'Data sync completed successfully', time: '10m ago', read: false },
    { id: 2, title: 'New login from Mac OS (Safari)', time: '2h ago', read: false },
    { id: 3, title: 'Weekly intelligence report generated', time: '1d ago', read: true },
  ];

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="relative" ref={dropdownRef}>
      <button 
        aria-label="Notifications"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        onClick={() => setIsOpen(!isOpen)} 
        className={`relative p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-full transition-colors border ${isOpen ? 'bg-[var(--bg-app)] border-[var(--border-color)]' : 'border-transparent hover:bg-[var(--bg-app)] hover:border-[var(--border-color)]'}`}
      >
        <Bell className="w-[18px] h-[18px]" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#D97C7C] border-2 border-[var(--bg-app)] animate-pulse"></span>
        )}
      </button>

      {isOpen && (
        <div 
          role="dialog"
          aria-label="Notifications Panel"
          className="absolute right-0 mt-2 w-[320px] bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)] bg-[#FCFBF9]">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Notifications</h3>
            <button className="text-[11px] font-medium text-[var(--primary-gold)] hover:text-[#BFA88C]">
              Mark all read
            </button>
          </div>
          <div className="max-h-[300px] overflow-y-auto">
            {notifications.map((n) => (
              <div key={n.id} className={`px-4 py-3 border-b border-[var(--border-color)]/50 last:border-0 hover:bg-[var(--bg-app)]/50 transition-colors cursor-pointer flex gap-3 ${!n.read ? 'bg-[#FAF7F2]/30' : ''}`}>
                <div className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${!n.read ? 'bg-[var(--primary-gold)]' : 'bg-transparent'}`} />
                <div>
                  <p className={`text-sm ${!n.read ? 'font-medium text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'}`}>
                    {n.title}
                  </p>
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
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button 
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={() => setIsOpen(!isOpen)}
        className="w-[34px] h-[34px] rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center transition-all hover:shadow-soft-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50 shrink-0 overflow-hidden"
      >
        <span className="text-sm font-semibold text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
          A
        </span>
      </button>

      {isOpen && (
        <div 
          role="menu"
          aria-label="User menu"
          className="absolute right-0 mt-2 w-[240px] bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50"
        >
          <div className="px-4 py-3 border-b border-[var(--border-color)] bg-[#FCFBF9]" role="none">
            <p className="text-sm font-semibold text-[var(--text-primary)] truncate">Admin User</p>
            <p className="text-xs text-[var(--text-secondary)] truncate">admin@kaori.io</p>
            <div className="mt-2 text-[10px] text-[var(--text-secondary)]/80 flex items-center gap-1 font-mono">
              <Clock className="w-3 h-3" /> Last login: Today, 08:24
            </div>
          </div>
          
          <div className="p-1.5" role="none">
            <div className="px-2 py-1.5 text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-wider opacity-70">
              Account
            </div>
            <button role="menuitem" className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors flex items-center gap-2">
              <User className="w-4 h-4 text-[var(--text-secondary)]" aria-hidden="true" /> Profile
            </button>
            <button 
              role="menuitem"
              onClick={() => { setActiveRoute('sessions'); setIsOpen(false); }}
              className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors flex items-center gap-2"
            >
              <Shield className="w-4 h-4 text-[var(--text-secondary)]" aria-hidden="true" /> Security & Sessions
            </button>
          </div>
          
          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" role="none" />
          
          <div className="p-1.5" role="none">
            <div className="px-2 py-1.5 text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-wider opacity-70">
              System
            </div>
            <button role="menuitem" className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors flex items-center gap-2">
              <Settings className="w-4 h-4 text-[var(--text-secondary)]" aria-hidden="true" /> Workspace Settings
            </button>
          </div>

          <div className="h-[1px] bg-[var(--border-color)]/50 mx-1.5" role="none" />

          <div className="p-1.5" role="none">
            <button role="menuitem" className="w-full text-left px-2 py-1.5 rounded-md-custom text-sm text-[#9B5050] hover:bg-[#FDF8F8] transition-colors flex items-center gap-2 font-medium">
              <LogOut className="w-4 h-4 text-[#9B5050]/80" aria-hidden="true" /> Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const GlobalHeader = ({  activeRoute, setActiveRoute, setIsMobileMenuOpen  }: any) => {
  const routeLabel = NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label || activeRoute;

  return (
    <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/90 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6 transition-all duration-300">
      
      {/* Left Section: Breadcrumb & Mobile Toggle */}
      <div className="flex items-center gap-4">
        <button 
          aria-label="Open Sidebar"
          className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white rounded-md-custom transition-colors border border-transparent hover:border-[var(--border-color)]"
          onClick={() => setIsMobileMenuOpen(true)}
        >
          <Menu className="w-5 h-5" />
        </button>
        
        {/* Dynamic Breadcrumbs */}
        <div className="hidden sm:flex items-center text-sm font-medium">
          <span className="text-[var(--text-secondary)]">Platform</span>
          <ChevronRight className="w-4 h-4 mx-2 text-[var(--border-color)] shrink-0 opacity-50" />
          <span className="text-[var(--text-primary)] capitalize">
            {routeLabel}
          </span>
        </div>
        
        {/* Mobile Title Fallback */}
        <div className="sm:hidden font-medium text-[var(--text-primary)] text-sm">
          {routeLabel}
        </div>
      </div>

      {/* Right Section: Environment, Actions, Notifications, User Menu */}
      <div className="flex items-center gap-3 sm:gap-4">
        
        {/* Environment Badge */}
        <EnvBadge env="production" />
        
        <div className="w-[1px] h-5 bg-[var(--border-color)] hidden md:block mx-1"></div>

        {/* Action Slot */}
        <div className="hidden sm:flex items-center gap-2">
           <div className="relative group hidden lg:block">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-[14px] h-[14px] text-[var(--text-secondary)] group-focus-within:text-[var(--primary-gold)] transition-colors" />
              <input 
                type="text" 
                placeholder="Search..." 
                className="h-8 w-48 pl-8 pr-10 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm"
              />
              <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1 pointer-events-none">
                <kbd className="hidden sm:inline-flex items-center justify-center h-5 px-1.5 text-[10px] font-medium text-[var(--text-secondary)] bg-[var(--bg-app)] border border-[var(--border-color)] rounded">⌘K</kbd>
              </div>
            </div>

            <Button variant="outline" size="sm" className="hidden md:flex">
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Workspace
            </Button>
        </div>

        {/* Notifications & User Menu */}
        <NotificationDropdown />
        <HeaderUserMenu setActiveRoute={setActiveRoute} />
        
      </div>
    </header>
  );
};


// --- LAYOUT COMPONENTS ---

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

  return (
    <aside className={`
      relative flex flex-col h-full bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] sidebar-transition z-30
      ${isMobile ? 'w-[280px]' : collapsed ? 'w-[72px]' : 'w-[240px]'}
    `}>
      
      {/* 1. LOGO SECTION */}
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

      {/* Workspace Switcher (Phase 2 Preview) */}
      <div className={`p-3 shrink-0 ${collapsed ? 'px-2 flex justify-center' : ''}`}>
        <button aria-label="Switch Workspace" aria-haspopup="listbox" className={`flex items-center w-full h-10 rounded-md-custom bg-[var(--bg-app)] border border-[var(--border-color)] shadow-sm hover:border-[var(--primary-gold)]/50 transition-colors ${collapsed ? 'justify-center w-10' : 'px-3 justify-between'}`}>
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="w-5 h-5 rounded bg-[#E6C07B]/20 text-[#9E814D] flex items-center justify-center text-[10px] font-bold shrink-0">P</div>
            {!collapsed && <span className="text-sm font-medium text-[var(--text-primary)] truncate">Production AI</span>}
          </div>
          {!collapsed && <ChevronsUpDown className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />}
        </button>
      </div>

      {/* 2. NAVIGATION GROUPS */}
      <nav aria-label="Main Navigation" className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-2 space-y-6">
        {NAVIGATION_CONFIG.map((group, idx) => (
          <div key={idx} className="flex flex-col">
            {/* Group Label */}
            {!collapsed ? (
              <div className="px-3 mb-2 text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-[0.1em] opacity-70">
                {group.group}
              </div>
            ) : (
              <div className="w-full h-[1px] bg-[var(--border-color)]/60 my-2 rounded-full" />
            )}

            {/* Nav Items */}
            <div className="space-y-1">
              {group.items.map((item) => {
                const isActive = activeRoute === item.id;
                const Icon = item.icon;
                
                return (
                  <SidebarTooltip key={item.id} content={item.label} isCollapsed={collapsed}>
                    <button
                      onClick={() => setActiveRoute(item.id)}
                      className={`
                        relative flex items-center h-10 rounded-md-custom transition-all duration-200 group w-full
                        ${isActive 
                          ? 'bg-[var(--primary-gold)]/10 text-[var(--text-primary)]' 
                          : 'text-[var(--text-secondary)] hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)]'}
                        ${collapsed ? 'justify-center px-0' : 'px-3 gap-3'}
                      `}
                    >
                      {/* Active Left Accent Bar */}
                      {isActive && (
                        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[var(--primary-gold)] rounded-r-md transition-all" />
                      )}
                      
                      <Icon className={`shrink-0 transition-colors ${isActive ? 'text-[var(--primary-gold)] w-5 h-5' : 'w-[18px] h-[18px] group-hover:text-[var(--text-primary)]'}`} />
                      
                      {!collapsed && (
                        <span className="text-sm font-medium truncate flex-1 text-left">
                          {item.label}
                        </span>
                      )}

                      {/* Optional Badge */}
                      {!collapsed && item.badge && (
                        <span className="shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-[var(--primary-gold)] text-white text-[10px] font-bold shadow-sm">
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

      {/* 3. BOTTOM SECTION (Cleaned up: User Menu moved to Header) */}
      <div className="shrink-0 p-3 flex justify-center">
        {/* Collapse Toggle (Hidden on Mobile) */}
        {!isMobile && (
          <button 
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={`
              w-full flex items-center h-8 rounded-md-custom text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors border border-transparent hover:border-[var(--border-color)]/50
              ${collapsed ? 'justify-center' : 'px-3 gap-3'}
            `}
          >
            {collapsed ? <PanelLeftOpen className="w-[18px] h-[18px]" /> : <PanelLeftClose className="w-[18px] h-[18px]" />}
            {!collapsed && <span className="text-xs font-medium">Collapse sidebar</span>}
          </button>
        )}
      </div>
    </aside>
  );
};


// --- DASHBOARD CONTENT COMPONENTS (Reused from previous iterations) ---
// Note: Keeping these exact to ensure the whole shell remains runnable

const MetricCard = ({  title, value, trend, isUp, inverseGood = false  }: any) => {
  const isPositive = (isUp && !inverseGood) || (!isUp && inverseGood);
  const trendColor = trend === '0%' ? 'text-[var(--text-secondary)]' : isPositive ? 'text-[#5C856A]' : 'text-[#9B5050]';
  return (
    <div className="bg-[var(--bg-card)] rounded-md-custom p-5 border border-[var(--border-color)] shadow-soft-sm transition-shadow hover:shadow-soft-md">
      <div className="text-sm font-medium text-[var(--text-secondary)] mb-3">{title}</div>
      <div className="flex items-baseline gap-3">
        <div className="text-3xl font-semibold text-[var(--text-primary)]">{value}</div>
        {trend !== '0%' && (
          <div className={`flex items-center text-xs font-medium ${trendColor}`}>
            {isUp ? <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" /> : <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" />}
            {trend}
          </div>
        )}
      </div>
      <div className="text-xs text-[var(--text-secondary)] mt-1 opacity-75">vs yesterday</div>
    </div>
  );
};

const PlatformOverview = () => {
  return (
    <div className="max-w-[1280px] mx-auto w-full space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-1">Platform Overview</h1>
          <p className="text-sm text-[var(--text-secondary)]">Monitor system health, usage, and recent activity.</p>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <MetricCard title="Total Workspaces" value="124" trend="+4" isUp={true} />
        <MetricCard title="Active Users" value="1,892" trend="+12.5%" isUp={true} />
        <MetricCard title="API Requests" value="2.4M" trend="+5.2%" isUp={true} />
        <MetricCard title="Failed Requests" value="482" trend="-18%" isUp={false} inverseGood={true} />
      </div>
      <div className="p-8 rounded-md-custom border border-dashed border-[var(--border-color)] bg-[var(--bg-app)]/50 text-center flex flex-col items-center">
        <Activity className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
        <h3 className="text-sm font-medium text-[var(--text-primary)]">Overview Dashboard</h3>
        <p className="text-xs text-[var(--text-secondary)]">Content generated in previous iterations remains available.</p>
      </div>
    </div>
  );
};

const SessionsPage = () => {
  return (
     <div className="max-w-[960px] mx-auto w-full space-y-8 animate-in fade-in duration-300 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-1">Active Sessions</h1>
          <p className="text-sm text-[var(--text-secondary)]">Manage devices where your account is currently signed in.</p>
        </div>
      </div>
      <div className="p-8 rounded-md-custom border border-dashed border-[var(--border-color)] bg-[var(--bg-app)]/50 text-center flex flex-col items-center">
        <Shield className="w-8 h-8 text-[var(--text-secondary)] mb-3" />
        <h3 className="text-sm font-medium text-[var(--text-primary)]">Security & Sessions</h3>
        <p className="text-xs text-[var(--text-secondary)]">Full functionality generated in previous step is active.</p>
      </div>
    </div>
  );
};


// --- MAIN PLATFORM SHELL COMPONENT ---

export default function KaoriPlatformShell() {
  const [activeRoute, setActiveRoute] = useState('overview');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  
  // Persisted collapse state logic
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('kaori_sidebar_collapsed');
      return saved === 'true';
    } catch {
      return false; // Fallback if iframe localstorage is blocked
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('kaori_sidebar_collapsed', isCollapsed);
    } catch (e) {
      // Ignore if localstorage fails in restricted iframe
    }
  }, [isCollapsed]);

  return (
    <>
      <GlobalStyles />
      <div className="flex h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
        
        {/* DESKTOP SIDEBAR */}
        <div className="hidden md:block shrink-0">
          <GlobalSidebar 
            isMobile={false} 
            activeRoute={activeRoute} 
            setActiveRoute={setActiveRoute}
            isCollapsed={isCollapsed}
            setIsCollapsed={setIsCollapsed}
          />
        </div>

        {/* MOBILE SIDEBAR OVERLAY */}
        {isMobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            <div className="fixed inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity" onClick={() => setIsMobileMenuOpen(false)} />
            <div className="relative flex flex-col shadow-2xl animate-in slide-in-from-left h-full">
              <button 
                onClick={() => setIsMobileMenuOpen(false)}
                className="absolute top-4 -right-12 p-2 text-white hover:text-white/80 bg-[var(--text-primary)] rounded-full shadow-md z-50"
              >
                <X className="w-5 h-5" />
              </button>
              {/* Force expanded state on mobile */}
              <GlobalSidebar 
                isMobile={true} 
                activeRoute={activeRoute} 
                setActiveRoute={(r: any) => { setActiveRoute(r); setIsMobileMenuOpen(false); }}
                isCollapsed={false}
                setIsCollapsed={() => {}}
              />
            </div>
          </div>
        )}

        {/* MAIN CONTENT WRAPPER */}
        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative">
          
          {/* DEDICATED GLOBAL HEADER */}
          <GlobalHeader 
            activeRoute={activeRoute} 
            setActiveRoute={setActiveRoute}
            setIsMobileMenuOpen={setIsMobileMenuOpen} 
          />

          {/* PAGE CONTENT AREA (Scrollable) */}
          <main className="flex-1 overflow-y-auto p-6 bg-[var(--bg-app)]">
            {activeRoute === 'overview' ? (
              <PlatformOverview />
            ) : activeRoute === 'sessions' ? (
              <SessionsPage />
            ) : (
              <div className="flex flex-col items-center justify-center py-20 px-4 text-center border border-dashed border-[var(--border-color)] rounded-lg-custom bg-[var(--bg-card)]/50 max-w-[960px] mx-auto w-full animate-in fade-in duration-300">
                <div className="w-12 h-12 rounded-lg-custom bg-[var(--bg-sidebar)] flex items-center justify-center border border-[var(--border-color)] mb-4">
                  {React.createElement(NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.icon || LayoutDashboard, { className: 'w-6 h-6 text-[var(--text-secondary)]' })}
                </div>
                <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">
                  {NAVIGATION_CONFIG.flatMap(g => g.items).find(n => n.id === activeRoute)?.label} module
                </h3>
                <p className="text-sm text-[var(--text-secondary)] max-w-sm">
                  This section of the platform is currently being designed. Content for {activeRoute} will populate here inside the Shell Wrapper.
                </p>
              </div>
            )}
          </main>
        </div>
      </div>
    </>
  );
}
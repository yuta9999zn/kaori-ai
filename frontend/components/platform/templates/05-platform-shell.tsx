// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 5Kaori Platform Shell.jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState } from 'react';
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
  ArrowDownRight
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
      
      /* Radii mapped to standard Tailwind classes for ease of use, but explicitly defined here */
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

    /* Custom utility classes based on tokens */
    .shadow-soft-sm { box-shadow: var(--shadow-soft-sm); }
    .shadow-soft-md { box-shadow: var(--shadow-soft-md); }
    
    .rounded-sm-custom { border-radius: var(--radius-sm); }
    .rounded-md-custom { border-radius: var(--radius-md); }
    .rounded-lg-custom { border-radius: var(--radius-lg); }

    /* Scrollbar styling for a cleaner look */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #E9E7E2; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #D4B88A; }
  `}</style>
);

// --- NAVIGATION CONFIG ---
const NAVIGATION = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'workspaces', label: 'Workspaces', icon: Briefcase },
  { id: 'keys', label: 'API Keys', icon: Key },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'admin', label: 'Admin', icon: Shield },
  { id: 'health', label: 'Platform Health', icon: Activity },
];

// --- COMPONENTS ---

const Badge = ({  variant = 'default', children  }: any) => {
  const variants = {
    default: "bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]",
    success: "bg-[var(--state-success)]/10 text-[#5C856A] border-[var(--state-success)]/30",
    warning: "bg-[var(--state-warning)]/10 text-[#9E814D] border-[var(--state-warning)]/30",
    error: "bg-[var(--state-error)]/10 text-[#9B5050] border-[var(--state-error)]/30",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm-custom text-[11px] font-medium border ${variants[variant]}`}>
      {children}
    </span>
  );
};

export default function KaoriPlatformShell() {
  const [activeRoute, setActiveRoute] = useState('overview');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Layout Components
  const Sidebar = ({  isMobile  }: any) => (
    <aside className={`
      flex flex-col h-full bg-[var(--bg-sidebar)] border-r border-[var(--border-color)]
      ${isMobile ? 'w-full' : 'w-[260px]'}
    `}>
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-6 h-16 shrink-0">
        <div className="flex h-8 w-8 items-center justify-center rounded-md-custom bg-white shadow-soft-sm border border-[var(--border-color)]">
          <svg className="w-5 h-5 text-[var(--primary-gold)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z" fill="currentColor" fillOpacity="0.1"/>
            <path d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z" fill="currentColor" fillOpacity="0.1"/>
          </svg>
        </div>
        <span className="font-serif text-lg font-medium text-[var(--text-primary)] tracking-wide">Kaori</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-4 py-6 space-y-1">
        {NAVIGATION.map((item) => {
          const isActive = activeRoute === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => {
                setActiveRoute(item.id);
                if (isMobile) setIsMobileMenuOpen(false);
              }}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-md-custom text-sm font-medium transition-all duration-200
                ${isActive 
                  ? 'bg-white text-[var(--text-primary)] shadow-soft-sm border border-[var(--border-color)]/50' 
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)] border border-transparent'}
              `}
            >
              <Icon className={`w-[18px] h-[18px] ${isActive ? 'text-[var(--primary-gold)]' : ''}`} />
              {item.label}
              
              {item.id === 'health' && (
                <span className="ml-auto flex h-2 w-2 rounded-full bg-[var(--state-success)]"></span>
              )}
            </button>
          );
        })}
      </nav>

      {/* User Profile Footer */}
      <div className="p-4 shrink-0 border-t border-[var(--border-color)]">
        <button className="w-full flex items-center gap-3 p-2 rounded-md-custom hover:bg-[var(--bg-app)] transition-colors text-left border border-transparent hover:border-[var(--border-color)]/50">
          <div className="w-9 h-9 rounded-md-custom bg-white flex items-center justify-center font-medium text-[var(--primary-gold)] shadow-soft-sm border border-[var(--border-color)]">
            A
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[var(--text-primary)] truncate">Admin User</p>
            <p className="text-xs text-[var(--text-secondary)] truncate">admin@company.com</p>
          </div>
          <MoreVertical className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />
        </button>
      </div>
    </aside>
  );

  return (
    <>
      <GlobalStyles />
      <div className="flex h-screen overflow-hidden bg-[var(--bg-app)]">
        
        {/* DESKTOP SIDEBAR */}
        <div className="hidden md:block shrink-0">
          <Sidebar isMobile={false} />
        </div>

        {/* MOBILE SIDEBAR OVERLAY */}
        {isMobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            <div className="fixed inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm" onClick={() => setIsMobileMenuOpen(false)} />
            <div className="relative w-[280px] h-full bg-[var(--bg-sidebar)] flex flex-col shadow-2xl animate-in slide-in-from-left">
              <button 
                onClick={() => setIsMobileMenuOpen(false)}
                className="absolute top-4 right-4 p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                <X className="w-5 h-5" />
              </button>
              <Sidebar isMobile={true} />
            </div>
          </div>
        )}

        {/* MAIN CONTENT WRAPPER */}
        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
          
          {/* HEADER */}
          <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/80 backdrop-blur-md sticky top-0 z-20 flex items-center justify-between px-4 sm:px-8">
            
            <div className="flex items-center gap-4">
              <button 
                className="md:hidden p-2 -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-md-custom"
                onClick={() => setIsMobileMenuOpen(true)}
              >
                <Menu className="w-5 h-5" />
              </button>
              
              {/* Breadcrumbs */}
              <div className="hidden sm:flex items-center text-sm font-medium">
                <span className="text-[var(--text-secondary)]">Platform</span>
                <ChevronRight className="w-4 h-4 mx-2 text-[var(--border-color)] shrink-0" />
                <span className="text-[var(--text-primary)] capitalize">
                  {NAVIGATION.find(n => n.id === activeRoute)?.label}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3 sm:gap-6">
              {/* Global Search */}
              <div className="relative group hidden sm:block">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)] group-focus-within:text-[var(--primary-gold)] transition-colors" />
                <input 
                  type="text" 
                  placeholder="Search resources..." 
                  className="h-9 w-64 pl-9 pr-12 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-sm"
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <kbd className="hidden sm:inline-flex items-center justify-center h-5 px-1.5 text-[10px] font-medium text-[var(--text-secondary)] bg-[var(--bg-app)] border border-[var(--border-color)] rounded">⌘K</kbd>
                </div>
              </div>

              {/* Notifications */}
              <button className="relative p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-full hover:bg-white transition-colors border border-transparent hover:border-[var(--border-color)]">
                <Bell className="w-5 h-5" />
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--primary-gold)] border-2 border-[var(--bg-app)]"></span>
              </button>
            </div>
          </header>

          {/* PAGE CONTENT AREA (Scrollable) */}
          <main className="flex-1 overflow-y-auto p-4 sm:p-8">
            <div className="max-w-[1080px] mx-auto w-full space-y-8 animate-in fade-in duration-300">
              
              {/* PAGE HEADER */}
              <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-1">
                    {NAVIGATION.find(n => n.id === activeRoute)?.label}
                  </h1>
                  <p className="text-sm text-[var(--text-secondary)]">
                    Overview of your data intelligence platform metrics and health.
                  </p>
                </div>
                {activeRoute === 'overview' && (
                   <div className="flex items-center gap-3">
                     <select className="h-9 px-3 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30">
                       <option>Last 7 days</option>
                       <option>Last 30 days</option>
                       <option>This year</option>
                     </select>
                     <button className="h-9 px-4 rounded-md-custom bg-[var(--primary-gold)] text-[var(--text-primary)] text-sm font-medium hover:bg-[#BFA88C] transition-colors shadow-soft-sm active:scale-[0.98]">
                       Export Report
                     </button>
                   </div>
                )}
              </div>

              {/* MOCK DATA DASHBOARD (Shows data-first UI usage) */}
              {activeRoute === 'overview' ? (
                <>
                  {/* KPI Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
                    {[
                      { label: 'Total Queries', value: '2.4M', trend: '+12.5%', isUp: true },
                      { label: 'Avg Latency', value: '42ms', trend: '-5.2%', isUp: true, inverseGood: true },
                      { label: 'Active Workspaces', value: '14', trend: '0%', isUp: null },
                      { label: 'Error Rate', value: '0.12%', trend: '+0.04%', isUp: false, inverseGood: true },
                    ].map((stat, i) => (
                      <div key={i} className="bg-[var(--bg-card)] rounded-lg-custom p-5 border border-[var(--border-color)] shadow-soft-sm">
                        <div className="text-sm font-medium text-[var(--text-secondary)] mb-3">{stat.label}</div>
                        <div className="flex items-baseline gap-3">
                          <div className="text-3xl font-semibold text-[var(--text-primary)]">{stat.value}</div>
                          {stat.trend !== '0%' && (
                            <div className={`flex items-center text-xs font-medium ${(stat.isUp && !stat.inverseGood) || (!stat.isUp && stat.inverseGood) ? 'text-[var(--state-success)]' : 'text-[var(--state-error)]'}`}>
                              {stat.isUp ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
                              {stat.trend}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Data Table Area */}
                  <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-md overflow-hidden">
                    <div className="px-6 py-5 border-b border-[var(--border-color)] flex justify-between items-center bg-[#FCFBF9]">
                      <h3 className="font-medium text-[var(--text-primary)]">Recent Operations</h3>
                      <button className="text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--primary-gold)] transition-colors">View all</button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] bg-[var(--bg-app)]">
                          <tr>
                            <th className="px-6 py-3 font-semibold">Workspace</th>
                            <th className="px-6 py-3 font-semibold">Operation</th>
                            <th className="px-6 py-3 font-semibold">Status</th>
                            <th className="px-6 py-3 font-semibold text-right">Duration</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border-color)]">
                          {[
                            { ws: 'Production AI', op: 'Data Sync (Daily)', status: 'success', time: '1.2s' },
                            { ws: 'Staging Env', op: 'Index Rebuild', status: 'warning', time: '45s' },
                            { ws: 'Analytics Core', op: 'Query Cache Clear', status: 'success', time: '120ms' },
                            { ws: 'Legacy API', op: 'Webhook Dispatch', status: 'error', time: 'timeout' },
                          ].map((row, i) => (
                            <tr key={i} className="hover:bg-[var(--bg-app)]/50 transition-colors">
                              <td className="px-6 py-4 font-medium text-[var(--text-primary)]">{row.ws}</td>
                              <td className="px-6 py-4 text-[var(--text-secondary)] font-mono text-xs">{row.op}</td>
                              <td className="px-6 py-4">
                                <Badge variant={row.status}>
                                  {row.status.charAt(0).toUpperCase() + row.status.slice(1)}
                                </Badge>
                              </td>
                              <td className="px-6 py-4 text-right text-[var(--text-secondary)] tabular-nums">{row.time}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-20 px-4 text-center border border-dashed border-[var(--border-color)] rounded-lg-custom bg-[var(--bg-card)]/50">
                  <div className="w-12 h-12 rounded-lg-custom bg-[var(--bg-sidebar)] flex items-center justify-center border border-[var(--border-color)] mb-4">
                    {React.createElement(NAVIGATION.find(n => n.id === activeRoute)?.icon || LayoutDashboard, { className: 'w-6 h-6 text-[var(--text-secondary)]' })}
                  </div>
                  <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">
                    {NAVIGATION.find(n => n.id === activeRoute)?.label} module
                  </h3>
                  <p className="text-sm text-[var(--text-secondary)] max-w-sm">
                    This section of the platform is currently being designed. Content for {activeRoute} will populate here inside the Shell Wrapper.
                  </p>
                </div>
              )}

            </div>
          </main>
        </div>
      </div>
    </>
  );
}
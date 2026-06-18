// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 6Kaori Session Management.jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState, useEffect } from 'react';
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
  ShieldAlert
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

    @keyframes slideUpFade {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .animate-slide-up-fade {
      animation: slideUpFade 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
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

// --- SHARED UI COMPONENTS ---

const Badge = ({  variant = 'default', children  }: any) => {
  const variants = {
    default: "bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]",
    success: "bg-[var(--state-success)]/10 text-[#5C856A] border-[var(--state-success)]/30",
    warning: "bg-[var(--state-warning)]/10 text-[#9E814D] border-[var(--state-warning)]/30",
    error: "bg-[var(--state-error)]/10 text-[#9B5050] border-[var(--state-error)]/30",
    current: "bg-[var(--primary-gold)]/10 text-[#9E814D] border-[var(--primary-gold)]/30",
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
    outline: "border border-[var(--border-color)] bg-transparent text-[var(--text-primary)] hover:bg-[var(--bg-app)] active:scale-[0.98]",
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

// --- SESSIONS MANAGEMENT COMPONENTS ---

const MOCK_SESSIONS = [
  {
    id: 'sess_curr_1',
    isCurrent: true,
    deviceType: 'desktop',
    deviceName: 'Chrome on Windows',
    browser: 'Chrome 124.0',
    os: 'Windows 11',
    location: 'Hanoi, Vietnam',
    ip: '103.142.***.***',
    lastActive: 'Now',
    isSuspicious: false,
    isNew: false
  },
  {
    id: 'sess_mob_2',
    isCurrent: false,
    deviceType: 'mobile',
    deviceName: 'Safari on iPhone',
    browser: 'Safari 17.4',
    os: 'iOS 17',
    location: 'Ho Chi Minh City, Vietnam',
    ip: '113.190.***.***',
    lastActive: '2 hours ago',
    isSuspicious: false,
    isNew: true
  },
  {
    id: 'sess_desk_3',
    isCurrent: false,
    deviceType: 'desktop',
    deviceName: 'Firefox on macOS',
    browser: 'Firefox 125.0',
    os: 'macOS 14',
    location: 'Singapore, SG',
    ip: '202.168.***.***',
    lastActive: 'Yesterday, 14:30',
    isSuspicious: true,
    isNew: false
  }
];

const SessionCard = ({  session, onSignOut  }: any) => (
  <div className={`
    p-5 rounded-md-custom bg-[var(--bg-card)] border flex flex-col sm:flex-row items-start gap-4 transition-all duration-200 hover:shadow-soft-sm
    ${session.isCurrent ? 'border-[var(--primary-gold)]/40 bg-[#FAF7F2]/30' : 'border-[var(--border-color)]'}
    ${session.isSuspicious ? 'border-[var(--state-error)]/30 bg-[var(--state-error)]/5' : ''}
  `}>
    <div className={`w-10 h-10 rounded-md-custom flex items-center justify-center shrink-0 border
      ${session.isSuspicious ? 'bg-white border-[var(--state-error)]/30' : 'bg-[var(--bg-app)] border-[var(--border-color)]'}
    `}>
      {session.deviceType === 'desktop' ? (
        <Laptop className={`w-5 h-5 ${session.isSuspicious ? 'text-[#9B5050]' : 'text-[var(--text-secondary)]'}`} />
      ) : (
        <Smartphone className={`w-5 h-5 ${session.isSuspicious ? 'text-[#9B5050]' : 'text-[var(--text-secondary)]'}`} />
      )}
    </div>

    <div className="flex-1 min-w-0 space-y-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          {session.deviceName}
        </h3>
        {session.isCurrent && <Badge variant="current">Current session</Badge>}
        {session.isNew && <Badge variant="success">New device</Badge>}
        {session.isSuspicious && <Badge variant="error">Suspicious login</Badge>}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-[var(--text-secondary)]">
        <span className="flex items-center gap-1.5">
          <Globe className="w-3.5 h-3.5" />
          {session.browser} • {session.os}
        </span>
        <span className="flex items-center gap-1.5">
          <MapPin className="w-3.5 h-3.5" />
          {session.location}
        </span>
        <span className="flex items-center gap-1.5 font-mono bg-[var(--bg-app)] px-1.5 py-0.5 rounded border border-[var(--border-color)]">
          {session.ip}
        </span>
      </div>

      <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] pt-1">
        <Clock className="w-3.5 h-3.5" />
        Last active: <span className="font-medium text-[var(--text-primary)]">{session.lastActive}</span>
      </div>
    </div>

    <div className="w-full sm:w-auto pt-2 sm:pt-0 sm:ml-auto flex justify-end">
      {session.isCurrent ? (
        <span className="text-xs font-medium text-[var(--text-secondary)] px-3 py-1.5 bg-[var(--bg-app)] rounded-md-custom border border-transparent">
          This device
        </span>
      ) : (
        <Button 
          variant="destructive-soft" 
          size="sm" 
          onClick={() => onSignOut(session.id)}
          className="w-full sm:w-auto"
        >
          Sign out
        </Button>
      )}
    </div>
  </div>
);

const LogoutModal = ({  isOpen, onClose, onConfirm, title, description, isLoading  }: any) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-[var(--text-primary)]/20 backdrop-blur-sm transition-opacity"
        onClick={!isLoading ? onClose : undefined}
      />
      {/* Modal Content */}
      <div className="relative bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md border border-[var(--border-color)] w-full max-w-[400px] overflow-hidden animate-slide-up-fade">
        <div className="p-6">
          <div className="w-10 h-10 rounded-full bg-[var(--state-error)]/10 flex items-center justify-center mb-4 border border-[var(--state-error)]/20">
            <LogOut className="w-5 h-5 text-[#9B5050]" />
          </div>
          <h3 className="font-serif text-xl font-semibold text-[var(--text-primary)] mb-2">
            {title}
          </h3>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            {description}
          </p>
        </div>
        <div className="p-4 bg-[var(--bg-app)] border-t border-[var(--border-color)] flex flex-col-reverse sm:flex-row justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={isLoading} autoFocus className="w-full sm:w-auto bg-white">
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} isLoading={isLoading} className="w-full sm:w-auto">
            Confirm sign out
          </Button>
        </div>
      </div>
    </div>
  );
};

const SessionsPage = () => {
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [modalTarget, setModalTarget] = useState(null); // null | 'all' | sessionId
  const [isRevoking, setIsRevoking] = useState(false);

  useEffect(() => {
    // Simulate API Fetch
    const fetchSessions = async () => {
      try {
        await new Promise(res => setTimeout(res, 800));
        setSessions(MOCK_SESSIONS);
      } catch (err) {
        setError("Unable to load sessions. Please try again.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchSessions();
  }, []);

  const handleSignOutConfirm = async () => {
    setIsRevoking(true);
    // Simulate API Revoke
    await new Promise(res => setTimeout(res, 600));
    
    if (modalTarget === 'all') {
      setSessions(prev => prev.filter(s => s.isCurrent));
    } else {
      setSessions(prev => prev.filter(s => s.id !== modalTarget));
    }
    
    setIsRevoking(false);
    setModalTarget(null);
  };

  const currentSession = sessions.find(s => s.isCurrent);
  const otherSessions = sessions.filter(s => !s.isCurrent);

  return (
    <div className="max-w-[960px] mx-auto w-full space-y-8 animate-in fade-in duration-300 pb-12">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-1">
            Active Sessions
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            Manage devices where your account is currently signed in.
          </p>
        </div>
        {otherSessions.length > 0 && !isLoading && !error && (
          <Button 
            variant="outline" 
            onClick={() => setModalTarget('all')}
            className="flex-shrink-0"
          >
            Sign out of all other sessions
          </Button>
        )}
      </div>

      {error && (
        <div className="p-4 rounded-md-custom bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-[#9B5050] shrink-0" />
          <p className="text-sm font-medium text-[#9B5050]">{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-[120px] bg-white rounded-md-custom border border-[var(--border-color)] p-5 flex gap-4 animate-pulse">
              <div className="w-10 h-10 bg-[var(--bg-app)] rounded-md-custom shrink-0" />
              <div className="flex-1 space-y-3 pt-1">
                <div className="h-4 bg-[var(--bg-app)] rounded w-1/4" />
                <div className="h-3 bg-[var(--bg-app)] rounded w-1/2" />
                <div className="h-3 bg-[var(--bg-app)] rounded w-1/3" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {/* Current Session */}
          {currentSession && (
            <section className="space-y-3">
              <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider pl-1">
                Current Session
              </h2>
              <SessionCard session={currentSession} onSignOut={() => {}} />
            </section>
          )}

          {/* Other Sessions */}
          <section className="space-y-3">
            <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider pl-1">
              Other Devices
            </h2>
            
            {otherSessions.length > 0 ? (
              <div className="space-y-3">
                {otherSessions.map(session => (
                  <SessionCard 
                    key={session.id} 
                    session={session} 
                    onSignOut={(id: any) => setModalTarget(id)} 
                  />
                ))}
              </div>
            ) : (
              <div className="p-8 rounded-md-custom border border-dashed border-[var(--border-color)] bg-[var(--bg-app)]/50 text-center flex flex-col items-center">
                <div className="w-10 h-10 bg-white rounded-full border border-[var(--border-color)] flex items-center justify-center mb-3 shadow-soft-sm">
                  <Shield className="w-5 h-5 text-[var(--primary-gold)]" />
                </div>
                <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">
                  No other active sessions
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">
                  Your account is currently active only on this device.
                </p>
              </div>
            )}
          </section>
        </div>
      )}

      {/* Modals */}
      <LogoutModal 
        isOpen={modalTarget !== null}
        isLoading={isRevoking}
        onClose={() => setModalTarget(null)}
        onConfirm={handleSignOutConfirm}
        title={modalTarget === 'all' ? "Sign out of all sessions?" : "Sign out session?"}
        description={
          modalTarget === 'all' 
            ? "This will sign you out from all devices except this one immediately. You will need to log back in on those devices."
            : "This device will be disconnected immediately. Any unsaved work on that device may be lost."
        }
      />
    </div>
  );
};

// --- MAIN PLATFORM SHELL COMPONENT ---

export default function KaoriPlatformShell() {
  const [activeRoute, setActiveRoute] = useState('sessions'); // Defaulted to Sessions for demonstration
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Layout Components
  const Sidebar = ({  isMobile  }: any) => (
    <aside className={`
      flex flex-col h-full bg-[var(--bg-sidebar)] border-r border-[var(--border-color)]
      ${isMobile ? 'w-full' : 'w-[260px]'}
    `}>
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-6 h-16 shrink-0 border-b border-transparent">
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

        {/* Dynamic Account Navigation appended */}
        <div className="mt-8 mb-2 px-3 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
          Account
        </div>
        <button
          onClick={() => {
            setActiveRoute('sessions');
            if (isMobile) setIsMobileMenuOpen(false);
          }}
          className={`
            w-full flex items-center gap-3 px-3 py-2.5 rounded-md-custom text-sm font-medium transition-all duration-200
            ${activeRoute === 'sessions' 
              ? 'bg-white text-[var(--text-primary)] shadow-soft-sm border border-[var(--border-color)]/50' 
              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)] border border-transparent'}
          `}
        >
          <Settings className={`w-[18px] h-[18px] ${activeRoute === 'sessions' ? 'text-[var(--primary-gold)]' : ''}`} />
          Security & Sessions
        </button>

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
          <header className="h-16 shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-app)]/80 backdrop-blur-md sticky top-0 z-20 flex items-center justify-between px-6">
            
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
                  {activeRoute === 'sessions' ? 'Security & Sessions' : NAVIGATION.find(n => n.id === activeRoute)?.label}
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
                  className="h-9 w-64 pl-9 pr-12 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all shadow-soft-sm"
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

          {/* PAGE CONTENT AREA (Scrollable) - Dynamic padding added to respect layout constraints */}
          <main className="flex-1 overflow-y-auto p-6">
            
            {activeRoute === 'sessions' ? (
              <SessionsPage />
            ) : activeRoute === 'overview' ? (
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
                  <div className="flex items-center gap-3">
                    <select className="h-9 px-3 rounded-md-custom bg-white border border-[var(--border-color)] text-sm text-[var(--text-primary)] shadow-soft-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30">
                      <option>Last 7 days</option>
                      <option>Last 30 days</option>
                      <option>This year</option>
                    </select>
                    <Button>Export Report</Button>
                  </div>
                </div>

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
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 px-4 text-center border border-dashed border-[var(--border-color)] rounded-lg-custom bg-[var(--bg-card)]/50 max-w-[960px] mx-auto w-full">
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
            
          </main>
        </div>
      </div>
    </>
  );
}
// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 1KaoriLogin.jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { useT } from '@/lib/i18n/provider';

// --- STYLES & FONTS ---
// Injecting the requested Google Fonts and custom animations for the self-contained environment.
const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400&display=swap');

    :root {
      --primary-gold: #D4B88A;
      --primary-taupe: #BFA88C;
      --bg-neutral: #FAF7F2;
      --card-bg: #FFFFFF;
      --border-color: #E9E7E2;
      --text-main: #2F2F2F;
      --text-muted: #8C8173;
    }

    body {
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-neutral);
      color: var(--text-main);
      margin: 0;
    }

    .font-serif {
      font-family: 'Playfair Display', serif;
    }

    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(16px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .animate-fade-in {
      animation: fadeInUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    /* Subtle animated pattern for the left panel */
    .bg-pattern {
      background-image: radial-gradient(#D4B88A 0.5px, transparent 0.5px);
      background-size: 24px 24px;
      opacity: 0.15;
    }
  `}</style>
);

// --- UI COMPONENTS (shadcn/ui style) ---

const Input = React.forwardRef<any, any>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={`flex h-11 w-full rounded-xl border border-[#E9E7E2] bg-white px-3 py-2 text-sm text-[#2F2F2F] placeholder:text-[#8C8173]/60 transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4B88A]/40 focus-visible:border-[#D4B88A] disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

const Button = React.forwardRef<any, any>(({ className, variant = "default", size = "default", isLoading, children, ...props }, ref) => {
  const variants = {
    default: "bg-[#D4B88A] text-[#2F2F2F] hover:bg-[#BFA88C] active:scale-[0.98] shadow-sm",
    outline: "border border-[#E9E7E2] bg-transparent text-[#2F2F2F] hover:bg-[#FAF7F2] active:scale-[0.98]",
    ghost: "bg-transparent text-[#8C8173] hover:text-[#2F2F2F] hover:bg-[#FAF7F2]",
  };
  
  const sizes = {
    default: "h-11 px-4 py-2",
    sm: "h-9 rounded-md px-3",
    icon: "h-10 w-10",
  };

  return (
    <button
      className={`inline-flex items-center justify-center rounded-xl text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4B88A] disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`}
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

const Label = React.forwardRef<any, any>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={`text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-[#2F2F2F] ${className}`}
    {...props}
  />
));
Label.displayName = "Label";

// --- MAIN PAGE COMPONENT ---

export default function KaoriLogin() {
  const t = useT();
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({ email: '', password: '', remember: false });

  // Handle Form Submission (Mock API Call)
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Mock validation
    if (formData.email !== 'admin@company.com' || formData.password !== 'password') {
      setError(t('templates01KaoriLogin.errInvalidCreds'));
      setIsLoading(false);
      return;
    }

    // Success state (would redirect here)
    window.location.href = '#dashboard';
    setIsLoading(false);
  };

  return (
    <>
      <GlobalStyles />
      <div className="min-h-screen w-full flex bg-[#FAF7F2] overflow-hidden selection:bg-[#D4B88A]/30">
        
        {/* LEFT SIDE: Brand Panel */}
        <div className="relative hidden lg:flex w-1/2 flex-col justify-between p-12 overflow-hidden bg-gradient-to-br from-[#FAF7F2] via-[#F4EFE6] to-[#E9E7E2]">
          
          {/* Decorative Abstract Background Elements */}
          <div className="absolute inset-0 bg-pattern z-0" />
          <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#D9C6C6] rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
          <div className="absolute bottom-10 -right-20 w-[30rem] h-[30rem] bg-[#AFC3B1] rounded-full mix-blend-multiply filter blur-[100px] opacity-20" />

          {/* Top: Logo */}
          <div className="relative z-10 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm border border-[#E9E7E2]">
              {/* Lotus-inspired icon */}
              <svg className="w-6 h-6 text-[#D4B88A]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z" fill="currentColor" fillOpacity="0.1"/>
                <path d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z" fill="currentColor" fillOpacity="0.1"/>
                <path d="M4 16C4 16 1 12 5 8C6.5 11 9.5 13 12 14" strokeLinecap="round"/>
                <path d="M20 16C20 16 23 12 19 8C17.5 11 14.5 13 12 14" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="font-serif text-xl font-semibold text-[#2F2F2F] tracking-wide">Kaori</span>
          </div>

          {/* Center: Copy */}
          <div className="relative z-10 flex flex-col max-w-lg mb-20 animate-fade-in">
            <h1 className="font-serif text-5xl leading-[1.15] text-[#2F2F2F] font-medium mb-6">
              {t('templates01KaoriLogin.heroTitleLine1')}<br/>
              <span className="text-[#8C8173] italic">{t('templates01KaoriLogin.heroTitleLine2')}</span>
            </h1>
            <p className="text-[#8C8173] text-lg leading-relaxed">
              {t('templates01KaoriLogin.heroDesc')}
            </p>
          </div>
          
          {/* Bottom: Subtle Footer */}
          <div className="relative z-10 flex items-center gap-4 text-sm text-[#8C8173]">
            <span>{t('templates01KaoriLogin.copyright')}</span>
            <span className="w-1 h-1 rounded-full bg-[#D4B88A]" />
            <a href="#" className="hover:text-[#2F2F2F] transition-colors">{t('templates01KaoriLogin.privacyPolicy')}</a>
          </div>
        </div>

        {/* RIGHT SIDE: Login Panel */}
        <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center p-6 sm:p-12">
          {/* Mobile Logo (hidden on large screens) */}
          <div className="absolute top-8 left-8 flex items-center gap-2 lg:hidden">
             <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white shadow-sm border border-[#E9E7E2]">
              <svg className="w-5 h-5 text-[#D4B88A]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z" fill="currentColor" fillOpacity="0.1"/>
                <path d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z" fill="currentColor" fillOpacity="0.1"/>
              </svg>
            </div>
            <span className="font-serif text-lg font-medium text-[#2F2F2F]">Kaori</span>
          </div>

          {/* Login Card */}
          <div className="w-full max-w-[420px] rounded-2xl bg-white p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-[#E9E7E2]/50 animate-fade-in backdrop-blur-sm">
            
            <div className="flex flex-col space-y-2 mb-8">
              <h2 className="font-serif text-3xl font-semibold tracking-tight text-[#2F2F2F]">
                {t('templates01KaoriLogin.welcomeBack')}
              </h2>
              <p className="text-sm text-[#8C8173]">
                {t('templates01KaoriLogin.signInSubtitle')}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              
              {/* Error Message */}
              {error && (
                <div className="rounded-xl bg-[#D9C6C6]/20 p-3 text-sm text-red-800 border border-[#D9C6C6]/30 animate-fade-in">
                  {error}
                </div>
              )}

              {/* Email Field */}
              <div className="space-y-2">
                <Label htmlFor="email">{t('templates01KaoriLogin.emailLabel')}</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.com"
                  value={formData.email}
                  onChange={(e: any) => setFormData({ ...formData, email: e.target.value })}
                  required
                  disabled={isLoading}
                />
              </div>

              {/* Password Field */}
              <div className="space-y-2">
                <Label htmlFor="password">{t('templates01KaoriLogin.passwordLabel')}</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={(e: any) => setFormData({ ...formData, password: e.target.value })}
                    required
                    disabled={isLoading}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={isLoading}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8C8173] hover:text-[#2F2F2F] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#D4B88A] rounded-md p-1"
                    aria-label={showPassword ? t('templates01KaoriLogin.hidePassword') : t('templates01KaoriLogin.showPassword')}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Inline Row */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="remember"
                    checked={formData.remember}
                    onChange={(e: any) => setFormData({ ...formData, remember: e.target.checked })}
                    className="h-4 w-4 rounded-md border-[#E9E7E2] text-[#D4B88A] focus:ring-[#D4B88A] accent-[#D4B88A] transition-colors cursor-pointer"
                  />
                  <Label htmlFor="remember" className="text-sm font-normal text-[#8C8173] cursor-pointer">
                    {t('templates01KaoriLogin.rememberMe')}
                  </Label>
                </div>
                <a
                  href="#forgot-password"
                  className="text-sm font-medium text-[#2F2F2F] hover:text-[#D4B88A] transition-colors"
                >
                  {t('templates01KaoriLogin.forgotPassword')}
                </a>
              </div>

              {/* Primary Button */}
              <Button type="submit" className="w-full mt-2" isLoading={isLoading}>
                {t('templates01KaoriLogin.signInButton')}
              </Button>

              {/* Divider */}
              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-[#E9E7E2]"></div>
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white px-2 text-[#8C8173]">
                    {t('templates01KaoriLogin.orContinueWith')}
                  </span>
                </div>
              </div>

              {/* Social Login */}
              <Button 
                type="button" 
                variant="outline" 
                className="w-full" 
                disabled={isLoading}
                onClick={() => {}}
              >
                <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    fill="#EA4335"
                  />
                </svg>
                Google
              </Button>
            </form>

          </div>
          
          {/* Footer */}
          <div className="mt-8 text-center text-sm text-[#8C8173] animate-fade-in">
            {t('templates01KaoriLogin.noAccount')}{' '}
            <a href="#request-access" className="font-medium text-[#2F2F2F] hover:text-[#D4B88A] transition-colors underline-offset-4 hover:underline">
              {t('templates01KaoriLogin.requestAccess')}
            </a>
          </div>

        </div>
      </div>
    </>
  );
}
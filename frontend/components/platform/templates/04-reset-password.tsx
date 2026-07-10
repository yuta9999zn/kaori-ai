// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 4Kaori Reset Password.jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState, useEffect } from 'react';
import { Loader2, ArrowLeft, Eye, EyeOff, CheckCircle2, AlertCircle, Check } from 'lucide-react';
import { useT } from '@/lib/i18n/provider';

// --- STYLES & FONTS ---
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
      --accent-sage: #AFC3B1;
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

// --- UI COMPONENTS ---

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
    ghost: "bg-transparent text-[#8C8173] hover:text-[#2F2F2F] hover:bg-[#FAF7F2] active:scale-[0.98]",
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

export default function KaoriResetPassword() {
  const t = useT();
  const [tokenState, setTokenState] = useState('validating'); // 'validating' | 'valid' | 'invalid'
  const [formState, setFormState] = useState('idle'); // 'idle' | 'loading' | 'success' | 'error'
  
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Password validation rules
  const rules = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    number: /[0-9]/.test(password),
  };
  
  const isPasswordValid = rules.length && rules.uppercase && rules.number;
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;
  const canSubmit = isPasswordValid && passwordsMatch;

  // Token Validation on Mount
  useEffect(() => {
    const validateToken = async () => {
      // Simulate API verification delay
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // In a real app, you would extract the token:
      // const params = new URLSearchParams(window.location.search);
      // const token = params.get('token');
      
      // We'll mock a valid token for the demo.
      // Set to 'invalid' to test the expired state.
      setTokenState('valid');
    };

    validateToken();
  }, []);

  // Auto-redirect on success
  useEffect(() => {
    let timeoutId;
    if (formState === 'success') {
      timeoutId = setTimeout(() => {
        window.location.href = '#login';
      }, 3000);
    }
    return () => clearTimeout(timeoutId);
  }, [formState]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;

    setFormState('loading');

    // Simulate API request delay
    await new Promise((resolve) => setTimeout(resolve, 1200));

    // Success State
    setFormState('success');
  };

  return (
    <>
      <GlobalStyles />
      <div className="min-h-screen w-full flex bg-[#FAF7F2] overflow-hidden selection:bg-[#D4B88A]/30">
        
        {/* LEFT SIDE: Brand Panel (Consistent with Auth Flow) */}
        <div className="relative hidden lg:flex w-1/2 flex-col justify-between p-12 overflow-hidden bg-gradient-to-br from-[#FAF7F2] via-[#F4EFE6] to-[#E9E7E2]">
          
          <div className="absolute inset-0 bg-pattern z-0" />
          <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#D9C6C6] rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
          <div className="absolute bottom-10 -right-20 w-[30rem] h-[30rem] bg-[#AFC3B1] rounded-full mix-blend-multiply filter blur-[100px] opacity-20" />

          {/* Logo */}
          <div className="relative z-10 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm border border-[#E9E7E2]">
              <svg className="w-6 h-6 text-[#D4B88A]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z" fill="currentColor" fillOpacity="0.1"/>
                <path d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z" fill="currentColor" fillOpacity="0.1"/>
                <path d="M4 16C4 16 1 12 5 8C6.5 11 9.5 13 12 14" strokeLinecap="round"/>
                <path d="M20 16C20 16 23 12 19 8C17.5 11 14.5 13 12 14" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="font-serif text-xl font-semibold text-[#2F2F2F] tracking-wide">Kaori</span>
          </div>

          {/* Copy */}
          <div className="relative z-10 flex flex-col max-w-lg mb-20 animate-fade-in">
            <h1 className="font-serif text-5xl leading-[1.15] text-[#2F2F2F] font-medium mb-6">
              {t('templates04ResetPassword.heroTitleLine1')}<br/>
              <span className="text-[#8C8173] italic">{t('templates04ResetPassword.heroTitleLine2')}</span>
            </h1>
            <p className="text-[#8C8173] text-lg leading-relaxed">
              {t('templates04ResetPassword.heroBody')}
            </p>
          </div>

          {/* Footer */}
          <div className="relative z-10 flex items-center gap-4 text-sm text-[#8C8173]">
            <span>{t('templates04ResetPassword.footerCopyright')}</span>
            <span className="w-1 h-1 rounded-full bg-[#D4B88A]" />
            <a href="#" className="hover:text-[#2F2F2F] transition-colors">{t('templates04ResetPassword.privacyPolicy')}</a>
          </div>
        </div>

        {/* RIGHT SIDE: Reset Password Panel */}
        <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center p-6 sm:p-12">
          
          {/* Mobile Logo */}
          <div className="absolute top-8 left-8 flex items-center gap-2 lg:hidden">
             <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white shadow-sm border border-[#E9E7E2]">
              <svg className="w-5 h-5 text-[#D4B88A]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z" fill="currentColor" fillOpacity="0.1"/>
                <path d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z" fill="currentColor" fillOpacity="0.1"/>
              </svg>
            </div>
            <span className="font-serif text-lg font-medium text-[#2F2F2F]">Kaori</span>
          </div>

          {/* Form Card */}
          <div className="w-full max-w-[420px] rounded-2xl bg-white p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-[#E9E7E2]/50 backdrop-blur-sm relative overflow-hidden min-h-[460px] flex flex-col justify-center">
            
            {/* TOKEN VALIDATING STATE */}
            {tokenState === 'validating' && (
              <div className="animate-fade-in flex flex-col items-center justify-center h-full text-center space-y-4">
                <Loader2 className="w-8 h-8 text-[#D4B88A] animate-spin" />
                <p className="text-sm text-[#8C8173] font-medium">{t('templates04ResetPassword.validatingLink')}</p>
              </div>
            )}

            {/* TOKEN INVALID / EXPIRED STATE */}
            {tokenState === 'invalid' && (
              <div className="animate-fade-in w-full h-full flex flex-col justify-center text-center">
                <div className="flex justify-center mb-6">
                  <div className="w-16 h-16 rounded-2xl bg-[#F5F3F0] flex items-center justify-center">
                    <AlertCircle className="w-8 h-8 text-[#8C8173]" />
                  </div>
                </div>
                
                <h2 className="font-serif text-2xl font-semibold tracking-tight text-[#2F2F2F] mb-3">
                  {t('templates04ResetPassword.linkExpiredTitle')}
                </h2>

                <p className="text-sm text-[#8C8173] leading-relaxed mb-8">
                  {t('templates04ResetPassword.linkExpiredBody')}
                </p>

                <Button
                  onClick={() => window.location.href = '#forgot-password'}
                  className="w-full"
                >
                  {t('templates04ResetPassword.requestNewLink')}
                </Button>
              </div>
            )}

            {/* VALID TOKEN: SHOW FORM */}
            {tokenState === 'valid' && formState !== 'success' && (
              <div className="animate-fade-in w-full h-full flex flex-col justify-center">
                <div className="flex flex-col space-y-2 mb-8">
                  <h2 className="font-serif text-3xl font-semibold tracking-tight text-[#2F2F2F]">
                    {t('templates04ResetPassword.formTitle')}
                  </h2>
                  <p className="text-sm text-[#8C8173] leading-relaxed">
                    {t('templates04ResetPassword.formSubtitle')}
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">

                  {/* Password Field */}
                  <div className="space-y-2">
                    <Label htmlFor="password">{t('templates04ResetPassword.newPasswordLabel')}</Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showPassword ? "text" : "password"}
                        placeholder={t('templates04ResetPassword.newPasswordPlaceholder')}
                        value={password}
                        onChange={(e: any) => setPassword(e.target.value)}
                        required
                        disabled={formState === 'loading'}
                        className="pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        disabled={formState === 'loading'}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8C8173] hover:text-[#2F2F2F] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#D4B88A] rounded-md p-1"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Password Rules Helper */}
                  <div className="bg-[#FAF7F2] rounded-xl p-4 space-y-2.5 border border-[#E9E7E2]/60">
                    <div className="flex items-center gap-2 text-sm">
                      {rules.length ? <Check className="w-3.5 h-3.5 text-[#AFC3B1]" /> : <div className="w-1.5 h-1.5 rounded-full bg-[#D9C6C6] ml-1" />}
                      <span className={rules.length ? "text-[#2F2F2F]" : "text-[#8C8173]"}>{t('templates04ResetPassword.ruleLength')}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      {rules.uppercase ? <Check className="w-3.5 h-3.5 text-[#AFC3B1]" /> : <div className="w-1.5 h-1.5 rounded-full bg-[#D9C6C6] ml-1" />}
                      <span className={rules.uppercase ? "text-[#2F2F2F]" : "text-[#8C8173]"}>{t('templates04ResetPassword.ruleUppercase')}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      {rules.number ? <Check className="w-3.5 h-3.5 text-[#AFC3B1]" /> : <div className="w-1.5 h-1.5 rounded-full bg-[#D9C6C6] ml-1" />}
                      <span className={rules.number ? "text-[#2F2F2F]" : "text-[#8C8173]"}>{t('templates04ResetPassword.ruleNumber')}</span>
                    </div>
                  </div>

                  {/* Confirm Password Field */}
                  <div className="space-y-2">
                    <Label htmlFor="confirmPassword">{t('templates04ResetPassword.confirmPasswordLabel')}</Label>
                    <div className="relative">
                      <Input
                        id="confirmPassword"
                        type={showConfirmPassword ? "text" : "password"}
                        placeholder={t('templates04ResetPassword.confirmPasswordPlaceholder')}
                        value={confirmPassword}
                        onChange={(e: any) => setConfirmPassword(e.target.value)}
                        required
                        disabled={formState === 'loading'}
                        className={`pr-10 ${confirmPassword && !passwordsMatch ? 'border-red-300 focus-visible:ring-red-400' : ''}`}
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        disabled={formState === 'loading'}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8C8173] hover:text-[#2F2F2F] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#D4B88A] rounded-md p-1"
                      >
                        {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {confirmPassword && !passwordsMatch && (
                      <p className="text-xs text-red-600 mt-1.5 font-medium animate-fade-in">{t('templates04ResetPassword.passwordsDoNotMatch')}</p>
                    )}
                  </div>

                  {formState === 'error' && (
                    <div className="text-sm text-red-600 font-medium">
                      {t('templates04ResetPassword.genericError')}
                    </div>
                  )}

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={!canSubmit}
                    isLoading={formState === 'loading'}
                  >
                    {t('templates04ResetPassword.resetPasswordButton')}
                  </Button>
                </form>
              </div>
            )}

            {/* FORM SUCCESS STATE */}
            {formState === 'success' && (
              <div className="animate-fade-in w-full h-full flex flex-col justify-center text-center">
                <div className="flex justify-center mb-6">
                  <div className="w-16 h-16 rounded-2xl bg-[#AFC3B1]/10 flex items-center justify-center">
                    <CheckCircle2 className="w-8 h-8 text-[#AFC3B1]" />
                  </div>
                </div>
                
                <h2 className="font-serif text-2xl font-semibold tracking-tight text-[#2F2F2F] mb-3">
                  {t('templates04ResetPassword.successTitle')}
                </h2>

                <p className="text-sm text-[#8C8173] leading-relaxed mb-8">
                  {t('templates04ResetPassword.successBody')}
                </p>

                <Button
                  onClick={() => window.location.href = '#login'}
                  className="w-full"
                >
                  {t('templates04ResetPassword.backToLogin')}
                </Button>
              </div>
            )}
            
          </div>
          
          {/* Footer Navigation (Hidden during validation or success) */}
          {(tokenState === 'invalid' || (tokenState === 'valid' && formState !== 'success')) && (
             <div className="mt-8 animate-fade-in">
              <a 
                href="#login" 
                className="inline-flex items-center text-sm font-medium text-[#8C8173] hover:text-[#2F2F2F] transition-colors group"
              >
                <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
                {t('templates04ResetPassword.backToLogin')}
              </a>
            </div>
          )}

        </div>
      </div>
    </>
  );
}
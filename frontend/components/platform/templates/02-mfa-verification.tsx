// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// Auto-converted from 2Kaori MFA Verification.jsx by convert_jsx_to_tsx.py.
// Source-of-truth is the .jsx file in `platform tenant/`. Edit there + re-run
// the script to regenerate. Lazy `any` types added; not meant for strict tsc.

import React, { useState, useEffect, useRef } from 'react';
import { Loader2, ArrowLeft, ShieldCheck } from 'lucide-react';
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

    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      20%, 60% { transform: translateX(-4px); }
      40%, 80% { transform: translateX(4px); }
    }

    .animate-shake {
      animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both;
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

// --- MAIN PAGE COMPONENT ---

export default function KaoriMFA() {
  const t = useT();
  const [code, setCode] = useState(Array(6).fill(''));
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [countdown, setCountdown] = useState(30);
  
  const inputRefs = useRef<any[]>([]);

  // Timer logic
  useEffect(() => {
    if (countdown > 0) {
      const timerId = setInterval(() => setCountdown((prev) => prev - 1), 1000);
      return () => clearInterval(timerId);
    }
  }, [countdown]);

  // Auto-submit when all 6 digits are filled
  useEffect(() => {
    const isComplete = code.every((digit) => digit !== '');
    if (isComplete && !isLoading && !error) {
      handleVerify(new Event('submit'));
    }
  }, [code]);

  const handleVerify = async (e) => {
    e?.preventDefault();
    const fullCode = code.join('');
    
    if (fullCode.length !== 6) return;
    
    setIsLoading(true);
    setError('');

    // Simulate API verification
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Mock validation logic (fails if code is not 000000)
    if (fullCode !== '000000') {
      setError(t('templates02MfaVerification.errInvalidCode'));
      setCode(Array(6).fill(''));
      inputRefs.current[0]?.focus();
      setIsLoading(false);
      return;
    }

    // Success redirect
    window.location.href = '#platform';
  };

  // OTP Input Handlers
  const handleKeyDown = (e: any, index: number) => {
    if (e.key === 'Backspace') {
      if (!code[index] && index > 0) {
        // If current is empty, delete previous and focus it
        const newCode = [...code];
        newCode[index - 1] = '';
        setCode(newCode);
        inputRefs.current[index - 1]?.focus();
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowRight' && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleChange = (e: any, index: number) => {
    const value = e.target.value;
    
    // Only allow numeric input
    if (!/^\d*$/.test(value)) return;

    const newCode = [...code];
    
    // Handle pasting multiple digits into a single field
    if (value.length > 1) {
      const pastedCode = value.slice(0, 6).split('');
      for (let i = 0; i < pastedCode.length; i++) {
        if (index + i < 6) {
          newCode[index + i] = pastedCode[i];
        }
      }
      setCode(newCode);
      
      // Focus the next empty input or the last one
      const nextIndex = Math.min(index + pastedCode.length, 5);
      inputRefs.current[nextIndex]?.focus();
      return;
    }

    // Standard single character input
    newCode[index] = value;
    setCode(newCode);

    // Auto-advance to next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
    
    // Clear error on new input
    if (error) setError('');
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pastedData) return;

    const newCode = [...code];
    for (let i = 0; i < pastedData.length; i++) {
      newCode[i] = pastedData[i];
    }
    setCode(newCode);
    
    // Focus last filled input
    inputRefs.current[Math.min(pastedData.length, 5)]?.focus();
    if (error) setError('');
  };

  const handleResend = () => {
    setCountdown(30);
    setError('');
    // Trigger API resend logic here
  };

  return (
    <>
      <GlobalStyles />
      <div className="min-h-screen w-full flex bg-[#FAF7F2] overflow-hidden selection:bg-[#D4B88A]/30">
        
        {/* LEFT SIDE: Brand Panel (Maintained from Login for consistency) */}
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
              {t('templates02MfaVerification.headlineLine1')}<br/>
              <span className="text-[#8C8173] italic">{t('templates02MfaVerification.headlineLine2')}</span>
            </h1>
            <p className="text-[#8C8173] text-lg leading-relaxed">
              {t('templates02MfaVerification.heroDesc')}
            </p>
          </div>
          
          {/* Footer */}
          <div className="relative z-10 flex items-center gap-4 text-sm text-[#8C8173]">
            <span>{t('templates02MfaVerification.footerCopyright')}</span>
            <span className="w-1 h-1 rounded-full bg-[#D4B88A]" />
            <a href="#" className="hover:text-[#2F2F2F] transition-colors">{t('templates02MfaVerification.privacyPolicy')}</a>
          </div>
        </div>

        {/* RIGHT SIDE: MFA Panel */}
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

          {/* MFA Card */}
          <div className={`w-full max-w-[420px] rounded-2xl bg-white p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-[#E9E7E2]/50 backdrop-blur-sm transition-all duration-300 ${error ? 'animate-shake border-red-200' : 'animate-fade-in'}`}>
            
            <div className="flex flex-col space-y-3 mb-8">
              <div className="w-12 h-12 rounded-xl bg-[#FAF7F2] border border-[#E9E7E2] flex items-center justify-center mb-2">
                <ShieldCheck className="w-6 h-6 text-[#D4B88A]" />
              </div>
              <h2 className="font-serif text-3xl font-semibold tracking-tight text-[#2F2F2F]">
                {t('templates02MfaVerification.title')}
              </h2>
              <p className="text-sm text-[#8C8173] leading-relaxed">
                {t('templates02MfaVerification.descPrefix')} <span className="font-medium text-[#2F2F2F]">a***@company.com</span>.
              </p>
            </div>

            <form onSubmit={handleVerify} className="space-y-6">
              
              {/* OTP Inputs */}
              <div className="flex justify-between items-center gap-2">
                {code.map((digit: any, index: number) => (
                  <input
                    key={index}
                    ref={(el: any) => (inputRefs.current[index] = el)}
                    type="text"
                    inputMode="numeric"
                    pattern="\d*"
                    maxLength={6}
                    value={digit}
                    onChange={(e: any) => handleChange(e, index)}
                    onKeyDown={(e: any) => handleKeyDown(e, index)}
                    onPaste={handlePaste}
                    disabled={isLoading}
                    className={`
                      w-12 h-14 sm:w-14 sm:h-16 text-center text-2xl font-medium rounded-xl border bg-white
                      transition-all duration-200 outline-none
                      focus:scale-105 focus:-translate-y-1 focus:shadow-sm
                      disabled:opacity-50 disabled:cursor-not-allowed
                      ${error 
                        ? 'border-red-300 text-red-700 bg-red-50/50 focus:border-red-400 focus:ring-2 focus:ring-red-400/20' 
                        : 'border-[#E9E7E2] text-[#2F2F2F] focus:border-[#D4B88A] focus:ring-2 focus:ring-[#D4B88A]/40'
                      }
                    `}
                    aria-label={t('templates02MfaVerification.digitAriaLabel', { n: index + 1 })}
                  />
                ))}
              </div>

              {/* Status / Error Message */}
              <div className="h-5 flex items-center justify-center text-sm transition-opacity">
                {error ? (
                  <span className="text-red-600 font-medium">{error}</span>
                ) : countdown > 0 ? (
                  <span className="text-[#8C8173]">
                    {t('templates02MfaVerification.refreshPrefix')} <span className="font-medium tabular-nums text-[#2F2F2F]">00:{countdown.toString().padStart(2, '0')}</span>
                  </span>
                ) : (
                  <span className="text-[#8C8173]">{t('templates02MfaVerification.codeExpired')}</span>
                )}
              </div>

              {/* Primary Button */}
              <Button 
                type="submit" 
                className="w-full" 
                isLoading={isLoading}
                disabled={code.some(d => !d)} // Disabled if not fully filled manually
              >
                {t('templates02MfaVerification.verify')}
              </Button>

              {/* Secondary Actions */}
              <div className="flex flex-col space-y-3 pt-4 text-center text-sm border-t border-[#E9E7E2]">
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={countdown > 0 || isLoading}
                  className="font-medium text-[#2F2F2F] hover:text-[#D4B88A] disabled:text-[#8C8173]/50 disabled:cursor-not-allowed transition-colors"
                >
                  {t('templates02MfaVerification.resendCode')}
                </button>
                <a
                  href="#backup-code"
                  className="font-medium text-[#8C8173] hover:text-[#2F2F2F] transition-colors"
                >
                  {t('templates02MfaVerification.useBackupCode')}
                </a>
              </div>
            </form>
          </div>
          
          {/* Footer Navigation */}
          <div className="mt-8 animate-fade-in">
            <a 
              href="#login" 
              className="inline-flex items-center text-sm font-medium text-[#8C8173] hover:text-[#2F2F2F] transition-colors group"
            >
              <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
              {t('templates02MfaVerification.backToLogin')}
            </a>
          </div>

        </div>
      </div>
    </>
  );
}
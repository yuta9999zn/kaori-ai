"use client";

/**
 * Legacy redirect — the Sprint 7 onboarding URL was renamed to /register
 * after pilot feedback that customers looked for "Đăng ký" rather than
 * "Kích hoạt". Kept as a thin shim so any sales email or bookmark with the
 * old URL still lands the user in the right place.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function OnboardingRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/register"); }, [router]);
  return null;
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuthHydrated, useAuthStore } from "@/store/auth";

// Redirects to /login once auth state has hydrated and there's no token.
// `ready` stays false during hydration and after a redirect has been fired,
// so pages should render nothing (or a loading state) until it's true.
export function useRequireAuth() {
  const router = useRouter();
  const hydrated = useAuthHydrated();
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (hydrated && !token) {
      router.replace("/login");
    }
  }, [hydrated, token, router]);

  return { ready: hydrated && !!token };
}

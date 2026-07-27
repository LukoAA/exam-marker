import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  id: number;
  email: string;
  name: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  setToken: (token: string | null) => void;
  setUser: (user: AuthUser | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setToken: (token) => set({ token }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: "exam-marker-auth" }
  )
);

// zustand's `persist` rehydrates from localStorage asynchronously, so on the
// first client render `token`/`user` are still null even for a logged-in
// user. Consumers that redirect on missing auth must wait for this to flip
// true before treating a null token as "logged out".
//
// `useAuthStore.persist` itself is only defined when `window` exists at store
// creation time. Next.js server-renders client-component pages once on the
// server (no `window`), so on that pass persist is skipped entirely and this
// property is undefined — treat that as "hydrated" since there's no
// localStorage to wait for there anyway; the real client bundle re-checks
// after mount.
export function useAuthHydrated() {
  const [hydrated, setHydrated] = useState(
    () => useAuthStore.persist?.hasHydrated() ?? true
  );

  useEffect(() => {
    const persistApi = useAuthStore.persist;
    if (!persistApi || persistApi.hasHydrated()) {
      setHydrated(true);
      return;
    }
    return persistApi.onFinishHydration(() => setHydrated(true));
  }, []);

  return hydrated;
}

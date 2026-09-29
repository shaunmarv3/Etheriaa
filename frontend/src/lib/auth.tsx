'use client';

/**
 * Etheria auth client (spec 9, 13.1). Replaces Clerk.
 *
 * - The access token (15 min JWT) lives in module memory only, never in localStorage.
 * - The refresh token is an httpOnly cookie scoped to /auth on the API origin; the
 *   browser sends it, this code never sees it.
 * - Refresh is single-flight: the backend rotates the refresh token on every call and
 *   treats a second use of the same cookie as theft (revoking the session), so
 *   concurrent 401s and React StrictMode's double effects share one in-flight
 *   /auth/refresh. (Two browser tabs refreshing in the same instant can still race;
 *   the loser is signed out.)
 * - The hooks keep the Clerk surface the pages already use (useAuth, useUser,
 *   useClerk, useSession), so pages changed their import path, not their logic.
 */

import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const EXPIRY_MARGIN_MS = 30_000;

export interface AuthUser {
  id: string;
  email: string;
  displayName: string | null;
}

type Status = 'loading' | 'signedIn' | 'signedOut';

interface Snapshot {
  status: Status;
  user: AuthUser | null;
}

interface TokenOut {
  access_token: string;
  expires_in: number;
  user: { id: string; email: string; display_name: string | null };
}

export class AuthError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number
  ) {
    super(message);
  }
}

// ── Module store ─────────────────────────────────────────────────────────────

let snapshot: Snapshot = { status: 'loading', user: null };
let accessToken: string | null = null;
let expiresAt = 0;
let refreshing: Promise<string | null> | null = null;
const listeners = new Set<() => void>();

function setSnapshot(next: Snapshot) {
  snapshot = next;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const SERVER_SNAPSHOT: Snapshot = { status: 'loading', user: null };

function accept(body: TokenOut) {
  accessToken = body.access_token;
  expiresAt = Date.now() + body.expires_in * 1000;
  setSnapshot({
    status: 'signedIn',
    user: { id: body.user.id, email: body.user.email, displayName: body.user.display_name },
  });
}

/** Forget the session locally (after logout, a failed refresh or account erasure). */
export function clearSession() {
  accessToken = null;
  expiresAt = 0;
  setSnapshot({ status: 'signedOut', user: null });
}

async function readError(res: Response): Promise<AuthError> {
  try {
    const body = await res.json();
    const err = body?.error;
    if (err?.message) return new AuthError(err.message, err.code ?? 'error', res.status);
    // FastAPI validation errors (422) carry a `detail` list.
    if (Array.isArray(body?.detail)) {
      const first = body.detail[0];
      return new AuthError(first?.msg ?? 'Invalid input', 'validation_error', res.status);
    }
  } catch {
    // fall through
  }
  return new AuthError(`Request failed (${res.status})`, 'error', res.status);
}

async function authPost(path: string, body?: unknown): Promise<Response> {
  return fetch(`${API}/auth/${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      // Required by the backend's CSRF guard on the cookie endpoints (spec 9).
      'X-Requested-With': 'fetch',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// ── Token access (used by api.ts outside React) ──────────────────────────────

/**
 * Exchange the refresh cookie for a new access token. Single-flight: every caller
 * during one refresh gets the same promise. Resolves to null when signed out.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await authPost('refresh');
        if (!res.ok) {
          clearSession();
          return null;
        }
        accept(await res.json());
        return accessToken;
      } catch {
        clearSession();
        return null;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

/** A valid access token, refreshed first when it is about to expire. */
export async function getAccessToken(): Promise<string | null> {
  if (accessToken && Date.now() < expiresAt - EXPIRY_MARGIN_MS) return accessToken;
  if (snapshot.status === 'signedOut') return null;
  return refreshAccessToken();
}

// ── Actions ──────────────────────────────────────────────────────────────────

export async function signIn(email: string, password: string): Promise<void> {
  const res = await authPost('login', { email, password });
  if (!res.ok) throw await readError(res);
  accept(await res.json());
}

export async function signUp(email: string, password: string, displayName?: string): Promise<void> {
  const res = await authPost('register', {
    email,
    password,
    ...(displayName ? { display_name: displayName } : {}),
  });
  if (!res.ok) throw await readError(res);
  accept(await res.json());
}

export async function signOut(opts?: { redirectUrl?: string }): Promise<void> {
  try {
    await authPost('logout');
  } catch {
    // The local session is cleared either way.
  }
  clearSession();
  if (opts?.redirectUrl && typeof window !== 'undefined') {
    window.location.href = opts.redirectUrl;
  }
}

// ── Provider and hooks ───────────────────────────────────────────────────────

/** Restores the session from the refresh cookie on load. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (snapshot.status === 'loading') void refreshAccessToken();
  }, []);
  return <>{children}</>;
}

function useSnapshot(): Snapshot {
  return useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => SERVER_SNAPSHOT
  );
}

export function useAuth() {
  const { status, user } = useSnapshot();
  const getToken = useCallback(() => getAccessToken(), []);
  return {
    isLoaded: status !== 'loading',
    isSignedIn: status === 'signedIn',
    userId: user?.id ?? null,
    getToken,
  };
}

export function useUser() {
  const { status, user } = useSnapshot();
  const clerkLike = useMemo(
    () =>
      user && {
        id: user.id,
        firstName: user.displayName,
        emailAddresses: [{ emailAddress: user.email }],
      },
    [user]
  );
  return { isLoaded: status !== 'loading', isSignedIn: status === 'signedIn', user: clerkLike };
}

export function useClerk() {
  return { signOut };
}

export function useSession() {
  const { status } = useSnapshot();
  const session = useMemo(
    () => (status === 'signedIn' ? { getToken: () => getAccessToken() } : null),
    [status]
  );
  return { session, isLoaded: status !== 'loading' };
}

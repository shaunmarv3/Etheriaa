import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { clearSession, getAccessToken, refreshAccessToken } from './auth';
import type { ChatRequest, TriageLevel, Symptom, DifferentialDiagnosis, Citation } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Axios instance for the Etheria backend.
 * - Attaches the in-memory access token (src/lib/auth.tsx).
 * - On a 401, refreshes once (single-flight) and retries; if that fails, the user is
 *   signed out and sent to /sign-in.
 */
export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(async (config) => {
  const token = await getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    if (error.response?.status === 401 && config && !config._retried) {
      config._retried = true;
      const token = await refreshAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
        return api.request(config);
      }
      clearSession();
      if (typeof window !== 'undefined') window.location.href = '/sign-in';
    }
    return Promise.reject(error);
  }
);

/** The backend's error shape is {"error": {"code", "message", "request_id"}}. */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { error?: { message?: string } } | undefined;
    return data?.error?.message ?? err.message ?? fallback;
  }
  return err instanceof Error ? err.message : fallback;
}

// ── Streaming Chat ─────────────────────────────────────────────────────────

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onMetadata: (meta: {
    sessionId: string;
    triageLevel: TriageLevel;
    symptoms: Symptom[];
    followUpQuestions: string[];
    differential: DifferentialDiagnosis[];
    citations: Citation[];
    agent_trace?: import('./types').AgentTrace;
  }) => void;
  onStatus?: (message: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

async function postStream(body: Record<string, unknown>, token: string | null) {
  return fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
}

/**
 * Send a chat message via the SSE streaming endpoint.
 * Calls callbacks as events arrive from the backend.
 *
 * @param authToken - an access token from `useAuth().getToken()`; refreshed and
 *                    retried once if the backend answers 401.
 */
export async function streamChat(
  req: ChatRequest,
  callbacks: StreamCallbacks,
  authToken?: string | null
): Promise<void> {
  // Frontend camelCase → Backend snake_case
  const body: Record<string, unknown> = {
    message: req.message,
  };
  if (req.sessionId) body.session_id = req.sessionId;

  let response = await postStream(body, authToken ?? (await getAccessToken()));
  if (response.status === 401) {
    const token = await refreshAccessToken();
    if (!token) {
      callbacks.onError('Your session has expired, please sign in again');
      return;
    }
    response = await postStream(body, token);
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data?.error?.message) message = data.error.message;
    } catch {
      // keep the status line
    }
    callbacks.onError(message);
    return;
  }

  if (!response.body) {
    callbacks.onError('No response body for streaming');
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split('\n');
      // Keep the last potentially incomplete line in the buffer
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;

        const jsonStr = trimmed.slice(6); // strip "data: "
        try {
          const event = JSON.parse(jsonStr);

          if (event.type === 'token') {
            callbacks.onToken(event.content ?? '');
          } else if (event.type === 'status') {
            callbacks.onStatus?.(event.message ?? '');
          } else if (event.type === 'metadata') {
            callbacks.onMetadata({
              sessionId: event.session_id ?? '',
              triageLevel: (event.triage_level ?? 'GREEN') as TriageLevel,
              symptoms: (event.symptoms ?? []) as Symptom[],
              followUpQuestions: (event.follow_up_questions ?? []) as string[],
              differential: (event.differential ?? []) as DifferentialDiagnosis[],
              citations: (event.citations ?? []) as Citation[],
              agent_trace: event.agent_trace,
            });
          } else if (event.type === 'done') {
            callbacks.onDone();
          } else if (event.type === 'error') {
            callbacks.onError(event.detail ?? 'Unknown streaming error');
          }
        } catch {
          // Skip malformed JSON lines
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err.message : 'Stream read error');
  }
}

// ── Document APIs ─────────────────────────────────────────────────────────────

export interface DocumentInfo {
  documentId: string;
  filename: string;
  fileType: string;
  status: 'pending' | 'processing' | 'done' | 'failed';
  pageCount: number | null;
  uploadedAt: string;
  docType: string | null;
  summary: string | null;
  reportDate: string | null;
}

/**
 * Upload a document (PDF or image) to the backend.
 */
export async function uploadDocument(file: File): Promise<{
  documentId: string;
  filename: string;
  status: string;
  pageCount: number | null;
}> {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post('/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 minute timeout for large files
  });

  return {
    documentId: data.document_id,
    filename: data.filename,
    status: data.status,
    pageCount: data.page_count ?? null,
  };
}

/**
 * Fetch all documents for the current user.
 */
export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const { data } = await api.get('/upload/');

  return (data.documents ?? []).map((doc: Record<string, unknown>) => ({
    documentId: doc.document_id as string,
    filename: doc.filename as string,
    fileType: doc.file_type as string,
    status: doc.status as DocumentInfo['status'],
    pageCount: (doc.page_count as number) ?? null,
    uploadedAt: doc.uploaded_at as string,
    docType: (doc.doc_type as string) ?? null,
    summary: (doc.summary as string) ?? null,
    reportDate: (doc.report_date as string) ?? null,
  }));
}

/**
 * Delete a document by ID.
 */
export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/upload/${documentId}`);
}

/**
 * Download a document: an authenticated fetch into a blob, then a save (spec 13.3).
 * A plain link cannot carry the Bearer token.
 */
export async function downloadDocument(documentId: string, filename: string): Promise<void> {
  const { data } = await api.get(`/upload/${documentId}/download`, {
    responseType: 'blob',
    timeout: 120000,
  });
  const url = URL.createObjectURL(data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── History APIs ──────────────────────────────────────────────────────────────

export interface SessionSummary {
  sessionId: string;
  name: string | null;
  triageLevel: TriageLevel | null;
  startedAt: string;
  endedAt: string | null;
  messageCount: number;
  preview: string;
}

export interface SessionMessage {
  messageId: string;
  role: 'user' | 'assistant';
  content: string;
  intent: string | null;
  symptoms: Symptom[] | null;
  triageLevel: TriageLevel | null;
  citations: Citation[];
  differential: DifferentialDiagnosis[];
  timestamp: string;
  createdAt: string;
}

export interface SessionDetail {
  sessionId: string;
  name: string | null;
  triageLevel: TriageLevel | null;
  startedAt: string;
  endedAt: string | null;
  messageCount: number;
  messages: SessionMessage[];
}

/**
 * Fetch paginated session history.
 */
export async function fetchHistory(
  page: number = 1,
  pageSize: number = 10
): Promise<{
  total: number;
  page: number;
  pageSize: number;
  sessions: SessionSummary[];
}> {
  const { data } = await api.get('/history/', {
    params: { page, page_size: pageSize },
  });

  return {
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
    sessions: (data.sessions ?? []).map((s: Record<string, unknown>) => ({
      sessionId: s.session_id as string,
      name: (s.name as string) ?? null,
      triageLevel: (s.triage_level as TriageLevel) ?? null,
      startedAt: s.started_at as string,
      endedAt: (s.ended_at as string) ?? null,
      messageCount: s.message_count as number,
      preview: s.preview as string,
    })),
  };
}

/**
 * Fetch full session detail with all messages.
 */
export async function fetchSessionDetail(sessionId: string): Promise<SessionDetail> {
  const { data } = await api.get(`/history/${sessionId}`);

  return {
    sessionId: data.session_id,
    name: data.name ?? null,
    triageLevel: data.triage_level ?? null,
    startedAt: data.started_at,
    endedAt: data.ended_at ?? null,
    messageCount: data.message_count,
    messages: (data.messages ?? []).map((m: Record<string, unknown>) => ({
      messageId: m.message_id as string,
      role: m.role as 'user' | 'assistant',
      content: m.content as string,
      intent: (m.intent as string) ?? null,
      symptoms: (m.symptoms as Symptom[]) ?? null,
      triageLevel: (m.triage_level as TriageLevel) ?? null,
      citations: (m.citations as Citation[]) ?? [],
      differential: (m.differential as DifferentialDiagnosis[]) ?? [],
      timestamp: m.created_at as string,
      createdAt: m.created_at as string,
    })),
  };
}

/**
 * Delete a session by ID.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/history/${sessionId}`);
}

/**
 * Rename a session.
 */
export async function renameSession(sessionId: string, name: string): Promise<void> {
  await api.patch(`/history/${sessionId}`, { name });
}

/**
 * Regenerate the last assistant response for a session (not streamed).
 */
export async function regenerateResponse(sessionId: string) {
  const { data } = await api.post(
    '/chat/regenerate',
    { session_id: sessionId },
    { timeout: 120000 }
  );
  return {
    sessionId: data.session_id as string,
    messageId: data.message_id as string,
    reply: data.reply as string,
    triageLevel: data.triage_level as TriageLevel,
    symptoms: (data.symptoms ?? []) as Symptom[],
    followUpQuestions: (data.follow_up_questions ?? []) as string[],
    differential: (data.differential ?? []) as DifferentialDiagnosis[],
    citations: (data.citations ?? []) as Citation[],
  };
}

// ── Account ───────────────────────────────────────────────────────────────────

/**
 * Erase the account and everything in it (spec 7). The caller clears the session.
 */
export async function deleteAccount(): Promise<void> {
  await api.delete('/user');
}

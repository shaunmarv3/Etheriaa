import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { StateCreator } from 'zustand';
import type { Message, Document, TriageLevel } from './types.js';

// ─────────────────────────────────────────────
// Session Slice
// ─────────────────────────────────────────────
interface SessionSlice {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  clearSession: () => void;
}

// ─────────────────────────────────────────────
// UI State Slice  (loading + error feedback)
// ─────────────────────────────────────────────
interface UISlice {
  isLoading: boolean;
  error: string | null;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
}

// ─────────────────────────────────────────────
// UI Preferences Slice (theme, text size, draft, etc.)
// ─────────────────────────────────────────────
interface UIPrefsSlice {
  theme: 'light' | 'dark';
  textSize: 'sm' | 'md' | 'lg';
  sidebarOpen: boolean;
  disclaimerCollapsed: boolean;
  draftMessage: string;
  sessionNames: Record<string, string>;
  lastUserMessage: string | null;
  setTheme: (theme: 'light' | 'dark') => void;
  setTextSize: (size: 'sm' | 'md' | 'lg') => void;
  setSidebarOpen: (open: boolean) => void;
  setDisclaimerCollapsed: (collapsed: boolean) => void;
  setDraftMessage: (draft: string) => void;
  setSessionName: (sessionId: string, name: string) => void;
  setLastUserMessage: (msg: string | null) => void;
}

type StoreState = SessionSlice &
  MessagesSlice &
  TriageSlice &
  DocumentsSlice &
  UISlice &
  UIPrefsSlice;
type SetState = Parameters<StateCreator<StoreState>>[0];

const createSessionSlice = (set: SetState): SessionSlice => ({
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),
  clearSession: () => set({ sessionId: null }),
});

const createUIPrefsSlice = (set: SetState): UIPrefsSlice => ({
  theme: 'light',
  textSize: 'md',
  sidebarOpen: false,
  disclaimerCollapsed: false,
  draftMessage: '',
  sessionNames: {},
  lastUserMessage: null,
  setTheme: (theme) => set({ theme }),
  setTextSize: (size) => set({ textSize: size }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setDisclaimerCollapsed: (collapsed) => set({ disclaimerCollapsed: collapsed }),
  setDraftMessage: (draft) => set({ draftMessage: draft }),
  setSessionName: (sessionId, name) =>
    set((state: StoreState) => ({
      sessionNames: { ...state.sessionNames, [sessionId]: name },
    })),
  setLastUserMessage: (msg) => set({ lastUserMessage: msg }),
});

const createUISlice = (set: SetState): UISlice => ({
  isLoading: false,
  error: null,
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),
});

// ─────────────────────────────────────────────
// Messages Slice
// ─────────────────────────────────────────────
interface MessagesSlice {
  messages: Message[];
  isStreaming: boolean;
  addMessage: (message: Message) => void;
  updateLastAssistant: (patch: Partial<Message>) => void;
  clearMessages: () => void;
  setMessages: (messages: Message[]) => void;
  setStreaming: (streaming: boolean) => void;
  resetChat: () => void;
}

const createMessagesSlice = (set: SetState): MessagesSlice => ({
  messages: [],
  isStreaming: false,
  addMessage: (message) =>
    set((state: StoreState) => ({
      messages: [...state.messages, message],
    })),
  updateLastAssistant: (patch) =>
    set((state: StoreState) => {
      const msgs = [...state.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i] = { ...msgs[i], ...patch };
          break;
        }
      }
      return { messages: msgs };
    }),
  clearMessages: () => set({ messages: [] }),
  setMessages: (messages) => set({ messages }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  resetChat: () => set({ messages: [], isStreaming: false, sessionId: null }),
});

// ─────────────────────────────────────────────
// Triage Slice
// ─────────────────────────────────────────────
interface TriageSlice {
  triageLevel: TriageLevel | null;
  setTriageLevel: (level: TriageLevel) => void;
  clearTriage: () => void;
}

const createTriageSlice = (set: SetState): TriageSlice => ({
  triageLevel: null,
  setTriageLevel: (level) => set({ triageLevel: level }),
  clearTriage: () => set({ triageLevel: null }),
});

// ─────────────────────────────────────────────
// Documents Slice
// ─────────────────────────────────────────────
interface DocumentsSlice {
  documents: Document[];
  addDocument: (document: Document) => void;
  removeDocument: (documentId: string) => void;
  updateDocumentStatus: (documentId: string, status: Document['status']) => void;
  setDocuments: (documents: Document[]) => void;
  clearDocuments: () => void;
}

const createDocumentsSlice = (set: SetState): DocumentsSlice => ({
  documents: [],
  addDocument: (document) =>
    set((state: StoreState) => ({
      documents: [...state.documents, document],
    })),
  removeDocument: (documentId) =>
    set((state: StoreState) => ({
      documents: state.documents.filter((doc: Document) => doc.id !== documentId),
    })),
  updateDocumentStatus: (documentId, status) =>
    set((state: StoreState) => ({
      documents: state.documents.map((doc: Document) =>
        doc.id === documentId ? { ...doc, status } : doc
      ),
    })),
  setDocuments: (documents) => set({ documents }),
  clearDocuments: () => set({ documents: [] }),
});

// ─────────────────────────────────────────────
// Combined Store
// ─────────────────────────────────────────────

export const useStore = create<StoreState>()(
  devtools(
    persist(
      (set) => ({
        ...createSessionSlice(set),
        ...createMessagesSlice(set),
        ...createTriageSlice(set),
        ...createDocumentsSlice(set),
        ...createUISlice(set),
        ...createUIPrefsSlice(set),
      }),
      {
        name: 'etheria-storage',
        // UI preferences only: nothing user-scoped (session ids, documents) is kept
        // in localStorage, where it would outlive sign-out and reach the next user.
        partialize: (state) => ({
          theme: state.theme,
          textSize: state.textSize,
          disclaimerCollapsed: state.disclaimerCollapsed,
        }),
      }
    )
  )
);

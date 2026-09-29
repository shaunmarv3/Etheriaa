// ─────────────────────────────────────────────
// Core Types - Mirroring Backend Pydantic Schemas
// ─────────────────────────────────────────────

export type TriageLevel = 'RED' | 'YELLOW' | 'GREEN';

export interface User {
  id: string;
  email: string;
  createdAt: string;
}

export interface Symptom {
  name: string;
  cui?: string;
  icd10?: string;
  snomed?: string;
  duration?: string;
  severity?: string;
  type?: 'symptom' | 'medication' | 'condition';
  rxcui?: string;
}

export interface Citation {
  source: 'user_document' | 'neo4j' | 'pubmed' | 'medlineplus' | 'curated';
  identifier: string;
  title?: string;
  url?: string;
  relevanceScore: number;
}

export interface DifferentialDiagnosis {
  condition: string;
  likelihood: 'likely' | 'possible' | 'unlikely';
  rationale: string;
  workup: string[];
  citations: string[];
}

export interface Message {
  id: string;
  sessionId: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  symptoms?: Symptom[];
  triageLevel?: TriageLevel;
  followUpQuestions?: string[];
  differential?: DifferentialDiagnosis[];
  citations?: Citation[];
  isStreaming?: boolean;
  agentTrace?: AgentTrace;
  createdAt: string;
}

export interface ConversationSession {
  id: string;
  userId: string;
  triageLevel: TriageLevel | null;
  createdAt: string;
  updatedAt: string;
}

export interface Document {
  id: string;
  userId: string;
  filename: string;
  fileSize: number;
  fileType: string;
  status: 'pending' | 'processing' | 'done' | 'failed';
  uploadedAt: string;
}

// ─────────────────────────────────────────────
// API Request/Response Types
// ─────────────────────────────────────────────

export interface ChatRequest {
  sessionId?: string;
  message: string;
}

export interface ChatResponse {
  sessionId: string;
  reply: string;
  triageLevel: TriageLevel;
  symptoms: Symptom[];
  followUpQuestions: string[];
  differential: DifferentialDiagnosis[];
  citations: Citation[];
}

export interface UploadRequest {
  file: File;
}

export interface UploadResponse {
  documentId: string;
  filename: string;
  status: string;
}

export interface HistoryResponse {
  sessions: ConversationSession[];
  messages: Message[];
}

export interface DocumentListResponse {
  documents: Document[];
}

// ─────────────────────────────────────────────
// Agent trace (metadata event)
// ─────────────────────────────────────────────

export interface AgentEntry {
  name: string;
  role: string;
  output: string;
  tools: string[];
  detail: Record<string, unknown>;
}

export interface AgentTrace {
  intent: string;
  symptoms_extracted: Symptom[];
  routing_flags: Record<string, boolean>;
  cache_hit: boolean;
  sources: Record<string, number>;
  context_chars: number;
  triage_reasoning: string | null;
  duration_ms: number;
  agents: AgentEntry[];
}

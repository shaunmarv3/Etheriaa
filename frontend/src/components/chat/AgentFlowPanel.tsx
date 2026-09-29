'use client';

import React, { useState } from 'react';
import type { AgentTrace, AgentEntry } from '../../lib/types';
import {
  IconMessage,
  IconSearch,
  IconBooks,
  IconScale,
  IconStethoscope,
  IconTrafficLight,
  IconShield,
  IconSparkle,
} from '../ui/Icons';

type IconComponent = React.ComponentType<{ size?: number; color?: string }>;

// ── Plain-English translations ────────────────────────────────────────────────

const INTENT_LABEL: Record<string, string> = {
  symptom_report: 'symptom report',
  report_question: 'question about your reports',
  medication_query: 'medication question',
  follow_up: 'follow-up question',
  emergency: 'emergency',
  general_health: 'general health question',
  off_topic: 'off-topic',
};

const TOOL_LABEL: Record<string, string> = {
  get_lab_values: 'your lab values',
  get_current_medications: 'your medicines',
  search_my_reports: 'your reports',
  search_medical_literature: 'PubMed',
  search_health_topics: 'MedlinePlus',
  explore_conditions: 'the condition graph',
  resolve_medicine: 'Indian brand names',
  check_interactions: 'drug interactions',
};

const LEVEL_TEXT: Record<string, string> = {
  RED: 'RED: emergency guidance sent first.',
  YELLOW: 'YELLOW: see a doctor soon.',
  GREEN: 'GREEN: general guidance.',
};

const list = (x: unknown): string[] => (Array.isArray(x) ? (x as string[]) : []);

// Keyed by graph node name, as sent in agent_trace.agents (spec 4.3, 4.7).
const AGENT_FRIENDLY: Record<
  string,
  { title: string; Icon: IconComponent; color: string; describe: (a: AgentEntry) => string | null }
> = {
  load_context: {
    Icon: IconBooks,
    color: '#7c3aed',
    title: 'Loaded your record',
    describe: (a) => a.output || null,
  },
  input_guard: {
    Icon: IconShield,
    color: '#475569',
    title: 'Checked for red flags',
    describe: (a) => {
      const rules = list(a.detail.rules);
      return rules.length ? `Matched: ${rules.join(', ')}.` : 'No red-flag rule matched.';
    },
  },
  understand: {
    Icon: IconMessage,
    color: '#6366f1',
    title: 'Understood your message',
    describe: (a) => {
      const intent = a.output.replace(/^intent /, '');
      const parts = [`Identified as: ${INTENT_LABEL[intent] ?? intent}.`];
      const symptoms = list(a.detail.symptoms);
      const meds = list(a.detail.medications);
      if (symptoms.length) parts.push(`Symptoms: ${symptoms.join(', ')}.`);
      if (meds.length) parts.push(`Medicines: ${meds.join(', ')}.`);
      return parts.join(' ');
    },
  },
  retrieval_agent: {
    Icon: IconSearch,
    color: '#16a34a',
    title: 'Searched sources',
    describe: (a) => {
      const used = [...new Set(a.tools.map((t) => TOOL_LABEL[t] ?? t))];
      const found = a.output.split(';')[0];
      return used.length ? `Looked in ${used.join(', ')}: ${found}.` : `${found}.`;
    },
  },
  triage: {
    Icon: IconTrafficLight,
    color: '#ea580c',
    title: 'Urgency assessment',
    describe: (a) => {
      const rules = list(a.detail.rules);
      const base = LEVEL_TEXT[a.output] ?? 'Urgency assessed.';
      return rules.length ? `${base} Rules: ${rules.join(', ')}.` : base;
    },
  },
  rerank_evidence: {
    Icon: IconScale,
    color: '#ca8a04',
    title: 'Ranked the evidence',
    describe: (a) => (a.output ? `${a.output}.` : null),
  },
  clinical_structuring: {
    Icon: IconStethoscope,
    color: '#0891b2',
    title: 'Prepared follow-up questions',
    describe: (a) => (a.output ? `${a.output}.` : null),
  },
  generate: {
    Icon: IconSparkle,
    color: '#44c767',
    title: 'Wrote the answer',
    describe: (a) => {
      const hits = list(a.detail.guard);
      return hits.length
        ? `Safety filter removed ${hits.length} sentence${hits.length > 1 ? 's' : ''}.`
        : 'Safety filter: nothing removed.';
    },
  },
};

const SOURCE_FRIENDLY: Record<string, { label: string; color: string }> = {
  user_document: { label: 'Your reports', color: '#b45309' },
  neo4j: { label: 'Medical knowledge graph', color: '#16a34a' },
  pubmed: { label: 'PubMed', color: '#0369a1' },
  medlineplus: { label: 'MedlinePlus', color: '#7c3aed' },
  curated: { label: 'Curated safety rules', color: '#475569' },
};

const TRIAGE_FRIENDLY: Record<string, { label: string; color: string; bg: string }> = {
  RED: { label: 'Emergency', color: '#dc2626', bg: 'rgba(220,38,38,0.08)' },
  YELLOW: { label: 'See a doctor', color: '#ca8a04', bg: 'rgba(202,138,4,0.08)' },
  GREEN: { label: 'Low urgency', color: '#16a34a', bg: 'rgba(22,163,74,0.08)' },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function AgentStep({ agent, index, total }: { agent: AgentEntry; index: number; total: number }) {
  const [expanded, setExpanded] = useState(false);
  const friendly = AGENT_FRIENDLY[agent.name];
  if (!friendly) return null;

  const description = friendly.describe(agent);
  if (description === null) return null;

  return (
    <div style={{ display: 'flex', gap: 12, position: 'relative' }}>
      {index < total - 1 && (
        <div
          style={{
            position: 'absolute',
            left: 14,
            top: 30,
            bottom: -4,
            width: 1,
            background: 'rgba(26,46,32,0.08)',
          }}
        />
      )}

      {/* Step icon */}
      <div
        style={{
          flexShrink: 0,
          width: 28,
          height: 28,
          borderRadius: '50%',
          background: `${friendly.color}12`,
          border: `1px solid ${friendly.color}25`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1,
        }}
      >
        <friendly.Icon size={14} color={friendly.color} />
      </div>

      <div style={{ flex: 1, paddingBottom: index < total - 1 ? 14 : 0 }}>
        <button
          onClick={() => setExpanded((v) => !v)}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 8,
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            textAlign: 'left',
          }}
        >
          <div>
            <p
              style={{
                margin: 0,
                fontSize: 12.5,
                fontWeight: 600,
                color: '#1a2e20',
                fontFamily: 'var(--font-sans)',
                lineHeight: 1.4,
              }}
            >
              {friendly.title}
            </p>
            <p
              style={{
                margin: '3px 0 0',
                fontSize: 12,
                color: '#555',
                fontFamily: 'var(--font-sans)',
                lineHeight: 1.7,
                whiteSpace: 'pre-line',
              }}
            >
              {description}
            </p>
          </div>
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="rgba(26,46,32,0.25)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              transform: expanded ? 'rotate(180deg)' : 'rotate(0)',
              transition: 'transform 0.2s',
              flexShrink: 0,
              marginTop: 4,
            }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {expanded && (
          <div
            style={{
              marginTop: 8,
              padding: '9px 11px',
              borderRadius: 8,
              background: 'rgba(255,255,255,0.6)',
              border: '1px solid rgba(26,46,32,0.07)',
              fontSize: 11.5,
              color: '#666',
              fontFamily: 'var(--font-sans)',
              lineHeight: 1.55,
            }}
          >
            <p
              style={{
                margin: '0 0 5px',
                fontSize: 10,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.07em',
                color: 'rgba(26,46,32,0.35)',
              }}
            >
              What this step does
            </p>
            <p style={{ margin: 0 }}>{agent.role}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface AgentFlowPanelProps {
  trace: AgentTrace;
  /** The message's triage level; `trace.triage_reasoning` is prose, not a level. */
  level?: string;
}

export default function AgentFlowPanel({ trace, level }: AgentFlowPanelProps) {
  const [open, setOpen] = useState(false);

  const triage = level ?? 'GREEN';
  const tc = TRIAGE_FRIENDLY[triage] ?? TRIAGE_FRIENDLY.GREEN;
  const totalSources = Object.keys(trace.sources ?? {}).length;
  const durationSec = trace.duration_ms ? (trace.duration_ms / 1000).toFixed(1) : null;
  const agents = trace.agents ?? [];

  // Build a one-line human summary
  const symptoms = trace.symptoms_extracted ?? [];
  const symText =
    symptoms.length > 0
      ? `based on ${symptoms.map((s) => s.name).join(', ')}`
      : 'based on your message';

  const summary = `Analysed ${symText} · checked ${totalSources} source${totalSources !== 1 ? 's' : ''}${durationSec ? ` in ${durationSec}s` : ''}`;

  return (
    <div
      className="agent-flow-panel"
      style={{
        marginBottom: 14,
        borderRadius: 12,
        border: '1px solid rgba(26,46,32,0.09)',
        background: 'rgba(248,251,248,0.85)',
        overflow: 'hidden',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 14px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
        }}
      >
        <IconSparkle size={13} color="#44c767" />

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: 'rgba(26,46,32,0.6)', fontWeight: 500 }}>
            {summary}
          </span>

          {/* Source pills — friendly names */}
          {Object.entries(trace.sources ?? {}).map(([src, n]) => {
            const s = SOURCE_FRIENDLY[src];
            if (!s) return null;
            return (
              <span
                key={src}
                style={{
                  fontSize: 10.5,
                  fontWeight: 600,
                  padding: '1px 8px',
                  borderRadius: 10,
                  color: s.color,
                  background: `${s.color}10`,
                  border: `1px solid ${s.color}20`,
                }}
              >
                {n} {s.label}
              </span>
            );
          })}

          {/* Triage */}
          <span
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              padding: '1px 8px',
              borderRadius: 10,
              color: tc.color,
              background: tc.bg,
            }}
          >
            {tc.label}
          </span>

          {trace.cache_hit && (
            <span
              style={{
                fontSize: 10,
                color: '#0369a1',
                background: 'rgba(3,105,161,0.07)',
                padding: '1px 7px',
                borderRadius: 10,
                fontWeight: 500,
              }}
            >
              answered from cache
            </span>
          )}
        </div>

        <svg
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="none"
          stroke="rgba(26,46,32,0.3)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: open ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform 0.2s',
            flexShrink: 0,
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Steps */}
      {open && (
        <div style={{ borderTop: '1px solid rgba(26,46,32,0.06)', padding: '14px 14px 10px' }}>
          <p
            style={{
              margin: '0 0 12px',
              fontSize: 10,
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'rgba(26,46,32,0.3)',
            }}
          >
            How I arrived at this answer
          </p>
          {agents
            .filter((a) => {
              const f = AGENT_FRIENDLY[a.name];
              return f && f.describe(a) !== null;
            })
            .map((agent, i, arr) => (
              <AgentStep key={agent.name} agent={agent} index={i} total={arr.length} />
            ))}
        </div>
      )}
    </div>
  );
}

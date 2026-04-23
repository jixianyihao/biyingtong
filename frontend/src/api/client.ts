import type {
  Agent,
  AuditRow,
  BacktestResult,
  JobStatus,
  ModelInfo,
  Persona,
  PromptVersion,
  SessionComposite,
  SessionSummary,
} from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`${r.status} ${r.statusText}: ${body}`);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export type CreateAgentBody = {
  persona_id: string;
  model_id: string;
  display_name: string;
  rules_override?: Record<string, unknown>;
  initial_capital?: number;
};

export type StartBacktestBody = {
  agent_ids: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  universe: string[];
  include_baselines?: boolean;
  session_id?: string;
};

export const api = {
  personas: () => request<Persona[]>('/api/personas'),
  models: () => request<ModelInfo[]>('/api/models'),
  agents: () => request<Agent[]>('/api/agents'),
  agentDetail: (id: string) => request<Agent>(`/api/agents/${id}`),
  agentHealth: (id: string) =>
    request<{ agent_id: string; health_score: number; trust_rating: string }>(
      `/api/agents/${id}/health`
    ),
  agentPromptVersions: (id: string) =>
    request<PromptVersion[]>(`/api/agents/${id}/prompt_versions`),
  createAgent: (body: CreateAgentBody) =>
    request<Agent>('/api/agents', { method: 'POST', body: JSON.stringify(body) }),
  backtestsForAgent: (agentId: string, limit = 50) =>
    request<BacktestResult[]>(`/api/backtests?agent_id=${agentId}&limit=${limit}`),
  backtestDetail: (id: string) => request<BacktestResult>(`/api/backtests/${id}`),
  session: (id: string) => request<SessionComposite>(`/api/backtests/session/${id}`),
  startBacktest: (body: StartBacktestBody) =>
    request<{ session_id: string; state: string }>('/api/backtests', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  jobStatus: (sid: string) => request<JobStatus>(`/api/backtests/jobs/${sid}`),
  listJobs: () => request<JobStatus[]>('/api/backtests/jobs'),
  listSessions: (limit = 50) =>
    request<SessionSummary[]>(`/api/backtests/sessions?limit=${limit}`),
  redlines: () => request<Record<string, unknown>>('/api/redlines'),
  updateRedlines: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/redlines', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  audit: (params: { agent_id?: string; kind?: string; limit?: number }) => {
    const entries = Object.entries(params).filter(([, v]) => v != null) as [string, string | number][];
    const q = new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
    return request<AuditRow[]>(`/api/audit?${q}`);
  },
};

// Re-export types for convenience
export type * from './types';

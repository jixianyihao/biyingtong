import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { BacktestEvent, JobStatus, UpdateAgentBody, UpdatePersonaBody } from './types';

export const usePersonas = () =>
  useQuery({ queryKey: ['personas'], queryFn: api.personas });

export const useModels = () =>
  useQuery({ queryKey: ['models'], queryFn: api.models });

export const useAgents = () =>
  useQuery({ queryKey: ['agents'], queryFn: api.agents });

export const useAgent = (id: string | undefined) =>
  useQuery({
    queryKey: ['agent', id],
    queryFn: () => api.agentDetail(id!),
    enabled: !!id,
  });

export const useCreateAgent = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createAgent,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agents'] });
    },
  });
};

export const useStartBacktest = () =>
  useMutation({ mutationFn: api.startBacktest });

/**
 * @deprecated Use `useJobStatusStream` (SSE) instead. Poll-based status
 * query is kept for backward compat; all first-party pages now use the
 * stream hook. This will be removed in a future cleanup.
 */
export const useJobStatus = (sid: string | undefined, enabled = true) =>
  useQuery({
    queryKey: ['job', sid],
    queryFn: () => api.jobStatus(sid!),
    enabled: !!sid && enabled,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === 'complete' || state === 'failed' ? false : 1500;
    },
  });

/** SSE-based job status subscription. Falls back to null until first event. */
export const useJobStatusStream = (
  sessionId: string | undefined,
  enabled = true,
) => {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [events, setEvents] = useState<BacktestEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId || !enabled) {
      setStatus(null);
      setEvents([]);
      setError(null);
      return;
    }
    setStatus(null);
    setEvents([]);
    setError(null);

    const es = new EventSource(`/api/backtests/jobs/${sessionId}/stream`);
    esRef.current = es;

    es.onmessage = (ev) => {
      try {
        setStatus(JSON.parse(ev.data) as JobStatus);
      } catch {
        /* ignore bad payload */
      }
    };

    const eventKinds: BacktestEvent['kind'][] = [
      'phase', 'progress', 'tool_call', 'decision',
      'blocked', 'baseline_done',
    ];
    for (const kind of eventKinds) {
      es.addEventListener(kind, (ev: MessageEvent) => {
        try {
          const parsed = JSON.parse(ev.data) as BacktestEvent;
          setEvents((prev) => [...prev, parsed]);
        } catch {
          /* ignore bad payload */
        }
      });
    }

    es.addEventListener('done', () => { es.close(); });
    es.addEventListener('notfound', () => {
      setError('job not found');
      es.close();
    });
    es.addEventListener('timeout', () => {
      setError('stream timeout');
      es.close();
    });
    es.onerror = () => {
      // EventSource auto-reconnects; only surface error if we haven't
      // received any status yet (likely endpoint down)
      setError((prev) => prev ?? 'stream error');
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [sessionId, enabled]);

  return { status, events, error };
};

export const useSession = (sid: string | undefined, enabled = true) =>
  useQuery({
    queryKey: ['session', sid],
    queryFn: () => api.session(sid!),
    enabled: !!sid && enabled,
  });

export const useRedlines = () =>
  useQuery({ queryKey: ['redlines'], queryFn: api.redlines });

export const useUpdateRedlines = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.updateRedlines,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['redlines'] });
      qc.invalidateQueries({ queryKey: ['audit'] });
    },
  });
};

export const useAuditQuery = (
  params: { agent_id?: string; kind?: string; limit?: number },
  opts: { refetchInterval?: number | false } = {},
) =>
  useQuery({
    queryKey: ['audit', params],
    queryFn: () => api.audit(params),
    enabled: !!(params.agent_id || params.kind),
    refetchInterval: opts.refetchInterval ?? false,
  });

export const useSessions = (limit = 50) =>
  useQuery({ queryKey: ['sessions', limit], queryFn: () => api.listSessions(limit) });

/** Recent backtests across all agents (no filter) for the history side-list. */
export const useBacktestList = (limit = 20) =>
  useQuery({
    queryKey: ['backtests', 'list', limit],
    queryFn: () => api.listBacktests(undefined, limit),
    staleTime: 10_000,
  });

/** Coverage of locally-cached k-line data for one stock. Returns
 *  {first_date, last_date, count} so the backtest form can warn when the
 *  requested window has no underlying data. staleTime is generous because
 *  coverage only changes when the operator re-ingests bars.
 */
export const useDataCoverage = (code: string | undefined) =>
  useQuery({
    queryKey: ['data-coverage', code],
    queryFn: () => api.dataCoverage(code!),
    enabled: !!code,
    staleTime: 60_000,
  });

/** Daily K-line for one stock over a date range, backed by the local
 *  SQLite cache (storage.kline()). No TDX live dependency.
 */
export const useKline = (
  code: string | undefined,
  period: string,
  start: string | undefined,
  end: string | undefined,
) =>
  useQuery({
    queryKey: ['kline', code, period, start, end],
    queryFn: () => api.kline(code!, period, start!, end!),
    enabled: !!code && !!start && !!end,
    staleTime: 60_000,
    retry: false,
  });

export const useAgentPromptVersions = (id: string | undefined) =>
  useQuery({
    queryKey: ['agent-prompts', id],
    queryFn: () => api.agentPromptVersions(id!),
    enabled: !!id,
  });

export const useBacktestNav = (resultId: string | undefined) =>
  useQuery({
    queryKey: ['backtest-nav', resultId],
    queryFn: () => api.backtestNav(resultId!),
    enabled: !!resultId,
  });

export const useBacktestTrades = (resultId: string | undefined) =>
  useQuery({
    queryKey: ['backtest-trades', resultId],
    queryFn: () => api.backtestTrades(resultId!),
    enabled: !!resultId,
  });

export const useBacktestThinking = (resultId: string | undefined) =>
  useQuery({
    queryKey: ['backtest-thinking', resultId],
    queryFn: () => api.backtestThinking(resultId!),
    enabled: !!resultId,
  });

export const useBacktestRating = (resultId: string | undefined) =>
  useQuery({
    queryKey: ['backtest-rating', resultId],
    queryFn: () => api.backtestRating(resultId!),
    enabled: !!resultId,
  });

// ─── P3-B CRUD mutations ──────────────────────────────────────────────────

export const useUpdateAgent = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateAgentBody }) =>
      api.updateAgent(id, body),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: ['agents'] });
      qc.invalidateQueries({ queryKey: ['agent', id] });
    },
  });
};

export const useDeleteAgent = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteAgent(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agents'] });
    },
  });
};

export const useRollbackPrompt = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ agentId, versionId }: { agentId: string; versionId: number }) =>
      api.rollbackPrompt(agentId, versionId),
    onSuccess: (_d, { agentId }) => {
      qc.invalidateQueries({ queryKey: ['agent-prompts', agentId] });
      qc.invalidateQueries({ queryKey: ['agent', agentId] });
    },
  });
};

export const useCreatePersona = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createPersona,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['personas'] }),
  });
};

export const useUpdatePersona = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdatePersonaBody }) =>
      api.updatePersona(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['personas'] });
      // If system_prompt changed, agent prompt_versions changed too
      qc.invalidateQueries({ queryKey: ['agents'] });
    },
  });
};

export const useDeletePersona = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deletePersona(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['personas'] }),
  });
};

// ─── P3-C rule mode ───────────────────────────────────────────────────────

export const useStrategies = () =>
  useQuery({ queryKey: ['strategies'], queryFn: api.strategies });

export const useStartRuleBacktest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.startRuleBacktest,
    onSuccess: (data) => {
      // Invalidate session query so ResultsTable picks up the new result row
      qc.invalidateQueries({ queryKey: ['session', data.session_id] });
    },
  });
};

export const useMonthlyReturns = (resultId: string | undefined) =>
  useQuery({
    queryKey: ['monthly-returns', resultId],
    queryFn: () => api.monthlyReturns(resultId!),
    enabled: !!resultId,
  });

export const useCancelJob = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => api.cancelJob(sessionId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['session', data.session_id] });
      qc.invalidateQueries({ queryKey: ['job', data.session_id] });
    },
  });
};

export const useDeleteBacktest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (resultId: string) => api.deleteBacktest(resultId),
    onSuccess: () => {
      // The session composite query may need refetch — invalidate broadly
      qc.invalidateQueries({ queryKey: ['session'] });
      qc.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
};

// ─── P3-F Phase 1: deploy + proposals ─────────────────────────────────────

export const useDeployAgent = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, schedule }: { id: string; schedule?: string }) =>
      api.deployAgent(id, schedule ? { schedule } : undefined),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['deploy-status', vars.id] });
    },
  });
};

export const useStopAgent = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.stopAgent(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ['deploy-status', id] });
    },
  });
};

export const useDeployStatus = (id: string | undefined) =>
  useQuery({
    queryKey: ['deploy-status', id],
    queryFn: () => api.deployStatus(id!),
    enabled: !!id,
    refetchInterval: 5000,  // poll every 5s to reflect status changes
    retry: false,
  });

export const useProposals = (params: {
  status?: string;
  agent_id?: string;
  limit?: number;
}) =>
  useQuery({
    queryKey: ['proposals', params],
    queryFn: () => api.listProposals(params),
    refetchInterval: 5000,  // keep pending list fresh
  });

export const useApproveProposal = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.approveProposal(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
};

export const useRejectProposal = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.rejectProposal(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
};

export function useApprovedProposals(agentId: string | undefined, limit = 50) {
  return useQuery({
    queryKey: ['proposals', 'approved', agentId, limit],
    queryFn: () => api.listProposals({ status: 'approved', agent_id: agentId!, limit }),
    enabled: !!agentId,
    staleTime: 5_000,
  });
}

export function usePollProposalStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.pollProposalStatus(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
}

export function useCancelProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.cancelProposal(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
}

// ─── P3-F Phase 2: execution mode ─────────────────────────────────────────

/**
 * Execution mode of the Flask server (dry_run vs live). Controlled by the
 * BIYINGTONG_EXECUTION_MODE env var at server start-up. The value never
 * changes without a server restart, so we cache indefinitely.
 */
export const useExecutionMode = () =>
  useQuery({
    queryKey: ['execution-mode'],
    queryFn: api.executionMode,
    staleTime: Infinity,
  });

/**
 * Real positions from GET /api/positions. In dry_run mode the server returns
 * an empty positions[] (no real orders were placed); the consumer should fall
 * back to demo stub rows. In live mode this returns the actual TDX holdings.
 * Polled every 10s while LiveTrading page is mounted.
 */
export function usePositions() {
  return useQuery({
    queryKey: ['positions'],
    queryFn: api.positions,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

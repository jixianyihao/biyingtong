import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { JobStatus, UpdateAgentBody, UpdatePersonaBody } from './types';

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
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId || !enabled) {
      setStatus(null);
      setError(null);
      return;
    }
    setStatus(null);
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
    es.addEventListener('done', () => {
      es.close();
    });
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

  return { status, error };
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

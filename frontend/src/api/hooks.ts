import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

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

export const useSession = (sid: string | undefined, enabled = true) =>
  useQuery({
    queryKey: ['session', sid],
    queryFn: () => api.session(sid!),
    enabled: !!sid && enabled,
  });

export const useRedlines = () =>
  useQuery({ queryKey: ['redlines'], queryFn: api.redlines });

import { useExecutionMode } from '../api/hooks';

/**
 * ExecutionModeBadge — header chip signalling which execution mode the Flask
 * server is running in. DRY-RUN is the default (grey); LIVE pulses red to
 * warn the operator that approve actions dispatch real TDX orders.
 *
 * Source of truth: GET /api/execution/mode (server env var
 * BIYINGTONG_EXECUTION_MODE). Cached with staleTime:Infinity because the
 * value cannot change without a server restart.
 */
export function ExecutionModeBadge() {
  const { data } = useExecutionMode();
  // Default to dry_run on unknown/loading — never imply LIVE when uncertain.
  const mode = data?.mode ?? 'dry_run';
  const isLive = mode === 'live';

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] mono font-medium tracking-wider uppercase ${
        isLive
          ? 'bg-red-500/20 text-red-400 border border-red-500/50 animate-pulse'
          : 'bg-bg-2 text-text-dim border border-panel-border-soft'
      }`}
      title={
        isLive
          ? '⚠ LIVE TRADING — 审批将提交真实订单到 TDX'
          : 'DRY-RUN — 审批仅写 DB 状态，不下真单'
      }
    >
      {isLive ? '● LIVE' : 'DRY-RUN'}
    </span>
  );
}

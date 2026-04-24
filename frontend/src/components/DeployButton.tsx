import { useState } from 'react';
import { useDeployAgent, useStopAgent, useDeployStatus } from '../api/hooks';

function formatUptime(startedAt: string | null | undefined): string {
  if (!startedAt) return '—';
  const started = new Date(startedAt.replace(' ', 'T'));
  if (Number.isNaN(started.getTime())) return '—';
  const sec = Math.max(0, Math.floor((Date.now() - started.getTime()) / 1000));
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
  return `${Math.floor(sec / 86400)}d ${Math.floor((sec % 86400) / 3600)}h`;
}

/**
 * DeployButton — toggles agent deployment.
 *
 * Phase 1 CRITICAL: When a deployed agent emits decisions, they are queued
 * as proposals for user review in ProposalsPanel. NO real TDX trade is ever
 * placed by deploying alone. Phase 2 (separate consent) wires execution.
 */
export function DeployButton({ agentId }: { agentId: string }) {
  const status = useDeployStatus(agentId);
  const deploy = useDeployAgent();
  const stop = useStopAgent();
  const [scheduleOverride, setScheduleOverride] = useState<string>('');

  const d = status.data;
  const running = d?.status === 'running';
  const busy = deploy.isPending || stop.isPending;

  const onDeploy = () => {
    deploy.mutate({
      id: agentId,
      schedule: scheduleOverride || undefined,
    });
  };
  const onStop = () => {
    stop.mutate(agentId);
  };

  return (
    <div
      className="panel p-4"
      style={{ display: 'grid', gap: 8 }}
    >
      <div className="flex items-baseline gap-2 flex-wrap">
        <h3 className="text-text-hi text-sm font-semibold">部署管理</h3>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Deploy
        </span>
        <span style={{ flex: 1 }} />
        {d && (
          <span
            className={
              d.status === 'running' ? 'pill brand'
              : d.status === 'crashed' ? 'pill down'
              : 'pill'
            }
            style={{ fontSize: 10 }}
          >
            {d.status === 'running' ? '运行中'
             : d.status === 'crashed' ? '崩溃'
             : '已停止'}
          </span>
        )}
      </div>

      <div
        className="text-[11px]"
        style={{
          padding: '6px 8px',
          background: 'var(--warn-bg, rgba(234,179,8,0.08))',
          color: 'var(--warn)',
          border: '1px solid var(--warn)',
          borderRadius: 4,
        }}
      >
        ⚠ Phase 1 安全承诺：部署仅让 agent 提交交易提议到待审批队列；
        批准也只改数据库状态，<strong>不会真实下单到 TDX</strong>。
      </div>

      {running && d && (
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <div className="text-[10px] text-text-faint uppercase tracking-wider">PID</div>
            <div className="mono text-text-hi">{d.pid}</div>
          </div>
          <div>
            <div className="text-[10px] text-text-faint uppercase tracking-wider">已运行</div>
            <div className="mono text-text-hi">{formatUptime(d.started_at)}</div>
          </div>
          <div>
            <div className="text-[10px] text-text-faint uppercase tracking-wider">Schedule</div>
            <div className="mono text-text-hi">{d.schedule}</div>
          </div>
        </div>
      )}

      {!running && (
        <div className="flex items-baseline gap-2">
          <label className="text-[10px] text-text-faint uppercase tracking-wider">
            Schedule 覆盖 (可选)
          </label>
          <select
            className="bg-bg-2 border border-panel-border-soft rounded px-2 py-1 text-xs text-text-hi"
            value={scheduleOverride}
            onChange={(e) => setScheduleOverride(e.target.value)}
            disabled={busy}
          >
            <option value="">使用 persona 默认</option>
            <option value="daily">daily</option>
            <option value="weekly">weekly</option>
            <option value="intraday_5m">intraday_5m</option>
          </select>
        </div>
      )}

      <div className="flex gap-2 justify-end">
        {running ? (
          <button
            className="btn"
            onClick={onStop}
            disabled={busy}
            style={{
              padding: '5px 14px',
              fontSize: 12,
              background: 'var(--down)',
              color: 'var(--bg)',
              borderColor: 'var(--down)',
            }}
          >
            {stop.isPending ? '停止中…' : '停止部署'}
          </button>
        ) : (
          <button
            className="btn primary"
            onClick={onDeploy}
            disabled={busy}
            style={{ padding: '5px 14px', fontSize: 12 }}
          >
            {deploy.isPending ? '启动中…' : '启动部署'}
          </button>
        )}
      </div>

      {(deploy.isError || stop.isError) && (
        <div className="text-xs" style={{ color: 'var(--down)' }}>
          {String(deploy.error ?? stop.error)}
        </div>
      )}
    </div>
  );
}

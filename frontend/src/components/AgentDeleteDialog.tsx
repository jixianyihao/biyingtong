import type React from 'react';
import { useDeleteAgent } from '../api/hooks';
import type { Agent } from '../api/types';

export function AgentDeleteDialog({
  agent,
  onClose,
  onDeleted,
}: {
  agent: Agent;
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const del = useDeleteAgent();
  const confirm = () => {
    del.mutate(agent.id, {
      onSuccess: () => {
        onClose();
        onDeleted?.();
      },
    });
  };
  return (
    <div style={overlayStyle} onClick={onClose}>
      <div
        className="panel"
        style={dialogStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-text-hi text-base font-semibold mb-3">
          删除 Agent
        </h2>
        <div className="text-sm text-text mb-2">
          确认删除 <span className="mono">{agent.display_name}</span>
          <span className="text-text-faint"> ({agent.id})</span> ?
        </div>
        <div
          className="text-xs text-text-faint mb-4"
          style={{ lineHeight: 1.6 }}
        >
          · Agent 及其所有 prompt 版本将被永久删除
          <br />· 历史 backtest 结果会保留（可从 session 查询）
          <br />· 此操作不可撤销
        </div>
        {del.isError && (
          <div className="text-xs mb-3" style={{ color: 'var(--down)' }}>
            {String(del.error)}
          </div>
        )}
        <div className="flex gap-2 justify-end">
          <button className="btn" onClick={onClose} disabled={del.isPending}>
            取消
          </button>
          <button
            className="btn"
            onClick={confirm}
            disabled={del.isPending}
            style={{
              background: 'var(--down)',
              color: 'var(--bg)',
              borderColor: 'var(--down)',
            }}
          >
            {del.isPending ? '删除中…' : '确认删除'}
          </button>
        </div>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
};

const dialogStyle: React.CSSProperties = {
  width: 'min(440px, 90vw)',
  padding: '20px 24px',
};

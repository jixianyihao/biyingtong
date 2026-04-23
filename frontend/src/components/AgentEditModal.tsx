import type React from 'react';
import { useState } from 'react';
import { useUpdateAgent } from '../api/hooks';
import type { Agent } from '../api/types';

export function AgentEditModal({
  agent,
  onClose,
}: {
  agent: Agent;
  onClose: () => void;
}) {
  const [displayName, setDisplayName] = useState(agent.display_name);
  const [rulesText, setRulesText] = useState(
    JSON.stringify(agent.rules_override, null, 2),
  );
  const [jsonError, setJsonError] = useState<string | null>(null);
  const update = useUpdateAgent();

  const onSave = () => {
    const body: { display_name?: string; rules_override?: Record<string, unknown> } = {};
    if (displayName.trim() && displayName.trim() !== agent.display_name) {
      body.display_name = displayName.trim();
    }
    const trimmed = rulesText.trim();
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed);
        if (JSON.stringify(parsed) !== JSON.stringify(agent.rules_override)) {
          body.rules_override = parsed;
        }
      } catch (e) {
        setJsonError(
          `JSON parse error: ${e instanceof Error ? e.message : String(e)}`,
        );
        return;
      }
    }
    setJsonError(null);
    if (Object.keys(body).length === 0) {
      // No changes — just close
      onClose();
      return;
    }
    update.mutate({ id: agent.id, body }, { onSuccess: onClose });
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div
        className="panel"
        style={dialogStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-text-hi text-base font-semibold mb-3">
          编辑 Agent
        </h2>
        <div className="mono text-[10px] text-text-faint mb-3">
          {agent.id}
        </div>

        <label className="text-[10px] text-text-faint uppercase tracking-wider mb-1 block">
          Display Name
        </label>
        <input
          className="w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi mb-3"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />

        <label className="text-[10px] text-text-faint uppercase tracking-wider mb-1 block">
          Rules Override (JSON)
        </label>
        <textarea
          className="w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-xs text-text-hi mono mb-2"
          rows={8}
          value={rulesText}
          onChange={(e) => {
            setRulesText(e.target.value);
            setJsonError(null);
          }}
        />
        {jsonError && (
          <div className="text-xs mb-3" style={{ color: 'var(--down)' }}>
            {jsonError}
          </div>
        )}
        {update.isError && (
          <div className="text-xs mb-3" style={{ color: 'var(--down)' }}>
            {String(update.error)}
          </div>
        )}

        <div className="flex gap-2 justify-end mt-3">
          <button className="btn" onClick={onClose} disabled={update.isPending}>
            取消
          </button>
          <button
            className="btn primary"
            onClick={onSave}
            disabled={update.isPending}
          >
            {update.isPending ? '保存中…' : '保存'}
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
  width: 'min(520px, 90vw)',
  maxHeight: '90vh',
  overflowY: 'auto',
  padding: '20px 24px',
};

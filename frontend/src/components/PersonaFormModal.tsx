import type React from 'react';
import { useState } from 'react';
import { useCreatePersona, useUpdatePersona } from '../api/hooks';
import type { Persona } from '../api/types';

type Mode = 'create' | 'edit';

// The backend Persona row carries `system_prompt` and `pool_filter` fields
// that haven't been surfaced on the shared Persona type yet (see types.ts).
// We widen locally so this form can round-trip them without fighting TS.
type PersonaFull = Persona & {
  system_prompt?: string;
  pool_filter?: Record<string, unknown> | null;
};

export function PersonaFormModal({
  mode,
  persona,
  onClose,
}: {
  mode: Mode;
  persona?: Persona; // required when mode === 'edit'
  onClose: () => void;
}) {
  const p = persona as PersonaFull | undefined;
  const [id, setId] = useState(p?.id ?? '');
  const [name, setName] = useState(p?.name ?? '');
  const [styleDesc, setStyleDesc] = useState(p?.style_desc ?? '');
  const [systemPrompt, setSystemPrompt] = useState(p?.system_prompt ?? '');
  const [schedule, setSchedule] = useState(p?.default_schedule ?? 'daily');
  const [poolText, setPoolText] = useState(
    (p?.default_pool ?? []).join(', '),
  );
  const [toolsText, setToolsText] = useState(
    (p?.allowed_tools ?? []).join(', '),
  );
  const [rulesJson, setRulesJson] = useState(
    p ? JSON.stringify(p.default_rules ?? {}, null, 2) : '{}',
  );
  const [poolFilterJson, setPoolFilterJson] = useState(
    p?.pool_filter ? JSON.stringify(p.pool_filter, null, 2) : '',
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = useCreatePersona();
  const update = useUpdatePersona();
  const isPending = create.isPending || update.isPending;

  const splitCsv = (s: string): string[] =>
    s.split(',').map((x) => x.trim()).filter(Boolean);

  const parseJsonField = (
    text: string,
    label: string,
    fallback: unknown,
  ): unknown => {
    const trimmed = text.trim();
    if (!trimmed) return fallback;
    try {
      return JSON.parse(trimmed);
    } catch (e) {
      throw new Error(
        `${label} JSON 解析失败: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  };

  const onSubmit = () => {
    setError(null);

    if (mode === 'create') {
      if (!id.trim()) return setError('id 必填');
      if (!/^[a-z][a-z0-9_]*$/.test(id.trim())) {
        return setError('id 只能用小写字母/数字/下划线，以字母开头');
      }
      if (!name.trim()) return setError('name 必填');
      if (!styleDesc.trim()) return setError('style_desc 必填');
      if (!systemPrompt.trim()) return setError('system_prompt 必填');
    }

    let defaultRules: Record<string, unknown>;
    let poolFilter: Record<string, unknown> | null;
    try {
      defaultRules = parseJsonField(rulesJson, 'default_rules', {}) as Record<
        string,
        unknown
      >;
      poolFilter = parseJsonField(
        poolFilterJson,
        'pool_filter',
        null,
      ) as Record<string, unknown> | null;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }

    const body = {
      name: name.trim(),
      style_desc: styleDesc.trim(),
      system_prompt: systemPrompt,
      default_schedule: schedule,
      default_pool: splitCsv(poolText),
      allowed_tools: splitCsv(toolsText),
      default_rules: defaultRules,
      pool_filter: poolFilter,
    };

    if (mode === 'create') {
      create.mutate(
        { id: id.trim(), ...body },
        { onSuccess: onClose },
      );
    } else if (persona) {
      update.mutate(
        { id: persona.id, body },
        { onSuccess: onClose },
      );
    }
  };

  const mutationError = create.error || update.error;

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div
        className="panel"
        style={dialogStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-text-hi text-base font-semibold mb-3">
          {mode === 'create' ? '新建 Persona' : '编辑 Persona'}
        </h2>

        <div className="grid gap-3">
          <Field label="ID">
            <input
              className={inputCls}
              value={id}
              onChange={(e) => setId(e.target.value)}
              disabled={mode === 'edit'}
              placeholder="e.g. growth_momentum"
            />
          </Field>
          <Field label="Name · 名称">
            <input
              className={inputCls}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="动量成长风格"
            />
          </Field>
          <Field label="Style · 风格描述">
            <input
              className={inputCls}
              value={styleDesc}
              onChange={(e) => setStyleDesc(e.target.value)}
              placeholder="追高成长股 · 止损纪律"
            />
          </Field>
          <Field label="System Prompt">
            <textarea
              className={`${inputCls} mono text-xs`}
              rows={10}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="You are..."
            />
          </Field>
          <Field label="Default Schedule · 调度">
            <select
              className={inputCls}
              value={schedule}
              onChange={(e) => setSchedule(e.target.value)}
            >
              <option value="daily">daily</option>
              <option value="weekly">weekly</option>
              <option value="intraday_5m">intraday_5m</option>
            </select>
          </Field>
          <Field label="Default Pool · 默认股票池 (逗号分隔)">
            <input
              className={`${inputCls} mono`}
              value={poolText}
              onChange={(e) => setPoolText(e.target.value)}
              placeholder="600519.SH, 000858.SZ"
            />
          </Field>
          <Field label="Allowed Tools · 允许工具 (逗号分隔)">
            <input
              className={`${inputCls} mono`}
              value={toolsText}
              onChange={(e) => setToolsText(e.target.value)}
              placeholder="get_kline, get_financials, place_decision"
            />
          </Field>

          <button
            type="button"
            className="text-[11px] text-text-faint underline self-start mt-1"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? '隐藏' : '展开'} Advanced (JSON)
          </button>
          {showAdvanced && (
            <>
              <Field label="Pool Filter (JSON, 留空则为 null)">
                <textarea
                  className={`${inputCls} mono text-xs`}
                  rows={4}
                  value={poolFilterJson}
                  onChange={(e) => setPoolFilterJson(e.target.value)}
                  placeholder='{"industry": "consumer"}'
                />
              </Field>
              <Field label="Default Rules (JSON)">
                <textarea
                  className={`${inputCls} mono text-xs`}
                  rows={4}
                  value={rulesJson}
                  onChange={(e) => setRulesJson(e.target.value)}
                  placeholder='{"max_holdings": 10}'
                />
              </Field>
            </>
          )}
        </div>

        {error && (
          <div className="text-xs mt-3" style={{ color: 'var(--down)' }}>
            {error}
          </div>
        )}
        {mutationError && (
          <div className="text-xs mt-3" style={{ color: 'var(--down)' }}>
            {String(mutationError)}
          </div>
        )}

        <div className="flex gap-2 justify-end mt-4">
          <button className="btn" onClick={onClose} disabled={isPending}>
            取消
          </button>
          <button
            className="btn primary"
            onClick={onSubmit}
            disabled={isPending}
          >
            {isPending ? '保存中…' : mode === 'create' ? '创建' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="text-[10px] text-text-faint uppercase tracking-wider mb-1 block">
        {label}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  'w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi';

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
  width: 'min(640px, 90vw)',
  maxHeight: '90vh',
  overflowY: 'auto',
  padding: '20px 24px',
};

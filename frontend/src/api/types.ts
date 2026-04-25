// TypeScript types mirroring Python dataclasses in the Flask backend.

export type Persona = {
  id: string;
  name: string;
  style_desc: string;
  default_schedule: string;
  default_pool: string[];
  allowed_tools: string[];
  default_rules: Record<string, unknown>;
  is_builtin: boolean;
  // Only returned by GET /api/personas/:id (detail) — absent on list rows.
  // Consumers that need these must call the detail endpoint.
  system_prompt?: string;
  pool_filter?: Record<string, unknown> | null;
};

export type ModelInfo = {
  id: string;
  provider: string;
  display_name: string;
  api_model_id: string;
  training_cutoff: string;
  supports_tool_use: boolean;
  max_tokens_out: number;
  enabled: boolean;
};

export type Agent = {
  id: string;
  persona_id: string;
  model_id: string;
  display_name: string;
  rules_override: Record<string, unknown>;
  initial_capital: number;
  status: string;
  health_score: number;
  trust_rating: string;
  current_prompt_version_id: number | null;
  created_at: string | null;
};

export type BacktestStats = {
  sharpe: number;
  max_drawdown_pct: number;
  trade_count: number;
  win_rate: number;
  max_daily_loss_pct: number;
  total_return_pct: number;
  final_equity: number;
};

export type ZoneStats = {
  zone: 'pollution' | 'buffer' | 'clean';
  days: number;
  stats: Record<string, number>;
};

export type BacktestResult = {
  id: string;
  session_id: string;
  agent_id: string;
  persona_id: string | null;
  model_id: string | null;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_equity: number | null;
  stats: BacktestStats;
  zone_stats: ZoneStats[];
  quality_gate_label: 'pass' | 'warn' | 'fail';
  quality_gate_criteria: Record<string, unknown>;
  divergence_flag: boolean;
  divergence_metric: number | null;
  kind: 'agent' | 'rule';
};

export type BaselineResult = {
  id: string;
  session_id: string;
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_equity: number | null;
  stats: BacktestStats;
};

export type JobStatus = {
  session_id: string;
  state: 'queued' | 'running' | 'complete' | 'failed' | 'cancelled';
  progress: string;
  agent_ids: string[];
  agent_result_ids: string[];
  baseline_result_ids: string[];
  error: string | null;
  submitted_at: number;
  started_at: number | null;
  finished_at: number | null;
  cancel_requested?: boolean;
};

export type SessionComposite = {
  session_id: string;
  agents: BacktestResult[];
  baselines: BaselineResult[];
};

export type AuditRow = {
  id: number;
  timestamp: string;
  kind: string;
  agent_id: string | null;
  persona_id: string | null;
  model_id: string | null;
  prompt_version: number | null;
  details: Record<string, unknown>;
};

export type SessionSummary = {
  session_id: string;
  start_date: string;
  end_date: string;
  agent_ids: string[];
  agent_count: number;
  baseline_count: number;
  created_at: string;
  notes: string | null;
};

export type PromptVersion = {
  id: number;
  agent_id: string;
  version_number: number;
  system_prompt: string;
  created_at: string | null;
  note: string | null;
};

export type NavPoint = {
  date: string;
  equity: number;
  // Agent curves always populate cash + pnl_pct; baselines use BaselineCurve instead.
  // Kept optional (not nullable) because the backend never emits null.
  cash?: number;
  pnl_pct?: number;
};

export type BaselineCurve = {
  name: string;
  curve: Array<{ date: string; equity: number }>;
};

export type NavResponse = {
  result_id: string;
  agent: NavPoint[];
  baselines: BaselineCurve[];
};

export type TradeRow = {
  date: string;
  code: string;
  action: 'buy' | 'sell';
  shares: number;
  price: number;
  fee: number;
};

export type TradesResponse = {
  result_id: string;
  trades: TradeRow[];
};

export type ThinkingDecision = {
  action: string;
  code?: string;
  shares?: number;
  price?: number;
  outcome?: string;
  reasoning?: string;
};

export type ThinkingEntry = {
  date: string;
  reasoning: string;
  tool_calls: Array<{ name: string; input: Record<string, unknown> }>;
  decisions: ThinkingDecision[];
};

export type ThinkingResponse = {
  result_id: string;
  thinking: ThinkingEntry[];
};

export type StrategyRating = {
  overall: number;
  letter: 'A+' | 'A' | 'B' | 'C' | 'D';
  // 5 sub-scores (0-100); names match backend rating/strategy_rating.py
  return_power: number;         // ① 收益能力
  risk_control: number;         // ② 风险控制
  stability: number;            // ③ 稳定性
  trading_efficiency: number;   // ④ 交易效率
  overfitting_risk: number;     // ⑤ 过拟合风险 (higher = less leakage = better)
  notes: string[];
};

/** One row of backend quality_gate_criteria. Matches validation/quality_gate.py. */
export type QualityGateCriterion = {
  ok: boolean;
  actual: number | string | boolean | null;
  threshold: number | string | boolean;
  reason?: string;
};

export type UpdateAgentBody = {
  display_name?: string;
  rules_override?: Record<string, unknown>;
};

export type CreatePersonaBody = {
  id: string;
  name: string;
  style_desc: string;
  system_prompt: string;
  default_pool?: string[];
  pool_filter?: Record<string, unknown> | null;
  default_schedule?: string;
  default_rules?: Record<string, unknown>;
  allowed_tools?: string[];
};

export type UpdatePersonaBody = Partial<Omit<CreatePersonaBody, 'id'>>;

export type StrategyDescriptor = {
  name: string;
  display_name: string;
  description: string;
  default_params: Record<string, number | string>;
};

export type StartRuleBacktestBody = {
  strategy_name: string;
  params?: Record<string, number>;
  session_id?: string;
  start_date: string;
  end_date: string;
  universe: string[];
  initial_capital: number;
};

export type StartRuleBacktestResponse = {
  session_id: string;
  result_id: string;
  state: string;
};

export type BacktestEventPhase = {
  kind: 'phase'; ts: number; phase: string; session_id?: string;
};
export type BacktestEventProgress = {
  kind: 'progress'; ts: number; agent_id: string; date: string;
  equity?: number; pnl_pct?: number;
};
export type BacktestEventToolCall = {
  kind: 'tool_call'; ts: number; agent_id: string; date: string;
  tool_name: string; tool_input: Record<string, unknown>;
};
export type BacktestEventDecision = {
  kind: 'decision'; ts: number; agent_id: string; date: string;
  action: string; code?: string; shares?: number; price?: number;
  outcome: string;
};
export type BacktestEventBlocked = {
  kind: 'blocked'; ts: number; agent_id: string; date: string;
  decision_input: Record<string, unknown>; reason: string;
};
export type BacktestEventBaselineDone = {
  kind: 'baseline_done'; ts: number; baseline_name: string; result_id: string;
};
export type BacktestEventDone = {
  kind: 'done'; ts: number; session_id?: string;
};

export type BacktestEvent =
  | BacktestEventPhase
  | BacktestEventProgress
  | BacktestEventToolCall
  | BacktestEventDecision
  | BacktestEventBlocked
  | BacktestEventBaselineDone
  | BacktestEventDone;

export type MonthlyReturn = {
  year: number;
  month: number;
  return_pct: number;
  days: number;
};

export type MonthlyReturnsResponse = {
  result_id: string;
  monthly_returns: MonthlyReturn[];
};

export type CancelJobResponse = {
  session_id: string;
  state: string;
};

export type ExecutionMode = 'dry_run' | 'live';

export type TradeProposal = {
  id: string;
  agent_id: string;
  created_at: string | null;
  decision_at: string;
  action: 'buy' | 'sell' | 'hold';
  code: string | null;
  shares: number | null;
  price: number | null;
  reason: string | null;
  thinking: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  decided_by: string | null;
  decided_at: string | null;
  // Phase 2 execution fields — populated by approve endpoint after dispatching
  // to ExecutionAdapter. Null on pending proposals and on Phase-1 rows pre-migration.
  execution_mode?: ExecutionMode | null;
  execution_order_id?: string | null;
  execution_error?: string | null;
  executed_at?: string | null;
  filled_qty?: number | null;
  filled_price?: number | null;
};

export type DeployStatus = {
  agent_id: string;
  pid: number;
  started_at: string;
  status: 'running' | 'stopped' | 'crashed';
  schedule: string;
};

export type Position = {
  code: string;
  name: string;
  shares: number;
  avg_price: number;
  last_price: number;
  pnl_pct: number;
};

export type PositionsResponse = {
  mode: ExecutionMode;
  positions: Position[];
  hint?: string;
};

export type DeployResponse = {
  agent_id: string;
  pid: number;
  schedule: string;
  status: string;
};

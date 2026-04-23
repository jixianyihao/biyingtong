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
  state: 'queued' | 'running' | 'complete' | 'failed';
  progress: string;
  agent_ids: string[];
  agent_result_ids: string[];
  baseline_result_ids: string[];
  error: string | null;
  submitted_at: number;
  started_at: number | null;
  finished_at: number | null;
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

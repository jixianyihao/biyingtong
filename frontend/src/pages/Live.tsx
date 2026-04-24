import { useProposals } from '../api/hooks';
import { ProposalsPanel } from '../components/ProposalsPanel';
import { PositionsPanel } from '../components/PositionsPanel';

/**
 * LiveTrading — Phase 1 preview page.
 *
 * CRITICAL: no real-money execution path exists here. ProposalsPanel approve
 * actions only mutate DB state (status=approved); the TDX place_order path is
 * gated behind Phase 2 and requires explicit user consent to enable.
 *
 * Layout:
 *   [ orange warning banner ]
 *   [ Positions (left) | Proposals queue (right) ]   -- grid on lg, stacked on sm
 *   [ AI 风控提示 (bottom, full width) ]
 */

function WarningBanner() {
  return (
    <div
      className="mb-4"
      style={{
        padding: '12px 16px',
        background: 'var(--warn-bg, rgba(234,179,8,0.08))',
        border: '1px solid var(--warn)',
        borderRadius: 6,
        color: 'var(--warn)',
        fontSize: 12.5,
        lineHeight: 1.55,
      }}
    >
      <span style={{ fontWeight: 600, marginRight: 4 }}>⚠</span>
      LiveTrading Phase 1 预览 —
      所有交易审批为状态变更，不会真实下单。
      真实下单 (Phase 2) 需用户明确同意后单独开启。
    </div>
  );
}

function RiskHintsCard({ proposalCount }: { proposalCount: number }) {
  const hints: string[] = [
    '当前 RedLine 配置：单票 ≤ 20%，单日最大亏损 ≤ 5%，禁止涨停追入 / ST 黑名单生效',
    '今日无超限决策（过去 24h 无 rejected / modified 记录）',
    `审批队列：${proposalCount} 待决`,
  ];

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">AI 风控提示</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          AI Risk Hints
        </span>
        <span style={{ flex: 1 }} />
        <span className="pill" style={{ fontSize: 10 }}>
          <span className="live-dot" /> preview
        </span>
      </div>

      <ul className="flex flex-col gap-2">
        {hints.map((h, i) => (
          <li
            key={i}
            className="flex items-start gap-2 text-sm text-text"
            style={{ lineHeight: 1.55 }}
          >
            <span
              className="mono text-[10px] text-text-ghost uppercase tracking-wider flex-shrink-0 mt-0.5"
              style={{ width: 22 }}
            >
              {String(i + 1).padStart(2, '0')}
            </span>
            <span>{h}</span>
          </li>
        ))}
      </ul>

      <div
        className="mono text-[10px] text-text-faint mt-4"
        style={{ lineHeight: 1.5 }}
      >
        Phase 2: 真实时风控提示将在接入 LiveTrading 后显示
      </div>
    </div>
  );
}

export function Live() {
  const proposals = useProposals({ status: 'pending', limit: 100 });
  const proposalCount = proposals.data?.length ?? 0;

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-2xl text-text-hi font-semibold">实盘交易</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          LiveTrading · Phase 1 Preview
        </div>
      </div>

      <WarningBanner />

      <div
        className="grid gap-5 mb-5"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))' }}
      >
        <PositionsPanel />

        <div className="panel p-5 flex flex-col min-h-0">
          <div className="flex items-baseline gap-2 mb-3 flex-wrap">
            <h2 className="text-text-hi text-base font-semibold">待审批提议</h2>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              Proposals Queue · Global Inbox
            </span>
            <span style={{ flex: 1 }} />
            <span className="pill" style={{ fontSize: 10 }}>
              {proposalCount} 待决
            </span>
          </div>
          <ProposalsPanel />
        </div>
      </div>

      <RiskHintsCard proposalCount={proposalCount} />
    </div>
  );
}

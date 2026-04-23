import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Logo } from './Logo';
import { Icon } from './Icon';

type NavItem = {
  id: string;
  kind: 'nav';
  icon: string;
  label: string;
  sub: string;
  to: string;
  badge?: string;
};
type SepItem = {
  id: string;
  kind: 'sep';
  label: string;
  sub: string;
};
type Item = NavItem | SepItem;

const ITEMS: Item[] = [
  { id: 'dashboard', kind: 'nav', icon: 'dashboard', label: '我的盈亏', sub: 'My P&L', to: '/' },
  { id: 'agent', kind: 'nav', icon: 'agent', label: '我的 AI 操盘手', sub: 'My Traders', to: '/agent', badge: '核心' },
  { id: 'live', kind: 'nav', icon: 'live', label: '实盘交易', sub: 'Trade', to: '/live' },
  { id: 'risk', kind: 'nav', icon: 'risk', label: '安全管控', sub: 'Safety', to: '/risk' },
  { id: 'audit', kind: 'nav', icon: 'list', label: '审计日志', sub: 'Audit Log', to: '/audit' },
  { id: '__sep', kind: 'sep', label: '研究工具', sub: 'RESEARCH' },
  { id: 'screener', kind: 'nav', icon: 'filter', label: '选股器', sub: 'Screener', to: '/screener' },
  { id: 'editor', kind: 'nav', icon: 'code', label: '策略研发', sub: 'Strategy', to: '/editor' },
  { id: 'backtest', kind: 'nav', icon: 'backtest', label: '回测', sub: 'Backtest', to: '/backtest' },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      style={{
        width: collapsed ? 56 : 208,
        background: 'var(--bg-1)',
        borderRight: '1px solid var(--panel-border)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        flexShrink: 0,
      }}
    >
      <div
        onClick={() => setCollapsed((c) => !c)}
        title={collapsed ? '展开' : '收起'}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '14px 14px 12px',
          borderBottom: '1px solid var(--panel-border-soft)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <Logo size={24} />
        {!collapsed && (
          <div style={{ lineHeight: 1.1 }}>
            <div style={{ fontWeight: 700, color: 'var(--text-hi)', letterSpacing: '0.02em' }}>
              必赢通
            </div>
            <div
              style={{
                fontSize: 9.5,
                color: 'var(--text-faint)',
                letterSpacing: '0.18em',
                textTransform: 'uppercase',
                marginTop: 2,
              }}
            >
              BiYingTong · v5.0
            </div>
          </div>
        )}
      </div>

      <nav style={{ padding: 8, flex: 1, overflowY: 'auto' }}>
        {ITEMS.map((it) => {
          if (it.kind === 'sep') {
            if (collapsed) {
              return (
                <div
                  key={it.id}
                  style={{
                    height: 1,
                    background: 'var(--panel-border-soft)',
                    margin: '10px 8px',
                  }}
                />
              );
            }
            return (
              <div
                key={it.id}
                style={{
                  padding: '12px 10px 4px',
                  fontSize: 9.5,
                  color: 'var(--text-ghost)',
                  letterSpacing: '0.16em',
                  textTransform: 'uppercase',
                  borderTop: '1px solid var(--panel-border-soft)',
                  marginTop: 8,
                }}
              >
                {it.label}
              </div>
            );
          }

          return (
            <NavLink
              key={it.id}
              to={it.to}
              end={it.to === '/'}
              title={collapsed ? it.label : ''}
              style={({ isActive }) => ({
                textDecoration: 'none',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: collapsed ? '9px 0' : '9px 10px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                margin: '2px 0',
                background: isActive ? 'var(--bg-3)' : 'transparent',
                border: '1px solid ' + (isActive ? 'var(--panel-border)' : 'transparent'),
                borderRadius: 6,
                color: isActive ? 'var(--text-hi)' : 'var(--text-dim)',
                cursor: 'pointer',
                position: 'relative',
                fontFamily: 'var(--f-ui)',
                fontSize: 12.5,
                textAlign: 'left',
                transition: 'all 0.12s ease',
              })}
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <div
                      style={{
                        position: 'absolute',
                        left: -9,
                        top: 6,
                        bottom: 6,
                        width: 2,
                        background: 'var(--brand)',
                        borderRadius: 2,
                      }}
                    />
                  )}
                  <Icon name={it.icon} size={15} />
                  {!collapsed && (
                    <div
                      style={{
                        flex: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 6,
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: isActive ? 600 : 500 }}>{it.label}</div>
                        <div
                          className="mono"
                          style={{
                            fontSize: 9.5,
                            color: 'var(--text-ghost)',
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            marginTop: 1,
                          }}
                        >
                          {it.sub}
                        </div>
                      </div>
                      {it.badge && (
                        <span
                          className="pill brand"
                          style={{ fontSize: 8.5, padding: '1px 5px' }}
                        >
                          {it.badge}
                        </span>
                      )}
                    </div>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {!collapsed && (
        <div style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)' }}>
          <div
            style={{
              padding: '10px 10px 9px',
              background: 'var(--bg-2)',
              borderRadius: 6,
              border: '1px solid var(--panel-border-soft)',
            }}
          >
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}
            >
              <span className="live-dot" style={{ color: 'var(--up)' }} />
              <span
                style={{
                  fontSize: 10.5,
                  color: 'var(--text-dim)',
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                }}
              >
                市场状态
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
              <span style={{ color: 'var(--text)' }}>沪深A股</span>
              <span className="mono up">+0.84%</span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 11,
                marginTop: 3,
              }}
            >
              <span style={{ color: 'var(--text)' }}>收盘倒计时</span>
              <span className="mono" style={{ color: 'var(--text-hi)' }}>
                01:24:17
              </span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

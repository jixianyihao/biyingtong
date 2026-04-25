// Single-stock OHLC candlestick over the backtest window.
// Mirrors NavChart's single-effect [data]-dependency pattern (per memo:
// 命令式图表库 + React 19 StrictMode → 不要分裂 mount-once / data-sync).
import { useEffect, useMemo, useRef } from 'react';
import {
  ColorType,
  LineStyle,
  createChart,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useKline } from '../api/hooks';
import type { OHLCBar } from '../api/types';

// CN market convention: red = up, green = down.
const UP = '#ef4444';
const DOWN = '#10b981';

function toTimestamp(dateStr: string): UTCTimestamp {
  return Math.floor(
    new Date(dateStr + 'T00:00:00Z').getTime() / 1000,
  ) as UTCTimestamp;
}

function trimToWindow(
  bars: OHLCBar[] | undefined,
  start: string,
  end: string,
): OHLCBar[] {
  if (!bars) return [];
  // dates are 'YYYY-MM-DD' so lexicographic compare is correct.
  return bars.filter((b) => b.date >= start && b.date <= end);
}

export function KLineChart({
  code,
  start,
  end,
  height = 200,
}: {
  code: string;
  start: string;
  end: string;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { data, isLoading, error } = useKline(code, '1d', start, end);

  const trimmed = useMemo(() => trimToWindow(data, start, end), [data, start, end]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || trimmed.length === 0) return;

    const chart = createChart(container, {
      width: container.clientWidth || 320,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8a8a8a',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: 'rgba(120,120,120,0.08)', style: LineStyle.Dotted },
        horzLines: { color: 'rgba(120,120,120,0.12)', style: LineStyle.Dotted },
      },
      timeScale: {
        borderColor: 'rgba(120,120,120,0.3)',
        timeVisible: false,
      },
      rightPriceScale: { borderColor: 'rgba(120,120,120,0.3)' },
      crosshair: { mode: 1 },
    });

    const series = chart.addCandlestickSeries({
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    series.setData(
      trimmed.map((b) => ({
        time: toTimestamp(b.date),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );
    chart.timeScale().fitContent();

    const ro = new ResizeObserver((entries) => {
      for (const e of entries) chart.applyOptions({ width: e.contentRect.width });
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [trimmed, height]);

  if (isLoading) {
    return (
      <div
        className="text-text-faint text-xs flex items-center justify-center"
        style={{ height }}
      >
        加载 K 线…
      </div>
    );
  }
  if (error) {
    return (
      <div
        className="text-xs flex items-center justify-center"
        style={{ height, color: 'var(--down)' }}
      >
        K 线加载失败
      </div>
    );
  }
  if (trimmed.length === 0) {
    return (
      <div
        className="text-text-faint text-xs italic flex items-center justify-center"
        style={{ height }}
      >
        该股该窗口无数据
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-baseline gap-2 mb-1">
        <span
          className="mono text-[10px] uppercase tracking-wider"
          style={{ color: 'var(--text-hi)' }}
        >
          {code}
        </span>
        <span className="mono text-[9.5px]" style={{ color: 'var(--text-ghost)' }}>
          {trimmed.length} bars
        </span>
      </div>
      <div ref={containerRef} style={{ width: '100%', height }} />
    </div>
  );
}

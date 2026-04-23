import { useEffect, useRef } from 'react';
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { NavResponse } from '../api/types';

// Agent line = brand gold; baselines walk these accent colors.
// Hex strings because lightweight-charts renders to canvas and can't use
// CSS vars.
const COLORS = ['#c9a227', '#808080', '#3b82f6', '#a855f7', '#22c55e'];

function toTimestamp(dateStr: string): UTCTimestamp {
  // Daily bars: midnight UTC is fine — the lib only uses this for tick labels.
  return Math.floor(
    new Date(dateStr + 'T00:00:00Z').getTime() / 1000,
  ) as UTCTimestamp;
}

export function NavChart({ data }: { data: NavResponse | undefined }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'>[]>([]);

  // Mount chart once; tear down on unmount
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8a8a8a',
        fontSize: 11,
      },
      grid: {
        vertLines: {
          color: 'rgba(120,120,120,0.15)',
          style: LineStyle.Dotted,
        },
        horzLines: {
          color: 'rgba(120,120,120,0.15)',
          style: LineStyle.Dotted,
        },
      },
      timeScale: {
        borderColor: 'rgba(120,120,120,0.3)',
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: 'rgba(120,120,120,0.3)',
      },
      crosshair: {
        mode: 1, // magnet
      },
    });
    chartRef.current = chart;

    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        chart.applyOptions({ width: e.contentRect.width });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = [];
    };
  }, []);

  // Sync series on data change
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !data) return;

    for (const s of seriesRef.current) {
      chart.removeSeries(s);
    }
    seriesRef.current = [];

    const agentSeries = chart.addLineSeries({
      color: COLORS[0],
      lineWidth: 2,
      title: 'Agent',
    });
    agentSeries.setData(
      data.agent.map((p) => ({
        time: toTimestamp(p.date),
        value: p.equity,
      })),
    );
    seriesRef.current.push(agentSeries);

    data.baselines.forEach((b, i) => {
      const s = chart.addLineSeries({
        color: COLORS[(i + 1) % COLORS.length],
        lineWidth: 1,
        title: b.name,
      });
      s.setData(
        b.curve.map((p) => ({
          time: toTimestamp(p.date),
          value: p.equity,
        })),
      );
      seriesRef.current.push(s);
    });

    chart.timeScale().fitContent();
  }, [data]);

  if (!data) {
    return <div className="text-text-faint text-sm">加载中…</div>;
  }
  if (data.agent.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        本次回测没有每日权益数据。
      </div>
    );
  }

  return (
    <div>
      <div ref={containerRef} style={{ width: '100%', height: 320 }} />
      <div className="flex flex-wrap gap-3 mt-2 text-[11px]">
        <LegendSwatch color={COLORS[0]} label="Agent" />
        {data.baselines.map((b, i) => (
          <LegendSwatch
            key={b.name}
            color={COLORS[(i + 1) % COLORS.length]}
            label={b.name}
          />
        ))}
        {data.baselines.length === 0 && (
          <span className="text-text-faint italic">
            （本次未运行对照组）
          </span>
        )}
      </div>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        style={{
          width: 14,
          height: 3,
          background: color,
          borderRadius: 1,
          display: 'inline-block',
        }}
      />
      <span className="text-text-dim">{label}</span>
    </span>
  );
}

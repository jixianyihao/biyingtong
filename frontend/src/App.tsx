import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { ComingSoon } from './pages/ComingSoon';

// Lazy-loaded route pages — split each into its own chunk to reduce
// initial bundle size. ComingSoon stays eager (tiny + reused).
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const Agent = lazy(() => import('./pages/Agent').then((m) => ({ default: m.Agent })));
const PromptHistory = lazy(() => import('./pages/PromptHistory').then((m) => ({ default: m.PromptHistory })));
const Risk = lazy(() => import('./pages/Risk').then((m) => ({ default: m.Risk })));
const Audit = lazy(() => import('./pages/Audit').then((m) => ({ default: m.Audit })));
const Screener = lazy(() => import('./pages/Screener').then((m) => ({ default: m.Screener })));
const Editor = lazy(() => import('./pages/Editor').then((m) => ({ default: m.Editor })));
const BacktestLab = lazy(() => import('./pages/BacktestLab').then((m) => ({ default: m.BacktestLab })));

function PageFallback() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: 'var(--text-faint)',
        fontSize: 13,
      }}
    >
      加载中…
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar />
          <main className="flex-1 overflow-auto">
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/agent" element={<Agent />} />
                <Route path="/agent/:agentId/prompts" element={<PromptHistory />} />
                <Route path="/live" element={<ComingSoon label="实盘交易" />} />
                <Route path="/risk" element={<Risk />} />
                <Route path="/audit" element={<Audit />} />
                <Route path="/screener" element={<Screener />} />
                <Route path="/editor" element={<Editor />} />
                <Route path="/backtest" element={<BacktestLab />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

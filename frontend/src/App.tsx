import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { Agent } from './pages/Agent';
import { BacktestLab } from './pages/BacktestLab';
import { ComingSoon } from './pages/ComingSoon';
import { Dashboard } from './pages/Dashboard';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar />
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/agent" element={<Agent />} />
              <Route path="/live" element={<ComingSoon label="实盘交易" />} />
              <Route path="/risk" element={<ComingSoon label="安全管控" />} />
              <Route path="/screener" element={<ComingSoon label="选股器" />} />
              <Route path="/editor" element={<ComingSoon label="策略研发" />} />
              <Route path="/backtest" element={<BacktestLab />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

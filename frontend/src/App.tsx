import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { Agent } from './pages/Agent';
import { Audit } from './pages/Audit';
import { BacktestLab } from './pages/BacktestLab';
import { ComingSoon } from './pages/ComingSoon';
import { Dashboard } from './pages/Dashboard';
import { Editor } from './pages/Editor';
import { PromptHistory } from './pages/PromptHistory';
import { Risk } from './pages/Risk';
import { Screener } from './pages/Screener';

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
              <Route path="/agent/:agentId/prompts" element={<PromptHistory />} />
              <Route path="/live" element={<ComingSoon label="实盘交易" />} />
              <Route path="/risk" element={<Risk />} />
              <Route path="/audit" element={<Audit />} />
              <Route path="/screener" element={<Screener />} />
              <Route path="/editor" element={<Editor />} />
              <Route path="/backtest" element={<BacktestLab />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

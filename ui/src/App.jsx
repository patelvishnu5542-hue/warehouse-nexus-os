import React, { useState, useEffect } from 'react';
import WarehouseGrid from './components/WarehouseGrid';

function App() {
  const API_BASE_URL = (() => {
    const configured = import.meta.env.VITE_API_URL;
    if (configured) return String(configured).replace(/\/$/, '');
    if (import.meta.env.DEV) return 'http://localhost:7860';
    return window.location.origin.replace(/\/$/, '');
  })();
  const [state, setState] = useState(null);
  const [metrics, setMetrics] = useState({ completed: 0, distance: 0, rewards: 0 });
  const [logs, setLogs] = useState([]);
  const [rewardLogs, setRewardLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [level, setLevel] = useState(2);
  const [mode, setMode] = useState('ai'); // dumb | logic | ai (server will confirm)
  const [hasToken, setHasToken] = useState(false);
  const [modelName, setModelName] = useState('');
  const [benchmark, setBenchmark] = useState(null);
  const [apiOnline, setApiOnline] = useState(true);
  const [apiError, setApiError] = useState('');
  const [showAiPopup, setShowAiPopup] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const stateRes = await fetch(`${API_BASE_URL}/state`, { cache: 'no-store' });
        const stateJson = await stateRes.json();
        const stateData = stateJson?.observation || stateJson;
        setState(stateData);

        const metricsRes = await fetch(`${API_BASE_URL}/metrics`, { cache: 'no-store' });
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);

        const logsRes = await fetch(`${API_BASE_URL}/logs`, { cache: 'no-store' });
        const logsData = await logsRes.json();
        setLogs(logsData.reverse()); 

        const rewardRes = await fetch(`${API_BASE_URL}/reward_logs`, { cache: 'no-store' });
        const rewardData = await rewardRes.json();
        setRewardLogs(rewardData.logs.reverse());

        const statusRes = await fetch(`${API_BASE_URL}/status`, { cache: 'no-store' });
        const statusData = await statusRes.json();
        setIsRunning(statusData.is_running);
        setIsThinking(statusData.is_thinking);
        if (typeof statusData.level === 'number') setLevel(statusData.level);
        if (typeof statusData.mode === 'string') setMode(statusData.mode);
        setHasToken(Boolean(statusData.has_hf_token));
        if (typeof statusData.model === 'string') setModelName(statusData.model);
        setApiOnline(true);
        setApiError('');
      } catch (err) {
        console.error("Failed to fetch state", err);
        setApiOnline(false);
        setApiError(`API not reachable at ${API_BASE_URL}`);
      }
    };

    const interval = setInterval(fetchData, 500);
    return () => clearInterval(interval);
  }, [API_BASE_URL]);

  useEffect(() => {
    if (mode === 'ai') {
      setShowAiPopup(true);
    } else {
      setShowAiPopup(false);
    }
  }, [mode]);

  const handleStartStop = async () => {
    try {
      const endpoint = isRunning ? 'stop' : 'start';
      const res = await fetch(`${API_BASE_URL}/${endpoint}`, { method: 'POST' });
      if (!res.ok) throw new Error(`${endpoint} failed`);
      const statusRes = await fetch(`${API_BASE_URL}/status`, { cache: 'no-store' });
      const statusData = await statusRes.json();
      setIsRunning(statusData.is_running);
      setIsThinking(statusData.is_thinking);
      if (typeof statusData.level === 'number') setLevel(statusData.level);
      if (typeof statusData.mode === 'string') setMode(statusData.mode);
      setHasToken(Boolean(statusData.has_hf_token));
      if (typeof statusData.model === 'string') setModelName(statusData.model);
      setApiOnline(true);
      setApiError('');
      if (!isRunning && statusData.mode === 'ai') setShowAiPopup(true);
    } catch (e) {
      console.error('Start/stop failed', e);
      setApiOnline(false);
      setApiError(`Failed to call ${API_BASE_URL}/${isRunning ? 'stop' : 'start'}`);
    }
  };

  const handleReset = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/reset`, { method: 'POST' });
      if (!res.ok) throw new Error('reset failed');
      setBenchmark(null);
      setApiOnline(true);
      setApiError('');
    } catch (e) {
      console.error('Reset failed', e);
      setApiOnline(false);
      setApiError(`Failed to call ${API_BASE_URL}/reset`);
    }
  };

  const handleConfigChange = async (nextLevel, nextMode) => {
    try {
      setApiError('');
      const res = await fetch(`${API_BASE_URL}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level: nextLevel, mode: nextMode })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        setLevel(data.level);
        setMode(data.mode);
        setHasToken(Boolean(data.has_hf_token));
        setModelName(data.model || '');
        setBenchmark(null);
        setApiOnline(true);
      } else {
        console.error('Config error', data);
        setApiOnline(true);
        setApiError(data.error || 'Config rejected by server');
      }
    } catch (e) {
      console.error('Failed to set config', e);
      setApiOnline(false);
      setApiError(`Failed to call ${API_BASE_URL}/config`);
    }
  };

  const runBenchmark = async () => {
    try {
      setBenchmark({ running: true });
      const res = await fetch(`${API_BASE_URL}/benchmark?level=${level}&steps=80&ai_steps=10`, { cache: 'no-store' });
      const data = await res.json();
      setBenchmark(data);
    } catch (e) {
      console.error('Benchmark failed', e);
      setBenchmark({ error: true });
    }
  };

  return (
    <div className="dashboard">
      {showAiPopup && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 50,
            padding: '24px'
          }}
          onClick={() => setShowAiPopup(false)}
        >
          <div
            className="glass-panel"
            style={{ maxWidth: '720px', width: '100%', padding: '18px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
              <div style={{ fontWeight: 800, letterSpacing: '0.04em' }}>AI MODE ACTIVE</div>
              <button className="btn btn-secondary" onClick={() => setShowAiPopup(false)}>CLOSE</button>
            </div>
            <div style={{ marginTop: '10px', fontSize: '12px', opacity: 0.9, lineHeight: 1.5 }}>
              This demo uses a real LLM controller via the <b>OpenAI Python client</b> (OpenAI-compatible endpoint).
              The environment provides a <b>points-based reward stream</b> (shown on the left) that represents the
              training signal you would use for RL or iterative improvement. The model is not updated online in this demo.
              {mode === 'ai' && !hasToken && (
                <div style={{ marginTop: '10px', color: 'var(--accent)' }}>
                  HF_TOKEN is not set → AI will fall back to the Logical controller.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      <header className="header">
        <div className="title">WAREHOUSE NEXUS OS</div>
        <div className="controls">
          {isThinking && mode === 'ai' && (
            <div className="thinking-indicator">
              <span className="dot"></span>
              AI ANALYZING (REWARD-DRIVEN)...
            </div>
          )}
          {!apiOnline && (
            <div className="thinking-indicator" style={{ color: 'var(--accent)', borderColor: 'rgba(244, 63, 94, 0.25)', background: 'rgba(244, 63, 94, 0.08)' }}>
              <span className="dot" style={{ background: 'var(--accent)', boxShadow: '0 0 10px var(--accent)' }}></span>
              API OFFLINE
            </div>
          )}
          <select
            value={level}
            onChange={(e) => handleConfigChange(Number(e.target.value), mode)}
            className="btn btn-secondary"
            style={{ padding: '10px 14px', marginRight: '10px' }}
          >
            <option value={1}>Level 1</option>
            <option value={2}>Level 2</option>
            <option value={3}>Level 3</option>
          </select>
          <select
            value={mode}
            onChange={(e) => handleConfigChange(level, e.target.value)}
            className="btn btn-secondary"
            style={{ padding: '10px 14px', marginRight: '10px' }}
          >
            <option value="dumb">Dumb</option>
            <option value="logic">Logical</option>
            <option value="ai">Real AI</option>
          </select>
          <button className={`btn ${isRunning ? 'btn-secondary' : ''}`} onClick={handleStartStop}>
            {isRunning ? 'PAUSE MISSION' : 'START SIMULATION'}
          </button>
          <button className="btn btn-secondary" style={{ marginLeft: '12px' }} onClick={handleReset}>
            RESET
          </button>
          <button className="btn btn-secondary" style={{ marginLeft: '12px' }} onClick={runBenchmark}>
            BENCHMARK
          </button>
        </div>
      </header>

      <aside className="glass-panel left-panel">
        <h3>ACTIVE WORKERS</h3>
        <div style={{ marginTop: '20px' }}>
          {state?.workers.map(w => (
            <div key={w.id} className="metric-card">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Worker {w.id}</span>
                <span style={{ color: w.status === 'busy' ? 'var(--accent)' : 'var(--secondary)' }}>
                  {w.status.toUpperCase()}
                </span>
              </div>
              <div style={{ fontSize: '12px', opacity: 0.7, marginTop: '8px' }}>
                Load: {w.load}/{w.capacity} | Pos: [{w.position.join(', ')}]
              </div>
            </div>
          ))}
        </div>

        <h3 style={{ marginTop: '24px' }}>PENDING ORDERS</h3>
        <div style={{ marginTop: '16px' }}>
          {state?.orders.map(o => (
            <div key={o.id} className="metric-card" style={{ fontSize: '12px' }}>
              <div style={{ fontWeight: 'bold' }}>Order #{o.id}</div>
              <div style={{ opacity: 0.8 }}>Items: {o.items.join(', ')}</div>
              <div style={{ color: o.priority === 'urgent' ? 'var(--accent)' : 'inherit', marginTop: '4px' }}>
                Priority: {o.priority} | Deadline: {o.deadline}
              </div>
            </div>
          ))}
        </div>

        <h3 style={{ marginTop: '24px' }}>REWARD STREAM</h3>
        <div className="reward-panel" style={{ marginTop: '16px' }}>
          {rewardLogs.map((log, i) => (
            <div key={i} className={`reward-item ${log.points >= 0 ? 'positive' : 'negative'}`}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span className="reason-text">{log.reason}</span>
                <span className="worker-badge">Worker {log.worker_id}</span>
              </div>
              <div className={`points-val ${log.points >= 0 ? 'pos' : 'neg'}`}>
                {log.points >= 0 ? '+' : ''}{log.points.toFixed(1)}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="glass-panel grid-container">
        {state && <WarehouseGrid state={state} />}
      </main>

      <aside className="glass-panel right-panel">
        <h3>COMMAND METRICS</h3>
        <div style={{ marginTop: '20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div className="metric-card">
            <div style={{ opacity: 0.7, fontSize: '10px' }}>Orders</div>
            <div className="metric-value" style={{ fontSize: '1.2rem' }}>{metrics.completed}</div>
          </div>
          <div className="metric-card">
            <div style={{ opacity: 0.7, fontSize: '10px' }}>Reward</div>
            <div className="metric-value" style={{ fontSize: '1.2rem', color: metrics.rewards >= 0 ? '#10b981' : '#f43f5e' }}>
              {metrics.rewards.toFixed(1)}
            </div>
          </div>
        </div>
        <div style={{ marginTop: '10px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div className="metric-card">
            <div style={{ opacity: 0.7, fontSize: '10px' }}>Distance</div>
            <div className="metric-value" style={{ fontSize: '1.1rem' }}>{metrics.distance}u</div>
          </div>
          <div className="metric-card">
            <div style={{ opacity: 0.7, fontSize: '10px' }}>Clock</div>
            <div className="metric-value" style={{ fontSize: '1.1rem' }}>{state?.time_step}s</div>
          </div>
        </div>
        
        <h3 style={{ marginTop: '24px' }}>SYSTEM LOGS</h3>
        <div className="glass-panel" style={{ marginTop: '16px', height: '150px', fontSize: '10px', padding: '10px', overflowY: 'auto' }}>
          {logs.map((log, i) => (
            <div key={i} style={{ marginBottom: '6px', borderLeft: '2px solid var(--secondary)', paddingLeft: '8px' }}>
              <span style={{ opacity: 0.5 }}>[{log.timestamp}s]</span> {log.message}
            </div>
          ))}
        </div>
        {apiError && (
          <div className="metric-card" style={{ marginTop: '16px', borderLeft: '3px solid var(--accent)' }}>
            <div style={{ fontWeight: 700, marginBottom: '6px' }}>Connection</div>
            <div style={{ fontSize: '11px', opacity: 0.85 }}>{apiError}</div>
          </div>
        )}

        <h3 style={{ marginTop: '24px' }}>BENCHMARK</h3>
        <div className="glass-panel" style={{ marginTop: '16px', fontSize: '11px', padding: '12px' }}>
          <div style={{ opacity: 0.75, marginBottom: '8px' }}>
            Mode: <b>{mode}</b> | Level: <b>{level}</b>
            {mode === 'ai' && !hasToken && (
              <span style={{ color: 'var(--accent)', marginLeft: '8px' }}>
                (HF_TOKEN not set → fallback)
              </span>
            )}
          </div>
          {modelName && <div style={{ opacity: 0.6, marginBottom: '8px' }}>Model: {modelName}</div>}
          {!benchmark && <div style={{ opacity: 0.7 }}>Click BENCHMARK to compare Dumb vs Logical vs AI.</div>}
          {benchmark?.running && <div style={{ opacity: 0.7 }}>Running…</div>}
          {benchmark?.error && <div style={{ color: 'var(--accent)' }}>Benchmark failed.</div>}
          {benchmark?.results && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.entries(benchmark.results).map(([k, v]) => (
                <div key={k} className="metric-card" style={{ marginBottom: 0, fontSize: '11px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 700, textTransform: 'uppercase' }}>{k}</span>
                    {v?.skipped ? <span style={{ opacity: 0.6 }}>skipped</span> : null}
                  </div>
                  {!v?.skipped && (
                    <div style={{ marginTop: '6px', opacity: 0.85 }}>
                      Completed: {v.completed ?? 0} | Reward: {(v.rewards ?? 0).toFixed?.(1) ?? v.rewards} | Distance: {v.distance ?? 0}
                    </div>
                  )}
                  {v?.skipped && <div style={{ marginTop: '6px', opacity: 0.7 }}>{v.reason}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

export default App;

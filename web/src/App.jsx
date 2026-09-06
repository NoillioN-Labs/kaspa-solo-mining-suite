import React, { useState, useEffect } from 'react';

function GlowingDot({ color }) {
  const shadowColor = color === 'red' ? 'rgba(239,68,68,0.5)' : color === 'yellow' ? 'rgba(245,158,11,0.5)' : 'rgba(112,199,186,0.5)';
  const bgColor = color === 'red' ? '#EF4444' : color === 'yellow' ? '#F59E0B' : '#70C7BA';
  
  return (
    <div style={{
      width: '12px',
      height: '12px',
      borderRadius: '50%',
      backgroundColor: bgColor,
      boxShadow: `0 0 10px ${shadowColor}`,
      display: 'inline-block',
      marginRight: '8px'
    }}></div>
  );
}

function CircularProgress({ progress }) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <svg width="50" height="50" viewBox="0 0 50 50" style={{ transform: 'rotate(-90deg)' }}>
      <circle
        cx="25" cy="25" r={radius}
        fill="transparent"
        stroke="var(--bg-surface-hover)"
        strokeWidth="4"
      />
      <circle
        cx="25" cy="25" r={radius}
        fill="transparent"
        stroke="var(--kaspa-teal)"
        strokeWidth="4"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        style={{ transition: 'stroke-dashoffset 0.5s ease' }}
      />
    </svg>
  );
}

function PresetSelector() {
  const [showModal, setShowModal] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('');
  
  const handleSelect = (e) => {
    setSelectedPreset(e.target.value);
    if (e.target.value) {
      setShowModal(true);
    }
  };

  const confirmTuning = async () => {
    try {
      const res = await fetch('/api/tuning', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset: selectedPreset })
      });
      if (res.ok) {
        alert(`Tuning applied: ${selectedPreset}`);
      }
    } catch (e) {
      console.error(e);
    }
    setShowModal(false);
    setSelectedPreset('');
  };

  return (
    <div style={{ marginTop: '24px' }}>
      <h3 className="card-title">ASIC Tuning Preset</h3>
      <select 
        value={selectedPreset} 
        onChange={handleSelect}
        style={{
          padding: '8px 12px',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: 'var(--bg-base)',
          color: 'var(--text-primary)',
          border: '1px solid var(--bg-surface-hover)',
          width: '100%',
          fontFamily: 'var(--font-sans)'
        }}
      >
        <option value="">Select a preset...</option>
        <option value="KS0">IceRiver KS0</option>
        <option value="KS1">IceRiver KS1</option>
        <option value="Antminer">Antminer KS3</option>
      </select>

      {showModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 100
        }}>
          <div className="card" style={{ maxWidth: '400px', width: '100%' }}>
            <h3 style={{ color: '#EF4444', marginBottom: '16px' }}>Warning: Mining Interruption</h3>
            <p style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
              Applying the <strong>{selectedPreset}</strong> preset will restart the Stratum Bridge. 
              Your ASIC will temporarily disconnect and reconnect. Do you wish to proceed?
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button 
                onClick={() => { setShowModal(false); setSelectedPreset(''); }}
                style={{
                  padding: '8px 16px', borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'transparent', color: 'var(--text-primary)',
                  border: '1px solid var(--bg-surface-hover)', cursor: 'pointer'
                }}
              >Cancel</button>
              <button 
                onClick={confirmTuning}
                style={{
                  padding: '8px 16px', borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--kaspa-teal)', color: '#000',
                  border: 'none', fontWeight: 'bold', cursor: 'pointer'
                }}
              >Apply Tuning</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LogViewer() {
  const [logs, setLogs] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = React.useRef(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        setLogs(data.logs);
      } catch (err) {
        console.error(err);
      }
    };
    fetchLogs();
    const int = setInterval(fetchLogs, 2000);
    return () => clearInterval(int);
  }, []);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  return (
    <div className="card" style={{ marginTop: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 className="card-title" style={{ marginBottom: 0 }}>Real-Time Logs</h3>
        <span style={{ fontSize: '0.8rem', color: autoScroll ? 'var(--kaspa-teal)' : 'var(--text-secondary)' }}>
          {autoScroll ? 'Auto-scrolling' : 'Paused'}
        </span>
      </div>
      
      <div 
        ref={scrollRef}
        onMouseEnter={() => setAutoScroll(false)}
        onMouseLeave={() => setAutoScroll(true)}
        style={{
          height: '250px',
          overflowY: 'auto',
          backgroundColor: '#0A0A0C',
          padding: '12px',
          borderRadius: 'var(--radius-sm)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.875rem',
          color: 'var(--text-secondary)'
        }}
      >
        {logs.map((log, i) => (
          <div key={i} style={{ 
            marginBottom: '4px', 
            color: log.includes('Error') ? '#EF4444' : log.includes('Accepted') ? 'var(--kaspa-teal)' : 'inherit'
          }}>
            {log}
          </div>
        ))}
        {logs.length === 0 && <div>Loading logs...</div>}
      </div>
    </div>
  );
}

function HealthMonitor({ setAlerts }) {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch('/api/health');
        const data = await res.json();
        setHealth(data);
        if (data.temp >= 85) {
          setAlerts(prev => {
            if (!prev.find(a => a.id === 'temp-alert')) {
              return [{ id: 'temp-alert', message: `CRITICAL: ASIC Temperature reached ${data.temp}°C` }, ...prev];
            }
            return prev;
          });
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchHealth();
    const int = setInterval(fetchHealth, 5000);
    return () => clearInterval(int);
  }, [setAlerts]);

  const isCritical = health && health.temp >= 85;

  return (
    <>
      <style>{`
        @keyframes pulse-red {
          0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
          70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .pulse-red {
          animation: pulse-red 2s infinite;
          border: 1px solid #EF4444 !important;
        }
      `}</style>
      <div className={`card ${isCritical ? 'pulse-red' : ''}`} style={{ marginTop: '24px' }}>
        <h3 className="card-title">Hardware Health</h3>
        {health ? (
          <div style={{ display: 'flex', gap: '24px' }}>
            <div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Temperature</div>
              <div style={{ fontSize: '1.5rem', color: isCritical ? '#EF4444' : 'var(--text-primary)' }}>{health.temp}°C</div>
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Fan Speed</div>
              <div style={{ fontSize: '1.5rem' }}>{health.fan} RPM</div>
            </div>
          </div>
        ) : (
          <div>Loading...</div>
        )}
      </div>
    </>
  );
}

function RewardsChart() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch('/api/rewards')
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  if (data.length === 0) return <div>Loading...</div>;

  const maxTotal = Math.max(...data.map(d => d.total));

  return (
    <div className="card" style={{ marginTop: '24px' }}>
      <h3 className="card-title">Reward Composition</h3>
      <div style={{ display: 'flex', alignItems: 'flex-end', height: '200px', gap: '8px', paddingTop: '20px' }}>
        {data.map((day, i) => {
          const subsidyPct = (day.subsidy / maxTotal) * 100;
          const feesPct = (day.fees / maxTotal) * 100;
          const dagPct = (day.dag / maxTotal) * 100;
          const totalStr = `Date: ${day.date}\nTotal: ${day.total.toFixed(2)} KAS\nSubsidy: ${day.subsidy.toFixed(2)}\nFees: ${day.fees.toFixed(2)}\nDAG: ${day.dag.toFixed(2)}`;

          return (
            <div key={i} title={totalStr} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', cursor: 'help' }}>
              <div style={{ height: `${dagPct}%`, backgroundColor: '#34D399' }}></div>
              <div style={{ height: `${feesPct}%`, backgroundColor: '#FCD34D' }}></div>
              <div style={{ height: `${subsidyPct}%`, backgroundColor: 'var(--kaspa-teal)' }}></div>
              <div style={{ textAlign: 'center', fontSize: '0.7rem', marginTop: '4px', color: 'var(--text-secondary)' }}>
                {day.date.slice(5)}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: '16px', marginTop: '16px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{width:'12px', height:'12px', backgroundColor:'var(--kaspa-teal)'}}></div> Subsidy</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{width:'12px', height:'12px', backgroundColor:'#FCD34D'}}></div> Fees</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{width:'12px', height:'12px', backgroundColor:'#34D399'}}></div> DAG</div>
      </div>
    </div>
  );
}

function ProfitabilityWidget() {
  const [fiat, setFiat] = useState(null);

  useEffect(() => {
    fetch('/api/fiat')
      .then(res => res.json())
      .then(setFiat)
      .catch(console.error);
  }, []);

  if (!fiat) return null;

  return (
    <div className="card" style={{ marginTop: '24px', display: 'flex', justifyContent: 'space-between' }}>
      <div>
        <h3 className="card-title">Estimated Daily Profit</h3>
        <div style={{ fontSize: '2rem', color: 'var(--kaspa-teal)' }}>
          ${fiat.dailyFiat.toFixed(2)} <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>{fiat.currency}</span>
        </div>
        <div style={{ color: 'var(--text-secondary)' }}>
          ~{fiat.dailyKas.toFixed(2)} KAS / day
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <h3 className="card-title">KAS Price</h3>
        <div style={{ fontSize: '1.5rem' }}>
          ${fiat.price.toFixed(3)}
        </div>
      </div>
    </div>
  );
}

function BlockCelebration({ onComplete }) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 4000);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      pointerEvents: 'none', zIndex: 9999, display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      backgroundColor: 'rgba(112, 199, 186, 0.2)'
    }}>
      <style>{`
        @keyframes float-up {
          0% { transform: translateY(100vh) scale(0.5); opacity: 1; }
          100% { transform: translateY(-20vh) scale(1.5); opacity: 0; }
        }
        .kaspa-coin {
          position: absolute;
          width: 60px; height: 60px;
          background-color: var(--kaspa-teal);
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          color: #000; font-weight: bold; font-size: 24px;
          animation: float-up 3s ease-out forwards;
        }
      `}</style>
      <div style={{ fontSize: '4rem', color: 'var(--kaspa-teal)', fontWeight: 'bold', textShadow: '0 0 20px rgba(112,199,186,0.8)' }}>
        BLOCK FOUND!
      </div>
      {Array.from({length: 20}).map((_, i) => (
        <div key={i} className="kaspa-coin" style={{
          left: `${Math.random() * 100}vw`,
          animationDelay: `${Math.random() * 0.5}s`
        }}>K</div>
      ))}
    </div>
  );
}

export function formatEta(seconds) {
  if (seconds === null || seconds === undefined || seconds <= 0) return 'Calculating...';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) return `~${hrs}h ${mins}m`;
  if (mins > 0) return `~${mins}m ${secs}s`;
  return `~${secs}s`;
}

export function SyncBanner({ sync }) {
  if (!sync) return null;

  // Stage 1: Pruning Point Proof Validation (~92k headers)
  if (sync.stage === 1) {
    return (
      <div style={{
        backgroundColor: 'rgba(245, 158, 11, 0.12)',
        border: '1px solid rgba(245, 158, 11, 0.4)',
        borderRadius: 'var(--radius-sm)',
        padding: '14px 18px',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
      }}>
        <style>{`
          @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); box-shadow: 0 0 12px rgba(245, 158, 11, 0.8); }
            50% { opacity: 0.5; transform: scale(0.9); box-shadow: 0 0 4px rgba(245, 158, 11, 0.3); }
          }
          .pulse-indicator { animation: pulse-dot 1.8s infinite ease-in-out; }
        `}</style>
        <div style={{
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          backgroundColor: '#F59E0B',
          flexShrink: 0
        }} className="pulse-indicator" />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, color: '#FCD34D', fontSize: '0.95rem' }}>
            Stage 1: Pruning Point Proof Validation
          </div>
          <div style={{ color: '#FDE68A', fontSize: '0.85rem', marginTop: '2px' }}>
            Validating DAG Pruning Proofs (~92k headers)... Network consensus verification in progress.
          </div>
        </div>
        <div style={{ fontSize: '0.85rem', color: '#FCD34D', fontWeight: 600 }}>
          {sync.headerCount ? `${sync.headerCount.toLocaleString()} / 92,160` : 'Verifying...'}
        </div>
      </div>
    );
  }

  // Stage 2: DAA Header Catchup
  if (sync.stage === 2) {
    return (
      <div style={{
        backgroundColor: 'rgba(112, 199, 186, 0.1)',
        border: '1px solid rgba(112, 199, 186, 0.3)',
        borderRadius: 'var(--radius-sm)',
        padding: '14px 18px',
        marginBottom: '20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: 'var(--kaspa-teal)',
              boxShadow: '0 0 8px var(--kaspa-teal)'
            }} />
            <span style={{ fontWeight: 600, color: 'var(--kaspa-teal)', fontSize: '0.95rem' }}>
              Stage 2: DAA Header Catchup
            </span>
          </div>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            ETA: <strong style={{ color: 'var(--text-primary)' }}>{formatEta(sync.etaSeconds)}</strong>
          </span>
        </div>
        <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-surface-hover)', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{
            width: `${Math.max(0.5, Math.min(100, sync.percent || sync.progress || 0))}%`,
            height: '100%',
            backgroundColor: 'var(--kaspa-teal)',
            transition: 'width 0.4s ease',
            boxShadow: '0 0 8px rgba(112,199,186,0.6)'
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          <span>DAA: {sync.currentDaa ? sync.currentDaa.toLocaleString() : 0} / {sync.targetDaa ? sync.targetDaa.toLocaleString() : '...'}</span>
          <span>{sync.percent || sync.progress || 0}%</span>
        </div>
      </div>
    );
  }

  // Stage 3: Synchronized
  return (
    <div style={{
      backgroundColor: 'rgba(52, 211, 153, 0.1)',
      border: '1px solid rgba(52, 211, 153, 0.3)',
      borderRadius: 'var(--radius-sm)',
      padding: '10px 18px',
      marginBottom: '20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          backgroundColor: '#34D399',
          boxShadow: '0 0 10px #34D399'
        }} />
        <span style={{ fontWeight: 600, color: '#34D399', fontSize: '0.95rem' }}>
          Synchronized (10 BPS) • Mining Active
        </span>
      </div>
      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
        DAA: {sync.currentDaa ? sync.currentDaa.toLocaleString() : 'Active'}
      </span>
    </div>
  );
}

export function SyncProgressCard({ sync }) {
  if (!sync) return null;

  return (
    <div className="card" style={{ marginTop: '24px' }}>
      <h3 className="card-title">Kaspa Node Sync State</h3>
      {sync.stage === 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#F59E0B', fontWeight: 600 }}>Stage 1: Pruning Proof Validation</span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Validating DAG Pruning Proofs (~92k headers)... Network consensus verification in progress.
          </p>
          <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-surface-hover)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{
              width: `${Math.max(1, Math.min(100, ((sync.headerCount || 0) / 92160) * 100))}%`,
              height: '100%',
              backgroundColor: '#F59E0B',
              transition: 'width 0.4s ease'
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <span>Headers Verified: {sync.headerCount ? sync.headerCount.toLocaleString() : 0} / 92,160</span>
            <span>{(((sync.headerCount || 0) / 92160) * 100).toFixed(1)}%</span>
          </div>
        </div>
      )}

      {sync.stage === 2 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--kaspa-teal)', fontWeight: 600 }}>Stage 2: DAA Header Catchup</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              ETA: <strong style={{ color: 'var(--text-primary)' }}>{formatEta(sync.etaSeconds)}</strong>
            </span>
          </div>
          <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-surface-hover)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{
              width: `${Math.max(0.5, Math.min(100, sync.percent || sync.progress || 0))}%`,
              height: '100%',
              backgroundColor: 'var(--kaspa-teal)',
              transition: 'width 0.4s ease'
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <span>Current DAA: {sync.currentDaa ? sync.currentDaa.toLocaleString() : 0}</span>
            <span>Target: {sync.targetDaa ? sync.targetDaa.toLocaleString() : '...'} ({sync.percent || sync.progress || 0}%)</span>
          </div>
        </div>
      )}

      {sync.stage === 3 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ color: '#34D399', fontWeight: 600 }}>Stage 3: Synchronized (10 BPS)</div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '4px' }}>
              Virtual DAG tip reached. Solo mining active on port 55555.
            </div>
          </div>
          <div style={{
            padding: '6px 14px',
            borderRadius: '16px',
            backgroundColor: 'rgba(52, 211, 153, 0.15)',
            color: '#34D399',
            fontSize: '0.85rem',
            fontWeight: 600,
            border: '1px solid rgba(52, 211, 153, 0.4)'
          }}>
            Tip Synced
          </div>
        </div>
      )}
    </div>
  );
}

export function AsicConnectionCard({ connection }) {
  const [copiedKey, setCopiedKey] = useState(null);

  const conn = connection || {
    lanIp: '127.0.0.1',
    port: 55555,
    stratumLan: 'stratum+tcp://127.0.0.1:55555',
    stratumHostname: 'stratum+tcp://umbrel.local:55555',
  };

  const handleCopy = (key, text) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(() => {});
    }
    setCopiedKey(key);
    setTimeout(() => {
      setCopiedKey(prev => (prev === key ? null : prev));
    }, 2000);
  };

  return (
    <div className="card" style={{ marginTop: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <h3 className="card-title" style={{ marginBottom: 0 }}>ASIC Stratum Connection Points</h3>
        <span style={{ fontSize: '0.8rem', color: 'var(--kaspa-teal)', fontWeight: 500 }}>
          Port: {conn.port || 55555}
        </span>
      </div>

      {/* Mining Readiness Callout (UX-DR6) */}
      <div style={{
        backgroundColor: 'rgba(112, 199, 186, 0.08)',
        border: '1px solid rgba(112, 199, 186, 0.25)',
        borderRadius: 'var(--radius-sm)',
        padding: '10px 14px',
        marginBottom: '16px',
        fontSize: '0.85rem',
        color: '#A7F3D0',
        lineHeight: 1.4,
      }}>
        ℹ️ <strong>Ready:</strong> ASICs can be connected now; mining will commence automatically once the node reaches the DAG tip.
      </div>

      {/* Primary: LAN IP (Recommended for IceRiver & Antminer ASICs) */}
      <div style={{ marginBottom: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Primary (Direct LAN IPv4 — Recommended for IceRiver/Antminer):
          </span>
          <span style={{ fontSize: '0.75rem', color: '#10B981', fontWeight: 600 }}>Zero mDNS Issues</span>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          backgroundColor: '#0A0A0C',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--bg-surface-hover)',
          padding: '6px 10px',
        }}>
          <code style={{
            flex: 1,
            color: 'var(--kaspa-teal)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.875rem',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {conn.stratumLan}
          </code>
          <button
            onClick={() => handleCopy('lan', conn.stratumLan)}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: copiedKey === 'lan' ? '#10B981' : 'var(--bg-surface)',
              color: copiedKey === 'lan' ? '#000' : 'var(--text-primary)',
              border: '1px solid var(--bg-surface-hover)',
              fontWeight: 600,
              fontSize: '0.8rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              marginLeft: '8px',
            }}
          >
            {copiedKey === 'lan' ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>

      {/* Secondary: Local Hostname (umbrel.local) */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Secondary (Local Hostname / mDNS):
          </span>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          backgroundColor: '#0A0A0C',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--bg-surface-hover)',
          padding: '6px 10px',
        }}>
          <code style={{
            flex: 1,
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.875rem',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {conn.stratumHostname}
          </code>
          <button
            onClick={() => handleCopy('hostname', conn.stratumHostname)}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: copiedKey === 'hostname' ? '#10B981' : 'var(--bg-surface)',
              color: copiedKey === 'hostname' ? '#000' : 'var(--text-primary)',
              border: '1px solid var(--bg-surface-hover)',
              fontWeight: 600,
              fontSize: '0.8rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              marginLeft: '8px',
            }}
          >
            {copiedKey === 'hostname' ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function formatHashrate(thVal) {
  const num = Number(thVal) || 0;
  if (num >= 1000) return `${(num / 1000).toFixed(2)} PH/s`;
  if (num >= 1) return `${num.toFixed(2)} TH/s`;
  if (num > 0) return `${(num * 1000).toFixed(1)} GH/s`;
  return '0.0 GH/s';
}

export function MetricCardsGrid({ stats, bridge }) {
  const hashrateTh = stats?.totalHashrateTh || bridge?.totalHashrate || 0;
  const activeMiners = stats?.activeMiners ?? bridge?.clients ?? 0;
  const blocks24h = stats?.blocks24h ?? 0;
  const effort = stats?.roundEffort ?? 0;
  const isLucky = effort < 100;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '16px',
      marginTop: '16px',
      marginBottom: '24px'
    }}>
      {/* 1. Fleet Hashrate */}
      <div className="card" style={{ padding: '18px' }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>
          Fleet Hashrate
        </div>
        <div style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          fontFamily: "'Fira Code', var(--font-mono), monospace",
          color: 'var(--kaspa-teal)',
          marginTop: '6px'
        }}>
          {formatHashrate(hashrateTh)}
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px' }}>
          Accepted: {stats?.acceptedShares ?? bridge?.acceptedShares ?? 0}
        </div>
      </div>

      {/* 2. Active Miners */}
      <div className="card" style={{ padding: '18px' }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>
          Active Miners
        </div>
        <div style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          fontFamily: "'Fira Code', var(--font-mono), monospace",
          color: 'var(--text-primary)',
          marginTop: '6px'
        }}>
          {activeMiners}
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px' }}>
          Port: 55555 stratum
        </div>
      </div>

      {/* 3. Blocks 24H */}
      <div className="card" style={{ padding: '18px' }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>
          Blocks (24H)
        </div>
        <div style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          fontFamily: "'Fira Code', var(--font-mono), monospace",
          color: '#34D399',
          marginTop: '6px'
        }}>
          {blocks24h}
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px' }}>
          Solo Solved Blocks
        </div>
      </div>

      {/* 4. Round Effort */}
      <div className="card" style={{ padding: '18px' }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>
          Round Effort
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          marginTop: '6px'
        }}>
          <span style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            fontFamily: 'var(--font-mono)',
            color: isLucky ? '#10B981' : '#F59E0B'
          }}>
            {effort}%
          </span>
          <span style={{
            fontSize: '0.75rem',
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: '10px',
            backgroundColor: isLucky ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
            color: isLucky ? '#10B981' : '#F59E0B'
          }}>
            {isLucky ? 'Lucky' : 'Normal'}
          </span>
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px' }}>
          Target ~100% avg
        </div>
      </div>
    </div>
  );
}

export function HashrateTrendChart() {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    fetch('/api/history?range=24h')
      .then(res => res.json())
      .then(data => setHistory(data.data || []))
      .catch(() => {});
  }, []);

  const points = history.length > 0 ? history : [
    { timeLabel: '00:00', hashrate: 0 },
    { timeLabel: '12:00', hashrate: 0 },
    { timeLabel: '24:00', hashrate: 0 }
  ];

  const maxHash = Math.max(1, ...points.map(p => p.hashrate || 0));
  const svgWidth = 500;
  const svgHeight = 120;
  const padding = 20;

  const coords = points.map((p, i) => {
    const x = padding + (i / Math.max(1, points.length - 1)) * (svgWidth - padding * 2);
    const y = svgHeight - padding - ((p.hashrate || 0) / maxHash) * (svgHeight - padding * 2);
    return { x, y, label: p.timeLabel };
  });

  const pathD = coords.reduce((acc, c, i) => (
    i === 0 ? `M ${c.x},${c.y}` : `${acc} L ${c.x},${c.y}`
  ), '');

  const areaD = `${pathD} L ${coords[coords.length - 1].x},${svgHeight - padding} L ${coords[0].x},${svgHeight - padding} Z`;

  return (
    <div className="card" style={{ marginTop: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 className="card-title" style={{ marginBottom: 0 }}>24-Hour Hashrate Trend</h3>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Peak: {maxHash.toFixed(2)} TH/s
        </span>
      </div>
      <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: '100%', height: '140px', overflow: 'visible' }}>
        <defs>
          <linearGradient id="hashrate-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#70C7BA" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#70C7BA" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <line x1={padding} y1={padding} x2={svgWidth - padding} y2={padding} stroke="var(--bg-surface-hover)" strokeDasharray="3 3" />
        <line x1={padding} y1={svgHeight / 2} x2={svgWidth - padding} y2={svgHeight / 2} stroke="var(--bg-surface-hover)" strokeDasharray="3 3" />
        <line x1={padding} y1={svgHeight - padding} x2={svgWidth - padding} y2={svgHeight - padding} stroke="var(--bg-surface-hover)" />
        <path d={areaD} fill="url(#hashrate-grad)" />
        <path d={pathD} fill="none" stroke="#70C7BA" strokeWidth="2.5" />
        <text x={padding} y={svgHeight - 4} fill="var(--text-secondary)" fontSize="10">24h ago</text>
        <text x={svgWidth - padding} y={svgHeight - 4} textAnchor="end" fill="var(--text-secondary)" fontSize="10">Now</text>
      </svg>
    </div>
  );
}

export function GhostdagCanvas() {
  const canvasRef = React.useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let lastBlockTime = performance.now();

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = (rect.width || 600) * dpr;
    canvas.height = 140 * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width || 600;
    const height = 140;

    let blocks = [];
    let idCounter = 0;

    const spawnBlock = (now) => {
      idCounter++;
      const isBlue = Math.random() > 0.15;
      const yPos = isBlue ? height / 2 + (Math.random() * 20 - 10) : (Math.random() > 0.5 ? 30 : height - 30);
      
      const newBlock = {
        id: idCounter,
        x: width + 20,
        y: yPos,
        radius: isBlue ? 7 : 5,
        isBlue,
        parents: blocks.filter(b => b.x > width - 180).slice(-2),
      };
      blocks.push(newBlock);
    };

    for (let i = 0; i < 15; i++) {
      idCounter++;
      const isBlue = Math.random() > 0.15;
      const yPos = isBlue ? height / 2 + (Math.random() * 20 - 10) : (Math.random() > 0.5 ? 30 : height - 30);
      blocks.push({
        id: idCounter,
        x: (width / 15) * i,
        y: yPos,
        radius: isBlue ? 7 : 5,
        isBlue,
        parents: [],
      });
    }

    const render = (now) => {
      if (now - lastBlockTime >= 100) {
        spawnBlock(now);
        lastBlockTime = now;
      }

      ctx.clearRect(0, 0, width, height);

      for (const b of blocks) {
        b.x -= 2.2;
      }
      blocks = blocks.filter(b => b.x >= -30);

      for (const b of blocks) {
        for (const p of b.parents) {
          ctx.beginPath();
          ctx.moveTo(b.x, b.y);
          ctx.lineTo(p.x, p.y);
          ctx.strokeStyle = b.isBlue && p.isBlue ? 'rgba(112, 199, 186, 0.35)' : 'rgba(239, 68, 68, 0.25)';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }

      for (const b of blocks) {
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.radius, 0, Math.PI * 2);
        ctx.fillStyle = b.isBlue ? '#70C7BA' : '#EF4444';
        ctx.shadowColor = b.isBlue ? 'rgba(112, 199, 186, 0.8)' : 'rgba(239, 68, 68, 0.8)';
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, []);

  return (
    <div className="card" style={{ marginTop: '24px', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 className="card-title" style={{ marginBottom: 0 }}>GHOSTDAG 10 BPS Consensus Stream</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            display: 'inline-block',
            width: '8px', height: '8px',
            borderRadius: '50%', backgroundColor: '#70C7BA',
            boxShadow: '0 0 8px #70C7BA'
          }} />
          <span style={{ fontSize: '0.8rem', color: 'var(--kaspa-teal)', fontWeight: 600 }}>
            10 BPS Live
          </span>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '140px',
          backgroundColor: '#0A0A0C',
          borderRadius: 'var(--radius-sm)',
          display: 'block',
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#70C7BA', display: 'inline-block' }} />
          Selected Chain (Blue Blocks)
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#EF4444', display: 'inline-block' }} />
          Parallel Merged (Red Blocks)
        </span>
      </div>
    </div>
  );
}

function App() {
  const [status, setStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [showCelebration, setShowCelebration] = useState(false);
  
  useEffect(() => {
    const pollBlockEvent = async () => {
      try {
        const res = await fetch('/api/block_event');
        const data = await res.json();
        if (data.blockFound) {
          setShowCelebration(true);
          setAlerts(prev => {
            const newAlert = { id: `block-${Date.now()}`, message: `🎉 Block Found! Hash: ${data.hash}`, type: 'success' };
            return [newAlert, ...prev];
          });
        }
      } catch (e) {
        console.error(e);
      }
    };
    const int = setInterval(pollBlockEvent, 3000);
    return () => clearInterval(int);
  }, []);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        setStatus(data);
      } catch (err) {
        console.error("Failed to fetch status", err);
        setStatus({ error: true });
      }
    };
    
    fetchStatus();
    const int = setInterval(fetchStatus, 5000);
    return () => clearInterval(int);
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        setStats(data);
      } catch (err) {
        console.error("Failed to fetch stats", err);
      }
    };

    fetchStats();
    const int = setInterval(fetchStats, 5000);
    return () => clearInterval(int);
  }, []);

  let dotColor = 'yellow';
  let message = 'Loading...';
  let showProgress = false;

  if (status?.error) {
    dotColor = 'red';
    message = 'Error connecting to backend API.';
  } else if (status) {
    if (status.node?.stage === 1) {
      dotColor = 'yellow';
      message = status.node.syncMessage || 'Validating DAG Pruning Proofs (~92k headers)... Network consensus verification in progress.';
      showProgress = true;
    } else if (status.node?.stage === 2) {
      dotColor = 'yellow';
      message = status.node.syncMessage || 'Catching up DAG headers to network tip...';
      showProgress = true;
    } else if (status.node?.isSynced || status.node?.stage === 3) {
      if (status.bridge?.status === 'connected') {
        dotColor = 'green';
        message = 'Synchronized (10 BPS) • Mining Active';
      } else {
        dotColor = 'yellow';
        message = 'Synchronized (10 BPS) • Waiting for ASIC connection on port 55555...';
      }
    } else if (status.bridge?.status === 'waiting') {
      dotColor = 'yellow';
      message = 'Waiting for ASIC connection on port 55555...';
    }
  }

  return (
    <div className="app-container">
      {showCelebration && <BlockCelebration onComplete={() => setShowCelebration(false)} />}
      <header className="app-header">
        <h1>Kaspa Solo Mining</h1>
      </header>
      
      <aside className="app-sidebar">
        <nav>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            <li style={{ marginBottom: '16px', color: 'var(--kaspa-teal)', fontWeight: '500' }}>Dashboard</li>
            <li style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>Settings</li>
          </ul>
        </nav>
      </aside>
      
      <main className="app-main">
        {alerts.map(alert => (
          <div key={alert.id} style={{
            backgroundColor: alert.type === 'success' ? 'rgba(112, 199, 186, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${alert.type === 'success' ? '#70C7BA' : '#EF4444'}`,
            color: alert.type === 'success' ? '#70C7BA' : '#EF4444',
            padding: '12px 16px',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span>{alert.message}</span>
            <button 
              onClick={() => setAlerts(alerts.filter(a => a.id !== alert.id))}
              style={{
                background: 'transparent', border: 'none', color: alert.type === 'success' ? '#70C7BA' : '#EF4444', cursor: 'pointer', fontSize: '1.2rem'
              }}
            >×</button>
          </div>
        ))}

        {/* Story 1.2: Multi-Stage Initial Block Download (IBD) Banner */}
        <SyncBanner sync={status?.node} />

        {/* Story 2.2: Primary Metric Cards Grid */}
        <MetricCardsGrid stats={stats} bridge={status?.bridge} />

        {/* Story 2.2: Live 10 BPS GHOSTDAG Canvas Visualizer */}
        <GhostdagCanvas />

        {/* Story 2.2: 24-Hour Hashrate Trend Chart */}
        <HashrateTrendChart />
        
        <div className="card" style={{ marginTop: '24px' }}>
          <h2 className="card-title">
            <GlowingDot color={dotColor} />
            System Status
          </h2>
          
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 20px',
            backgroundColor: 'var(--bg-base)',
            borderRadius: 'var(--radius-sm)',
            marginTop: '16px'
          }}>
            {showProgress && (
              <div style={{ marginBottom: '16px' }}>
                <CircularProgress progress={status.node.progress || status.node.percent || 0} />
                <div style={{ textAlign: 'center', marginTop: '8px', color: 'var(--text-secondary)' }}>
                  {status.node.progress || status.node.percent || 0}%
                </div>
              </div>
            )}
            
            <p style={{ color: dotColor === 'red' ? '#EF4444' : 'var(--text-secondary)', textAlign: 'center' }}>
              {message}
            </p>
          </div>
          
          <PresetSelector />
        </div>

        {/* Story 1.2: Multi-Stage IBD Progress Card */}
        <SyncProgressCard sync={status?.node} />

        {/* Story 1.3: Dual ASIC Stratum Connection Point & Quick-Copy */}
        <AsicConnectionCard connection={status?.bridge?.connection} />
        
        <HealthMonitor setAlerts={setAlerts} />
        
        <ProfitabilityWidget />
        <RewardsChart />
        
        <LogViewer />
      </main>
    </div>
  );
}

export default App;

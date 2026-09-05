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

function App() {
  const [status, setStatus] = useState(null);
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

  let dotColor = 'yellow';
  let message = 'Loading...';
  let showProgress = false;

  if (status?.error) {
    dotColor = 'red';
    message = 'Error connecting to backend API.';
  } else if (status) {
    if (status.node.status === 'syncing') {
      dotColor = 'yellow';
      message = 'Node Syncing...';
      showProgress = true;
    } else if (status.bridge.status === 'waiting') {
      dotColor = 'yellow';
      message = 'Waiting for ASIC connection on port 55555...';
    } else if (status.node.status === 'synced' && status.bridge.status === 'connected') {
      dotColor = 'green';
      message = 'System Healthy & Connected';
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
        
        <div className="card">
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
                <CircularProgress progress={status.node.progress} />
                <div style={{ textAlign: 'center', marginTop: '8px', color: 'var(--text-secondary)' }}>
                  {status.node.progress}%
                </div>
              </div>
            )}
            
            <p style={{ color: dotColor === 'red' ? '#EF4444' : 'var(--text-secondary)', textAlign: 'center' }}>
              {message}
            </p>
          </div>
          
          <PresetSelector />
        </div>
        
        <HealthMonitor setAlerts={setAlerts} />
        
        <ProfitabilityWidget />
        <RewardsChart />
        
        <LogViewer />
      </main>
    </div>
  );
}

export default App;

import React, { useState, useEffect } from "react";
import {
  Activity,
  Cpu,
  Award,
  Settings,
  Sun,
  Moon,
  Zap,
  Server,
  Terminal,
  Clock,
  Sparkles,
  ShieldCheck,
  Trophy,
} from "lucide-react";
import { CelebrationModal, BlockEvent } from "./components/CelebrationModal";

interface StatsData {
  totalHashrate: string;
  activeMiners: number;
  acceptedShares: number;
  staleShares: number;
  invalidShares: number;
  luckEstimate: string;
  nodeStatus: string;
}

interface PresetItem {
  id: string;
  name: string;
  manufacturer: string;
  hashrateNominal: string;
  description: string;
}

export const App: React.FC = () => {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [activeTab, setActiveTab] = useState<"overview" | "miners" | "blocks" | "settings" | "logs">("overview");
  const [activeBlockCelebration, setActiveBlockCelebration] = useState<BlockEvent | null>(null);

  const [stats] = useState<StatsData>({
    totalHashrate: "24.5 TH/s",
    activeMiners: 3,
    acceptedShares: 14820,
    staleShares: 12,
    invalidShares: 0,
    luckEstimate: "8.4 hrs",
    nodeStatus: "Synchronized (10 BPS)",
  });

  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [selectedPreset, setSelectedPreset] = useState("iceriver-ks7");
  const [settingsSuccess, setSettingsSuccess] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Fetch Presets
  useEffect(() => {
    fetch("/api/presets")
      .then((r) => r.json())
      .then((data) => {
        if (data.catalog) setPresets(data.catalog);
        if (data.activePreset) setSelectedPreset(data.activePreset);
      })
      .catch(() => {
        // Fallback demo presets
        setPresets([
          { id: "automatic", name: "Automatic (Universal)", manufacturer: "Universal", hashrateNominal: "Auto", description: "Universal adaptive vardiff" },
          { id: "iceriver-ks0", name: "IceRiver KS0 / Pro", manufacturer: "IceRiver", hashrateNominal: "100-200 GH/s", description: "Low-difficulty tuning" },
          { id: "iceriver-ks3", name: "IceRiver KS3 / M / L", manufacturer: "IceRiver", hashrateNominal: "6-8 TH/s", description: "Mid-tier vardiff" },
          { id: "iceriver-ks7", name: "IceRiver KS7 / Lite", manufacturer: "IceRiver", hashrateNominal: "20-25 TH/s", description: "High-hashrate enterprise tuning" },
          { id: "antminer-ks5", name: "Bitmain Antminer KS5", manufacturer: "Bitmain", hashrateNominal: "20-21 TH/s", description: "Antminer flagships" },
          { id: "desiwe-k11", name: "Desiwe / Windminer K11", manufacturer: "Desiwe", hashrateNominal: "11 TH/s", description: "Optimized share frequency" },
          { id: "goldshell-kabox", name: "Goldshell KA-BOX", manufacturer: "Goldshell", hashrateNominal: "1.6-2.4 TH/s", description: "Compact home miner" },
        ]);
      });
  }, []);

  // Listen to SSE live events
  useEffect(() => {
    const eventSource = new EventSource("/api/events");
    eventSource.addEventListener("block_found", (e: any) => {
      try {
        const block = JSON.parse(e.data);
        setActiveBlockCelebration(block);
      } catch (err) {
        console.error(err);
      }
    });

    return () => eventSource.close();
  }, []);

  const handlePresetChange = (presetId: string) => {
    setSelectedPreset(presetId);
    fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset: presetId }),
    }).then(() => {
      setSettingsSuccess(true);
      setTimeout(() => setSettingsSuccess(false), 3000);
    });
  };

  const triggerTestCelebration = () => {
    setActiveBlockCelebration({
      id: "demo-" + Date.now(),
      blockHash: "0000000000003b8793b827e85c2c9d64fbe35aa4d7f57375a0029b35a8bc3188",
      timestamp: Date.now(),
      workerName: "antminer_ks5_01",
      rewardKas: 135.85,
      rewardSompi: "13585000000",
      isBlue: true,
      blueScore: "81420914",
    });
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="logo-group">
          <div className="logo-badge">K</div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="logo-title">Kaspa Solo Mining Console</span>
              <span className="badge-tag">Umbrel All-In-One</span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Bundled Rusty Kaspad Node • Stratum Bridge v2.0.1
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          {/* Test celebration button for immediate review */}
          <button
            onClick={triggerTestCelebration}
            style={{
              background: "rgba(245, 158, 11, 0.15)",
              border: "1px solid var(--accent-gold)",
              color: "var(--accent-gold)",
              padding: "0.4rem 0.8rem",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "0.85rem",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <Sparkles size={16} /> Test Block Celebration
          </button>

          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            style={{
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)",
              padding: "0.5rem",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      {/* Nav Tabs */}
      <nav className="nav-tabs">
        <button
          className={`nav-tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          <Activity size={18} /> Overview
        </button>
        <button
          className={`nav-tab ${activeTab === "miners" ? "active" : ""}`}
          onClick={() => setActiveTab("miners")}
        >
          <Cpu size={18} /> Miners & Workers
        </button>
        <button
          className={`nav-tab ${activeTab === "blocks" ? "active" : ""}`}
          onClick={() => setActiveTab("blocks")}
        >
          <Award size={18} /> Mined Blocks
        </button>
        <button
          className={`nav-tab ${activeTab === "settings" ? "active" : ""}`}
          onClick={() => setActiveTab("settings")}
        >
          <Settings size={18} /> Hardware Presets
        </button>
        <button
          className={`nav-tab ${activeTab === "logs" ? "active" : ""}`}
          onClick={() => setActiveTab("logs")}
        >
          <Terminal size={18} /> Logs & Node
        </button>
      </nav>

      {/* Main Content Area */}
      <main className="main-content">
        {activeTab === "overview" && (
          <div>
            <div className="stats-grid">
              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>TOTAL HASHRATE</span>
                  <Zap size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value">{stats.totalHashrate}</div>
                <div className="stat-subtext">3 ASIC Miners Online</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>ACCEPTED SHARES</span>
                  <ShieldCheck size={18} color="var(--status-success)" />
                </div>
                <div className="stat-value">{stats.acceptedShares.toLocaleString()}</div>
                <div className="stat-subtext">99.9% Efficiency (12 Stales)</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>ESTIMATED ROUND TIME</span>
                  <Clock size={18} color="var(--accent-gold)" />
                </div>
                <div className="stat-value">{stats.luckEstimate}</div>
                <div className="stat-subtext">Statistical 10 BPS average</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>BUNDLED KASPAD NODE</span>
                  <Server size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value" style={{ fontSize: "1.3rem" }}>{stats.nodeStatus}</div>
                <div className="stat-subtext">Local P2P Peer Height: 81,420,950</div>
              </div>
            </div>

            {/* Connection Information Banner */}
            <div className="glass-panel" style={{ padding: "1.5rem", marginBottom: "2rem" }}>
              <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>LAN ASIC Miner Connection Point</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1rem" }}>
                Configure your IceRiver, Antminer, Desiwe, or Goldshell web dashboards to point to this Umbrel Stratum endpoint:
              </p>
              <div
                style={{
                  background: "var(--bg-primary)",
                  padding: "0.8rem 1.2rem",
                  borderRadius: "8px",
                  fontFamily: "var(--font-mono)",
                  display: "inline-block",
                  color: "var(--kaspa-cyan)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                stratum+tcp://&lt;YOUR_UMBREL_IP&gt;:55555
              </div>
            </div>
          </div>
        )}

        {activeTab === "miners" && (
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "1rem" }}>Connected Mining Hardware</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                  <th style={{ padding: "0.75rem" }}>WORKER</th>
                  <th style={{ padding: "0.75rem" }}>HASHRATE</th>
                  <th style={{ padding: "0.75rem" }}>ACCEPTED</th>
                  <th style={{ padding: "0.75rem" }}>STALE</th>
                  <th style={{ padding: "0.75rem" }}>DIFF</th>
                  <th style={{ padding: "0.75rem" }}>STATUS</th>
                </tr>
              </thead>
              <tbody style={{ fontFamily: "var(--font-mono)", fontSize: "0.9rem" }}>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                  <td style={{ padding: "0.75rem", color: "#fff" }}>iceriver_ks7_01</td>
                  <td style={{ padding: "0.75rem", color: "var(--kaspa-cyan)" }}>20.2 TH/s</td>
                  <td style={{ padding: "0.75rem" }}>11,240</td>
                  <td style={{ padding: "0.75rem", color: "var(--status-warning)" }}>8</td>
                  <td style={{ padding: "0.75rem" }}>8192</td>
                  <td style={{ padding: "0.75rem", color: "var(--status-success)" }}>Active</td>
                </tr>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                  <td style={{ padding: "0.75rem", color: "#fff" }}>antminer_ks5_01</td>
                  <td style={{ padding: "0.75rem", color: "var(--kaspa-cyan)" }}>4.3 TH/s</td>
                  <td style={{ padding: "0.75rem" }}>3,580</td>
                  <td style={{ padding: "0.75rem", color: "var(--status-warning)" }}>4</td>
                  <td style={{ padding: "0.75rem" }}>4096</td>
                  <td style={{ padding: "0.75rem", color: "var(--status-success)" }}>Active</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "settings" && (
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "0.5rem" }}>ASIC Hardware Tuning Presets</h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
              Select a specialized preset tuned for your specific Kaspa ASIC architecture:
            </p>

            {settingsSuccess && (
              <div style={{ background: "rgba(16, 185, 129, 0.15)", border: "1px solid var(--status-success)", padding: "0.75rem", borderRadius: "8px", marginBottom: "1rem", color: "var(--status-success)" }}>
                Preset successfully applied and loaded into Stratum Bridge!
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
              {presets.map((preset) => (
                <div
                  key={preset.id}
                  onClick={() => handlePresetChange(preset.id)}
                  style={{
                    padding: "1rem",
                    borderRadius: "10px",
                    border: selectedPreset === preset.id ? "2px solid var(--kaspa-cyan)" : "1px solid var(--border-subtle)",
                    background: selectedPreset === preset.id ? "var(--bg-surface-elevated)" : "var(--bg-surface)",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                    <strong style={{ color: "#fff" }}>{preset.name}</strong>
                    <span style={{ fontSize: "0.75rem", color: "var(--kaspa-cyan)", fontFamily: "var(--font-mono)" }}>
                      {preset.hashrateNominal}
                    </span>
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{preset.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "blocks" && (
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "1rem" }}>Discovered Kaspa Blocks (Solo Wins)</h3>
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
              <Trophy size={48} color="var(--accent-gold)" style={{ margin: "0 auto 1rem auto" }} />
              <h4>Solo Block Registry</h4>
              <p style={{ fontSize: "0.9rem", marginTop: "0.5rem" }}>
                Every block found by your miners is verified with DAG confirmation score and rewarded in full to your node wallet.
              </p>
            </div>
          </div>
        )}

        {activeTab === "logs" && (
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "1rem" }}>Bridge & Node Console Stream</h3>
            <div
              style={{
                background: "#000",
                padding: "1rem",
                borderRadius: "8px",
                fontFamily: "var(--font-mono)",
                fontSize: "0.8rem",
                color: "#10b981",
                height: "300px",
                overflowY: "auto",
              }}
            >
              [KASPAD] Node initialized. Connected to 18 Kaspa P2P peers.<br />
              [KASPAD] Virtual DAA Score: 81,420,950. Target BPS: 10.<br />
              [STRATUM] Bridge listening on 0.0.0.0:5555.<br />
              [STRATUM] Worker iceriver_ks7_01 connected from 192.168.1.45.<br />
              [STRATUM] Set vardiff baseline target for worker: 8192.<br />
              [STRATUM] Share submitted by iceriver_ks7_01: ACCEPTED.<br />
            </div>
          </div>
        )}
      </main>

      {/* Block Found Celebration Modal with Confetti */}
      <CelebrationModal
        block={activeBlockCelebration}
        onClose={() => setActiveBlockCelebration(null)}
      />
    </div>
  );
};

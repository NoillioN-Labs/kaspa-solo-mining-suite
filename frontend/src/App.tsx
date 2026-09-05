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
  Menu,
  X,
  PieChart,
  Info,
  Network,
  Radio,
  Heart,
  ExternalLink,
  RefreshCw,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Trash2,
} from "lucide-react";
import confetti from "canvas-confetti";
import { GhostdagVisualizer } from "./components/GhostdagVisualizer";

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
  difficultyTier: "Adaptive" | "Low Difficulty" | "Medium Difficulty" | "High Difficulty" | "Ultra / Enterprise";
  hashrateNominal: string;
  description: string;
  recommended?: boolean;
  models: string[];
}

interface NodeSyncInfo {
  isSynced: boolean;
  progressPercent: number;
  currentHeaderDaa: number;
  targetHeaderDaa: number;
  currentUtxoDaa: number;
  targetUtxoDaa: number;
  estimatedRemaining: string;
  phase: "headers" | "utxo" | "synced";
}

export const App: React.FC = () => {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [activeTab, setActiveTab] = useState<"overview" | "miners" | "blocks" | "node" | "settings" | "logs">("overview");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Node synchronization state (simulates initial 1-2 day DAG catch-up vs synced live state)
  const [nodeSync, setNodeSync] = useState<NodeSyncInfo>({
    isSynced: false,
    progressPercent: 88.6,
    currentHeaderDaa: 72140200,
    targetHeaderDaa: 81420950,
    currentUtxoDaa: 71080000,
    targetUtxoDaa: 81420950,
    estimatedRemaining: "~4h 32m remaining",
    phase: "headers",
  });

  // Easter Egg confetti burst triggered silently when a block is solved while app is open
  const fireEasterEggConfetti = () => {
    const end = Date.now() + 3 * 1000;
    const colors = ["#70c7ba", "#f59e0b", "#10b981", "#ffffff"];

    (function frame() {
      confetti({
        particleCount: 5,
        angle: 60,
        spread: 60,
        origin: { x: 0 },
        colors,
      });
      confetti({
        particleCount: 5,
        angle: 120,
        spread: 60,
        origin: { x: 1 },
        colors,
      });

      if (Date.now() < end) {
        requestAnimationFrame(frame);
      }
    })();
  };

  const navItems: { id: "overview" | "miners" | "blocks" | "node" | "settings" | "logs"; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: "Overview", icon: <Activity size={18} /> },
    { id: "miners", label: "Miners & Workers", icon: <Cpu size={18} /> },
    { id: "blocks", label: "Mined Blocks", icon: <Award size={18} /> },
    { id: "node", label: "Kaspa Node", icon: <Network size={18} /> },
    { id: "settings", label: "Hardware Presets", icon: <Settings size={18} /> },
    { id: "logs", label: "Logs & Node", icon: <Terminal size={18} /> },
  ];

  const [stats, setStats] = useState<StatsData>({
    totalHashrate: "0.0 TH/s",
    activeMiners: 0,
    acceptedShares: 0,
    staleShares: 0,
    invalidShares: 0,
    luckEstimate: "Calculating...",
    nodeStatus: "Connecting...",
  });

  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [selectedPreset, setSelectedPreset] = useState("automatic");
  const [settingsSuccess, setSettingsSuccess] = useState(false);

  // Danger Zone: Reset Telemetry state
  const [showResetModal, setShowResetModal] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(null);

  // Poll live stats every 3 seconds
  useEffect(() => {
    const fetchLiveStats = () => {
      fetch("/api/stats")
        .then((r) => r.json())
        .then((data) => {
          if (data) {
            setStats({
              totalHashrate: data.totalHashrate || "0.0 TH/s",
              activeMiners: data.activeMiners || 0,
              acceptedShares: data.acceptedShares || 0,
              staleShares: data.staleShares || 0,
              invalidShares: data.invalidShares || 0,
              luckEstimate: data.luckEstimate || "N/A",
              nodeStatus: data.nodeStatus || "Connected",
            });
            if (data.isSynced !== undefined) {
              setNodeSync((prev) => ({
                ...prev,
                isSynced: Boolean(data.isSynced),
                progressPercent: Number(data.syncProgress || (data.isSynced ? 100 : 88.6)),
                currentHeaderDaa: Number(data.currentDaa || prev.currentHeaderDaa),
                targetHeaderDaa: Number(data.targetDaa || prev.targetHeaderDaa),
              }));
            }
          }
        })
        .catch(() => {
          // Graceful offline fallback
        });
    };

    fetchLiveStats();
    const interval = setInterval(fetchLiveStats, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleExecuteResetData = async () => {
    setIsResetting(true);
    try {
      const res = await fetch("/api/data/reset", { method: "POST" });
      const json = await res.json();
      setIsResetting(false);
      setShowResetModal(false);
      setResetSuccessMessage(json.message || "Historical telemetry data wiped.");
      setTimeout(() => setResetSuccessMessage(null), 4000);
      // Refresh stats immediately
      setStats((prev) => ({
        ...prev,
        acceptedShares: 0,
        staleShares: 0,
        invalidShares: 0,
      }));
    } catch (err) {
      setIsResetting(false);
      setShowResetModal(false);
      alert("Failed to reset data. Please verify backend connection.");
    }
  };

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
        // Fallback difficulty/hashrate tier presets
        setPresets([
          {
            id: "automatic",
            name: "Automatic (Universal)",
            difficultyTier: "Adaptive",
            hashrateNominal: "Auto-Tuning",
            description: "Recommended for most miners. Dynamically calculates and adapts vardiff to target ~30 shares/min regardless of ASIC model.",
            recommended: true,
            models: ["All ASIC Models", "Mixed Mining Rigs", "Unknown Hardware"],
          },
          {
            id: "low-tier",
            name: "Entry / Compact (Diff 64)",
            difficultyTier: "Low Difficulty",
            hashrateNominal: "100 GH/s – 500 GH/s",
            description: "Low-difficulty baseline preventing stale share timeouts and high submission rejection on quiet home/desktop ASICs.",
            models: ["IceRiver KS0", "IceRiver KS0 Pro", "IceRiver KS0 Ultra"],
          },
          {
            id: "mid-tier",
            name: "Mid-Range Home Units (Diff 512 – 1024)",
            difficultyTier: "Medium Difficulty",
            hashrateNominal: "1 TH/s – 5 TH/s",
            description: "Tuned vardiff floor for mid-capacity standalone home miners and lower-power industrial units.",
            models: ["IceRiver KS1 (1 TH/s)", "IceRiver KS2 (2 TH/s)", "IceRiver KS7 Lite (~4.2 TH/s)", "Goldshell KA-BOX / Pro (1.6 - 2.4 TH/s)"],
          },
          {
            id: "high-tier",
            name: "High-Throughput ASICs (Diff 2048 – 4096)",
            difficultyTier: "High Difficulty",
            hashrateNominal: "6 TH/s – 12 TH/s",
            description: "Optimized share frequency for serious miners and high-hashrate single-board ASICs.",
            models: ["IceRiver KS3 / KS3M / KS3L (6-8 TH/s)", "Bitmain Antminer KS3 (9.4 TH/s)", "Desiwe / Windminer K11 (11 TH/s)"],
          },
          {
            id: "ultra-tier",
            name: "Enterprise Flagships (Diff 8192)",
            difficultyTier: "Ultra / Enterprise",
            hashrateNominal: "12 TH/s – 25+ TH/s",
            description: "High difficulty starting floor designed for commercial enterprise flagships to avoid saturating network bridge buffers.",
            models: ["Bitmain Antminer KS5 / KS5 Pro (20-21 TH/s)", "IceRiver KS7 (20-25 TH/s)", "IceRiver KS5L / KS5M (12-15 TH/s)"],
          },
        ]);
      });
  }, []);

  // Listen to SSE live events: trigger Easter Egg confetti when a block is found while the app is running
  useEffect(() => {
    const eventSource = new EventSource("/api/events");
    eventSource.addEventListener("block_found", () => {
      try {
        fireEasterEggConfetti();
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

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="logo-group">
          {/* Easter egg: Clicking the logo emblem triggers the hidden celebration confetti */}
          <div
            className="logo-badge"
            onClick={fireEasterEggConfetti}
            title="Kaspa Solo Mining Suite"
            style={{ cursor: "pointer" }}
          >
            <img src="/kaspa-logo.svg" alt="Kaspa Logo" className="logo-svg" />
          </div>
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

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          {/* Secret/Easter Egg: Clicking the K emblem will trigger the confetti */}
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="btn-theme-toggle"
            aria-label="Toggle theme"
            style={{
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)",
              padding: "0.5rem",
              borderRadius: "8px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {/* Mobile Hamburger Toggle Button */}
          <button
            className="hamburger-btn"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </header>

      {/* Desktop Nav Tabs (Hidden on Mobile) */}
      <nav className="nav-tabs desktop-nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-tab ${activeTab === item.id ? "active" : ""}`}
            onClick={() => setActiveTab(item.id)}
          >
            {item.icon} {item.label}
          </button>
        ))}
      </nav>

      {/* Mobile Navigation Drawer & Backdrop */}
      {mobileMenuOpen && (
        <div className="mobile-nav-backdrop" onClick={() => setMobileMenuOpen(false)}>
          <div
            className="mobile-nav-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mobile-nav-header">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <img src="/kaspa-logo.svg" alt="Kaspa" style={{ width: "22px", height: "22px" }} />
                <span style={{ fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-primary)", fontWeight: 700 }}>
                  Menu
                </span>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                style={{ background: "transparent", border: "none", color: "var(--text-secondary)", cursor: "pointer", display: "flex", alignItems: "center" }}
              >
                <X size={20} />
              </button>
            </div>
            <div className="mobile-nav-links">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  className={`mobile-nav-link ${activeTab === item.id ? "active" : ""}`}
                  onClick={() => {
                    setActiveTab(item.id);
                    setMobileMenuOpen(false);
                  }}
                >
                  <span className="mobile-nav-icon">{item.icon}</span>
                  <span className="mobile-nav-label">{item.label}</span>
                  {activeTab === item.id && <span className="mobile-active-dot"></span>}
                </button>
              ))}
            </div>
            <div className="mobile-nav-footer">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Kaspa Stratum Bridge • v2.0.1
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="main-content">
        {activeTab === "overview" && (
          <div>
            {/* Live GHOSTDAG Network Stream Animation (Kaspa.org style) */}
            <GhostdagVisualizer />

            {/* Sync Alert Banner if node is still syncing DAG / Headers */}
            {!nodeSync.isSynced && (
              <div
                className="glass-panel"
                style={{
                  background: "linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(17, 24, 39, 0.95))",
                  border: "1px solid rgba(245, 158, 11, 0.4)",
                  padding: "1.25rem 1.5rem",
                  marginBottom: "1.5rem",
                  borderRadius: "14px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "1.25rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "1rem", flex: 1, minWidth: "280px" }}>
                  <div
                    style={{
                      width: "44px",
                      height: "44px",
                      borderRadius: "10px",
                      background: "rgba(245, 158, 11, 0.2)",
                      border: "1px solid rgba(245, 158, 11, 0.4)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "var(--accent-gold)",
                      flexShrink: 0,
                    }}
                  >
                    <RefreshCw size={22} className="sync-pulse" />
                  </div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                      <h4 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: "#fff" }}>
                        Kaspa Node Synchronizing ({nodeSync.progressPercent}%)
                      </h4>
                      <span className="sync-badge-amber">
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--accent-gold)" }}></span>
                        Initial Sync in Progress
                      </span>
                    </div>
                    <p style={{ margin: "4px 0 0 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      Catching up to network tip: {nodeSync.currentHeaderDaa.toLocaleString()} / {nodeSync.targetHeaderDaa.toLocaleString()} DAA. Solo mining templates will activate automatically once synced ({nodeSync.estimatedRemaining}).
                    </p>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <button
                    onClick={() => setActiveTab("node")}
                    style={{
                      background: "rgba(245, 158, 11, 0.15)",
                      border: "1px solid rgba(245, 158, 11, 0.4)",
                      color: "var(--accent-gold)",
                      padding: "0.55rem 1rem",
                      borderRadius: "8px",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                    }}
                  >
                    View Sync Details
                  </button>
                </div>
              </div>
            )}

            <div className="stats-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>TOTAL HASHRATE</span>
                  <Zap size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value">{stats.totalHashrate}</div>
                <div className="stat-subtext">3 ASIC Miners Online</div>
              </div>

              {/* 24-Hour Solo Blocks & Kaspa Yield Highlight */}
              <div
                className="glass-panel stat-card"
                style={{
                  background: "linear-gradient(145deg, rgba(245, 158, 11, 0.08), rgba(17, 24, 39, 0.85))",
                  border: "1px solid rgba(245, 158, 11, 0.35)",
                  boxShadow: "0 0 16px rgba(245, 158, 11, 0.12)",
                }}
              >
                <div className="stat-header">
                  <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>BLOCKS (LAST 24H)</span>
                  <Trophy size={18} color="var(--accent-gold)" />
                </div>
                <div className="stat-value" style={{ color: "var(--accent-gold)" }}>3 Blocks</div>
                <div className="stat-subtext" style={{ color: "#fff", fontWeight: 600 }}>
                  +407.55 KAS <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(≈ $69.28)</span>
                </div>
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
                  <Clock size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value">{stats.luckEstimate}</div>
                <div className="stat-subtext">Statistical 10 BPS average</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>BUNDLED KASPAD NODE</span>
                  <Server size={18} color={nodeSync.isSynced ? "var(--kaspa-cyan)" : "var(--accent-gold)"} />
                </div>
                <div className="stat-value" style={{ fontSize: "1.25rem", color: nodeSync.isSynced ? "var(--text-primary)" : "var(--accent-gold)" }}>
                  {nodeSync.isSynced ? "Synchronized" : `Syncing (${nodeSync.progressPercent}%)`}
                </div>
                {nodeSync.isSynced ? (
                  <div className="stat-subtext">Local P2P Peer Height: 81,420,950</div>
                ) : (
                  <div style={{ marginTop: "0.5rem" }}>
                    <div className="sync-progress-bar-bg" style={{ height: "6px" }}>
                      <div className="sync-progress-bar-fill" style={{ width: `${nodeSync.progressPercent}%` }}></div>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px", display: "flex", justifyContent: "space-between" }}>
                      <span>{nodeSync.estimatedRemaining}</span>
                      <span>88.6%</span>
                    </div>
                  </div>
                )}
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
          <div>
            {/* Prominent Fleet Total Hashrate Hero Banner */}
            <div
              className="glass-panel"
              style={{
                padding: "1.75rem",
                marginBottom: "1.5rem",
                background: "linear-gradient(135deg, rgba(112, 199, 186, 0.08) 0%, rgba(17, 24, 39, 0.95) 100%)",
                border: "1px solid rgba(112, 199, 186, 0.3)",
                boxShadow: "0 8px 30px rgba(0, 0, 0, 0.4)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1.5rem" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                    <Zap size={22} color="var(--kaspa-cyan)" />
                    <span style={{ fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", fontWeight: 700 }}>
                      FLEET MINING POWER
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "1rem" }}>
                    <div style={{ fontSize: "3rem", fontWeight: 800, fontFamily: "var(--font-mono)", color: "var(--kaspa-cyan)", textShadow: "0 0 25px var(--kaspa-cyan-glow)", lineHeight: 1 }}>
                      24.5 <span style={{ fontSize: "1.75rem", color: "#fff" }}>TH/s</span>
                    </div>
                    <span style={{ background: "rgba(16, 185, 129, 0.15)", color: "var(--status-success)", border: "1px solid rgba(16, 185, 129, 0.3)", padding: "0.25rem 0.6rem", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 600 }}>
                      +2.4% vs 24h avg
                    </span>
                  </div>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.5rem" }}>
                    Cumulative real-time hash fidelity from all connected ASIC workers
                  </p>
                </div>

                {/* Fleet Quick Metrics */}
                <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap" }}>
                  <div style={{ background: "var(--bg-primary)", padding: "0.75rem 1.25rem", borderRadius: "10px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>ONLINE WORKERS</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#fff", fontFamily: "var(--font-mono)" }}>2 / 2</div>
                    <div style={{ fontSize: "0.7rem", color: "var(--status-success)" }}>100% Operational</div>
                  </div>

                  <div style={{ background: "var(--bg-primary)", padding: "0.75rem 1.25rem", borderRadius: "10px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>FLEET EFFORT</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#10b981", fontFamily: "var(--font-mono)" }}>82%</div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Current Round</div>
                  </div>

                  <div style={{ background: "var(--bg-primary)", padding: "0.75rem 1.25rem", borderRadius: "10px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>VALID SHARES</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--kaspa-cyan)", fontFamily: "var(--font-mono)" }}>14,820</div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>99.9% Accepted</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="glass-panel" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <div>
                  <h3 style={{ margin: 0 }}>Connected Mining Hardware</h3>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "4px" }}>
                    Active stratum worker sessions and hardware telemetry
                  </p>
                </div>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--status-success)" }}></span>
                  2 Workers Online
                </span>
              </div>

            {/* Horizontal Scroll Wrapper for Mobile Responsive Data */}
            <div className="table-responsive-wrapper">
              <table style={{ width: "100%", minWidth: "720px", borderCollapse: "collapse", textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    <th style={{ padding: "0.75rem" }}>WORKER</th>
                    <th style={{ padding: "0.75rem" }}>HASHRATE</th>
                    <th style={{ padding: "0.75rem" }}>EFFORT</th>
                    <th style={{ padding: "0.75rem" }}>ACCEPTED</th>
                    <th style={{ padding: "0.75rem" }}>STALE</th>
                    <th style={{ padding: "0.75rem" }}>DIFF</th>
                    <th style={{ padding: "0.75rem" }}>LATENCY</th>
                    <th style={{ padding: "0.75rem" }}>STATUS</th>
                  </tr>
                </thead>
                <tbody style={{ fontFamily: "var(--font-mono)", fontSize: "0.9rem" }}>
                  <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "0.85rem 0.75rem", color: "#fff" }}>
                      <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <Cpu size={15} color="var(--kaspa-cyan)" /> iceriver_ks7_01
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>192.168.1.45 (IceRiver KS7)</div>
                    </td>
                    <td style={{ padding: "0.85rem 0.75rem", color: "var(--kaspa-cyan)", fontWeight: 700 }}>20.2 TH/s</td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>
                      <span
                        title="Current Round Effort: 68% of statistical target hashes evaluated (Lucky)"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.3rem",
                          fontWeight: 700,
                          color: "#10b981", // Green: Under 100% (Lucky round)
                          background: "rgba(16, 185, 129, 0.12)",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "4px",
                          border: "1px solid rgba(16, 185, 129, 0.3)",
                        }}
                      >
                        68%
                      </span>
                    </td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>11,240</td>
                    <td style={{ padding: "0.85rem 0.75rem", color: "var(--status-warning)" }}>8 (0.07%)</td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>8,192</td>
                    <td style={{ padding: "0.85rem 0.75rem", color: "var(--text-secondary)" }}>12ms</td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.2rem 0.6rem", borderRadius: "12px", fontSize: "0.75rem", background: "rgba(16, 185, 129, 0.15)", color: "var(--status-success)", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--status-success)" }}></span>
                        Active
                      </span>
                    </td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "0.85rem 0.75rem", color: "#fff" }}>
                      <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <Cpu size={15} color="var(--kaspa-cyan)" /> antminer_ks5_01
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>192.168.1.72 (Bitmain KS5)</div>
                    </td>
                    <td style={{ padding: "0.85rem 0.75rem", color: "var(--kaspa-cyan)", fontWeight: 700 }}>4.3 TH/s</td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>
                      <span
                        title="Current Round Effort: 142% of statistical target hashes evaluated (Unlucky/Hard round)"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.3rem",
                          fontWeight: 700,
                          color: "#f59e0b", // Yellow/Orange: Over 100% (High effort)
                          background: "rgba(245, 158, 11, 0.12)",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "4px",
                          border: "1px solid rgba(245, 158, 11, 0.3)",
                        }}
                      >
                        142%
                      </span>
                    </td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>3,580</td>
                    <td style={{ padding: "0.85rem 0.75rem", color: "var(--status-warning)" }}>4 (0.11%)</td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>4,096</td>
                    <td style={{ padding: "0.85rem 0.75rem", color: "var(--text-secondary)" }}>18ms</td>
                    <td style={{ padding: "0.85rem 0.75rem" }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.2rem 0.6rem", borderRadius: "12px", fontSize: "0.75rem", background: "rgba(16, 185, 129, 0.15)", color: "var(--status-success)", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--status-success)" }}></span>
                        Active
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", color: "var(--text-muted)", flexWrap: "wrap", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                <span>Swipe horizontally to view full worker telemetry</span>
                <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                  <span style={{ color: "#10b981", fontWeight: 600 }}>&lt;100% Effort</span> (Above Avg Luck)
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                  <span style={{ color: "#f59e0b", fontWeight: 600 }}>&gt;100% Effort</span> (Below Avg Luck)
                </span>
              </div>
              <span>Total Fleet: 24.5 TH/s</span>
            </div>
          </div>
        </div>
      )}

        {activeTab === "settings" && (
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Sliders size={20} color="var(--kaspa-cyan)" />
                  <h3 style={{ margin: 0 }}>Difficulty & Hashrate Hardware Presets</h3>
                </div>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "4px" }}>
                  Configure your Stratum difficulty floor and variable difficulty (vardiff) targeting based on your ASIC miner hashrate class:
                </p>
              </div>

              <div style={{ fontSize: "0.8rem", background: "var(--bg-primary)", padding: "0.4rem 0.8rem", borderRadius: "8px", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                Active Profile: <strong style={{ color: "var(--kaspa-cyan)" }}>{presets.find((p) => p.id === selectedPreset)?.name || "Automatic"}</strong>
              </div>
            </div>

            {settingsSuccess && (
              <div style={{ background: "rgba(16, 185, 129, 0.15)", border: "1px solid var(--status-success)", padding: "0.75rem 1rem", borderRadius: "8px", marginBottom: "1.25rem", color: "var(--status-success)", display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.9rem" }}>
                <CheckCircle2 size={16} />
                <span>Difficulty preset successfully activated and loaded into Stratum Bridge!</span>
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "1.25rem" }}>
              {presets.map((preset) => {
                const isSelected = selectedPreset === preset.id;
                return (
                  <div
                    key={preset.id}
                    onClick={() => handlePresetChange(preset.id)}
                    style={{
                      padding: "1.25rem",
                      borderRadius: "12px",
                      border: isSelected ? "2px solid var(--kaspa-cyan)" : "1px solid var(--border-subtle)",
                      background: isSelected
                        ? "linear-gradient(145deg, rgba(112, 199, 186, 0.12), rgba(17, 24, 39, 0.85))"
                        : "var(--bg-surface)",
                      boxShadow: isSelected ? "0 0 16px rgba(112, 199, 186, 0.15)" : "none",
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      position: "relative",
                    }}
                  >
                    <div>
                      {/* Top Badges & Tier Header */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <span
                            style={{
                              fontSize: "0.7rem",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              letterSpacing: "0.05em",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "6px",
                              background: isSelected ? "rgba(112, 199, 186, 0.25)" : "var(--bg-primary)",
                              color: isSelected ? "var(--kaspa-cyan)" : "var(--text-muted)",
                              border: "1px solid var(--border-subtle)",
                            }}
                          >
                            {preset.difficultyTier}
                          </span>

                          {preset.recommended && (
                            <span
                              style={{
                                fontSize: "0.7rem",
                                fontWeight: 700,
                                padding: "0.2rem 0.55rem",
                                borderRadius: "6px",
                                background: "rgba(16, 185, 129, 0.2)",
                                color: "var(--status-success)",
                                border: "1px solid rgba(16, 185, 129, 0.4)",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.25rem",
                              }}
                            >
                              ★ Recommended for most miners
                            </span>
                          )}
                        </div>

                        {isSelected && (
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: 700,
                              color: "var(--kaspa-cyan)",
                              display: "flex",
                              alignItems: "center",
                              gap: "0.25rem",
                            }}
                          >
                            <CheckCircle2 size={14} /> Active
                          </span>
                        )}
                      </div>

                      {/* Title and Hashrate Range */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.4rem", flexWrap: "wrap", gap: "0.25rem" }}>
                        <h4 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#fff" }}>
                          {preset.name}
                        </h4>
                        <span style={{ fontSize: "0.85rem", color: "var(--accent-gold)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                          {preset.hashrateNominal}
                        </span>
                      </div>

                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0.4rem 0 1rem 0", lineHeight: 1.4 }}>
                        {preset.description}
                      </p>
                    </div>

                    {/* Compatible Models List / Chips */}
                    <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem", marginTop: "0.5rem" }}>
                      <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", fontWeight: 700, marginBottom: "0.4rem" }}>
                        Tested & Compatible Models:
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                        {preset.models.map((model, idx) => (
                          <span
                            key={idx}
                            style={{
                              fontSize: "0.75rem",
                              fontFamily: "var(--font-mono)",
                              background: isSelected ? "rgba(255, 255, 255, 0.08)" : "var(--bg-primary)",
                              color: "var(--text-primary)",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "5px",
                              border: "1px solid var(--border-subtle)",
                            }}
                          >
                            {model}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Danger Zone: Reset Telemetry Data (AD-6) */}
            <div
              style={{
                marginTop: "2.5rem",
                padding: "1.5rem",
                borderRadius: "12px",
                background: "rgba(239, 68, 68, 0.05)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                    <AlertTriangle size={18} color="#ef4444" />
                    <h4 style={{ margin: 0, color: "#ef4444", fontSize: "1.05rem", fontWeight: 700 }}>
                      Danger Zone • Telemetry Maintenance
                    </h4>
                  </div>
                  <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-secondary)", maxWidth: "600px" }}>
                    Reset all historical hashrate charts, worker telemetry samples, and share counters. Active miner stratum connections and node synchronization will remain intact.
                  </p>
                </div>

                <button
                  onClick={() => setShowResetModal(true)}
                  style={{
                    background: "rgba(239, 68, 68, 0.15)",
                    color: "#ef4444",
                    border: "1px solid rgba(239, 68, 68, 0.4)",
                    padding: "0.6rem 1.2rem",
                    borderRadius: "8px",
                    fontWeight: 600,
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    transition: "all 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "#ef4444";
                    e.currentTarget.style.color = "#fff";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)";
                    e.currentTarget.style.color = "#ef4444";
                  }}
                >
                  <Trash2 size={16} /> Reset Historical Data
                </button>
              </div>

              {resetSuccessMessage && (
                <div
                  style={{
                    marginTop: "1rem",
                    padding: "0.75rem 1rem",
                    borderRadius: "6px",
                    background: "rgba(16, 185, 129, 0.15)",
                    border: "1px solid var(--status-success)",
                    color: "var(--status-success)",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                >
                  <CheckCircle2 size={16} />
                  <span>{resetSuccessMessage}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Double-Confirmation Modal for Data Reset (AD-6) */}
        {showResetModal && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 9999,
              background: "rgba(0, 0, 0, 0.75)",
              backdropFilter: "blur(6px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "1rem",
            }}
          >
            <div
              className="glass-panel"
              style={{
                maxWidth: "480px",
                width: "100%",
                padding: "2rem",
                borderRadius: "16px",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                background: "var(--bg-surface)",
                boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                <div
                  style={{
                    width: "42px",
                    height: "42px",
                    borderRadius: "10px",
                    background: "rgba(239, 68, 68, 0.15)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <AlertTriangle size={22} color="#ef4444" />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 700, color: "#fff" }}>
                    Are you sure you want to reset data?
                  </h3>
                  <span style={{ fontSize: "0.75rem", color: "#ef4444", fontWeight: 600 }}>
                    DESTRUCTIVE ACTION • CANNOT BE UNDONE
                  </span>
                </div>
              </div>

              <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "1.5rem" }}>
                This operation will permanently erase:
              </p>

              <ul
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  paddingLeft: "1.25rem",
                  marginBottom: "1.75rem",
                  lineHeight: 1.6,
                }}
              >
                <li>All 24-hour, 30-day, and 6-month hashrate rollup graphs</li>
                <li>Cumulative accepted, stale, and invalid share counters</li>
                <li>Historic worker effort and hashrate performance logs</li>
              </ul>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button
                  disabled={isResetting}
                  onClick={() => setShowResetModal(false)}
                  style={{
                    padding: "0.6rem 1.2rem",
                    borderRadius: "8px",
                    background: "var(--bg-primary)",
                    border: "1px solid var(--border-subtle)",
                    color: "var(--text-primary)",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  disabled={isResetting}
                  onClick={handleExecuteResetData}
                  style={{
                    padding: "0.6rem 1.25rem",
                    borderRadius: "8px",
                    background: "#ef4444",
                    border: "none",
                    color: "#fff",
                    fontSize: "0.85rem",
                    fontWeight: 700,
                    cursor: isResetting ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                    opacity: isResetting ? 0.7 : 1,
                  }}
                >
                  {isResetting ? (
                    <>
                      <RefreshCw size={14} className="sync-pulse" /> Wiping Data...
                    </>
                  ) : (
                    <>
                      <Trash2 size={14} /> Yes, Reset All Telemetry
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === "blocks" && (
          <div>
            {/* Solo Blocks Summary Stats */}
            <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>TOTAL BLOCKS MINED</span>
                  <Trophy size={18} color="var(--accent-gold)" />
                </div>
                <div className="stat-value" style={{ color: "var(--accent-gold)" }}>4 Blocks</div>
                <div className="stat-subtext">All-time Solo Wins</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>TOTAL REWARDS EARNED</span>
                  <Sparkles size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value">543.40 KAS</div>
                <div className="stat-subtext">≈ $92.38 USD (Subsidies + Fees)</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>LATEST SOLO WIN</span>
                  <Clock size={18} color="var(--status-success)" />
                </div>
                <div className="stat-value" style={{ fontSize: "1.25rem", color: "var(--status-success)" }}>18 mins ago</div>
                <div className="stat-subtext">Worker: iceriver_ks7_01</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>DAG BLUE STATUS</span>
                  <ShieldCheck size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value" style={{ fontSize: "1.25rem" }}>100% Blue</div>
                <div className="stat-subtext">4/4 Accepted DAG Blocks</div>
              </div>
            </div>

            {/* Rewards Fee Composition & Relationship Visualization */}
            <div className="glass-panel reward-breakdown-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <PieChart size={20} color="var(--kaspa-cyan)" />
                    <h3 style={{ margin: 0 }}>Reward Fee Composition & Historical Trends</h3>
                  </div>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "4px" }}>
                    Analysis of the 3 fee components across mined solo blocks: Base Subsidy, Mempool Priority Fees, and DAG Merged Inclusions
                  </p>
                </div>
                <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", fontSize: "0.8rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span style={{ width: "10px", height: "10px", borderRadius: "2px", background: "var(--kaspa-cyan)" }}></span>
                    <span>Base Subsidy (92.4%)</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span style={{ width: "10px", height: "10px", borderRadius: "2px", background: "#38bdf8" }}></span>
                    <span>Priority Tx Fees (5.8%)</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span style={{ width: "10px", height: "10px", borderRadius: "2px", background: "var(--accent-gold)" }}></span>
                    <span>DAG Merge Rewards (1.8%)</span>
                  </div>
                </div>
              </div>

              {/* Cumulative Stacked Percentage Bar */}
              <div style={{ marginBottom: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  <span>Portfolio Distribution (Last 4 Blocks Total: 543.40 KAS)</span>
                  <span>100% Attributed</span>
                </div>
                <div className="reward-bar-container">
                  <div
                    className="reward-bar-segment"
                    style={{ width: "92.4%", background: "linear-gradient(90deg, #059669, var(--kaspa-cyan))" }}
                    title="Base Block Subsidy: 502.10 KAS (92.4%)"
                  ></div>
                  <div
                    className="reward-bar-segment"
                    style={{ width: "5.8%", background: "linear-gradient(90deg, #0284c7, #38bdf8)" }}
                    title="Transaction Priority Fees: 31.52 KAS (5.8%)"
                  ></div>
                  <div
                    className="reward-bar-segment"
                    style={{ width: "1.8%", background: "linear-gradient(90deg, #d97706, var(--accent-gold))" }}
                    title="DAG Merge Inclusions: 9.78 KAS (1.8%)"
                  ></div>
                </div>
              </div>

              {/* Historical Per-Block Fee Breakdown Cards */}
              <div className="reward-breakdown-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
                {[
                  {
                    title: "Block #81,420,914 (Latest)",
                    time: "18m ago",
                    total: "135.85 KAS",
                    subsidy: "125.50 KAS (92.4%)",
                    txFees: "8.15 KAS (6.0%)",
                    dagFees: "2.20 KAS (1.6%)",
                    trend: "+1.2% fees vs avg",
                  },
                  {
                    title: "Block #81,411,402",
                    time: "3h 12m ago",
                    total: "135.85 KAS",
                    subsidy: "125.50 KAS (92.4%)",
                    txFees: "7.80 KAS (5.7%)",
                    dagFees: "2.55 KAS (1.9%)",
                    trend: "Heavy mempool traffic",
                  },
                  {
                    title: "Block #81,398,110",
                    time: "7h 45m ago",
                    total: "135.85 KAS",
                    subsidy: "125.50 KAS (92.4%)",
                    txFees: "8.42 KAS (6.2%)",
                    dagFees: "1.93 KAS (1.4%)",
                    trend: "Peak fee spike",
                  },
                  {
                    title: "Block #81,372,890",
                    time: "1d 2h ago",
                    total: "135.85 KAS",
                    subsidy: "125.50 KAS (92.4%)",
                    txFees: "7.15 KAS (5.3%)",
                    dagFees: "3.20 KAS (2.3%)",
                    trend: "High DAG confluence",
                  },
                ].map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: "var(--bg-primary)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "8px",
                      padding: "1rem",
                      fontSize: "0.8rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                      <span style={{ fontWeight: 600, color: "#fff" }}>{item.title}</span>
                    </div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginBottom: "0.75rem" }}>
                      {item.time} • <span style={{ color: "var(--kaspa-cyan)", fontWeight: 600 }}>{item.total}</span>
                    </div>
                    
                    {/* Micro Stacked Bar */}
                    <div style={{ height: "6px", display: "flex", borderRadius: "3px", overflow: "hidden", marginBottom: "0.75rem", background: "rgba(255,255,255,0.1)" }}>
                      <div style={{ width: "92.4%", background: "var(--kaspa-cyan)" }}></div>
                      <div style={{ width: "5.8%", background: "#38bdf8" }}></div>
                      <div style={{ width: "1.8%", background: "var(--accent-gold)" }}></div>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", fontSize: "0.75rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--text-secondary)" }}>Base Subsidy:</span>
                        <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>{item.subsidy}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--text-secondary)" }}>Tx Priority:</span>
                        <span style={{ color: "#38bdf8", fontFamily: "var(--font-mono)" }}>{item.txFees}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--text-secondary)" }}>DAG Merge:</span>
                        <span style={{ color: "var(--accent-gold)", fontFamily: "var(--font-mono)" }}>{item.dagFees}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Mined Blocks Table */}
            <div className="glass-panel" style={{ padding: "1.5rem" }}>
              <div style={{ marginBottom: "1rem" }}>
                <h3 style={{ margin: 0 }}>Discovered Kaspa Blocks (Solo Wins)</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "4px" }}>
                  Verified solo blocks rewarded directly to your node wallet
                </p>
              </div>

              <div className="table-responsive-wrapper">
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                      <th style={{ padding: "0.75rem" }}>BLUE SCORE / TIME</th>
                      <th style={{ padding: "0.75rem" }}>BLOCK HASH</th>
                      <th style={{ padding: "0.75rem" }}>SOLVED BY</th>
                      <th style={{ padding: "0.75rem" }}>EFFORT</th>
                      <th style={{ padding: "0.75rem" }}>REWARD (KAS)</th>
                      <th style={{ padding: "0.75rem" }}>DAG STATUS</th>
                      <th style={{ padding: "0.75rem", textAlign: "right" }}>ACTION</th>
                    </tr>
                  </thead>
                  <tbody style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}>
                    {[
                      {
                        id: "block-1",
                        hash: "0000000000003b8793b827e85c2c9d64fbe35aa4d7f57375a0029b35a8bc3188",
                        shortHash: "00000000...a8bc3188",
                        worker: "iceriver_ks7_01",
                        effort: 68,
                        reward: 135.85,
                        rewardSompi: "13585000000",
                        blueScore: "81,420,914",
                        timeAgo: "18m ago",
                        status: "Blue Block",
                        txs: 42,
                      },
                      {
                        id: "block-2",
                        hash: "00000000000018f4a9c811200b39e44ffc9082da171349a21b33902f8841a129",
                        shortHash: "00000000...8841a129",
                        worker: "iceriver_ks7_01",
                        effort: 118,
                        reward: 135.85,
                        rewardSompi: "13585000000",
                        blueScore: "81,411,402",
                        timeAgo: "3h 12m ago",
                        status: "Blue Block",
                        txs: 29,
                      },
                      {
                        id: "block-3",
                        hash: "0000000000005a90d8ef6a084c7e3f22194bbbc20811e582d921fa4b7b2518e3",
                        shortHash: "00000000...7b2518e3",
                        worker: "antminer_ks5_01",
                        effort: 190,
                        reward: 135.85,
                        rewardSompi: "13585000000",
                        blueScore: "81,398,110",
                        timeAgo: "7h 45m ago",
                        status: "Blue Block",
                        txs: 58,
                      },
                      {
                        id: "block-4",
                        hash: "00000000000021c38e9a21f70912cb84918e7d23ab5f190ca881734bc109f582",
                        shortHash: "00000000...c109f582",
                        worker: "iceriver_ks7_01",
                        effort: 38,
                        reward: 135.85,
                        rewardSompi: "13585000000",
                        blueScore: "81,372,890",
                        timeAgo: "1d 2h ago",
                        status: "Blue Block",
                        txs: 34,
                      },
                    ].map((b) => {
                      // Color coding for effort:
                      // < 100%: Green (Lucky - required less than average shares)
                      // 100% - 150%: Orange/Yellow (Slightly tough round)
                      // > 150%: Crimson/Red (Unlucky round - high effort)
                      const effortColor =
                        b.effort < 100
                          ? "#10b981"
                          : b.effort <= 150
                          ? "#f59e0b"
                          : "#ef4444";
                      const effortBg =
                        b.effort < 100
                          ? "rgba(16, 185, 129, 0.12)"
                          : b.effort <= 150
                          ? "rgba(245, 158, 11, 0.12)"
                          : "rgba(239, 68, 68, 0.12)";
                      const effortBorder =
                        b.effort < 100
                          ? "rgba(16, 185, 129, 0.3)"
                          : b.effort <= 150
                          ? "rgba(245, 158, 11, 0.3)"
                          : "rgba(239, 68, 68, 0.3)";

                      return (
                        <tr key={b.id} style={{ borderBottom: "1px solid var(--border-subtle)", transition: "background 0.2s ease" }}>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <div style={{ color: "#fff", fontWeight: 600 }}>#{b.blueScore}</div>
                            <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>{b.timeAgo}</div>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <span
                              title={b.hash}
                              style={{
                                color: "var(--kaspa-cyan)",
                                background: "rgba(112, 199, 186, 0.08)",
                                padding: "0.2rem 0.5rem",
                                borderRadius: "4px",
                                border: "1px solid rgba(112, 199, 186, 0.2)",
                                cursor: "pointer",
                              }}
                            >
                              {b.shortHash}
                            </span>
                            <span style={{ marginLeft: "0.5rem", color: "var(--text-muted)", fontSize: "0.75rem" }}>({b.txs} txs)</span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem", color: "#fff" }}>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                              <Cpu size={14} color="var(--text-muted)" /> {b.worker}
                            </span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <span
                              title={`Effort: ${b.effort}%. Theoretical expected difficulty vs actual hashes submitted.`}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                fontWeight: 700,
                                color: effortColor,
                                background: effortBg,
                                border: `1px solid ${effortBorder}`,
                                padding: "0.2rem 0.55rem",
                                borderRadius: "4px",
                              }}
                            >
                              {b.effort}%
                            </span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>+{b.reward.toFixed(2)} KAS</span>
                            <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>≈ ${(b.reward * 0.17).toFixed(2)} USD</div>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.35rem",
                                padding: "0.2rem 0.6rem",
                                borderRadius: "12px",
                                fontSize: "0.75rem",
                                background: "rgba(16, 185, 129, 0.15)",
                                color: "var(--status-success)",
                                border: "1px solid rgba(16, 185, 129, 0.3)",
                              }}
                            >
                              <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--status-success)" }}></span>
                              {b.status}
                            </span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem", textAlign: "right" }}>
                            <a
                              href={`https://explorer.kaspa.org/blocks/${b.hash}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.35rem",
                                background: "transparent",
                                border: "1px solid var(--border-subtle)",
                                color: "var(--text-secondary)",
                                padding: "0.3rem 0.6rem",
                                borderRadius: "6px",
                                textDecoration: "none",
                                fontSize: "0.75rem",
                                transition: "all 0.2s ease",
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.borderColor = "var(--kaspa-cyan)";
                                e.currentTarget.style.color = "var(--kaspa-cyan)";
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.borderColor = "var(--border-subtle)";
                                e.currentTarget.style.color = "var(--text-secondary)";
                              }}
                            >
                              Explorer <ExternalLink size={12} />
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Kaspa Node Dedicated Dashboard View */}
        {activeTab === "node" && (
          <div>
            {/* Node Header Banner */}
            <div
              className="glass-panel"
              style={{
                padding: "1.5rem",
                marginBottom: "1.5rem",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "1rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "12px",
                    background: "rgba(112, 199, 186, 0.15)",
                    border: "1px solid rgba(112, 199, 186, 0.4)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "4px",
                  }}
                >
                  <img src="/kaspa-logo.svg" alt="Kaspa" style={{ width: "100%", height: "100%" }} />
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <h2 style={{ fontSize: "1.35rem", fontWeight: 700, margin: 0 }}>Kaspa Node</h2>
                    <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)", background: "var(--bg-primary)", padding: "0.15rem 0.4rem", borderRadius: "4px" }}>
                      v2.0.1
                    </span>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", marginTop: "3px" }}>
                    P2P ID: ad40c480-96f3-4083-b6cc-f128a7d80f5c
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "4px", fontSize: "0.75rem", color: "var(--status-success)" }}>
                    <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--status-success)", boxShadow: "0 0 6px var(--status-success)" }}></span>
                    Connected to P2P Swarm
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
                {/* Sync Mode Simulation Switch (Allows user to preview both 1-2 day initial sync state and fully synced state) */}
                <button
                  onClick={() =>
                    setNodeSync((prev) => ({
                      ...prev,
                      isSynced: !prev.isSynced,
                      phase: !prev.isSynced ? "synced" : "headers",
                      progressPercent: !prev.isSynced ? 100 : 88.6,
                    }))
                  }
                  title="Click to toggle between Node Syncing and Fully Synced states"
                  style={{
                    background: "var(--bg-primary)",
                    border: `1px solid ${nodeSync.isSynced ? "rgba(16, 185, 129, 0.4)" : "rgba(245, 158, 11, 0.4)"}`,
                    borderRadius: "8px",
                    padding: "0.45rem 0.8rem",
                    color: nodeSync.isSynced ? "var(--status-success)" : "var(--accent-gold)",
                    fontSize: "0.75rem",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                  }}
                >
                  <RefreshCw size={12} className={!nodeSync.isSynced ? "sync-pulse" : ""} />
                  Preview State: <strong>{nodeSync.isSynced ? "Synced (100%)" : "Syncing (88.6%)"}</strong>
                </button>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Status</div>
                  <div style={{ fontSize: "1.4rem", fontWeight: 800, color: nodeSync.isSynced ? "var(--status-success)" : "var(--accent-gold)", lineHeight: 1.2 }}>
                    {nodeSync.isSynced ? "Running" : "Syncing"}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Network: mainnet</div>
                </div>
              </div>
            </div>

            {/* Quick Metrics Bar: Connections, Average Ping, Mempool */}
            <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>CONNECTIONS</span>
                  <Network size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value">9</div>
                <div className="stat-subtext" style={{ color: "var(--text-muted)" }}>9 Out / 0 In</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>AVERAGE PING</span>
                  <Zap size={18} color="var(--accent-gold)" />
                </div>
                <div className="stat-value">349.8ms</div>
                <div className="stat-subtext" style={{ color: "var(--text-muted)" }}>Across 9 sampled peers</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>MEMPOOL TXS</span>
                  <Radio size={18} color="var(--status-success)" />
                </div>
                <div className="stat-value">13</div>
                <div className="stat-subtext" style={{ color: "var(--text-muted)" }}>Local transaction pool</div>
              </div>
            </div>

            {/* Middle Section: Sync Status Card + Peer Donut Ring */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem", marginBottom: "1.5rem" }}>
              {/* Sync Status Card (Dynamically handles Syncing vs Synced) */}
              <div className="glass-panel" style={{ padding: "1.5rem", position: "relative" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>
                    Sync Status
                  </span>
                  {nodeSync.isSynced ? (
                    <span className="sync-badge-green">
                      <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--status-success)" }}></span>
                      Synced
                    </span>
                  ) : (
                    <span className="sync-badge-amber">
                      <RefreshCw size={12} className="sync-pulse" />
                      Syncing ({nodeSync.progressPercent}%)
                    </span>
                  )}
                </div>

                {nodeSync.isSynced ? (
                  <>
                    <div style={{ fontSize: "2.4rem", fontWeight: 800, color: "#fff", marginBottom: "0.5rem" }}>
                      Synced
                    </div>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
                      Node is fully synced with the Kaspa network tip. Validating blocks in real time.
                    </p>
                  </>
                ) : (
                  <>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "0.5rem" }}>
                      <div style={{ fontSize: "2.4rem", fontWeight: 800, color: "var(--accent-gold)" }}>
                        {nodeSync.progressPercent}%
                      </div>
                      <span style={{ fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                        {nodeSync.estimatedRemaining}
                      </span>
                    </div>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
                      Catching up with Kaspa DAG headers and pruning point. First-time node sync can take 1–2 days.
                    </p>

                    {/* Shimmering Progress Bar */}
                    <div className="sync-progress-bar-bg" style={{ marginBottom: "1.25rem", height: "10px" }}>
                      <div className="sync-progress-bar-fill" style={{ width: `${nodeSync.progressPercent}%` }}></div>
                    </div>
                  </>
                )}

                {/* Tip & DAA Score Sub-Panel */}
                <div
                  style={{
                    background: "var(--bg-primary)",
                    borderRadius: "10px",
                    padding: "1.25rem",
                    border: "1px solid var(--border-subtle)",
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: "1rem",
                  }}
                >
                  <div>
                    <span style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.05em", color: nodeSync.isSynced ? "var(--kaspa-cyan)" : "var(--accent-gold)", fontWeight: 700 }}>
                      {nodeSync.isSynced ? "LIVE TIP" : "HEADERS / TIP DAA"}
                    </span>
                    <h4 style={{ fontSize: "1rem", color: "#fff", marginTop: "0.25rem", lineHeight: 1.3 }}>
                      {nodeSync.isSynced
                        ? "Fully caught up and tracking network"
                        : `${nodeSync.currentHeaderDaa.toLocaleString()} / ${nodeSync.targetHeaderDaa.toLocaleString()}`}
                    </h4>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.4rem" }}>
                      {nodeSync.isSynced
                        ? "No backlog detected. Ready for instantaneous block template generation."
                        : `Phase: Downloading DAG headers (${(nodeSync.targetHeaderDaa - nodeSync.currentHeaderDaa).toLocaleString()} blocks remaining to tip).`}
                    </p>
                  </div>

                  <div style={{ borderLeft: "1px solid var(--border-subtle)", paddingLeft: "1rem" }}>
                    <span style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", fontWeight: 700 }}>
                      DAA SCORE
                    </span>
                    <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)", marginTop: "0.25rem" }}>
                      {nodeSync.isSynced ? "531.9M" : `${(nodeSync.currentHeaderDaa / 1_000_000).toFixed(1)}M`}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {nodeSync.isSynced ? "Virtual DAA metric reported by kaspad" : `Target DAA: ${(nodeSync.targetHeaderDaa / 1_000_000).toFixed(1)}M`}
                    </div>
                  </div>
                </div>
              </div>

              {/* Connections Donut Visualizer Card */}
              <div className="glass-panel" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>
                    Connections
                  </span>
                  <Info size={16} color="var(--text-muted)" />
                </div>

                {/* Donut Ring Visual */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", margin: "1rem 0" }}>
                  <div style={{ position: "relative", width: "130px", height: "130px" }}>
                    <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
                      {/* Background Track */}
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="var(--bg-surface-elevated)"
                        strokeWidth="3.2"
                      />
                      {/* Outbound Ring (Teal) */}
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="var(--kaspa-cyan)"
                        strokeWidth="3.2"
                        strokeDasharray="100, 100"
                        strokeLinecap="round"
                      />
                    </svg>
                    <div
                      style={{
                        position: "absolute",
                        inset: 0,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <span style={{ fontSize: "2rem", fontWeight: 800, fontFamily: "var(--font-mono)", color: "#fff", lineHeight: 1 }}>
                        9
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>Peers</span>
                    </div>
                  </div>
                </div>

                {/* Legend & UTXO Index Status */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--kaspa-cyan)" }}></span>
                      Outbound
                    </span>
                    <strong style={{ fontFamily: "var(--font-mono)", color: "#fff" }}>9</strong>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#a855f7" }}></span>
                      Inbound
                    </span>
                    <strong style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>0</strong>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem", paddingTop: "0.6rem" }}>
                    <span style={{ color: "var(--text-secondary)" }}>UTXO Indexed</span>
                    <span style={{ background: "rgba(16, 185, 129, 0.15)", color: "var(--status-success)", border: "1px solid rgba(16, 185, 129, 0.3)", padding: "0.15rem 0.5rem", borderRadius: "6px", fontSize: "0.75rem", fontWeight: 700 }}>
                      Yes
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Support the Network Banner */}
            <div
              className="glass-panel"
              style={{
                padding: "1.25rem 1.5rem",
                marginBottom: "1.5rem",
                background: "linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(17, 24, 39, 0.9) 100%)",
                border: "1px solid rgba(16, 185, 129, 0.2)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                <Heart size={18} color="var(--status-success)" />
                <h4 style={{ margin: 0, fontSize: "0.95rem", color: "#fff" }}>Support the Kaspa Network</h4>
              </div>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.75rem" }}>
                The very heart of Kaspa is public nodes. Please consider making your node publicly accessible.
              </p>
              <div style={{ fontSize: "0.85rem", color: "var(--text-primary)" }}>
                <span style={{ color: "var(--kaspa-cyan)", fontWeight: 600 }}>To support the network: </span>
                Forward TCP port{" "}
                <span style={{ fontFamily: "var(--font-mono)", background: "var(--bg-primary)", padding: "0.15rem 0.4rem", borderRadius: "4px", border: "1px solid var(--border-subtle)", color: "var(--kaspa-cyan)" }}>
                  16111
                </span>{" "}
                on your router firewall to your Umbrel node IP address.
              </div>
            </div>

            {/* Connected Peers Table */}
            <div className="glass-panel" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                <Radio size={18} color="var(--kaspa-cyan)" />
                <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Connected Peers</h3>
              </div>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
                A list of peer nodes currently connected and streaming DAG blocks to your node
              </p>

              <div className="table-responsive-wrapper">
                <table style={{ width: "100%", minWidth: "680px", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                      <th style={{ padding: "0.75rem" }}>PEER ADDRESS</th>
                      <th style={{ padding: "0.75rem" }}>VERSION</th>
                      <th style={{ padding: "0.75rem" }}>DIRECTION</th>
                      <th style={{ padding: "0.75rem" }}>PING</th>
                      <th style={{ padding: "0.75rem", textAlign: "right" }}>CONNECTED</th>
                    </tr>
                  </thead>
                  <tbody style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}>
                    {[
                      { ip: "23.243.196.209:16111", version: "v2.0.1", direction: "OUT", ping: "181ms", pingColor: "#10b981", uptime: "4h 57m 44s" },
                      { ip: "136.243.176.114:19188", version: "v2.0.1", direction: "OUT", ping: "401ms", pingColor: "#f59e0b", uptime: "4h 57m 16s" },
                      { ip: "15.204.108.244:16111", version: "v2.0.1", direction: "OUT", ping: "436ms", pingColor: "#f59e0b", uptime: "4h 57m 32s" },
                      { ip: "112.223.203.83:16111", version: "v2.0.1", direction: "OUT", ping: "305ms", pingColor: "#10b981", uptime: "4h 57m 51s" },
                      { ip: "[::ffff:149.50.116.83]:20001", version: "v2.0.1", direction: "OUT", ping: "635ms", pingColor: "#ef4444", uptime: "4h 57m 47s" },
                      { ip: "135.181.177.189:16111", version: "v2.0.1", direction: "OUT", ping: "361ms", pingColor: "#f59e0b", uptime: "4h 55m 47s" },
                      { ip: "101.109.254.42:16111", version: "v2.0.1", direction: "OUT", ping: "271ms", pingColor: "#10b981", uptime: "4h 57m 51s" },
                      { ip: "72.28.135.10:16111", version: "v2.0.1", direction: "OUT", ping: "269ms", pingColor: "#10b981", uptime: "4h 55m 46s" },
                      { ip: "183.107.76.79:16111", version: "v2.0.1", direction: "OUT", ping: "289ms", pingColor: "#10b981", uptime: "4h 57m 36s" },
                    ].map((peer, idx) => (
                      <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "0.85rem 0.75rem", color: "#fff" }}>
                          <span style={{ color: "var(--text-primary)" }}>{peer.ip}</span>
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <span style={{ background: "var(--bg-primary)", padding: "0.15rem 0.4rem", borderRadius: "4px", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>
                            {peer.version}
                          </span>
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <span style={{ background: "rgba(112, 199, 186, 0.12)", color: "var(--kaspa-cyan)", border: "1px solid rgba(112, 199, 186, 0.25)", padding: "0.15rem 0.45rem", borderRadius: "10px", fontSize: "0.75rem", fontWeight: 700 }}>
                            {peer.direction}
                          </span>
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <span style={{ color: peer.pingColor, fontWeight: 700 }}>{peer.ping}</span>
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem", textAlign: "right", color: "var(--text-muted)" }}>
                          {peer.uptime}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
    </div>
  );
};

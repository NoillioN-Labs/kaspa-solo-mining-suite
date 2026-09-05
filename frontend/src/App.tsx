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
  mempoolTxCount?: number;
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

interface WorkerItem {
  id: string;
  name: string;
  ip: string;
  hashrate: number;
  difficulty: number;
  shares: number;
  effort: number;
  status: "online" | "idle";
  lastShare: string;
}

interface PeerItem {
  id: string;
  address: string;
  direction: "inbound" | "outbound";
  ping: number;
  version: string;
}

interface MinedBlockItem {
  id?: string;
  hash: string;
  shortHash?: string;
  worker?: string;
  effort?: number;
  reward: number;
  rewardSompi?: string;
  blueScore?: string | number;
  timestamp: number;
  timeAgo?: string;
  status?: string;
  txs?: number;
}

export const App: React.FC = () => {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [activeTab, setActiveTab] = useState<"overview" | "miners" | "blocks" | "node" | "settings" | "logs">("overview");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Live collections from backend collector
  const [workers, setWorkers] = useState<WorkerItem[]>([]);
  const [peers, setPeers] = useState<PeerItem[]>([]);
  const [peerCounts, setPeerCounts] = useState<{ inbound: number; outbound: number; total: number }>({ inbound: 0, outbound: 0, total: 0 });
  const [minedBlocks, setMinedBlocks] = useState<MinedBlockItem[]>([]);
  const [logs, setLogs] = useState<string[]>([]);

  // Node synchronization state strictly reflecting kaspad RPC
  const [nodeSync, setNodeSync] = useState<NodeSyncInfo>({
    isSynced: false,
    progressPercent: 0,
    currentHeaderDaa: 0,
    targetHeaderDaa: 0,
    currentUtxoDaa: 0,
    targetUtxoDaa: 0,
    estimatedRemaining: "Connecting...",
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
    mempoolTxCount: 0,
  });

  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [selectedPreset, setSelectedPreset] = useState("automatic");
  const [settingsSuccess, setSettingsSuccess] = useState(false);

  // Danger Zone: Reset Telemetry state
  const [showResetModal, setShowResetModal] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(null);

  // Poll live stats, workers, peers, rewards, and logs every 3-5 seconds
  useEffect(() => {
    const fetchAllData = () => {
      // 1. Stats & Node Sync
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
              mempoolTxCount: Number(data.mempoolTxCount || 0),
            });
            if (data.isSynced !== undefined) {
              const isSyn = Boolean(data.isSynced);
              const progress = Number(data.syncProgress || (isSyn ? 100 : 0));
              setNodeSync((prev) => ({
                ...prev,
                isSynced: isSyn,
                progressPercent: progress,
                currentHeaderDaa: Number(data.currentDaa || 0),
                targetHeaderDaa: Number(data.targetDaa || 0),
                estimatedRemaining: isSyn ? "Synchronized" : (progress > 0 ? `~${(100 - progress).toFixed(1)}% remaining` : "Calculating..."),
                phase: isSyn ? "synced" : "headers",
              }));
            }
          }
        })
        .catch(() => {});

      // 2. Active Workers
      fetch("/api/workers")
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) {
            setWorkers(data);
          }
        })
        .catch(() => {});

      // 3. Connected Peers
      fetch("/api/peers")
        .then((r) => r.json())
        .then((data) => {
          if (data) {
            if (Array.isArray(data.peers)) setPeers(data.peers);
            setPeerCounts({
              inbound: Number(data.inbound || 0),
              outbound: Number(data.outbound || 0),
              total: Number(data.total || 0),
            });
          }
        })
        .catch(() => {});

      // 4. Mined Blocks Rewards
      fetch("/api/rewards")
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) {
            setMinedBlocks(data);
          }
        })
        .catch(() => {});

      // 5. Dynamic Console Stream
      fetch("/api/logs")
        .then((r) => r.json())
        .then((data) => {
          if (data && Array.isArray(data.logs)) {
            setLogs(data.logs);
          }
        })
        .catch(() => {});
    };

    fetchAllData();
    const interval = setInterval(fetchAllData, 3000);
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
              <span className="logo-title">Kaspa Solo Mining Suite</span>
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
                <div className="stat-subtext">{stats.activeMiners} ASIC Miner{stats.activeMiners === 1 ? "" : "s"} Online</div>
              </div>

              {/* 24-Hour Solo Blocks & Kaspa Yield Highlight */}
              <div
                className="glass-panel stat-card"
                style={{
                  background: minedBlocks.length > 0 ? "linear-gradient(145deg, rgba(245, 158, 11, 0.08), rgba(17, 24, 39, 0.85))" : "var(--bg-surface)",
                  border: minedBlocks.length > 0 ? "1px solid rgba(245, 158, 11, 0.35)" : "1px solid var(--border-subtle)",
                }}
              >
                <div className="stat-header">
                  <span style={{ color: minedBlocks.length > 0 ? "var(--accent-gold)" : "var(--text-muted)", fontWeight: 700 }}>BLOCKS (LAST 24H)</span>
                  <Trophy size={18} color={minedBlocks.length > 0 ? "var(--accent-gold)" : "var(--text-muted)"} />
                </div>
                <div className="stat-value" style={{ color: minedBlocks.length > 0 ? "var(--accent-gold)" : "#fff" }}>
                  {minedBlocks.filter(b => Date.now() - b.timestamp < 86400000).length} Blocks
                </div>
                <div className="stat-subtext" style={{ color: "var(--text-secondary)" }}>
                  {minedBlocks.length > 0
                    ? `+${minedBlocks.reduce((acc, b) => acc + (b.reward || 0), 0).toFixed(2)} KAS Total`
                    : "No solo blocks mined yet"}
                </div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>ACCEPTED SHARES</span>
                  <ShieldCheck size={18} color="var(--status-success)" />
                </div>
                <div className="stat-value">{stats.acceptedShares.toLocaleString()}</div>
                <div className="stat-subtext">
                  {stats.acceptedShares + stats.staleShares > 0
                    ? `${((stats.acceptedShares / (stats.acceptedShares + stats.staleShares + stats.invalidShares)) * 100).toFixed(1)}% Efficiency (${stats.staleShares} Stales)`
                    : "Waiting for miner shares"}
                </div>
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
                  <div className="stat-subtext">DAA Height: {nodeSync.currentHeaderDaa > 0 ? nodeSync.currentHeaderDaa.toLocaleString() : "Live"}</div>
                ) : (
                  <div style={{ marginTop: "0.5rem" }}>
                    <div className="sync-progress-bar-bg" style={{ height: "6px" }}>
                      <div className="sync-progress-bar-fill" style={{ width: `${nodeSync.progressPercent}%` }}></div>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px", display: "flex", justifyContent: "space-between" }}>
                      <span>{nodeSync.estimatedRemaining}</span>
                      <span>{nodeSync.progressPercent}%</span>
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
                      {stats.totalHashrate}
                    </div>
                    {stats.activeMiners > 0 && (
                      <span style={{ background: "rgba(16, 185, 129, 0.15)", color: "var(--status-success)", border: "1px solid rgba(16, 185, 129, 0.3)", padding: "0.25rem 0.6rem", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 600 }}>
                        {stats.activeMiners} Active
                      </span>
                    )}
                  </div>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.5rem" }}>
                    {stats.activeMiners > 0
                      ? "Cumulative real-time hash fidelity from all connected ASIC workers"
                      : "Point your ASIC miner stratum client to this Umbrel node to begin mining"}
                  </p>
                </div>

                {/* Fleet Quick Metrics */}
                <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap" }}>
                  <div style={{ background: "var(--bg-primary)", padding: "0.75rem 1.25rem", borderRadius: "10px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>ONLINE WORKERS</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#fff", fontFamily: "var(--font-mono)" }}>
                      {stats.activeMiners} / {workers.length > 0 ? workers.length : stats.activeMiners}
                    </div>
                    <div style={{ fontSize: "0.7rem", color: stats.activeMiners > 0 ? "var(--status-success)" : "var(--text-muted)" }}>
                      {stats.activeMiners > 0 ? "Operational" : "No miners active"}
                    </div>
                  </div>

                  <div style={{ background: "var(--bg-primary)", padding: "0.75rem 1.25rem", borderRadius: "10px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>FLEET EFFORT</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--kaspa-cyan)", fontFamily: "var(--font-mono)" }}>
                      {workers.length > 0
                        ? `${Math.round(workers.reduce((acc, w) => acc + (w.effort || 0), 0) / workers.length)}%`
                        : "0%"}
                    </div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Current Round</div>
                  </div>

                  <div style={{ background: "var(--bg-primary)", padding: "0.75rem 1.25rem", borderRadius: "10px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>VALID SHARES</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--kaspa-cyan)", fontFamily: "var(--font-mono)" }}>
                      {stats.acceptedShares.toLocaleString()}
                    </div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                      {stats.acceptedShares + stats.staleShares > 0
                        ? `${((stats.acceptedShares / (stats.acceptedShares + stats.staleShares + stats.invalidShares)) * 100).toFixed(1)}% Accepted`
                        : "0 Accepted"}
                    </div>
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
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: stats.activeMiners > 0 ? "var(--status-success)" : "var(--text-muted)" }}></span>
                  {stats.activeMiners} Worker{stats.activeMiners === 1 ? "" : "s"} Online
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
                    <th style={{ padding: "0.75rem" }}>LAST SHARE</th>
                    <th style={{ padding: "0.75rem" }}>STATUS</th>
                  </tr>
                </thead>
                <tbody style={{ fontFamily: "var(--font-mono)", fontSize: "0.9rem" }}>
                  {workers.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ padding: "2.5rem 1rem", textAlign: "center", color: "var(--text-muted)" }}>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.75rem" }}>
                          <Cpu size={32} color="var(--border-subtle)" />
                          <div style={{ fontSize: "1rem", color: "var(--text-primary)", fontWeight: 600 }}>No ASIC Miners Connected</div>
                          <div style={{ fontSize: "0.85rem", maxWidth: "480px", color: "var(--text-secondary)" }}>
                            Point your IceRiver, Antminer, Desiwe, or Goldshell miner to <strong style={{ color: "var(--kaspa-cyan)" }}>stratum+tcp://&lt;YOUR_UMBREL_IP&gt;:55555</strong> to start hashing.
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    workers.map((w, idx) => (
                      <tr key={w.id || idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "0.85rem 0.75rem", color: "#fff" }}>
                          <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem" }}>
                            <Cpu size={15} color="var(--kaspa-cyan)" /> {w.name}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{w.ip}</div>
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem", color: "var(--kaspa-cyan)", fontWeight: 700 }}>
                          {w.hashrate > 0 ? `${(w.hashrate / 1e12).toFixed(2)} TH/s` : "0.0 TH/s"}
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "0.3rem",
                              fontWeight: 700,
                              color: (w.effort || 0) < 100 ? "#10b981" : "#f59e0b",
                              background: (w.effort || 0) < 100 ? "rgba(16, 185, 129, 0.12)" : "rgba(245, 158, 11, 0.12)",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "4px",
                              border: `1px solid ${(w.effort || 0) < 100 ? "rgba(16, 185, 129, 0.3)" : "rgba(245, 158, 11, 0.3)"}`,
                            }}
                          >
                            {w.effort || 0}%
                          </span>
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem" }}>{(w.shares || 0).toLocaleString()}</td>
                        <td style={{ padding: "0.85rem 0.75rem", color: "var(--status-warning)" }}>0</td>
                        <td style={{ padding: "0.85rem 0.75rem" }}>{(w.difficulty || 1).toLocaleString()}</td>
                        <td style={{ padding: "0.85rem 0.75rem", color: "var(--text-secondary)" }}>
                          {w.lastShare ? new Date(w.lastShare).toLocaleTimeString() : "N/A"}
                        </td>
                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <span style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.35rem",
                            padding: "0.2rem 0.6rem",
                            borderRadius: "12px",
                            fontSize: "0.75rem",
                            background: w.status === "online" ? "rgba(16, 185, 129, 0.15)" : "rgba(107, 114, 128, 0.15)",
                            color: w.status === "online" ? "var(--status-success)" : "var(--text-muted)",
                            border: `1px solid ${w.status === "online" ? "rgba(16, 185, 129, 0.3)" : "rgba(107, 114, 128, 0.3)"}`,
                          }}>
                            <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: w.status === "online" ? "var(--status-success)" : "var(--text-muted)" }}></span>
                            {w.status === "online" ? "Active" : "Idle"}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
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
              <span>Total Fleet: {stats.totalHashrate}</span>
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
                <div className="stat-value" style={{ color: "var(--accent-gold)" }}>{minedBlocks.length} Blocks</div>
                <div className="stat-subtext">All-time Solo Wins</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>TOTAL REWARDS EARNED</span>
                  <Sparkles size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value">
                  {minedBlocks.reduce((acc, b) => acc + (b.reward || 0), 0).toFixed(2)} KAS
                </div>
                <div className="stat-subtext">
                  ≈ ${(minedBlocks.reduce((acc, b) => acc + (b.reward || 0), 0) * 0.174).toFixed(2)} USD
                </div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>LATEST SOLO WIN</span>
                  <Clock size={18} color="var(--status-success)" />
                </div>
                <div className="stat-value" style={{ fontSize: "1.25rem", color: minedBlocks.length > 0 ? "var(--status-success)" : "var(--text-muted)" }}>
                  {minedBlocks[0]?.timeAgo || (minedBlocks.length > 0 ? "Recently" : "None yet")}
                </div>
                <div className="stat-subtext">
                  {minedBlocks[0]?.worker ? `Worker: ${minedBlocks[0].worker}` : "Waiting for first win"}
                </div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>DAG BLUE STATUS</span>
                  <ShieldCheck size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value" style={{ fontSize: "1.25rem" }}>
                  {minedBlocks.length > 0 ? "100% Blue" : "N/A"}
                </div>
                <div className="stat-subtext">
                  {minedBlocks.length > 0 ? `${minedBlocks.length}/${minedBlocks.length} Accepted DAG Blocks` : "0 verified blocks"}
                </div>
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
                    {minedBlocks.length === 0 ? (
                      <tr>
                        <td colSpan={7} style={{ padding: "2.5rem 1rem", textAlign: "center", color: "var(--text-muted)" }}>
                          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.75rem" }}>
                            <Award size={36} color="var(--border-subtle)" />
                            <div style={{ fontSize: "1rem", color: "var(--text-primary)", fontWeight: 600 }}>No Solo Blocks Mined Yet</div>
                            <div style={{ fontSize: "0.85rem", maxWidth: "480px", color: "var(--text-secondary)" }}>
                              When your ASIC miner solves a valid network block, it will be validated and permanently logged here with transaction fees.
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      minedBlocks.map((b, idx) => {
                        const effortColor = (b.effort || 0) < 100 ? "#10b981" : (b.effort || 0) <= 150 ? "#f59e0b" : "#ef4444";
                        const shortHash = b.shortHash || `${b.hash.slice(0, 8)}...${b.hash.slice(-8)}`;
                        return (
                          <tr key={b.id || idx} style={{ borderBottom: "1px solid var(--border-subtle)", transition: "background 0.2s ease" }}>
                            <td style={{ padding: "0.85rem 0.75rem" }}>
                              <div style={{ color: "#fff", fontWeight: 600 }}>#{b.blueScore || "DAG Tip"}</div>
                              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                {b.timeAgo || new Date(b.timestamp).toLocaleString()}
                              </div>
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
                                {shortHash}
                              </span>
                            </td>
                            <td style={{ padding: "0.85rem 0.75rem", color: "#fff" }}>
                              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                                <Cpu size={14} color="var(--text-muted)" /> {b.worker || "Solo Miner"}
                              </span>
                            </td>
                            <td style={{ padding: "0.85rem 0.75rem" }}>
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  fontWeight: 700,
                                  color: effortColor,
                                  padding: "0.2rem 0.55rem",
                                  borderRadius: "4px",
                                  border: `1px solid ${effortColor}40`,
                                }}
                              >
                                {b.effort || 100}%
                              </span>
                            </td>
                            <td style={{ padding: "0.85rem 0.75rem" }}>
                              <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>+{b.reward.toFixed(2)} KAS</span>
                              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>≈ ${(b.reward * 0.174).toFixed(2)} USD</div>
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
                                {b.status || "Blue Block"}
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
                              >
                                Explorer <ExternalLink size={12} />
                              </a>
                            </td>
                          </tr>
                        );
                      })
                    )}
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

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Status</div>
                  <div style={{ fontSize: "1.4rem", fontWeight: 800, color: nodeSync.isSynced ? "var(--status-success)" : "var(--accent-gold)", lineHeight: 1.2 }}>
                    {nodeSync.isSynced ? "Running" : "Syncing"}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Network: mainnet</div>
                </div>
            </div>

            {/* Quick Metrics Bar: Connections, Average Ping, Mempool */}
            <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>CONNECTIONS</span>
                  <Network size={18} color="var(--kaspa-cyan)" />
                </div>
                <div className="stat-value">{peerCounts.total}</div>
                <div className="stat-subtext" style={{ color: "var(--text-muted)" }}>{peerCounts.outbound} Out / {peerCounts.inbound} In</div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>AVERAGE PING</span>
                  <Zap size={18} color="var(--accent-gold)" />
                </div>
                <div className="stat-value">
                  {peers.length > 0
                    ? `${(peers.reduce((acc, p) => acc + (p.ping || 0), 0) / peers.length).toFixed(1)}ms`
                    : "0.0ms"}
                </div>
                <div className="stat-subtext" style={{ color: "var(--text-muted)" }}>
                  {peers.length > 0 ? `Across ${peers.length} active peers` : "No peer telemetry"}
                </div>
              </div>

              <div className="glass-panel stat-card">
                <div className="stat-header">
                  <span>MEMPOOL TXS</span>
                  <Radio size={18} color="var(--status-success)" />
                </div>
                <div className="stat-value">{stats.mempoolTxCount ?? 0}</div>
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
                      Syncing DAG ({nodeSync.progressPercent.toFixed(1)}%)
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "baseline", gap: "0.6rem", marginBottom: "0.5rem" }}>
                  <span style={{ fontSize: "2.5rem", fontWeight: 800, fontFamily: "var(--font-mono)", color: "#fff", lineHeight: 1 }}>
                    {nodeSync.progressPercent.toFixed(1)}%
                  </span>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    {nodeSync.isSynced ? "Virtual Tip Synchronized" : nodeSync.estimatedRemaining}
                  </span>
                </div>

                {/* Progress Bar with glowing neon cap */}
                <div className="sync-bar-container" style={{ marginBottom: "1.25rem" }}>
                  <div
                    className={`sync-bar-fill ${nodeSync.isSynced ? "synced" : "syncing"}`}
                    style={{ width: `${Math.min(100, Math.max(0, nodeSync.progressPercent))}%` }}
                  >
                    {!nodeSync.isSynced && nodeSync.progressPercent > 0 && <div className="sync-glow-cap"></div>}
                  </div>
                </div>

                {/* Live Tip / Target Info Grid */}
                <div
                  style={{
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
                        : `Phase: Downloading DAG headers (${(Math.max(0, nodeSync.targetHeaderDaa - nodeSync.currentHeaderDaa)).toLocaleString()} blocks remaining to tip).`}
                    </p>
                  </div>

                  <div style={{ borderLeft: "1px solid var(--border-subtle)", paddingLeft: "1rem" }}>
                    <span style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", fontWeight: 700 }}>
                      DAA SCORE
                    </span>
                    <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)", marginTop: "0.25rem" }}>
                      {nodeSync.currentHeaderDaa > 0 ? `${(nodeSync.currentHeaderDaa / 1_000_000).toFixed(1)}M` : "0.0M"}
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
                      {peerCounts.total > 0 && (
                        <path
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                          fill="none"
                          stroke="var(--kaspa-cyan)"
                          strokeWidth="3.2"
                          strokeDasharray={`${(peerCounts.outbound / peerCounts.total) * 100}, 100`}
                          strokeLinecap="round"
                        />
                      )}
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
                        {peerCounts.total}
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
                    <strong style={{ fontFamily: "var(--font-mono)", color: "#fff" }}>{peerCounts.outbound}</strong>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#a855f7" }}></span>
                      Inbound
                    </span>
                    <strong style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{peerCounts.inbound}</strong>
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
                      <th style={{ padding: "0.75rem", textAlign: "right" }}>STATUS</th>
                    </tr>
                  </thead>
                  <tbody style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}>
                    {peers.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: "center", padding: "2.5rem 1rem", color: "var(--text-muted)" }}>
                          Discovering and connecting to Kaspa P2P swarm peers...
                        </td>
                      </tr>
                    ) : (
                      peers.map((peer, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "0.85rem 0.75rem", color: "#fff" }}>
                            <span style={{ color: "var(--text-primary)" }}>{peer.address}</span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <span style={{ background: "var(--bg-primary)", padding: "0.15rem 0.4rem", borderRadius: "4px", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>
                              {peer.version || "v0.14.0"}
                            </span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <span style={{ background: "rgba(112, 199, 186, 0.12)", color: "var(--kaspa-cyan)", border: "1px solid rgba(112, 199, 186, 0.25)", padding: "0.15rem 0.45rem", borderRadius: "10px", fontSize: "0.75rem", fontWeight: 700 }}>
                              {peer.direction.toUpperCase()}
                            </span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem" }}>
                            <span style={{ color: peer.ping < 250 ? "#10b981" : peer.ping < 500 ? "#f59e0b" : "#ef4444", fontWeight: 700 }}>
                              {peer.ping}ms
                            </span>
                          </td>
                          <td style={{ padding: "0.85rem 0.75rem", textAlign: "right", color: "var(--status-success)" }}>
                            Connected
                          </td>
                        </tr>
                      ))
                    )}
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
                lineHeight: 1.6,
              }}
            >
              {logs.length === 0 ? (
                <div style={{ color: "var(--text-muted)" }}>Listening for node and bridge console output...</div>
              ) : (
                logs.map((logLine, idx) => <div key={idx}>{logLine}</div>)
              )}
            </div>
          </div>
        )}
      </main>

      {/* Mobile Bottom Navigation Bar (iPhone 16 Pro Thumb Zone) */}
      <nav className="mobile-bottom-bar">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`mobile-bottom-item ${activeTab === item.id ? "active" : ""}`}
            onClick={() => {
              setActiveTab(item.id);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            aria-label={item.label}
          >
            {item.icon}
            <span>{item.id === "settings" ? "Presets" : item.id === "miners" ? "Workers" : item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
};

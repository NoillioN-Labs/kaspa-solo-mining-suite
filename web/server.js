import express from 'express';
import cors from 'cors';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import { collector } from './collector.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Dynamically resolves local LAN IPv4 address (Story 1.3 / FR-6)
 */
export function getLanIp() {
  if (process.env.HOST_LAN_IP) return process.env.HOST_LAN_IP;
  try {
    const interfaces = os.networkInterfaces();
    for (const name of Object.keys(interfaces)) {
      for (const net of interfaces[name] || []) {
        if ((net.family === 'IPv4' || net.family === 4) && !net.internal && !net.address.startsWith('127.')) {
          return net.address;
        }
      }
    }
  } catch (err) {
    console.warn(`[SERVER] Could not resolve network interfaces: ${err.message}`);
  }
  return '127.0.0.1';
}

export function getConnectionEndpoints(port = 55555) {
  const lanIp = getLanIp();
  return {
    lanIp,
    port,
    stratumLan: `stratum+tcp://${lanIp}:${port}`,
    stratumHostname: `stratum+tcp://umbrel.local:${port}`,
    readinessNotice: 'ASICs can be connected now; mining will commence automatically once the node reaches the DAG tip.',
  };
}

const app = express();
const port = process.env.API_PORT || 3001;

app.use(cors());
app.use(express.json());

// Start autonomous background telemetry collector (AD-1)
collector.start();

// Hardware tuning presets catalog
const PRESET_CATALOG = [
  {
    id: "automatic",
    name: "Automatic Universal (Auto-Vardiff)",
    difficultyTier: "Adaptive",
    hashrateNominal: "Dynamic",
    description: "Continuously adjusts difficulty to target 15-20 shares/min across all miner scales.",
    recommended: true,
    models: ["Universal", "Any ASIC / FPGA"],
  },
  {
    id: "iceriver-ks0",
    name: "IceRiver KS0 / KS0 Pro / KS0 Ultra",
    difficultyTier: "Low Difficulty",
    hashrateNominal: "100 - 400 GH/s",
    description: "Optimized share submission frequency for compact desktop and home-lab ASICs.",
    models: ["KS0 (100 GH/s)", "KS0 Pro (200 GH/s)", "KS0 Ultra (400 GH/s)"],
  },
  {
    id: "iceriver-ks1-ks2",
    name: "IceRiver KS1 / KS2 & Mid-Range",
    difficultyTier: "Medium Difficulty",
    hashrateNominal: "1 - 4.5 TH/s",
    description: "Low latency stratum configuration for mid-range solo miners.",
    models: ["KS1 (1 TH/s)", "KS2 (2 TH/s)", "KS7 Lite (~4.2 TH/s)"],
  },
  {
    id: "antminer-ks3-ks5",
    name: "Bitmain Antminer KS3 / KS5 Pro",
    difficultyTier: "High Difficulty",
    hashrateNominal: "8.3 - 21 TH/s",
    description: "High difficulty ceiling preventing connection starvation on high-hashrate rigs.",
    models: ["Antminer KS3 (8.3-9.4 TH/s)", "Antminer KS5 (20 TH/s)", "Antminer KS5 Pro (21 TH/s)"],
  },
  {
    id: "enterprise-ks7-farm",
    name: "Enterprise Hashrate / Multi-Unit Farm",
    difficultyTier: "Ultra / Enterprise",
    hashrateNominal: "25+ TH/s",
    description: "Ultra-high stratum difficulty for heavy multi-rig farms and high-density deployments.",
    models: ["IceRiver KS7 (25 TH/s)", "Multi-Miner Farm"],
  },
];

let activePreset = "automatic";

// 1. Live Aggregated Status
app.get('/api/status', (req, res) => {
  const { live } = collector.state;
  res.json({
    node: {
      status: live.isSynced ? 'synced' : (live.syncStage === 1 ? 'proof_validation' : 'syncing'),
      stage: live.syncStage,
      stageName: live.syncStageName,
      syncMessage: live.syncMessage,
      progress: live.syncProgress,
      currentDaa: live.currentDaa,
      targetDaa: live.targetDaa,
      headerCount: live.headerCount,
      blockCount: live.blockCount,
      difficulty: live.difficulty,
      etaSeconds: live.etaSeconds,
      isSynced: live.isSynced,
    },
    bridge: {
      status: live.activeMiners > 0 ? 'connected' : 'waiting',
      clients: live.activeMiners,
      totalHashrate: live.totalHashrate,
      acceptedShares: live.acceptedShares,
      staleShares: live.staleShares,
      invalidShares: live.invalidShares,
      connection: getConnectionEndpoints(),
    },
    luckEstimate: live.luckEstimate,
  });
});

// 1b. Multi-Stage Initial Block Download (IBD) Telemetry (Story 1.2 / FR-5 / ARCH-2)
app.get('/api/node/sync', (req, res) => {
  res.json(collector.getSyncState());
});

// 1c. Dual ASIC Connection Endpoints (Story 1.3 / FR-6 / UX-DR6)
app.get('/api/connection', (req, res) => {
  res.json(getConnectionEndpoints());
});

// 2. Comprehensive Stats Endpoint
app.get('/api/stats', (req, res) => {
  const { live, minedBlocks } = collector.state;
  const dayAgo = Date.now() - 86400000;
  const blocks24h = minedBlocks.filter(b => (b.timestamp || 0) >= dayAgo).length;
  const workers = live.workers || [];
  const roundEffort = workers.length > 0
    ? Number((workers.reduce((acc, w) => acc + (w.effort || 0), 0) / workers.length).toFixed(1))
    : 0;

  res.json({
    totalHashrate: live.totalHashrate > 0 ? `${live.totalHashrate.toFixed(1)} TH/s` : "0.0 TH/s",
    totalHashrateTh: live.totalHashrate || 0,
    activeMiners: live.activeMiners,
    blocks24h,
    roundEffort,
    acceptedShares: live.acceptedShares,
    staleShares: live.staleShares,
    invalidShares: live.invalidShares,
    luckEstimate: live.luckEstimate,
    nodeStatus: live.nodeStatus,
    isSynced: live.isSynced,
    syncProgress: live.syncProgress,
    currentDaa: live.currentDaa,
    targetDaa: live.targetDaa,
    mempoolTxCount: live.mempoolTxCount || 0,
    headerCount: live.headerCount || 0,
    difficulty: live.difficulty || 0,
  });
});

// 3. Connected Workers
app.get('/api/workers', (req, res) => {
  res.json(collector.state.live.workers);
});

// 4. P2P Connected Peers
app.get('/api/peers', (req, res) => {
  const { live } = collector.state;
  res.json({
    peers: live.peers,
    inbound: live.inboundPeers,
    outbound: live.outboundPeers,
    total: live.peers.length,
  });
});

// 5. Tiered Historical Rollups (AD-5: 24h, 30d, 6m)
app.get('/api/history', (req, res) => {
  const range = req.query.range || '24h';
  if (range === '6m') {
    res.json({ range: '6m', data: collector.state.history6m });
  } else if (range === '30d') {
    res.json({ range: '30d', data: collector.state.history30d });
  } else {
    res.json({ range: '24h', data: collector.state.history24h });
  }
});

// 6. Presets Catalog & Tuning
app.get('/api/presets', (req, res) => {
  res.json({
    activePreset,
    catalog: PRESET_CATALOG,
  });
});

app.post('/api/tuning', (req, res) => {
  const { preset } = req.body;
  const match = PRESET_CATALOG.find(p => p.id === preset);
  if (match) {
    activePreset = preset;
    console.log(`[TUNING] Preset updated to: ${preset} (${match.name})`);
    res.json({ success: true, activePreset });
  } else {
    res.status(400).json({ error: 'Invalid preset ID' });
  }
});

// 7. Mined Block Rewards Ledger
app.get('/api/rewards', (req, res) => {
  res.json(collector.state.minedBlocks);
});

// 8. Block Event / Confetti trigger
app.get('/api/block_event', (req, res) => {
  const recent = collector.state.minedBlocks[0];
  if (recent && (Date.now() - recent.timestamp < 30000)) {
    res.json({ blockFound: true, hash: recent.hash, reward: recent.reward });
  } else {
    res.json({ blockFound: false });
  }
});

// 9. Reset Historical Data (AD-6: Danger Zone Safety Gate)
app.post('/api/data/reset', (req, res) => {
  const result = collector.resetData();
  res.json(result);
});

// 10. Live Logs Stream
let recentLogs = [
  "[COLLECTOR] Initialized 24/7 background telemetry engine",
  "[STRATUM] Bridge stratum listener binding to port 55555",
  "[KASPAD] Connecting to local node RPC on 18110",
];

app.get('/api/logs', (req, res) => {
  const dynamicLogs = [...recentLogs];
  if (collector.state.live.isSynced) {
    dynamicLogs.push(`[KASPAD] Node synchronized with Kaspa network. Current DAA: ${collector.state.live.currentDaa}`);
  } else if (collector.state.live.syncProgress > 0) {
    dynamicLogs.push(`[KASPAD] Node syncing headers: ${collector.state.live.currentDaa} / ${collector.state.live.targetDaa} (${collector.state.live.syncProgress}%)`);
  }
  if (collector.state.live.activeMiners > 0) {
    dynamicLogs.push(`[STRATUM] Active ASIC workers connected: ${collector.state.live.activeMiners}. Total hashrate: ${collector.state.live.totalHashrate.toFixed(1)} TH/s`);
  }
  res.json({ logs: dynamicLogs });
});

// Health metrics
app.get('/api/health', (req, res) => {
  res.json({
    status: collector.state.live.isSynced ? 'healthy' : 'syncing',
    activeMiners: collector.state.live.activeMiners,
    totalHashrate: collector.state.live.totalHashrate,
    nodeSynced: collector.state.live.isSynced,
  });
});

// Fiat rates
app.get('/api/fiat', (req, res) => {
  res.json({
    price: 0.174,
    currency: "USD",
  });
});

// 11. Settings Endpoint Alias (for frontend compatibility)
app.post('/api/settings', (req, res) => {
  const { preset } = req.body;
  const match = PRESET_CATALOG.find(p => p.id === preset);
  if (match) {
    activePreset = preset;
    console.log(`[SETTINGS] Preset updated to: ${preset} (${match.name})`);
    res.json({ success: true, activePreset });
  } else {
    res.status(400).json({ error: 'Invalid preset ID' });
  }
});

// Serve compiled static production frontend
const publicPath = path.join(__dirname, 'public');
app.use(express.static(publicPath));

// SPA fallback for all non-API GET routes (Express 5 compatible)
app.get('/{0,}', (req, res) => {
  res.sendFile(path.join(publicPath, 'index.html'));
});

const listenPort = process.env.PORT || process.env.API_PORT || 8080;
app.listen(listenPort, '0.0.0.0', () => {
  console.log(`Kaspa Solo Mining Suite server listening on 0.0.0.0:${listenPort}`);
});



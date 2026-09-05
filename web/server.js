import express from 'express';
import cors from 'cors';
import { collector } from './collector.js';

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
      status: live.isSynced ? 'synced' : (live.syncProgress > 0 ? 'syncing' : 'connecting'),
      progress: live.syncProgress,
      currentDaa: live.currentDaa,
      targetDaa: live.targetDaa,
      headerCount: live.headerCount,
      blockCount: live.blockCount,
      difficulty: live.difficulty,
    },
    bridge: {
      status: live.activeMiners > 0 ? 'connected' : 'waiting',
      clients: live.activeMiners,
      totalHashrate: live.totalHashrate,
      acceptedShares: live.acceptedShares,
      staleShares: live.staleShares,
      invalidShares: live.invalidShares,
    },
    luckEstimate: live.luckEstimate,
  });
});

// 2. Comprehensive Stats Endpoint
app.get('/api/stats', (req, res) => {
  const { live } = collector.state;
  res.json({
    totalHashrate: live.totalHashrate > 0 ? `${live.totalHashrate.toFixed(1)} TH/s` : "0.0 TH/s",
    activeMiners: live.activeMiners,
    acceptedShares: live.acceptedShares,
    staleShares: live.staleShares,
    invalidShares: live.invalidShares,
    luckEstimate: live.luckEstimate,
    nodeStatus: live.nodeStatus,
    isSynced: live.isSynced,
    syncProgress: live.syncProgress,
    currentDaa: live.currentDaa,
    targetDaa: live.targetDaa,
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
  "[BRIDGE] Stratum listener binding to port 5555",
  "[KASPAD] Connecting to local node RPC on 18110",
];

app.get('/api/logs', (req, res) => {
  res.json({ logs: recentLogs });
});

// Health metrics
app.get('/api/health', (req, res) => {
  res.json({
    temp: 68,
    fan: 4200,
    status: 'healthy',
  });
});

// Fiat rates
app.get('/api/fiat', (req, res) => {
  res.json({
    price: 0.174,
    dailyKas: 0,
    dailyFiat: 0,
    currency: "USD",
  });
});

app.listen(port, () => {
  console.log(`Aggregator API listening on port ${port}`);
});


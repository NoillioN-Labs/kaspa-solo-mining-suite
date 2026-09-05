import express from 'express';
import cors from 'cors';

const app = express();
const port = process.env.API_PORT || 3001;

app.use(cors());
app.use(express.json());

// Mock state for now
let nodeSyncing = true;
let asicConnected = false;

app.get('/api/status', (req, res) => {
  res.json({
    node: {
      status: nodeSyncing ? 'syncing' : 'synced',
      progress: nodeSyncing ? 45 : 100
    },
    bridge: {
      status: asicConnected ? 'connected' : 'waiting',
      clients: asicConnected ? 1 : 0
    }
  });
});

app.post('/api/tuning', (req, res) => {
  const { preset } = req.body;
  console.log(`Applying tuning preset: ${preset}`);
  // In reality, this writes to config.yaml and restarts bridge
  res.json({ success: true, preset });
});

let mockLogLines = [
  "[BRIDGE] Starting Kaspa Stratum Bridge on :55555",
  "[KASPAD] Node sync initialized at block 1205934",
  "[BRIDGE] New client connected: 192.168.1.5",
  "[BRIDGE] Accepted share from 192.168.1.5 at diff 10.0"
];

app.get('/api/logs', (req, res) => {
  // Simulate new logs arriving over time
  if (Math.random() > 0.5) {
    mockLogLines.push(`[BRIDGE] Accepted share from 192.168.1.5 at diff ${Math.floor(Math.random() * 50)}.0`);
  }
  // Keep only last 50 lines to prevent memory leak in mock
  if (mockLogLines.length > 50) mockLogLines.shift();
  
  res.json({ logs: mockLogLines });
});

app.get('/api/health', (req, res) => {
  // Random temp between 70 and 95 to sometimes trigger alert (>85)
  const temp = Math.floor(Math.random() * 25) + 70;
  const fan = Math.floor(Math.random() * 2000) + 4000;
  res.json({
    temp,
    fan
  });
});

app.get('/api/rewards', (req, res) => {
  // Generate 7 days of mock block data
  const data = Array.from({length: 7}).map((_, i) => {
    const subsidy = 100 + Math.random() * 20;
    const fees = Math.random() * 5;
    const dag = Math.random() * 2;
    return {
      date: new Date(Date.now() - (6 - i) * 86400000).toISOString().split('T')[0],
      subsidy,
      fees,
      dag,
      total: subsidy + fees + dag
    };
  });
  res.json(data);
});

app.get('/api/fiat', (req, res) => {
  // Mock price and profitability
  res.json({
    price: 0.174,
    dailyKas: 450.5,
    dailyFiat: 450.5 * 0.174,
    currency: "USD"
  });
});

app.get('/api/block_event', (req, res) => {
  // 10% chance to mock a block found during each poll
  const blockFound = Math.random() > 0.9;
  if (blockFound) {
    res.json({ blockFound: true, hash: "00000000a1b2c3d4...", reward: 115.5 });
  } else {
    res.json({ blockFound: false });
  }
});

app.listen(port, () => {
  console.log(`Aggregator API listening on port ${port}`);
});

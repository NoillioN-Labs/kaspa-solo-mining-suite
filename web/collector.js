import fs from 'fs';
import path from 'path';

/**
 * BackgroundCollectorService
 * --------------------------
 * Autonomous 24/7 telemetry collection daemon.
 * - Polls Stratum Bridge API (bridge:3030) for worker & hashrate stats
 * - Polls Kaspad JSON-RPC (kaspad:18110) for DAG info, peer swarm, and mempool fees
 * - Manages 6-Month Tiered Storage:
 *     1. 24 Hours: 1-minute samples (~1,440 points)
 *     2. 30 Days: 15-minute averaged rollups (~2,880 points)
 *     3. 6 Months (180 Days): 1-hour averaged rollups (~4,320 points)
 *     4. Mined Block Ledger: Permanent
 * - Total disk footprint is < 4 MB across 6 months.
 */

const DATA_DIR = process.env.DATA_DIR || path.join(process.cwd(), 'data');
const STORAGE_FILE = path.join(DATA_DIR, 'telemetry_history.json');

const BRIDGE_URL = process.env.BRIDGE_API_URL || 'http://bridge:3030';
const KASPAD_RPC_URL = process.env.KASPAD_RPC_URL || 'http://kaspad:18110';

export class BackgroundCollectorService {
  constructor() {
    this.pollIntervalMs = 5000; // 5 seconds polling
    this.timer = null;
    this.last1mRollup = Date.now();
    this.last15mRollup = Date.now();
    this.last1hRollup = Date.now();

    this.state = {
      live: {
        totalHashrate: 0,
        activeMiners: 0,
        acceptedShares: 0,
        staleShares: 0,
        invalidShares: 0,
        luckEstimate: 'Calculating...',
        nodeStatus: 'Connecting to Kaspa node...',
        isSynced: false,
        syncProgress: 0,
        currentDaa: 0,
        targetDaa: 0,
        headerCount: 0,
        blockCount: 0,
        difficulty: 0,
        peers: [],
        inboundPeers: 0,
        outboundPeers: 0,
        workers: [],
        mempoolTxCount: 0,
        lastUpdated: null,
      },
      // Tier 1: 24h of 1-minute averaged points (max 1440)
      history24h: [],
      // Tier 2: 30d of 15-minute averaged points (max 2880)
      history30d: [],
      // Tier 3: 6m (180d) of 1-hour averaged points (max 4320)
      history6m: [],
      // Permanent block ledger
      minedBlocks: [],
      // Stored logs
      recentLogs: [],
    };

    this.rawBuffer = []; // Temp buffer of 5s samples to compute 1m rollups
    this.initStorage();
  }

  initStorage() {
    try {
      if (!fs.existsSync(DATA_DIR)) {
        fs.mkdirSync(DATA_DIR, { recursive: true });
      }
      if (fs.existsSync(STORAGE_FILE)) {
        const raw = fs.readFileSync(STORAGE_FILE, 'utf8');
        const parsed = JSON.parse(raw);
        if (parsed.history24h) this.state.history24h = parsed.history24h;
        if (parsed.history30d) this.state.history30d = parsed.history30d;
        if (parsed.history6m) this.state.history6m = parsed.history6m;
        if (parsed.minedBlocks) this.state.minedBlocks = parsed.minedBlocks;
        console.log(`[COLLECTOR] Loaded existing telemetry history: 24h(${this.state.history24h.length}), 30d(${this.state.history30d.length}), 6m(${this.state.history6m.length})`);
      }
    } catch (err) {
      console.warn(`[COLLECTOR] Could not load telemetry storage: ${err.message}`);
    }
  }

  saveStorage() {
    try {
      if (!fs.existsSync(DATA_DIR)) {
        fs.mkdirSync(DATA_DIR, { recursive: true });
      }
      const dataToPersist = {
        savedAt: new Date().toISOString(),
        history24h: this.state.history24h,
        history30d: this.state.history30d,
        history6m: this.state.history6m,
        minedBlocks: this.state.minedBlocks,
      };
      fs.writeFileSync(STORAGE_FILE, JSON.stringify(dataToPersist, null, 2), 'utf8');
    } catch (err) {
      console.error(`[COLLECTOR] Error saving telemetry storage: ${err.message}`);
    }
  }

  async fetchRpc(method, params = []) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    try {
      const res = await fetch(KASPAD_RPC_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method, params }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (!res.ok) throw new Error(`RPC HTTP ${res.status}`);
      const json = await res.json();
      if (json.error) throw new Error(json.error.message || 'RPC Error');
      return json.result;
    } catch (err) {
      clearTimeout(timeout);
      return null;
    }
  }

  async fetchBridge(endpoint) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    try {
      const res = await fetch(`${BRIDGE_URL}${endpoint}`, {
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (!res.ok) throw new Error(`Bridge HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      clearTimeout(timeout);
      return null;
    }
  }

  async pollCycle() {
    const now = Date.now();

    // 1. Query Stratum Bridge
    const bridgeStats = await this.fetchBridge('/api/stats');
    const bridgeWorkers = await this.fetchBridge('/api/workers');

    let totalHashrate = 0;
    let activeMiners = 0;
    let acceptedShares = 0;
    let staleShares = 0;
    let invalidShares = 0;
    let workersList = [];

    if (bridgeStats) {
      totalHashrate = Number(bridgeStats.hashrate || bridgeStats.totalHashrate || 0);
      acceptedShares = Number(bridgeStats.accepted || bridgeStats.validShares || 0);
      staleShares = Number(bridgeStats.stale || bridgeStats.staleShares || 0);
      invalidShares = Number(bridgeStats.invalid || bridgeStats.invalidShares || 0);
    }

    if (Array.isArray(bridgeWorkers)) {
      workersList = bridgeWorkers.map((w) => ({
        id: w.id || w.name || 'Worker',
        name: w.name || w.worker || 'Worker',
        ip: w.ip || w.clientIp || '127.0.0.1',
        hashrate: Number(w.hashrate || 0),
        difficulty: Number(w.difficulty || w.diff || 1),
        shares: Number(w.accepted || w.shares || 0),
        effort: Number(w.effort || 0),
        status: w.connected ? 'online' : 'idle',
        lastShare: w.lastShare ? new Date(w.lastShare).toISOString() : new Date().toISOString(),
      }));
      activeMiners = workersList.filter(w => w.status === 'online').length;
      if (totalHashrate === 0 && workersList.length > 0) {
        totalHashrate = workersList.reduce((acc, cur) => acc + cur.hashrate, 0);
      }
    }

    // 2. Query Kaspad RPC
    const dagInfo = await this.fetchRpc('getDagInfo');
    const peerInfo = await this.fetchRpc('getConnectedPeerInfo');
    const syncInfo = await this.fetchRpc('getInfo');

    let isSynced = false;
    let currentDaa = 0;
    let targetDaa = 0;
    let headerCount = 0;
    let blockCount = 0;
    let difficulty = 0;
    let peersList = [];
    let inboundPeers = 0;
    let outboundPeers = 0;

    if (dagInfo) {
      currentDaa = Number(dagInfo.virtualDaaScore || 0);
      headerCount = Number(dagInfo.headerCount || 0);
      blockCount = Number(dagInfo.blockCount || 0);
      difficulty = Number(dagInfo.difficulty || 0);
    }

    if (syncInfo) {
      isSynced = Boolean(syncInfo.isSynced);
      targetDaa = Number(syncInfo.targetDaaScore || syncInfo.headerCount || (currentDaa > 0 ? currentDaa : 0));
    }

    if (Array.isArray(peerInfo)) {
      peersList = peerInfo.map((p) => {
        const isIb = p.isIbPeer ?? (p.direction === 'inbound');
        if (isIb) inboundPeers++;
        else outboundPeers++;
        return {
          id: p.id || p.address,
          address: p.address || 'unknown',
          direction: isIb ? 'inbound' : 'outbound',
          ping: Number(p.lastPingDuration || p.ping || 0),
          version: p.userAgent || p.version || 'v0.14.0',
        };
      });
    }

    // Determine sync progress
    let syncProgress = 100;
    if (!isSynced && targetDaa > 0 && currentDaa > 0 && currentDaa < targetDaa) {
      syncProgress = Math.min(99.9, Number(((currentDaa / targetDaa) * 100).toFixed(1)));
    } else if (!isSynced && currentDaa > 0 && headerCount > 0 && currentDaa < headerCount) {
      syncProgress = Math.min(99.9, Number(((currentDaa / headerCount) * 100).toFixed(1)));
    } else if (isSynced) {
      syncProgress = 100;
    }

    // Calculate luck estimate if hashrate & difficulty available
    let luckEstimate = 'N/A (No Hashrate)';
    if (totalHashrate > 0 && difficulty > 0) {
      const secondsToBlock = (difficulty * 4294967296) / (totalHashrate * 1e12);
      const hours = (secondsToBlock / 3600).toFixed(1);
      luckEstimate = `${hours} hrs`;
    }

    // Update live state
    this.state.live = {
      totalHashrate,
      activeMiners,
      acceptedShares,
      staleShares,
      invalidShares,
      luckEstimate,
      nodeStatus: isSynced ? 'Synchronized (10 BPS)' : `Syncing DAG (${syncProgress}%)`,
      isSynced,
      syncProgress,
      currentDaa,
      targetDaa: targetDaa || currentDaa,
      headerCount,
      blockCount,
      difficulty,
      peers: peersList,
      inboundPeers,
      outboundPeers,
      workers: workersList,
      lastUpdated: new Date().toISOString(),
    };

    // Buffer instantaneous sample
    this.rawBuffer.push({
      timestamp: now,
      hashrate: totalHashrate,
      acceptedShares,
      staleShares,
      difficulty,
    });

    // 3. Rollup Logic (AD-5: Tiered Rollup Retention)
    // Every 60s -> compute 1-minute point for 24h history
    if (now - this.last1mRollup >= 60000) {
      this.aggregate1Minute(now);
      this.last1mRollup = now;
    }

    // Every 15m -> compute 15-minute point for 30d history
    if (now - this.last15mRollup >= 900000) {
      this.aggregate15Minutes(now);
      this.last15mRollup = now;
    }

    // Every 1h -> compute 1-hour point for 6m history & prune >180d
    if (now - this.last1hRollup >= 3600000) {
      this.aggregate1Hour(now);
      this.pruneOldData(now);
      this.last1hRollup = now;
      this.saveStorage();
    }
  }

  aggregate1Minute(now) {
    if (this.rawBuffer.length === 0) return;
    const avgHashrate = this.rawBuffer.reduce((acc, c) => acc + c.hashrate, 0) / this.rawBuffer.length;
    const latest = this.rawBuffer[this.rawBuffer.length - 1];

    this.state.history24h.push({
      timestamp: now,
      timeLabel: new Date(now).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      hashrate: Number(avgHashrate.toFixed(2)),
      shares: latest.acceptedShares,
      difficulty: latest.difficulty,
    });

    // Max 1440 points (24 hours @ 1m)
    if (this.state.history24h.length > 1440) {
      this.state.history24h.shift();
    }

    this.rawBuffer = [];
  }

  aggregate15Minutes(now) {
    const slice = this.state.history24h.slice(-15);
    if (slice.length === 0) return;
    const avgHashrate = slice.reduce((acc, c) => acc + c.hashrate, 0) / slice.length;
    const latest = slice[slice.length - 1];

    this.state.history30d.push({
      timestamp: now,
      timeLabel: new Date(now).toISOString().slice(5, 16).replace('T', ' '),
      hashrate: Number(avgHashrate.toFixed(2)),
      shares: latest.shares,
      difficulty: latest.difficulty,
    });

    // Max 2880 points (30 days @ 15m)
    if (this.state.history30d.length > 2880) {
      this.state.history30d.shift();
    }
  }

  aggregate1Hour(now) {
    const slice = this.state.history30d.slice(-4);
    if (slice.length === 0) return;
    const avgHashrate = slice.reduce((acc, c) => acc + c.hashrate, 0) / slice.length;
    const latest = slice[slice.length - 1];

    this.state.history6m.push({
      timestamp: now,
      dateLabel: new Date(now).toISOString().slice(0, 10),
      hashrate: Number(avgHashrate.toFixed(2)),
      shares: latest.shares,
      difficulty: latest.difficulty,
    });

    // Max 4320 points (180 days / 6 months @ 1h)
    if (this.state.history6m.length > 4320) {
      this.state.history6m.shift();
    }
  }

  pruneOldData(now) {
    const sixMonthsAgo = now - 180 * 24 * 60 * 60 * 1000;
    this.state.history6m = this.state.history6m.filter(pt => pt.timestamp >= sixMonthsAgo);
  }

  resetData() {
    console.log('[COLLECTOR] Executing telemetry reset: wiping 24h, 30d, 6m history and share stats');
    this.state.history24h = [];
    this.state.history30d = [];
    this.state.history6m = [];
    this.state.minedBlocks = [];
    this.rawBuffer = [];
    this.state.live.acceptedShares = 0;
    this.state.live.staleShares = 0;
    this.state.live.invalidShares = 0;
    this.saveStorage();
    return { success: true, message: 'All historical mining telemetry has been wiped.' };
  }

  recordBlockFound(hash, reward = 100) {
    const event = {
      hash,
      reward,
      timestamp: Date.now(),
      date: new Date().toISOString().split('T')[0],
      daaScore: this.state.live.currentDaa,
    };
    this.state.minedBlocks.unshift(event);
    this.saveStorage();
    return event;
  }

  start() {
    console.log('[COLLECTOR] Starting 24/7 Autonomous Background Telemetry Collector (polling interval: 5s)');
    this.pollCycle().catch(err => console.error(`[COLLECTOR] Initial cycle error: ${err.message}`));
    this.timer = setInterval(() => {
      this.pollCycle().catch(err => console.error(`[COLLECTOR] Cycle error: ${err.message}`));
    }, this.pollIntervalMs);
  }

  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
      console.log('[COLLECTOR] Stopped Background Collector');
    }
    this.saveStorage();
  }
}

export const collector = new BackgroundCollectorService();

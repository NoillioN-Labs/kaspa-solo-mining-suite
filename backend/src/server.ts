import express from "express";
import cors from "cors";
import { PRESET_CATALOG, validateSettings, BridgeSettings } from "./presets.js";
import { HistoryStore } from "./history.js";
import { KaspaNodeClient } from "./kaspad.js";
import { BridgeSupervisor } from "./supervisor.js";

export function createServer(options?: {
  historyStore?: HistoryStore;
  supervisor?: BridgeSupervisor;
  nodeClient?: KaspaNodeClient;
}) {
  const app = express();
  app.use(cors());
  app.use(express.json());

  // Serve compiled frontend static assets in production
  app.use(express.static("public"));

  const history = options?.historyStore ?? new HistoryStore();
  const supervisor = options?.supervisor ?? new BridgeSupervisor();
  const kaspad = options?.nodeClient ?? new KaspaNodeClient();

  let activePreset = "automatic";
  let activeSettings: BridgeSettings = { ...PRESET_CATALOG.automatic.settings };

  // 1. System & Bridge Status
  app.get("/api/status", (_req, res) => {
    res.json({
      status: "ok",
      supervisor: supervisor.getStatus(),
      activePreset,
      settings: activeSettings,
      timestamp: Date.now(),
    });
  });

  // 2. ASIC Presets Catalog
  app.get("/api/presets", (_req, res) => {
    res.json({
      catalog: Object.values(PRESET_CATALOG),
      activePreset,
    });
  });

  // 3. Update Settings / Select Preset
  app.post("/api/settings", async (req, res) => {
    const { preset, ...customSettings } = req.body;

    if (preset && PRESET_CATALOG[preset]) {
      activePreset = preset;
      activeSettings = { ...PRESET_CATALOG[preset].settings };
      return res.json({
        success: true,
        message: `Activated preset ${PRESET_CATALOG[preset].name}`,
        activePreset,
        settings: activeSettings,
      });
    }

    const validation = validateSettings(customSettings);
    if (!validation.isValid) {
      return res.status(400).json({
        success: false,
        issues: validation.issues,
      });
    }

    activePreset = "custom";
    activeSettings = validation.cleanSettings!;
    res.json({
      success: true,
      message: "Custom settings saved successfully.",
      activePreset,
      settings: activeSettings,
    });
  });

  // 4. Mining History & Blocks
  app.get("/api/history", (_req, res) => {
    res.json({
      samples: history.getRecentSamples(288),
      blocks: history.getBlocks(),
    });
  });

  // 5. Mark Block Celebrated
  app.post("/api/blocks/:id/celebrate", (req, res) => {
    history.markCelebrated(req.params.id);
    res.json({ success: true });
  });

  // 6. Logs Endpoint
  app.get("/api/logs", (req, res) => {
    const limit = Number(req.query.limit) || 200;
    res.json({
      logs: supervisor.getLogs(limit),
    });
  });

  // 7. Live Events via Server-Sent Events (SSE)
  app.get("/api/events", (req, res) => {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    });

    const sendEvent = (event: string, data: any) => {
      res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
    };

    const onBlockDiscovered = (block: any) => {
      sendEvent("block_found", block);
    };

    const onLog = (log: any) => {
      sendEvent("log", log);
    };

    history.on("block_discovered", onBlockDiscovered);
    supervisor.on("log", onLog);

    // Initial heartbeat
    sendEvent("connected", { time: Date.now() });
    const interval = setInterval(() => {
      sendEvent("ping", { time: Date.now() });
    }, 15000);

    req.on("close", () => {
      clearInterval(interval);
      history.off("block_discovered", onBlockDiscovered);
      supervisor.off("log", onLog);
    });
  });

  return { app, history, supervisor, kaspad };
}

// Auto-start server when run directly as node entrypoint
const port = Number(process.env.PORT) || 8080;
const host = process.env.HOST || "0.0.0.0";
const { app } = createServer();
app.listen(port, host, () => {
  console.log(`Kaspa Solo Mining Suite running on http://${host}:${port}`);
});


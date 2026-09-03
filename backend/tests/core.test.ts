import { describe, it, expect, beforeEach } from "vitest";
import { PRESET_CATALOG, validateSettings } from "../src/presets.js";
import { HistoryStore } from "../src/history.js";
import { KaspaNodeClient, sompiToKas } from "../src/kaspad.js";
import { createServer } from "../src/server.js";

describe("ASIC Presets & Validation", () => {
  it("should contain tuned presets for IceRiver, Antminer, Desiwe, and Goldshell", () => {
    expect(PRESET_CATALOG["iceriver-ks0"]).toBeDefined();
    expect(PRESET_CATALOG["iceriver-ks7"]).toBeDefined();
    expect(PRESET_CATALOG["antminer-ks5"]).toBeDefined();
    expect(PRESET_CATALOG["desiwe-k11"]).toBeDefined();
    expect(PRESET_CATALOG["goldshell-kabox"]).toBeDefined();
  });

  it("should validate valid hardware settings", () => {
    const result = validateSettings({
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 2048,
    });
    expect(result.isValid).toBe(true);
    expect(result.cleanSettings?.minimumShareDifficulty).toBe(2048);
  });

  it("should reject non-power-of-two share difficulties", () => {
    const result = validateSettings({
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 3000, // Not power of two!
    });
    expect(result.isValid).toBe(false);
    expect(result.issues.some((i) => i.field === "minimumShareDifficulty")).toBe(true);
  });
});

describe("Kaspa Node & Reward Calculations", () => {
  const client = new KaspaNodeClient();

  it("should convert Sompi to KAS correctly", () => {
    expect(sompiToKas(100_000_000n)).toBe(1);
    expect(sompiToKas(250_000_000n)).toBe(2.5);
  });

  it("should calculate solo mining luck accurately", () => {
    // 10 TH/s miner on 500 PH/s network (10 BPS)
    const luck = client.calculateLuck(10e12, 500e15, 10);
    expect(luck.dailyEstimatedBlocks).toBeGreaterThan(0);
    expect(luck.estimatedSecondsPerBlock).toBeGreaterThan(0);
    expect(luck.networkSharePercentage).toBeGreaterThan(0);
  });
});

describe("HistoryStore & Block Celebrations", () => {
  let store: HistoryStore;

  beforeEach(() => {
    store = new HistoryStore("./test_data_" + Math.random());
  });

  it("should emit block_discovered event with celebration payload", () => {
    let emittedBlock: any = null;
    store.on("block_discovered", (block) => {
      emittedBlock = block;
    });

    const block = store.recordFoundBlock({
      blockHash: "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
      timestamp: Date.now(),
      workerName: "antminer_ks5_rack1",
      rewardKas: 125.45,
      rewardSompi: "12545000000",
      isBlue: true,
      blueScore: "7891234",
    });

    expect(emittedBlock).toBeDefined();
    expect(emittedBlock.id).toBe(block.id);
    expect(emittedBlock.celebrated).toBe(false);

    store.markCelebrated(block.id);
    expect(store.getBlocks()[0].celebrated).toBe(true);
  });
});

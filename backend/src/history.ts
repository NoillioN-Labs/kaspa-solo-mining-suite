import EventEmitter from "node:events";
import { promises as fs } from "node:fs";
import path from "node:path";
import { BlockRewardDecomposition } from "./kaspad.js";

export interface WorkerSample {
  name: string;
  hashrateHs: number;
  acceptedShares: number;
  staleShares: number;
  invalidShares: number;
  lastShareTimestamp: number;
  currentDifficulty: number;
}

export interface MetricSample {
  timestamp: number;
  totalHashrateHs: number;
  acceptedShares: number;
  staleShares: number;
  invalidShares: number;
  workers: WorkerSample[];
}

export interface FoundBlockEvent {
  id: string;
  blockHash: string;
  timestamp: number;
  workerName: string;
  rewardKas: number;
  rewardSompi: string;
  isBlue: boolean;
  blueScore: string;
  celebrated: boolean;
}

export class HistoryStore extends EventEmitter {
  private samples: MetricSample[] = [];
  private blocks: FoundBlockEvent[] = [];
  private dataFilePath: string;
  private readonly MAX_SAMPLES = 2016; // 7 days at 5-minute sampling intervals

  constructor(storageDir: string = "./data") {
    super();
    this.dataFilePath = path.join(storageDir, "mining_history.json");
  }

  public async init(): Promise<void> {
    try {
      const data = await fs.readFile(this.dataFilePath, "utf8");
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed.samples)) this.samples = parsed.samples;
      if (Array.isArray(parsed.blocks)) this.blocks = parsed.blocks;
    } catch {
      // File doesn't exist yet, start clean
      this.samples = [];
      this.blocks = [];
    }
  }

  public addSample(sample: MetricSample): void {
    this.samples.push(sample);
    if (this.samples.length > this.MAX_SAMPLES) {
      this.samples.shift();
    }
  }

  public recordFoundBlock(block: Omit<FoundBlockEvent, "celebrated" | "id">): FoundBlockEvent {
    const existing = this.blocks.find((b) => b.blockHash.toLowerCase() === block.blockHash.toLowerCase());
    if (existing) return existing;

    const newBlock: FoundBlockEvent = {
      ...block,
      id: `${Date.now()}-${block.blockHash.slice(0, 8)}`,
      celebrated: false,
    };

    this.blocks.unshift(newBlock);
    // Emit event so SSE / UI can immediately trigger the celebration confetti!
    this.emit("block_discovered", newBlock);
    this.save().catch(() => {});
    return newBlock;
  }

  public markCelebrated(blockId: string): void {
    const block = this.blocks.find((b) => b.id === blockId);
    if (block) {
      block.celebrated = true;
      this.save().catch(() => {});
    }
  }

  public getRecentSamples(limit: number = 288): MetricSample[] {
    return this.samples.slice(-limit);
  }

  public getBlocks(): FoundBlockEvent[] {
    return this.blocks;
  }

  public async save(): Promise<void> {
    try {
      const dir = path.dirname(this.dataFilePath);
      await fs.mkdir(dir, { recursive: true });
      const payload = JSON.stringify({ samples: this.samples, blocks: this.blocks }, null, 2);
      await fs.writeFile(this.dataFilePath, payload, "utf8");
    } catch (err) {
      console.error("Failed to save mining history:", err);
    }
  }
}

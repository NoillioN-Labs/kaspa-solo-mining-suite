/**
 * Kaspa Node gRPC & RPC Client Adapter
 * Queries the local Rusty Kaspad node for DAG stats, blue score, sync status, and block rewards.
 */

export interface DagInfo {
  networkName: string;
  blockCount: bigint;
  headerCount: bigint;
  difficulty: number;
  pastMedianTime: number;
  virtualParentHashes: string[];
  pruningPointHash: string;
  virtualDaaScore: bigint;
  sink: string;
}

export interface NodeSyncStatus {
  isSynced: boolean;
  hasPeers: boolean;
  peerCount: number;
  networkHashrateEstimateHs: number;
  virtualDaaScore: bigint;
}

export interface BlockRewardDecomposition {
  blockHash: string;
  isBlue: boolean;
  blueScore: bigint;
  subsidySompi: bigint;
  txFeesSompi: bigint;
  totalRewardSompi: bigint;
  totalRewardKas: number;
  rewardRecipientAddress?: string;
  resolvedAt: number;
}

export const SOMPI_PER_KAS = 100_000_000n;

export const sompiToKas = (sompi: bigint): number => {
  return Number(sompi) / 100_000_000;
};

export class KaspaNodeClient {
  private rpcEndpoint: string;

  constructor(rpcEndpoint: string = "127.0.0.1:16110") {
    this.rpcEndpoint = rpcEndpoint;
  }

  /**
   * Calculates current mining luck and estimated time to find a block.
   * Based on miner's hashrate vs total network hashrate and network target (1 BPS or 10 BPS).
   */
  public calculateLuck(
    minerHashrateHs: number,
    networkHashrateHs: number,
    bps: number = 10
  ): {
    estimatedSecondsPerBlock: number;
    dailyEstimatedBlocks: number;
    networkSharePercentage: number;
  } {
    if (minerHashrateHs <= 0 || networkHashrateHs <= 0) {
      return {
        estimatedSecondsPerBlock: Infinity,
        dailyEstimatedBlocks: 0,
        networkSharePercentage: 0,
      };
    }

    const networkShare = minerHashrateHs / networkHashrateHs;
    // Kaspa produces 'bps' blocks per second
    const blocksPerSecond = networkShare * bps;
    const estimatedSeconds = blocksPerSecond > 0 ? 1 / blocksPerSecond : Infinity;
    const dailyBlocks = blocksPerSecond * 86400;

    return {
      estimatedSecondsPerBlock: Math.round(estimatedSeconds),
      dailyEstimatedBlocks: Number(dailyBlocks.toFixed(4)),
      networkSharePercentage: Number((networkShare * 100).toFixed(6)),
    };
  }

  /**
   * Helper to decompose Sompi values into clean display figures.
   */
  public parseBlockReward(
    blockHash: string,
    blueScore: bigint,
    isBlue: boolean,
    subsidySompi: bigint,
    txFeesSompi: bigint = 0n
  ): BlockRewardDecomposition {
    const total = subsidySompi + txFeesSompi;
    return {
      blockHash,
      isBlue,
      blueScore,
      subsidySompi,
      txFeesSompi,
      totalRewardSompi: total,
      totalRewardKas: sompiToKas(total),
      resolvedAt: Date.now(),
    };
  }
}

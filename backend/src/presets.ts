/**
 * Kaspa ASIC Hardware Tuning Presets Catalog
 *
 * Provides optimized Stratum bridge parameters for major Kaspa mining hardware:
 * - IceRiver (KS0, KS1, KS2, KS3 series, KS5 series, KS7 series)
 * - Bitmain Antminer (KS3, KS5, KS5 Pro)
 * - Desiwe / Windminer (K11)
 * - Goldshell (KA-BOX, KA-BOX Pro)
 */

export interface BridgeSettings {
  stratumPort: number;
  variableDifficulty: boolean;
  sharesPerMinute: number;
  powerOfTwoClamp: boolean;
  extranonceSize: number;
  minimumShareDifficulty: number;
}

export interface PresetProfile {
  id: string;
  name: string;
  difficultyTier: "Adaptive" | "Low Difficulty" | "Medium Difficulty" | "High Difficulty" | "Ultra / Enterprise";
  hashrateNominal: string;
  description: string;
  recommended?: boolean;
  models: string[];
  settings: BridgeSettings;
}

export const PRESET_CATALOG: Record<string, PresetProfile> = {
  // Automatic / Universal Default
  automatic: {
    id: "automatic",
    name: "Automatic (Universal)",
    difficultyTier: "Adaptive",
    hashrateNominal: "Auto-Tuning",
    description: "Recommended for most miners. Dynamically calculates and adapts vardiff to target ~30 shares/min regardless of ASIC model.",
    recommended: true,
    models: ["All ASIC Models", "Mixed Mining Rigs", "Unknown Hardware"],
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 2048,
    },
  },

  // Low Difficulty Tier (100 GH/s – 500 GH/s)
  "low-tier": {
    id: "low-tier",
    name: "Entry / Compact (Diff 64)",
    difficultyTier: "Low Difficulty",
    hashrateNominal: "100 GH/s – 500 GH/s",
    description: "Low-difficulty baseline preventing stale share timeouts and high submission rejection on quiet home/desktop ASICs.",
    models: ["IceRiver KS0", "IceRiver KS0 Pro", "IceRiver KS0 Ultra"],
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 24,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 64,
    },
  },

  // Medium Difficulty Tier (1 TH/s – 5 TH/s)
  "mid-tier": {
    id: "mid-tier",
    name: "Mid-Range Home Units (Diff 512 – 1024)",
    difficultyTier: "Medium Difficulty",
    hashrateNominal: "1 TH/s – 5 TH/s",
    description: "Tuned vardiff floor for mid-capacity standalone home miners and lower-power industrial units.",
    models: ["IceRiver KS1 (1 TH/s)", "IceRiver KS2 (2 TH/s)", "IceRiver KS7 Lite (~4.2 TH/s)", "Goldshell KA-BOX / Pro (1.6 - 2.4 TH/s)"],
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 28,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 512,
    },
  },

  // High Difficulty Tier (6 TH/s – 12 TH/s)
  "high-tier": {
    id: "high-tier",
    name: "High-Throughput ASICs (Diff 2048 – 4096)",
    difficultyTier: "High Difficulty",
    hashrateNominal: "6 TH/s – 12 TH/s",
    description: "Optimized share frequency for serious miners and high-hashrate single-board ASICs.",
    models: ["IceRiver KS3 / KS3M / KS3L (6-8 TH/s)", "Bitmain Antminer KS3 (9.4 TH/s)", "Desiwe / Windminer K11 (11 TH/s)"],
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 2048,
    },
  },

  // Enterprise / Ultra High Difficulty Tier (12 TH/s – 25+ TH/s)
  "ultra-tier": {
    id: "ultra-tier",
    name: "Enterprise Flagships (Diff 8192)",
    difficultyTier: "Ultra / Enterprise",
    hashrateNominal: "12 TH/s – 25+ TH/s",
    description: "High difficulty starting floor designed for commercial enterprise flagships to avoid saturating network bridge buffers.",
    models: ["Bitmain Antminer KS5 / KS5 Pro (20-21 TH/s)", "IceRiver KS7 (20-25 TH/s)", "IceRiver KS5L / KS5M (12-15 TH/s)"],
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 35,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 8192,
    },
  },
};

export interface ValidationIssue {
  field: string;
  message: string;
}

export const isPowerOfTwo = (n: number): boolean => {
  return Number.isSafeInteger(n) && n > 0 && (BigInt(n) & (BigInt(n) - 1n)) === 0n;
};

export const validateSettings = (
  input: Partial<BridgeSettings> & { preset?: string }
): { isValid: boolean; issues: ValidationIssue[]; cleanSettings?: BridgeSettings } => {
  const issues: ValidationIssue[] = [];

  const port = Number(input.stratumPort);
  if (!Number.isSafeInteger(port) || port < 1024 || port > 65535) {
    issues.push({ field: "stratumPort", message: "Stratum port must be between 1024 and 65535." });
  }

  const sharesPerMin = Number(input.sharesPerMinute);
  if (!Number.isSafeInteger(sharesPerMin) || sharesPerMin < 1 || sharesPerMin > 120) {
    issues.push({ field: "sharesPerMinute", message: "Target shares per minute must be between 1 and 120." });
  }

  const extranonce = Number(input.extranonceSize);
  if (!Number.isSafeInteger(extranonce) || extranonce < 1 || extranonce > 4) {
    issues.push({ field: "extranonceSize", message: "Extranonce size must be between 1 and 4 bytes." });
  }

  const minDiff = Number(input.minimumShareDifficulty);
  if (!Number.isSafeInteger(minDiff) || minDiff < 1 || minDiff > 4_294_967_296 || !isPowerOfTwo(minDiff)) {
    issues.push({ field: "minimumShareDifficulty", message: "Minimum share difficulty must be a power of 2 (1 to 4,294,967,296)." });
  }

  if (input.variableDifficulty === false && input.powerOfTwoClamp === true) {
    issues.push({ field: "powerOfTwoClamp", message: "Power-of-two clamping requires variable difficulty to be active." });
  }

  if (issues.length > 0) {
    return { isValid: false, issues };
  }

  return {
    isValid: true,
    issues: [],
    cleanSettings: {
      stratumPort: port,
      variableDifficulty: Boolean(input.variableDifficulty),
      sharesPerMinute: sharesPerMin,
      powerOfTwoClamp: Boolean(input.powerOfTwoClamp),
      extranonceSize: extranonce,
      minimumShareDifficulty: minDiff,
    },
  };
};

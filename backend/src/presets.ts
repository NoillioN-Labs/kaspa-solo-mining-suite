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
  manufacturer: string;
  hashrateNominal: string;
  description: string;
  settings: BridgeSettings;
}

export const PRESET_CATALOG: Record<string, PresetProfile> = {
  // Automatic / Universal Defaults
  automatic: {
    id: "automatic",
    name: "Automatic (Universal)",
    manufacturer: "Universal",
    hashrateNominal: "Auto",
    description: "Adaptive vardiff suitable for mixed fleets or general miners.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 2048,
    },
  },

  // IceRiver Series
  "iceriver-ks0": {
    id: "iceriver-ks0",
    name: "IceRiver KS0 / KS0 Pro",
    manufacturer: "IceRiver",
    hashrateNominal: "100 - 200 GH/s",
    description: "Low-diff tuning optimized for entry-level IceRiver desktop units.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 24,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 64,
    },
  },
  "iceriver-ks1-ks2": {
    id: "iceriver-ks1-ks2",
    name: "IceRiver KS1 / KS2",
    manufacturer: "IceRiver",
    hashrateNominal: "1 - 2 TH/s",
    description: "Tuned vardiff for mid-tier KS1 & KS2 units.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 28,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 512,
    },
  },
  "iceriver-ks3": {
    id: "iceriver-ks3",
    name: "IceRiver KS3 / KS3M / KS3L",
    manufacturer: "IceRiver",
    hashrateNominal: "6 - 8 TH/s",
    description: "High-throughput vardiff for IceRiver KS3 family.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 2048,
    },
  },
  "iceriver-ks5": {
    id: "iceriver-ks5",
    name: "IceRiver KS5L / KS5M",
    manufacturer: "IceRiver",
    hashrateNominal: "12 - 15 TH/s",
    description: "Optimized for high-hashrate KS5 series with power-of-two clamping.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 32,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 4096,
    },
  },
  "iceriver-ks7": {
    id: "iceriver-ks7",
    name: "IceRiver KS7 / KS7 Lite",
    manufacturer: "IceRiver",
    hashrateNominal: "20 - 25 TH/s",
    description: "Tested enterprise configuration for IceRiver flagship KS7 series.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 35,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 8192,
    },
  },

  // Bitmain Antminer Series
  "antminer-ks3": {
    id: "antminer-ks3",
    name: "Bitmain Antminer KS3",
    manufacturer: "Bitmain",
    hashrateNominal: "9.4 TH/s",
    description: "Tuned for Antminer KS3 hardware stability.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 2048,
    },
  },
  "antminer-ks5": {
    id: "antminer-ks5",
    name: "Bitmain Antminer KS5 / KS5 Pro",
    manufacturer: "Bitmain",
    hashrateNominal: "20 - 21 TH/s",
    description: "High difficulty starting floor for Antminer KS5 flagships.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 35,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 8192,
    },
  },

  // Desiwe / Windminer
  "desiwe-k11": {
    id: "desiwe-k11",
    name: "Desiwe / Windminer K11",
    manufacturer: "Desiwe",
    hashrateNominal: "11 TH/s",
    description: "Custom share frequency for Windminer K11 ASIC architecture.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 30,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 4096,
    },
  },

  // Goldshell
  "goldshell-kabox": {
    id: "goldshell-kabox",
    name: "Goldshell KA-BOX / Pro",
    manufacturer: "Goldshell",
    hashrateNominal: "1.6 - 2.4 TH/s",
    description: "Low-latency compact miner preset for Goldshell home units.",
    settings: {
      stratumPort: 5555,
      variableDifficulty: true,
      sharesPerMinute: 25,
      powerOfTwoClamp: true,
      extranonceSize: 2,
      minimumShareDifficulty: 512,
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

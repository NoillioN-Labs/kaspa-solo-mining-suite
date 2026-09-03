# NoillioN Labs Umbrel Community App Store

This repository is an official **Umbrel Community App Store** publishing the **Kaspa Solo Mining Console (All-In-One)**.

---

## What the app provides

- **100% Self-Contained Solo Mining:** Bundles the official **Rusty Kaspad Full Node**, the **Rusty Kaspa Stratum Bridge v2.0.1**, and a **Modern High-Performance Management Console** in a single one-click app (zero external dependencies).
- **Interactive Block Celebrations:** Live celebratory confetti particle physics and golden block trophy display with Sompi & KAS reward breakdown whenever a solo block is mined.
- **Tuned ASIC Hardware Presets:** Out-of-the-box optimized configurations for:
  - **IceRiver:** KS0 / Pro, KS1 / KS2, KS3 / M / L, KS5L / KS5M, KS7 / KS7 Lite
  - **Bitmain Antminer:** KS3, KS5, KS5 Pro
  - **Desiwe / Windminer:** K11
  - **Goldshell:** KA-BOX / Pro
  - **Universal / Automatic Vardiff**
- **Modern Responsive Dashboard:** Fast, lightweight Vite + React interface with Dark & Light modes, per-worker share tracking, and LAN connection guidance for your ASICs on port `5555`.

---

## How to Install on Umbrel

1. On your Umbrel server, open **App Store → Community App Stores → Add**.
2. Paste this repository URL:
   ```
   https://github.com/NoillioN-Labs/kaspa-solo-mining-umbrel-store
   ```
3. Open the **NoillioN Labs** community store section and click **Install** on **Kaspa Solo Mining Console**.
4. Configure your ASIC miners on your local network to point to:
   ```
   stratum+tcp://<YOUR_UMBREL_IP>:5555
   ```

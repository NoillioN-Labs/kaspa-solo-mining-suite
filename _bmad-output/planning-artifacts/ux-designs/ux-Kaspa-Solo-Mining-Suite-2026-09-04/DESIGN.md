---
title: Kaspa Solo Mining Suite DESIGN
status: final
created: 2026-09-04
updated: 2026-09-04
colors:
  primary: "#70C7BA" # Kaspa Teal
  background: "#121212" # Umbrel Dark
  surface: "#1E1E1E" # Umbrel Surface
  text: "#FFFFFF"
  danger: "#FF4D4D"
typography:
  sans: "Inter, sans-serif"
  mono: "Fira Code, monospace"
rounded:
  md: "8px"
  lg: "12px"
spacing:
  4: "16px"
  6: "24px"
---
# Brand & Style
The aesthetic mimics the native Umbrel OS design system, feeling seamlessly integrated as a first-party app. It relies on a "Dark Mode by Default" philosophy, using deep greys and blacks anchored by the signature Kaspa Teal (`#70C7BA`) for accents and primary actions.

# Colors
- **Primary:** `#70C7BA` (Kaspa Teal) used for active states, primary buttons, and successful data graphs.
- **Background:** `#121212` (Umbrel Native Dark base)
- **Surface:** `#1E1E1E` (Umbrel Native Surface) for cards and modals.
- **Text:** `#FFFFFF` (Primary) and `#A0A0A0` (Secondary text).
- **Warning/Danger:** `#FF4D4D` for hardware temperature alerts and connection errors.

# Typography
- **Primary Font:** `Inter` (standard Umbrel sans-serif) for all UI copy, headers, and dashboard labels.
- **Numbers/Data:** `Fira Code` (or a legible monospace) for hashrate digits, Kaspa amounts, and block hashes to ensure alignment in tables and charts.

# Layout & Spacing
- The dashboard uses a modular CSS Grid, segmenting distinct data sets (Hashrate, Rewards, Temps) into distinct cards.
- Heavy use of padding (24px standard for cards) to keep the UI breathable and uncluttered, preventing information overload.

# Elevation & Depth
- Minimal drop shadows. Depth and separation are achieved primarily through background color contrast (`#121212` base vs `#1E1E1E` surface) and subtle 1px borders (`#333333`).

# Shapes
- `8px` and `12px` border radii on all cards and buttons to match Umbrel's soft, approachable tech aesthetic.

# Components
- **Graphs/Charts:** Area charts for Hashrate, stacked bar charts for Reward composition (Subsidies, Fees, DAG).
- **GHOSTDAG Stream:** Real-time HTML5 canvas rendering 10 BPS DAG blocks with blue/gold consensus distinction and pulsing connections.
- **Metric Cards:** Large typography for the primary number, with subtle sparklines or deltas (e.g., "+407.55 KAS (24h)") underneath.
- **Status Indicator:** Glowing dot (Green/Yellow/Red) and pulsating amber badge indicating ASIC connection and Node Sync state.
- **Mobile Navigation:** Responsive hamburger drawer with backdrop dismissal, smooth transitions, and 48px touch targets for small screens.
- **Kaspa Branding:** Official high-contrast SVG emblem with cropped viewBox (`40 40 117 117`) and teal backlight glow.

# Do's and Don'ts
- **Do:** Use visual graphs (charts, sparklines, progress rings, canvas visualizers) to represent data.
- **Don't:** Rely on dense, non-scrollable data tables or intrusive full-screen modal popups for routine alerts.

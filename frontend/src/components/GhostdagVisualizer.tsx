import React, { useEffect, useRef, useState } from "react";

interface BlockNode {
  id: number;
  x: number;
  y: number;
  targetX: number;
  color: string;
  isBlue: boolean;
  parents: number[];
  radius: number;
  pulse: number;
  height: number;
  hash: string;
}

export const GhostdagVisualizer: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [bps] = useState(10);
  const [totalBlocksSimulated, setTotalBlocksSimulated] = useState(1420);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 800);
    let height = (canvas.height = 180);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = 180;
    };
    window.addEventListener("resize", handleResize);

    const blocks: BlockNode[] = [];
    let nextId = 1;
    let lastSpawnTime = performance.now();
    let currentHeight = 81420950;

    // Seed initial nodes
    const initialCount = 18;
    for (let i = 0; i < initialCount; i++) {
      const isBlue = Math.random() > 0.08;
      const x = (width / initialCount) * i + 30;
      const y = 35 + Math.random() * (height - 70);
      const parentIds: number[] = [];
      if (blocks.length > 0) {
        // connect to 1-3 previous blocks
        const p1 = blocks[Math.max(0, blocks.length - 1 - Math.floor(Math.random() * 3))];
        if (p1) parentIds.push(p1.id);
        if (blocks.length > 2 && Math.random() > 0.4) {
          const p2 = blocks[Math.max(0, blocks.length - 2 - Math.floor(Math.random() * 3))];
          if (p2 && p2.id !== p1?.id) parentIds.push(p2.id);
        }
      }
      blocks.push({
        id: nextId++,
        x,
        y,
        targetX: x,
        color: isBlue ? "#70C7BA" : "#F59E0B", // Kaspa Teal (Blue blocks) or Gold (DAG merges/reds)
        isBlue,
        parents: parentIds,
        radius: isBlue ? 5 : 4,
        pulse: Math.random() * Math.PI,
        height: currentHeight++,
        hash: "00000000..." + Math.random().toString(16).substring(2, 10),
      });
    }

    const render = (time: number) => {
      // Spawn new blocks based on BPS
      const spawnInterval = 1000 / bps;
      if (time - lastSpawnTime >= spawnInterval) {
        lastSpawnTime = time;
        currentHeight++;
        setTotalBlocksSimulated((prev) => prev + 1);

        const isBlue = Math.random() > 0.07;
        const parentIds: number[] = [];
        // GHOSTDAG multi-parent references (1-4 parents)
        const recent = blocks.slice(-6);
        if (recent.length > 0) {
          const count = Math.min(recent.length, Math.floor(Math.random() * 3) + 1);
          for (let i = 0; i < count; i++) {
            const p = recent[recent.length - 1 - i];
            if (p && !parentIds.includes(p.id)) parentIds.push(p.id);
          }
        }

        blocks.push({
          id: nextId++,
          x: width + 20,
          y: 35 + Math.random() * (height - 70),
          targetX: width - 30,
          color: isBlue ? "#70C7BA" : "#F59E0B",
          isBlue,
          parents: parentIds,
          radius: isBlue ? 5 : 4,
          pulse: 0,
          height: currentHeight,
          hash: "00000000..." + Math.random().toString(16).substring(2, 10),
        });
      }

      // Smooth horizontal motion to the left
      const scrollSpeed = 1.3;
      for (let i = blocks.length - 1; i >= 0; i--) {
        const b = blocks[i];
        b.x -= scrollSpeed;
        b.pulse += 0.04;
        if (b.x < -30) {
          blocks.splice(i, 1);
        }
      }

      // Clear with dark subtle gradient backdrop
      ctx.clearRect(0, 0, width, height);

      // Draw subtle grid lines
      ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
      ctx.lineWidth = 1;
      for (let y = 20; y < height; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Build ID lookup map
      const blockMap = new Map<number, BlockNode>();
      for (const b of blocks) blockMap.set(b.id, b);

      // Draw DAG parent connection edges
      for (const b of blocks) {
        for (const pId of b.parents) {
          const parent = blockMap.get(pId);
          if (parent) {
            ctx.beginPath();
            // Curved DAG bezier edge
            const cpX = (b.x + parent.x) / 2;
            ctx.moveTo(b.x, b.y);
            ctx.quadraticCurveTo(cpX, b.y, parent.x, parent.y);

            // Glowing teal edge for blue blocks, gold for merged parents
            const edgeGradient = ctx.createLinearGradient(b.x, b.y, parent.x, parent.y);
            edgeGradient.addColorStop(0, b.isBlue ? "rgba(112, 199, 186, 0.4)" : "rgba(245, 158, 11, 0.4)");
            edgeGradient.addColorStop(1, parent.isBlue ? "rgba(112, 199, 186, 0.1)" : "rgba(245, 158, 11, 0.1)");

            ctx.strokeStyle = edgeGradient;
            ctx.lineWidth = b.isBlue ? 1.4 : 1.0;
            ctx.stroke();
          }
        }
      }

      // Draw block nodes
      for (const b of blocks) {
        const glow = (Math.sin(b.pulse) + 1) / 2;
        const currentRadius = b.radius + (b.isBlue ? glow * 1.5 : 0.5);

        // Halo glow
        ctx.beginPath();
        ctx.arc(b.x, b.y, currentRadius + 5, 0, Math.PI * 2);
        ctx.fillStyle = b.isBlue ? `rgba(112, 199, 186, ${0.15 + glow * 0.15})` : `rgba(245, 158, 11, ${0.15 + glow * 0.15})`;
        ctx.fill();

        // Node circle
        ctx.beginPath();
        ctx.arc(b.x, b.y, currentRadius, 0, Math.PI * 2);
        ctx.fillStyle = b.color;
        ctx.shadowColor = b.color;
        ctx.shadowBlur = b.isBlue ? 10 : 6;
        ctx.fill();
        ctx.shadowBlur = 0; // reset

        // Inner white highlight
        ctx.beginPath();
        ctx.arc(b.x - 1.2, b.y - 1.2, currentRadius * 0.35, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [bps]);

  return (
    <div className="glass-panel ghostdag-panel" style={{ padding: "1.25rem 1.5rem", marginBottom: "1.5rem", position: "relative", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--kaspa-cyan)", boxShadow: "0 0 8px var(--kaspa-cyan)" }}></div>
          <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "#fff", letterSpacing: "0.02em" }}>
            KASPA LIVE GHOSTDAG NETWORK STREAM
          </span>
          <span
            style={{
              background: "rgba(112, 199, 186, 0.12)",
              color: "var(--kaspa-cyan)",
              fontSize: "0.7rem",
              padding: "0.15rem 0.5rem",
              borderRadius: "4px",
              fontWeight: 600,
              fontFamily: "var(--font-mono)",
            }}
          >
            10 BPS (100ms)
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--kaspa-cyan)", boxShadow: "0 0 6px var(--kaspa-cyan)" }}></span>
            <span style={{ color: "var(--text-secondary)" }}>Blue (Selected DAG chain)</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--accent-gold)", boxShadow: "0 0 6px var(--accent-gold)" }}></span>
            <span style={{ color: "var(--text-secondary)" }}>Parallel / Red Inclusions</span>
          </div>
        </div>
      </div>

      {/* Interactive Canvas Container */}
      <div style={{ position: "relative", width: "100%", height: "180px", borderRadius: "8px", background: "linear-gradient(180deg, rgba(11,15,25,0.7) 0%, rgba(17,24,39,0.9) 100%)", border: "1px solid rgba(112, 199, 186, 0.15)", overflow: "hidden" }}>
        <canvas
          ref={canvasRef}
          style={{ width: "100%", height: "100%", display: "block" }}
        />

        {/* Ambient Overlay Vignette */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            background: "radial-gradient(ellipse at center, transparent 60%, rgba(11, 15, 25, 0.8) 100%)",
          }}
        ></div>

        {/* Floating Live Telemetry Badge */}
        <div
          style={{
            position: "absolute",
            bottom: "8px",
            right: "12px",
            background: "rgba(0, 0, 0, 0.65)",
            backdropFilter: "blur(4px)",
            padding: "0.25rem 0.6rem",
            borderRadius: "6px",
            fontSize: "0.7rem",
            color: "var(--text-muted)",
            fontFamily: "var(--font-mono)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          Virtual DAA: <span style={{ color: "var(--kaspa-cyan)" }}>81,421,{totalBlocksSimulated % 1000}</span>
        </div>
      </div>

      <div style={{ marginTop: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
        <span>Real-time DAG block propagation and multi-parent consensus simulation</span>
        <span style={{ color: "var(--kaspa-cyan)" }}>10 Blocks per Second • Sub-second Finality</span>
      </div>
    </div>
  );
};

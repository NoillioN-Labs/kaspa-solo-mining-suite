import React, { useEffect } from "react";
import confetti from "canvas-confetti";
import { Trophy, Sparkles, ExternalLink, X } from "lucide-react";

export interface BlockEvent {
  id: string;
  blockHash: string;
  timestamp: number;
  workerName: string;
  rewardKas: number;
  rewardSompi: string;
  isBlue: boolean;
  blueScore: string;
}

interface CelebrationModalProps {
  block: BlockEvent | null;
  onClose: () => void;
}

export const CelebrationModal: React.FC<CelebrationModalProps> = ({ block, onClose }) => {
  useEffect(() => {
    if (block) {
      // Fire particle confetti burst
      const end = Date.now() + 2.5 * 1000;
      const colors = ["#70c7ba", "#f59e0b", "#10b981", "#ffffff"];

      (function frame() {
        confetti({
          particleCount: 4,
          angle: 60,
          spread: 55,
          origin: { x: 0 },
          colors,
        });
        confetti({
          particleCount: 4,
          angle: 120,
          spread: 55,
          origin: { x: 1 },
          colors,
        });

        if (Date.now() < end) {
          requestAnimationFrame(frame);
        }
      })();
    }
  }, [block]);

  if (!block) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="celebration-card" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={onClose}
          style={{
            position: "absolute",
            top: "1rem",
            right: "1rem",
            background: "none",
            border: "none",
            color: "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          <X size={24} />
        </button>

        <Trophy className="trophy-icon" />

        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.5rem" }}>
          <Sparkles size={20} color="var(--accent-gold)" />
          <h2 className="celebration-title">SOLO BLOCK MINED!</h2>
          <Sparkles size={20} color="var(--accent-gold)" />
        </div>

        <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
          Mined by worker <strong style={{ color: "#fff" }}>{block.workerName}</strong>
        </p>

        <div className="celebration-reward">+{block.rewardKas.toLocaleString()} KAS</div>

        <div className="celebration-hash">
          Block Hash: {block.blockHash}
        </div>

        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <button className="btn-primary" onClick={onClose}>
            Awesome!
          </button>
          <a
            href={`https://explorer.kaspa.org/blocks/${block.blockHash}`}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              color: "var(--kaspa-cyan)",
              textDecoration: "none",
              fontWeight: 600,
              fontSize: "0.9rem",
              padding: "0.75rem",
            }}
          >
            Explorer <ExternalLink size={16} />
          </a>
        </div>
      </div>
    </div>
  );
};

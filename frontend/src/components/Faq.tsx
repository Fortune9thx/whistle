import { useState } from "react";

const ITEMS: [string, string][] = [
  [
    "What does GenLayer actually decide?",
    "Whether two locked publisher desks report the same completed (FT) scoreline for the same fixture. No LLM is involved -- code alone maps that scoreline to 1X2.",
  ],
  [
    "What happens if the desks disagree?",
    "Every bettor gets their own stake back in full, zero fee. WHISTLE never guesses under conflict, a stale LIVE/PRE reading, or a postponed/abandoned match.",
  ],
  [
    "Why only one factory contract?",
    "Every Bundesliga fixture lives in one deployed contract -- no per-match redeploy, no fragmented liquidity.",
  ],
  [
    "What if nobody resolves the fixture?",
    "A 36-hour outer window forces an INCONCLUSIVE fallback. If it's still stuck after 7 days, anyone can force a full refund via recover_refund.",
  ],
  [
    "Can I appeal a bad call?",
    "Yes -- any bettor in the fixture can appeal within the appeal window, posting a bond scaled to the decisive pool. A stalled appeal reverts to the prior verdict after an hour.",
  ],
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div id="faq" style={{ maxWidth: 720, margin: "0 auto" }}>
      {ITEMS.map(([q, a], i) => (
        <div key={q} className="card-hairline" style={{ marginBottom: 10, overflow: "hidden" }}>
          <button
            onClick={() => setOpen(open === i ? null : i)}
            style={{
              width: "100%",
              textAlign: "left",
              background: "transparent",
              border: "none",
              color: "var(--text)",
              padding: "18px 20px",
              fontSize: 15,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            {q}
            <span className="mute">{open === i ? "−" : "+"}</span>
          </button>
          {open === i && (
            <p className="mute" style={{ padding: "0 20px 18px", fontSize: 14, lineHeight: 1.6, margin: 0 }}>
              {a}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

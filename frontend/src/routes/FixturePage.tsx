import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import * as api from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/networkStatusContext";
import { useWallet } from "../lib/whistle/walletContext";
import { useNow } from "../lib/whistle/useNow";
import { useConfig } from "../lib/whistle/useConfig";
import { formatGen, genToWei, shortAddr } from "../lib/whistle/format";
import { FixtureTicket } from "../components/FixtureTicket";
import type { Fixture } from "../lib/whistle/types";

const OUTCOMES = ["HOME", "DRAW", "AWAY"] as const;
const GROUNDS = ["SCORE", "STATUS", "FIXTURE", "REVISED"];
// Used only until get_config() lands; the live value always wins.
const RESOLVE_BOND_FALLBACK_WEI = 2n * 10n ** 16n;

export function FixturePage() {
  const { id } = useParams<{ id: string }>();
  const isLive = useIsLive();
  const { address, provider } = useWallet();
  const config = useConfig();
  // Hooks must run before any early return, so the clock is read here
  // and the time-derived gates below re-evaluate every tick.
  const now = useNow();
  const resolveBondWei = config ? BigInt(config.resolve_bond_wei) : RESOLVE_BOND_FALLBACK_WEI;
  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [scoreline, setScoreline] = useState<Record<string, unknown> | null>(null);
  const [tab, setTab] = useState<"ticket" | "evidence">("ticket");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [betAmount, setBetAmount] = useState("1");
  const [betOutcome, setBetOutcome] = useState<(typeof OUTCOMES)[number]>("HOME");

  const refresh = useCallback(() => {
    if (!isLive || !id) return;
    api.getFixture(id).then(setFixture).catch(() => setFixture(null));
    api.getScoreline(id).then(setScoreline).catch(() => setScoreline(null));
  }, [isLive, id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const ctx = provider && address ? { provider, account: address } : null;

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setMsg(null);
    try {
      await fn();
      setMsg(`${label}: confirmed`);
      refresh();
    } catch (e: any) {
      setMsg(`${label} failed: ${e?.message ?? e}`);
    } finally {
      setBusy(null);
    }
  }

  if (!isLive) {
    return <div className="empty-state">No live contract to read from yet.</div>;
  }
  if (!fixture || !id) {
    return <div className="empty-state">Loading fixture...</div>;
  }

  const canBet = fixture.state === "OPEN" && now < fixture.kickoff_unix;
  const canResolve = fixture.state === "OPEN" && now >= fixture.kickoff_unix && Number(fixture.total_pool) > 0;
  const canFinalize = fixture.state === "PENDING";
  const canAppeal = fixture.state === "PENDING";
  const canReAdjudicate = fixture.state === "APPEALED";
  const canLapse = fixture.state === "APPEALED";
  const canCancel = fixture.state === "OPEN" && Number(fixture.total_pool) === 0;
  const canExpire = fixture.state === "OPEN" && now >= fixture.kickoff_unix && Number(fixture.total_pool) === 0;
  const canClaim = fixture.state === "FINALIZED" || fixture.state === "INCONCLUSIVE";
  const canReclaim = fixture.state === "FINALIZED" || fixture.state === "INCONCLUSIVE";
  const canRecover = ["OPEN", "PENDING", "APPEALED"].includes(fixture.state);

  return (
    <div>
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <button className={`app-tab ${tab === "ticket" ? "active" : ""}`} onClick={() => setTab("ticket")}>
          Ticket
        </button>
        <button className={`app-tab ${tab === "evidence" ? "active" : ""}`} onClick={() => setTab("evidence")}>
          Evidence
        </button>
      </div>

      {tab === "ticket" ? (
        <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 32 }}>
          <FixtureTicket fixture={fixture} />

          <div>
            {!ctx && (
              <p className="mute" style={{ marginBottom: 16 }}>
                Connect a wallet on Studio Next (61997) to bet or act on this fixture.
              </p>
            )}

            {canBet && ctx && (
              <div className="card" style={{ marginBottom: 16 }}>
                <h3 style={{ marginTop: 0 }}>Place a bet</h3>
                <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                  {OUTCOMES.map((o) => (
                    <button
                      key={o}
                      className={`pill ${betOutcome === o ? "pill-up" : ""}`}
                      style={{ cursor: "pointer", background: "transparent" }}
                      onClick={() => setBetOutcome(o)}
                    >
                      {o}
                    </button>
                  ))}
                </div>
                <input
                  className="mono"
                  value={betAmount}
                  onChange={(e) => setBetAmount(e.target.value)}
                  style={{ padding: 8, borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--text)", width: 120 }}
                />
                <button
                  className="btn btn-primary btn-sm"
                  style={{ marginLeft: 10 }}
                  disabled={busy !== null}
                  onClick={() => run("place_bet", () => api.placeBet(ctx, id, betOutcome, genToWei(betAmount)))}
                >
                  Bet {betAmount} GEN on {betOutcome}
                </button>
              </div>
            )}

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {canResolve && ctx && (
                <ActionButton label="resolve" busy={busy} onClick={() => run("resolve", () => api.resolveFixture(ctx, id, resolveBondWei))} />
              )}
              {canFinalize && (
                <ActionButton label="finalize" busy={busy} onClick={() => run("finalize", () => api.finalizeFixture(ctx!, id))} disabled={!ctx} />
              )}
              {canAppeal && ctx && (
                <ActionButton
                  label="appeal"
                  busy={busy}
                  onClick={() => run("appeal", () => api.appealFixture(ctx, id, GROUNDS[0], genToWei("0.05")))}
                />
              )}
              {canReAdjudicate && ctx && (
                <ActionButton label="re_adjudicate" busy={busy} onClick={() => run("re_adjudicate", () => api.reAdjudicate(ctx, id, resolveBondWei))} />
              )}
              {canLapse && (
                <ActionButton label="lapse_appeal" busy={busy} onClick={() => run("lapse_appeal", () => api.lapseAppeal(ctx!, id))} disabled={!ctx} />
              )}
              {canCancel && ctx && (
                <ActionButton label="cancel_fixture" busy={busy} onClick={() => run("cancel_fixture", () => api.cancelFixture(ctx, id))} />
              )}
              {canExpire && (
                <ActionButton label="expire_fixture" busy={busy} onClick={() => run("expire_fixture", () => api.expireFixture(ctx!, id))} disabled={!ctx} />
              )}
              {canClaim && ctx && (
                <ActionButton label="claim" busy={busy} onClick={() => run("claim", () => api.claimFixture(ctx, id))} />
              )}
              {canReclaim && ctx && (
                <ActionButton label="reclaim_bonds" busy={busy} onClick={() => run("reclaim_bonds", () => api.reclaimBonds(ctx, id))} />
              )}
              {canRecover && ctx && (
                <ActionButton label="recover_refund" busy={busy} onClick={() => run("recover_refund", () => api.recoverRefund(ctx, id))} />
              )}
            </div>

            {msg && <p className="mute" style={{ marginTop: 16 }}>{msg}</p>}

            <div className="card" style={{ marginTop: 20 }}>
              <h3 style={{ marginTop: 0 }}>Details</h3>
              <Row label="Creator" value={shortAddr(fixture.creator)} />
              <Row label="Resolver" value={fixture.resolver ? shortAddr(fixture.resolver) : "-"} />
              <Row label="Verdict" value={fixture.verdict ?? "-"} />
              <Row label="Code" value={fixture.code ?? "-"} />
              <Row label="Total pool" value={`${formatGen(fixture.total_pool)} GEN`} />
            </div>
          </div>
        </div>
      ) : (
        <div className="card mono" style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>
          {scoreline && Object.keys(scoreline).length > 0 ? JSON.stringify(scoreline, null, 2) : "No scoreline recorded yet."}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13.5 }}>
      <span className="mute">{label}</span>
      <span className="mono">{value}</span>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  busy,
  disabled,
}: {
  label: string;
  onClick: () => void;
  busy: string | null;
  disabled?: boolean;
}) {
  return (
    <button className="btn btn-ghost btn-sm" onClick={onClick} disabled={disabled || busy !== null}>
      {busy === label ? "waiting for consensus..." : label}
    </button>
  );
}

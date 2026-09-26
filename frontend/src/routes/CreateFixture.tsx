import { useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/NetworkStatusProvider";
import { useWallet } from "../lib/whistle/WalletProvider";

const CREATE_BOND_GEN = "0.05";
const MIN_LEAD_HOURS = 2;

export function CreateFixture() {
  const isLive = useIsLive();
  const { address, provider } = useWallet();
  const navigate = useNavigate();

  const [fixtureId, setFixtureId] = useState("");
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  const [kickoff, setKickoff] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ctx = provider && address ? { provider, account: address } : null;

  async function submit() {
    if (!ctx || !fixtureId || !home || !away || !kickoff) return;
    setBusy(true);
    setError(null);
    try {
      const kickoffUnix = Math.floor(new Date(kickoff).getTime() / 1000);
      await api.createFixture(ctx, fixtureId, home, away, kickoffUnix, 5n * 10n ** 16n);
      navigate(`/app/f/${fixtureId}`);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!isLive) {
    return <div className="empty-state">No live contract to write to yet.</div>;
  }

  const minKickoff = new Date(Date.now() + (MIN_LEAD_HOURS * 3600 + 60) * 1000).toISOString().slice(0, 16);

  return (
    <div style={{ maxWidth: 480 }}>
      <h1 style={{ fontSize: 22 }}>Create fixture</h1>
      <p className="mute" style={{ fontSize: 13.5, marginBottom: 24 }}>
        Kickoff must be at least {MIN_LEAD_HOURS} hours out. Posting this
        fixture requires a {CREATE_BOND_GEN} GEN create bond, slashed to
        treasury only if it reaches kickoff with zero bets.
      </p>

      {!ctx && <p className="pill pill-warn" style={{ marginBottom: 16 }}>Connect a wallet on Studio Next to create a fixture.</p>}

      <Field label="Fixture id">
        <input value={fixtureId} onChange={(e) => setFixtureId(e.target.value)} placeholder="ucl-2026-md1-001" />
      </Field>
      <Field label="Home">
        <input value={home} onChange={(e) => setHome(e.target.value)} placeholder="Real Madrid" />
      </Field>
      <Field label="Away">
        <input value={away} onChange={(e) => setAway(e.target.value)} placeholder="Bayern Munich" />
      </Field>
      <Field label="Kickoff (local time)">
        <input type="datetime-local" min={minKickoff} value={kickoff} onChange={(e) => setKickoff(e.target.value)} />
      </Field>

      {error && <p className="pill pill-down" style={{ marginBottom: 16 }}>{error}</p>}

      <button className="btn btn-primary" disabled={!ctx || busy} onClick={submit}>
        {busy ? "waiting for consensus..." : `Create (${CREATE_BOND_GEN} GEN bond)`}
      </button>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label className="mute" style={{ display: "block", fontSize: 12.5, marginBottom: 6 }}>
        {label}
      </label>
      <div className="field-input">{children}</div>
    </div>
  );
}

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/NetworkStatusProvider";
import { useWallet } from "../lib/whistle/WalletProvider";
import { FixtureTicket } from "../components/FixtureTicket";
import type { Fixture } from "../lib/whistle/types";

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

  const previewFixture: Partial<Fixture> = useMemo(() => {
    const kickoffUnix = kickoff ? Math.floor(new Date(kickoff).getTime() / 1000) : undefined;
    return {
      fixture_id: fixtureId,
      competition: "UCL_LP",
      home: home || "Home",
      away: away || "Away",
      state: "OPEN",
      kickoff_unix: kickoffUnix ?? Math.floor(Date.now() / 1000) + MIN_LEAD_HOURS * 3600,
      pool_by_outcome: { HOME: "0", DRAW: "0", AWAY: "0" } as any,
    };
  }, [fixtureId, home, away, kickoff]);

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
    <div>
      <div className="section-eyebrow" style={{ textAlign: "left" }}>New fixture</div>
      <h1 style={{ fontSize: 26, margin: "0 0 8px", letterSpacing: "-0.01em" }}>Lock in a fixture</h1>
      <p className="mute" style={{ fontSize: 14, marginBottom: 32, maxWidth: 520 }}>
        Kickoff must be at least {MIN_LEAD_HOURS} hours out. Posting this
        fixture requires a {CREATE_BOND_GEN} GEN create bond, slashed to
        treasury only if it reaches kickoff with zero bets.
      </p>

      <div className="create-layout">
        <div className="card create-form-card">
          {!ctx && (
            <p className="pill pill-warn" style={{ marginBottom: 20 }}>
              Connect a wallet on Studio Next to create a fixture.
            </p>
          )}

          <Field label="Fixture id">
            <input value={fixtureId} onChange={(e) => setFixtureId(e.target.value)} placeholder="ucl-2026-md1-001" />
          </Field>
          <div className="create-form-row">
            <Field label="Home">
              <input value={home} onChange={(e) => setHome(e.target.value)} placeholder="Real Madrid" />
            </Field>
            <Field label="Away">
              <input value={away} onChange={(e) => setAway(e.target.value)} placeholder="Bayern Munich" />
            </Field>
          </div>
          <Field label="Kickoff (local time)">
            <input type="datetime-local" min={minKickoff} value={kickoff} onChange={(e) => setKickoff(e.target.value)} />
          </Field>

          {error && <p className="pill pill-down" style={{ marginTop: 4, marginBottom: 16 }}>{error}</p>}

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center", marginTop: 8 }} disabled={!ctx || busy} onClick={submit}>
            {busy ? "waiting for consensus..." : `Create (${CREATE_BOND_GEN} GEN bond)`}
          </button>
        </div>

        <div className="create-preview-col">
          <div className="create-preview-label mute">Live preview</div>
          <FixtureTicket fixture={previewFixture as Fixture} />

          <div className="card create-econ-card">
            <div className="create-econ-row">
              <span className="mute">Create bond</span>
              <span className="mono">{CREATE_BOND_GEN} GEN</span>
            </div>
            <div className="create-econ-row">
              <span className="mute">Min lead time</span>
              <span className="mono">{MIN_LEAD_HOURS}h</span>
            </div>
            <div className="create-econ-row">
              <span className="mute">Bond slashed if</span>
              <span>zero bets at kickoff</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <label className="mute" style={{ display: "block", fontSize: 12.5, marginBottom: 7 }}>
        {label}
      </label>
      <div className="field-input">{children}</div>
    </div>
  );
}

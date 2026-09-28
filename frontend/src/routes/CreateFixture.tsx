import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/networkStatusContext";
import { useWallet } from "../lib/whistle/walletContext";
import { useNow } from "../lib/whistle/useNow";
import { useConfig } from "../lib/whistle/useConfig";
import { formatGen } from "../lib/whistle/format";
import { FixtureTicket } from "../components/FixtureTicket";
import type { Fixture } from "../lib/whistle/types";

// Fallbacks, used only until get_config() lands. The live on-chain
// values always take precedence -- see useConfig().
const CREATE_BOND_FALLBACK_WEI = 5n * 10n ** 16n;
const MIN_LEAD_FALLBACK_SECONDS = 7200;

export function CreateFixture() {
  const isLive = useIsLive();
  const { address, provider } = useWallet();
  const navigate = useNavigate();
  const config = useConfig();
  // Hooks run before any early return; the clock ticks so the minimum
  // selectable kickoff stays honest on a page left open.
  const now = useNow(30_000);

  const createBondWei = config ? BigInt(config.create_bond_wei) : CREATE_BOND_FALLBACK_WEI;
  const minLeadSeconds = config?.min_lead_seconds ?? MIN_LEAD_FALLBACK_SECONDS;
  const createBondGen = formatGen(createBondWei);
  const minLeadHours = Math.round((minLeadSeconds / 3600) * 10) / 10;

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
      kickoff_unix: kickoffUnix ?? now + minLeadSeconds,
      pool_by_outcome: { HOME: "0", DRAW: "0", AWAY: "0" } as any,
    };
  }, [fixtureId, home, away, kickoff, now, minLeadSeconds]);

  async function submit() {
    if (!ctx || !fixtureId || !home || !away || !kickoff) return;
    setBusy(true);
    setError(null);
    try {
      const kickoffUnix = Math.floor(new Date(kickoff).getTime() / 1000);
      await api.createFixture(ctx, fixtureId, home, away, kickoffUnix, createBondWei);
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

  const minKickoff = new Date((now + minLeadSeconds + 60) * 1000).toISOString().slice(0, 16);

  return (
    <div>
      <div className="section-eyebrow" style={{ textAlign: "left" }}>New fixture</div>
      <h1 style={{ fontSize: 26, margin: "0 0 8px", letterSpacing: "-0.01em" }}>Lock in a fixture</h1>
      <p className="mute" style={{ fontSize: 14, marginBottom: 32, maxWidth: 520 }}>
        Kickoff must be at least {minLeadHours} hours out. Posting this
        fixture requires a {createBondGen} GEN create bond, slashed to
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
            {busy ? "waiting for consensus..." : `Create (${createBondGen} GEN bond)`}
          </button>
        </div>

        <div className="create-preview-col">
          <div className="create-preview-label mute">Live preview</div>
          <FixtureTicket fixture={previewFixture as Fixture} />

          <div className="card create-econ-card">
            <div className="create-econ-row">
              <span className="mute">Create bond</span>
              <span className="mono">{createBondGen} GEN</span>
            </div>
            <div className="create-econ-row">
              <span className="mute">Min lead time</span>
              <span className="mono">{minLeadHours}h</span>
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

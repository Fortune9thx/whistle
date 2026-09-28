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
  const [deskARef, setDeskARef] = useState("");
  const [deskBRef, setDeskBRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ctx = provider && address ? { provider, account: address } : null;

  const previewFixture: Partial<Fixture> = useMemo(() => {
    const kickoffUnix = kickoff ? Math.floor(new Date(kickoff).getTime() / 1000) : undefined;
    return {
      fixture_id: fixtureId,
      competition: config?.competition ?? "BL1",
      home: home || "Home",
      away: away || "Away",
      state: "OPEN",
      kickoff_unix: kickoffUnix ?? now + minLeadSeconds,
      pool_by_outcome: { HOME: "0", DRAW: "0", AWAY: "0" } as any,
      desk_refs: { desk_a: deskARef, desk_b: deskBRef },
    };
  }, [fixtureId, home, away, kickoff, now, minLeadSeconds, config, deskARef, deskBRef]);

  // Mirrors the contract's own rule exactly (is_valid_desk_ref): a bare
  // run of digits, so a reference can never smuggle a path or query into
  // an otherwise locked publisher URL.
  const maxRefLen = config?.max_desk_ref_len ?? 24;
  const refIsValid = (ref: string) => /^\d+$/.test(ref.trim()) && ref.trim().length <= maxRefLen;
  const deskARefOk = refIsValid(deskARef);
  const deskBRefOk = refIsValid(deskBRef);
  const canSubmit = Boolean(ctx && fixtureId && home && away && kickoff && deskARefOk && deskBRefOk);

  async function submit() {
    if (!canSubmit || !ctx) return;
    setBusy(true);
    setError(null);
    try {
      const kickoffUnix = Math.floor(new Date(kickoff).getTime() / 1000);
      await api.createFixture(
        ctx,
        fixtureId,
        home,
        away,
        kickoffUnix,
        deskARef.trim(),
        deskBRef.trim(),
        createBondWei
      );
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
            <input value={fixtureId} onChange={(e) => setFixtureId(e.target.value)} placeholder="bl1-2026-md1-001" />
          </Field>
          <div className="create-form-row">
            <Field label="Home">
              <input value={home} onChange={(e) => setHome(e.target.value)} placeholder="Bayern Munich" />
            </Field>
            <Field label="Away">
              <input value={away} onChange={(e) => setAway(e.target.value)} placeholder="Borussia Dortmund" />
            </Field>
          </div>
          <div className="create-form-row">
            <Field label="desk_a reference (TheSportsDB idEvent)">
              <input
                value={deskARef}
                onChange={(e) => setDeskARef(e.target.value)}
                placeholder="441613"
                inputMode="numeric"
                aria-invalid={deskARef !== "" && !deskARefOk}
              />
            </Field>
            <Field label="desk_b reference (OpenLigaDB matchID)">
              <input
                value={deskBRef}
                onChange={(e) => setDeskBRef(e.target.value)}
                placeholder="66632"
                inputMode="numeric"
                aria-invalid={deskBRef !== "" && !deskBRefOk}
              />
            </Field>
          </div>
          <p className="mute" style={{ fontSize: 12.5, margin: "-10px 0 18px" }}>
            The two desks key the same match by unrelated ids, so each is
            named separately. Digits only, up to {maxRefLen} -- the contract
            rejects anything else, because this is the only caller-supplied
            part of either locked publisher URL.
          </p>
          <Field label="Kickoff (local time)">
            <input type="datetime-local" min={minKickoff} value={kickoff} onChange={(e) => setKickoff(e.target.value)} />
          </Field>

          {error && <p className="pill pill-down" style={{ marginTop: 4, marginBottom: 16 }}>{error}</p>}

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center", marginTop: 8 }} disabled={!canSubmit || busy} onClick={submit}>
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

import { useEffect, useState } from "react";
import * as api from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/networkStatusContext";
import { formatGen } from "../lib/whistle/format";
import type { Config } from "../lib/whistle/types";

export function Docs() {
  const isLive = useIsLive();
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    if (isLive) api.getConfig().then(setConfig).catch(() => setConfig(null));
  }, [isLive]);

  return (
    <div style={{ maxWidth: 640 }}>
      <h1 style={{ fontSize: 22 }}>Docs</h1>

      <Section title="What settles">
        Two locked publisher desks must independently report the same
        completed (FT) integer scoreline for the same fixture_id. No LLM
        is involved anywhere -- each validator independently fetches both
        desk URLs itself, and code alone maps the agreed scoreline to
        1X2. The contract never trusts a bare HOME/DRAW/AWAY claim from
        any source but its own derivation.
      </Section>

      <Section title="Failure policy">
        Any conflict, a stale LIVE/PRE reading past the earliest-resolve
        offset, a POSTPONED/ABANDONED match, or the 36-hour outer window
        lapsing unresolved settles INCONCLUSIVE: full stake back to every
        bettor, zero fee, no winner side.
      </Section>

      <Section title="Economics">
        {config ? (
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>Min bet: {formatGen(config.min_bet_wei)} GEN</li>
            <li>Create bond: {formatGen(config.create_bond_wei)} GEN</li>
            <li>Resolve bond: {formatGen(config.resolve_bond_wei)} GEN</li>
            <li>Fee: {config.fee_bps / 100}% of the decisive pot, split resolver/treasury</li>
            <li>Appeal bond floor: {formatGen(config.appeal_bond_floor_wei)} GEN</li>
          </ul>
        ) : (
          <span className="mute">Connect to a live contract to read current economics.</span>
        )}
      </Section>

      <Section title="Network">
        Studio Next / Studio Devnet, chain id 61997. State resets -- this
        is a preview network, not a durable mainnet.
      </Section>

      <Section title="Source">
        <a href="https://github.com/Fortune9thx/whistle" target="_blank" rel="noreferrer">
          github.com/Fortune9thx/whistle
        </a>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <h3 style={{ fontSize: 15, marginBottom: 8 }}>{title}</h3>
      <div className="mute" style={{ fontSize: 14, lineHeight: 1.7 }}>
        {children}
      </div>
    </div>
  );
}

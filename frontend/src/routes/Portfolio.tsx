import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/NetworkStatusProvider";
import { useWallet } from "../lib/whistle/WalletProvider";
import { formatGen } from "../lib/whistle/format";
import type { Fixture, Position } from "../lib/whistle/types";

export function Portfolio() {
  const isLive = useIsLive();
  const { address } = useWallet();
  const [positions, setPositions] = useState<Position[]>([]);
  const [claimable, setClaimable] = useState<Fixture[]>([]);

  useEffect(() => {
    if (!isLive || !address) return;
    api.getPositions(address).then((p) => setPositions(p.rows));
    api.getClaimable(address).then((p) => setClaimable(p.rows));
  }, [isLive, address]);

  if (!isLive) return <div className="empty-state">No live contract to read from yet.</div>;
  if (!address) return <div className="empty-state">Connect a wallet to see your portfolio.</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, marginBottom: 20 }}>Portfolio</h1>

      {claimable.length > 0 && (
        <div className="card" style={{ marginBottom: 24, borderColor: "var(--up)" }}>
          <h3 style={{ marginTop: 0 }}>Claimable</h3>
          {claimable.map((f) => (
            <div key={f.fixture_id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <Link to={`/app/f/${f.fixture_id}`}>{f.home} vs {f.away}</Link>
              <span className="pill pill-up">{f.state}</span>
            </div>
          ))}
        </div>
      )}

      {positions.length === 0 ? (
        <div className="empty-state">No positions yet.</div>
      ) : (
        <div className="grid-2x2">
          {positions.map((p) => (
            <Link key={p.fixture_id} to={`/app/f/${p.fixture_id}`} className="card" style={{ display: "block" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span className="mono mute" style={{ fontSize: 12 }}>{p.fixture_id}</span>
                <span className="pill">{p.state}</span>
              </div>
              <div>{p.outcome ?? "-"} &middot; {formatGen(p.amount)} GEN</div>
              {p.claimed && <div className="mute" style={{ fontSize: 12 }}>claimed</div>}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

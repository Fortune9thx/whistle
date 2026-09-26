import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/NetworkStatusProvider";
import { useWallet } from "../lib/whistle/WalletProvider";
import { formatGen } from "../lib/whistle/format";
import type { Position } from "../lib/whistle/types";

export function Activity() {
  const isLive = useIsLive();
  const { address } = useWallet();
  const [rows, setRows] = useState<Position[]>([]);

  useEffect(() => {
    if (!isLive || !address) return;
    api.getActivity(address).then((p) => setRows(p.rows));
  }, [isLive, address]);

  if (!isLive) return <div className="empty-state">No live contract to read from yet.</div>;
  if (!address) return <div className="empty-state">Connect a wallet to see your activity.</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, marginBottom: 20 }}>Activity</h1>
      {rows.length === 0 ? (
        <div className="empty-state">No activity yet.</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          {rows.map((r, i) => (
            <div
              key={r.fixture_id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "14px 20px",
                borderTop: i === 0 ? "none" : "1px solid var(--line)",
              }}
            >
              <Link to={`/app/f/${r.fixture_id}`}>{r.fixture_id}</Link>
              <span className="mute">{r.outcome} &middot; {formatGen(r.amount)} GEN &middot; {r.state}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

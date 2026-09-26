import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getBoard } from "../lib/whistle/api";
import { useIsLive } from "../lib/whistle/NetworkStatusProvider";
import { formatGen, formatKickoff } from "../lib/whistle/format";
import type { Fixture } from "../lib/whistle/types";

const STATE_FILTERS = ["", "OPEN", "PENDING", "APPEALED", "FINALIZED", "INCONCLUSIVE"];

export function Board() {
  const isLive = useIsLive();
  const [rows, setRows] = useState<Fixture[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLive) {
      setRows([]);
      return;
    }
    setLoading(true);
    setError(null);
    getBoard(0, 50, filter)
      .then((page) => setRows(page.rows))
      .catch((e) => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false));
  }, [isLive, filter]);

  if (!isLive) {
    return (
      <div className="empty-state">
        <p>No live contract to read from yet.</p>
        <p className="mute" style={{ fontSize: 13 }}>
          Check the banner above -- the board only ever shows real on-chain fixtures.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Board</h1>
        <Link to="/app/create" className="btn btn-primary btn-sm">
          Create fixture
        </Link>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {STATE_FILTERS.map((s) => (
          <button
            key={s || "ALL"}
            className={`pill ${filter === s ? "pill-up" : ""}`}
            style={{ cursor: "pointer", background: "transparent" }}
            onClick={() => setFilter(s)}
          >
            {s || "ALL"}
          </button>
        ))}
      </div>

      {loading && <p className="mute">Loading...</p>}
      {error && <p className="pill-down pill">{error}</p>}

      {!loading && rows.length === 0 && !error && (
        <div className="empty-state">
          <p>No fixtures yet.</p>
        </div>
      )}

      <div className="grid-2x2">
        {rows.map((f) => (
          <Link to={`/app/f/${f.fixture_id}`} key={f.fixture_id} className="card" style={{ display: "block" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
              <span className="mute mono" style={{ fontSize: 12 }}>
                {f.fixture_id}
              </span>
              <span className="pill">{f.state}</span>
            </div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>
              {f.home} vs {f.away}
            </div>
            <div className="mute mono" style={{ fontSize: 12.5 }}>
              {formatKickoff(f.kickoff_unix)} &middot; {formatGen(f.total_pool)} GEN pooled
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

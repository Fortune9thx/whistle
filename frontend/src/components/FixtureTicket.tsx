import { formatGen, formatKickoff, timeUntil } from "../lib/whistle/format";
import type { Fixture } from "../lib/whistle/types";

const OUTCOME_LABEL: Record<string, string> = { HOME: "1", DRAW: "X", AWAY: "2" };

export function FixtureTicket({ fixture, demo }: { fixture?: Fixture; demo?: boolean }) {
  const data: Partial<Fixture> = fixture ?? (demo ? DEMO_FIXTURE : {});
  const pools = data.pool_by_outcome ?? { HOME: "0", DRAW: "0", AWAY: "0" } as any;
  const total = Object.values(pools).reduce((a: number, b) => a + Number(b), 0) || 1;

  return (
    <div className="ticket card">
      <div className="ticket-top">
        <span className="mute" style={{ fontSize: 12.5 }}>
          {data.competition ?? "BL1"} &middot; FT 90
        </span>
        <span className={`pill ${data.state === "OPEN" ? "" : data.state === "FINALIZED" ? "pill-up" : "pill-warn"}`}>
          {data.state ?? "OPEN"}
        </span>
      </div>
      <div className="ticket-teams">
        <span>{data.home ?? "Home"}</span>
        <span className="mute">vs</span>
        <span>{data.away ?? "Away"}</span>
      </div>
      <div className="ticket-kickoff mute mono">
        {data.kickoff_unix ? `${formatKickoff(data.kickoff_unix)} · closes in ${timeUntil(data.kickoff_unix)}` : "kickoff TBD"}
      </div>
      <div className="ticket-bars">
        {(["HOME", "DRAW", "AWAY"] as const).map((o) => {
          const val = Number(pools[o] ?? 0);
          const pct = Math.round((val / total) * 100);
          return (
            <div className="ticket-bar-row" key={o}>
              <span className="ticket-bar-label mono">{OUTCOME_LABEL[o]}</span>
              <div className="ticket-bar-track">
                <div className="ticket-bar-fill" style={{ width: `${pct}%` }} />
              </div>
              <span className="mute mono ticket-bar-pct">{pct}%</span>
            </div>
          );
        })}
      </div>
      <div className="ticket-pool mono mute">{formatGen(total)} GEN pooled</div>
    </div>
  );
}

const DEMO_FIXTURE: Partial<Fixture> = {
  competition: "BL1",
  home: "Home FC",
  away: "Away FC",
  state: "OPEN",
  kickoff_unix: Math.floor(Date.now() / 1000) + 3600 * 6,
  pool_by_outcome: { HOME: "0", DRAW: "0", AWAY: "0" } as any,
};

export type Outcome = "HOME" | "DRAW" | "AWAY";
export type Verdict = Outcome | "INCONCLUSIVE";
export type FixtureState =
  | "OPEN"
  | "PENDING"
  | "APPEALED"
  | "FINALIZED"
  | "INCONCLUSIVE"
  | "CANCELED"
  | "EXPIRED";

export interface AppealRecord {
  appellant: string;
  ground: string;
  bond: string;
  opened_at: number;
  prior_verdict: string | null;
  prior_code: string | null;
}

export interface Fixture {
  fixture_id: string;
  competition: string;
  /** The publisher-side row this fixture is bound to on each locked desk.
   *  The two desks use unrelated id spaces, so both are recorded. */
  desk_refs?: { desk_a: string; desk_b: string };
  home: string;
  away: string;
  kickoff_unix: number;
  creator: string;
  state: FixtureState;
  locked: boolean;
  verdict: Verdict | null;
  code: string | null;
  total_pool: string;
  pool_by_outcome: Record<Outcome, string>;
  resolver: string | null;
  appeal: AppealRecord | null;
  last_state_change_at: number;
  create_bond_returned: boolean;
  create_bond_slashed: boolean;
  resolve_bond_returned: boolean;
}

export interface Position {
  fixture_id?: string;
  address?: string;
  outcome: Outcome | null;
  amount: string;
  claimed: boolean;
  state?: FixtureState;
}

export interface Config {
  competition: string;
  result_type: string;
  market: string;
  publishers: string[];
  min_lead_seconds: number;
  min_bet_wei: string;
  create_bond_wei: string;
  resolve_bond_wei: string;
  fee_bps: number;
  appeal_bond_floor_wei: string;
  resolve_earliest_offset: number;
  resolve_latest_offset: number;
  lapse_appeal_stall: number;
  recover_refund_after: number;
  max_open_per_creator: number;
  max_page_size: number;
  max_desk_ref_len: number;
  valid_appeal_grounds: string[];
  treasury: string;
  appeal_window_seconds: number;
  total_fixtures: number;
  chain_id: number;
  network: string;
  state_may_reset: boolean;
}

export interface Page<T> {
  rows: T[];
  next_cursor: number;
}

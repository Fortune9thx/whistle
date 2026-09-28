import { readContract, submitWrite } from "./sdk";
import type { Eip1193Provider } from "./wallet";
import type { Config, Fixture, Page, Position } from "./types";

export const getConfig = () => readContract<Config>("get_config");
export const getRegistry = () => readContract<Record<string, { host: string; format: string; html_table: boolean }>>("get_registry");
export const getFixture = (fixtureId: string) => readContract<Fixture>("get_fixture", [fixtureId]);
export const getBoard = (cursor = 0, limit = 50, stateFilter = "") =>
  readContract<Page<Fixture>>("get_board", [cursor, limit, stateFilter]);
export const getScoreline = (fixtureId: string) =>
  readContract<{ home: number; away: number; status: string } | Record<string, never>>("get_scoreline", [fixtureId]);
export const getPosition = (fixtureId: string, address: string) =>
  readContract<Position>("get_position", [fixtureId, address]);
export const getPositions = (address: string, cursor = 0, limit = 50) =>
  readContract<Page<Position>>("get_positions", [address, cursor, limit]);
export const getClaimable = (address: string, cursor = 0, limit = 50) =>
  readContract<Page<Fixture>>("get_claimable", [address, cursor, limit]);
export const getActivity = (address: string, cursor = 0, limit = 50) =>
  readContract<Page<Position>>("get_activity", [address, cursor, limit]);

export interface WalletCtx {
  provider: Eip1193Provider;
  account: string;
}

export const createFixture = (
  ctx: WalletCtx,
  fixtureId: string,
  home: string,
  away: string,
  kickoffUnix: number,
  deskARef: string,
  deskBRef: string,
  bondWei: bigint
) =>
  submitWrite(
    ctx.provider,
    ctx.account,
    "create_fixture",
    [fixtureId, home, away, kickoffUnix, deskARef, deskBRef],
    bondWei
  );

export const placeBet = (ctx: WalletCtx, fixtureId: string, outcome: string, amountWei: bigint) =>
  submitWrite(ctx.provider, ctx.account, "place_bet", [fixtureId, outcome], amountWei);

export const resolveFixture = (ctx: WalletCtx, fixtureId: string, bondWei: bigint) =>
  submitWrite(ctx.provider, ctx.account, "resolve", [fixtureId], bondWei);

export const finalizeFixture = (ctx: WalletCtx, fixtureId: string) =>
  submitWrite(ctx.provider, ctx.account, "finalize", [fixtureId], 0n);

export const appealFixture = (ctx: WalletCtx, fixtureId: string, ground: string, bondWei: bigint) =>
  submitWrite(ctx.provider, ctx.account, "appeal", [fixtureId, ground], bondWei);

export const reAdjudicate = (ctx: WalletCtx, fixtureId: string, bondWei: bigint) =>
  submitWrite(ctx.provider, ctx.account, "re_adjudicate", [fixtureId], bondWei);

export const lapseAppeal = (ctx: WalletCtx, fixtureId: string) =>
  submitWrite(ctx.provider, ctx.account, "lapse_appeal", [fixtureId], 0n);

export const cancelFixture = (ctx: WalletCtx, fixtureId: string) =>
  submitWrite(ctx.provider, ctx.account, "cancel_fixture", [fixtureId], 0n);

export const expireFixture = (ctx: WalletCtx, fixtureId: string) =>
  submitWrite(ctx.provider, ctx.account, "expire_fixture", [fixtureId], 0n);

export const claimFixture = (ctx: WalletCtx, fixtureId: string) =>
  submitWrite(ctx.provider, ctx.account, "claim", [fixtureId], 0n);

export const recoverRefund = (ctx: WalletCtx, fixtureId: string) =>
  submitWrite(ctx.provider, ctx.account, "recover_refund", [fixtureId], 0n);

export const reclaimBonds = (ctx: WalletCtx, fixtureId: string) =>
  submitWrite(ctx.provider, ctx.account, "reclaim_bonds", [fixtureId], 0n);

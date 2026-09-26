import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { CONTRACT_ADDRESS } from "./network";
import type { Eip1193Provider } from "./wallet";

/**
 * A complete, non-zero fee distribution is required on every write --
 * a bare estimateTransactionFees() call, or a partial distribution, is
 * known to fail client-side (FeeValueMustBeNonZero) before the tx ever
 * reaches the chain. This object is the same shape confirmed against a
 * real successful transaction on this network -- see
 * docs/architecture.md and deploy/deploy.mjs.
 */
const FALLBACK_FEES = {
  distribution: {
    rotations: [0],
    appealRounds: 0,
    totalMessageFees: 0,
    executionConsumed: 0,
    receiptFeeMaxGasPrice: "300000000",
    storageFeeMaxGasPrice: "300000000",
    maxPriceGenPerTimeUnit: "2",
    executionBudgetPerRound: "94643100000000",
    leaderTimeunitsAllocation: "100",
    validatorTimeunitsAllocation: "200",
  },
  feeValue: 94643100002588n,
};

function readClient() {
  return createClient({ chain: studioDevnet });
}

export async function readContract<T = unknown>(
  functionName: string,
  args: any[] = []
): Promise<T> {
  const client = readClient();
  return client.readContract({
    address: CONTRACT_ADDRESS as `0x${string}`,
    functionName,
    args,
  }) as Promise<T>;
}

export interface WriteResult {
  hash: string;
  txExecutionResultName?: string;
}

/**
 * Methods that move real GEN OUT of the contract via
 * _Recipient(...).emit_transfer() -- claim, reclaim_bonds, and every
 * bond/fee-paying escape hatch. An EOA-directed value transfer only
 * actually executes at true FINALIZED, not the earlier "decided"
 * (ACCEPTED-equivalent) state -- waiting only for "decided" here would
 * let the UI say "confirmed" before the GEN has actually landed. Every
 * other write is state-only (or GEN moving IN, which is atomic with the
 * write itself) and "decided" is sufficient.
 */
const VALUE_OUT_FUNCTIONS = new Set([
  "claim",
  "reclaim_bonds",
  "finalize",
  "cancel_fixture",
  "expire_fixture",
  "lapse_appeal",
  "re_adjudicate",
  "recover_refund",
]);

/**
 * Waits for the transaction to actually reach the bar its own
 * side-effect requires (see VALUE_OUT_FUNCTIONS) and throws unless
 * execution genuinely returned -- a FINALIZED/ACCEPTED status is not
 * itself proof of success; a reverted write can still show up with a
 * real tx hash.
 */
export async function submitWrite(
  provider: Eip1193Provider,
  account: string,
  functionName: string,
  args: any[],
  value: bigint = 0n
): Promise<WriteResult> {
  const client = createClient({
    chain: studioDevnet,
    account: account as `0x${string}`,
    provider: provider as any,
  });

  let fees;
  try {
    fees = await client.estimateTransactionFeesForWrite({
      address: CONTRACT_ADDRESS as `0x${string}`,
      functionName,
      args,
      value,
    });
  } catch {
    fees = FALLBACK_FEES;
  }

  const hash = await client.writeContract({
    address: CONTRACT_ADDRESS as `0x${string}`,
    functionName,
    args,
    value,
    fees,
  });

  const needsFinalized = VALUE_OUT_FUNCTIONS.has(functionName);
  // Match the platform's own tooling default budget for the FINALIZED
  // case (genlayer CLI's `receipt` command: 100 attempts x 5s) rather
  // than reusing whatever short budget was tuned for "decided" --
  // FINALIZED has been observed taking several minutes longer.
  const receipt = await client
    .waitForTransactionReceipt(
      needsFinalized
        ? { hash, waitUntil: "finalized", interval: 5000, retries: 100 }
        : { hash, waitUntil: "decided" }
    )
    .catch(() => null);

  const tx = receipt ?? (await client.getTransaction({ hash }).catch(() => null));
  const resultName = (tx as any)?.txExecutionResultName as string | undefined;
  if (resultName && resultName !== "FINISHED_WITH_RETURN") {
    throw new Error(`Transaction did not succeed: ${resultName}`);
  }

  return { hash, txExecutionResultName: resultName };
}

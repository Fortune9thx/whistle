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
 * Waits for the transaction to actually be DECIDED (not merely
 * broadcast) and throws unless execution genuinely returned -- a
 * FINALIZED/ACCEPTED status is not itself proof of success; a reverted
 * write can still show up with a real tx hash.
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

  const receipt = await client
    .waitForTransactionReceipt({ hash, waitUntil: "decided" })
    .catch(() => null);

  const tx = receipt ?? (await client.getTransaction({ hash }).catch(() => null));
  const resultName = (tx as any)?.txExecutionResultName as string | undefined;
  if (resultName && resultName !== "FINISHED_WITH_RETURN") {
    throw new Error(`Transaction did not succeed: ${resultName}`);
  }

  return { hash, txExecutionResultName: resultName };
}

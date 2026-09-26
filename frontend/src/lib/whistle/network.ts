export const CHAIN_ID = 61997;
export const RPC_URL = "https://studio-dev.genlayer.com/api";
export const EXPLORER_URL = "https://explorer-studio-dev.genlayer.com";
export const STUDIO_URL = "https://studio-dev.genlayer.com";

export const CONTRACT_ADDRESS = (import.meta.env.VITE_CONTRACT_ADDRESS as string | undefined) || "";

export type LivenessState = "no_address" | "checking" | "live" | "no_code" | "rpc_down";

/**
 * Liveness MUST use gen_getContractSchema, never eth_getCode -- a
 * GenLayer intelligent contract is not an EVM contract, so eth_getCode
 * returns "0x" for a perfectly live, responding address. Confirmed
 * against a real deployed contract on a prior GenLayer build.
 */
export async function probeLiveness(address: string): Promise<LivenessState> {
  if (!address) return "no_address";
  try {
    const res = await fetch(RPC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "gen_getContractSchema",
        params: [address],
      }),
    });
    if (!res.ok) return "rpc_down";
    const json = await res.json();
    if (json.error) return "no_code";
    if (json.result) return "live";
    return "no_code";
  } catch {
    return "rpc_down";
  }
}

export function explorerAddressUrl(address: string): string {
  return `${EXPLORER_URL}/address/${address}`;
}

export function explorerTxUrl(hash: string): string {
  return `${EXPLORER_URL}/transactions/${hash}`;
}

import { CHAIN_ID, RPC_URL } from "./network";

export interface Eip1193Provider {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
  on?(event: string, handler: (...args: unknown[]) => void): void;
  removeListener?(event: string, handler: (...args: unknown[]) => void): void;
}

interface Eip6963ProviderDetail {
  info: { uuid: string; name: string; icon: string };
  provider: Eip1193Provider;
}

const CHAIN_ID_HEX = `0x${CHAIN_ID.toString(16)}`;

const discovered = new Map<string, Eip6963ProviderDetail>();
const listeners = new Set<() => void>();

function notify() {
  for (const l of listeners) l();
}

if (typeof window !== "undefined") {
  window.addEventListener("eip6963:announceProvider", (event) => {
    const detail = (event as CustomEvent<Eip6963ProviderDetail>).detail;
    if (detail?.provider && detail?.info?.uuid) {
      discovered.set(detail.info.uuid, detail);
      notify();
    }
  });
  window.dispatchEvent(new Event("eip6963:requestProvider"));

  // Late-injecting extensions: poll briefly, then subscribe for good.
  let attempts = 0;
  const poll = setInterval(() => {
    attempts += 1;
    window.dispatchEvent(new Event("eip6963:requestProvider"));
    if (attempts > 6) clearInterval(poll);
  }, 500);
}

export function subscribeWallets(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function listProviders(): Eip6963ProviderDetail[] {
  const list = Array.from(discovered.values());
  if (list.length === 0 && typeof window !== "undefined" && (window as any).ethereum) {
    return [
      {
        info: { uuid: "legacy", name: "Injected Wallet", icon: "" },
        provider: (window as any).ethereum as Eip1193Provider,
      },
    ];
  }
  return list;
}

export function hasWallet(): boolean {
  return listProviders().length > 0;
}

export async function connectWallet(
  provider: Eip1193Provider
): Promise<{ address: string; balanceWei: bigint }> {
  const accounts = (await provider.request({ method: "eth_requestAccounts" })) as string[];
  const address = accounts[0];
  await ensureChain(provider);
  const balanceWei = await getBalance(provider, address);
  return { address, balanceWei };
}

export async function ensureChain(provider: Eip1193Provider): Promise<void> {
  try {
    const currentChainId = (await provider.request({ method: "eth_chainId" })) as string;
    if (currentChainId?.toLowerCase() === CHAIN_ID_HEX) return;
    try {
      await provider.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: CHAIN_ID_HEX }],
      });
    } catch (switchErr: any) {
      if (switchErr?.code === 4902) {
        await provider.request({
          method: "wallet_addEthereumChain",
          params: [
            {
              chainId: CHAIN_ID_HEX,
              chainName: "GenLayer Studio Next",
              nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
              rpcUrls: [RPC_URL],
              blockExplorerUrls: ["https://explorer-studio-dev.genlayer.com"],
            },
          ],
        });
      } else {
        throw switchErr;
      }
    }
  } catch {
    // best-effort -- the write path itself will fail loudly if the
    // wallet is still on the wrong network.
  }
}

export async function getBalance(provider: Eip1193Provider, address: string): Promise<bigint> {
  try {
    const hex = (await provider.request({
      method: "eth_getBalance",
      params: [address, "latest"],
    })) as string;
    return BigInt(hex);
  } catch {
    return 0n;
  }
}

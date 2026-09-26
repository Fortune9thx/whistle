import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import {
  connectWallet,
  getBalance,
  hasWallet,
  listProviders,
  subscribeWallets,
  type Eip1193Provider,
} from "./wallet";

interface WalletState {
  hasWallet: boolean;
  address: string | null;
  balanceWei: bigint;
  connecting: boolean;
  connect: () => Promise<void>;
  provider: Eip1193Provider | null;
}

const WalletContext = createContext<WalletState | null>(null);

export function WalletProvider({ children }: { children: ReactNode }) {
  const [walletsSeen, setWalletsSeen] = useState(hasWallet());
  const [address, setAddress] = useState<string | null>(null);
  const [balanceWei, setBalanceWei] = useState<bigint>(0n);
  const [connecting, setConnecting] = useState(false);
  const [provider, setProvider] = useState<Eip1193Provider | null>(null);

  useEffect(() => subscribeWallets(() => setWalletsSeen(hasWallet())), []);

  const connect = useCallback(async () => {
    const providers = listProviders();
    if (providers.length === 0) return;
    setConnecting(true);
    try {
      const chosen = providers[0].provider;
      const { address: addr, balanceWei: bal } = await connectWallet(chosen);
      setProvider(chosen);
      setAddress(addr);
      setBalanceWei(bal);
    } finally {
      setConnecting(false);
    }
  }, []);

  useEffect(() => {
    if (!provider || !address) return;
    const refresh = () => getBalance(provider, address).then(setBalanceWei);
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, [provider, address]);

  return (
    <WalletContext.Provider
      value={{ hasWallet: walletsSeen, address, balanceWei, connecting, connect, provider }}
    >
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet(): WalletState {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used inside WalletProvider");
  return ctx;
}

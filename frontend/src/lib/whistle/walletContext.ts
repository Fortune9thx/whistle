import { createContext, useContext } from "react";
import type { Eip1193Provider } from "./wallet";

export interface WalletState {
  hasWallet: boolean;
  address: string | null;
  balanceWei: bigint;
  connecting: boolean;
  connect: () => Promise<void>;
  provider: Eip1193Provider | null;
}

export const WalletContext = createContext<WalletState | null>(null);

export function useWallet(): WalletState {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used inside WalletProvider");
  return ctx;
}

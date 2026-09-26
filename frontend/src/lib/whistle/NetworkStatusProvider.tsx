import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { CONTRACT_ADDRESS, probeLiveness, type LivenessState } from "./network";

const NetworkStatusContext = createContext<LivenessState>("no_address");

export function NetworkStatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LivenessState>(CONTRACT_ADDRESS ? "checking" : "no_address");

  useEffect(() => {
    if (!CONTRACT_ADDRESS) {
      setState("no_address");
      return;
    }
    let cancelled = false;
    const check = () => probeLiveness(CONTRACT_ADDRESS).then((s) => !cancelled && setState(s));
    check();
    const id = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return <NetworkStatusContext.Provider value={state}>{children}</NetworkStatusContext.Provider>;
}

export function useLivenessState(): LivenessState {
  return useContext(NetworkStatusContext);
}

export function useIsLive(): boolean {
  return useLivenessState() === "live";
}

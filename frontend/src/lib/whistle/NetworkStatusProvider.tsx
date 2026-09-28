import { useEffect, useState, type ReactNode } from "react";
import { CONTRACT_ADDRESS, probeLiveness, type LivenessState } from "./network";
import { NetworkStatusContext } from "./networkStatusContext";

export function NetworkStatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LivenessState>(CONTRACT_ADDRESS ? "checking" : "no_address");

  useEffect(() => {
    // With no configured address the initial state is already
    // "no_address" -- nothing to probe, and nothing to set.
    if (!CONTRACT_ADDRESS) return;
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

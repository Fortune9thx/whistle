import { createContext, useContext } from "react";
import type { LivenessState } from "./network";

export const NetworkStatusContext = createContext<LivenessState>("no_address");

export function useLivenessState(): LivenessState {
  return useContext(NetworkStatusContext);
}

export function useIsLive(): boolean {
  return useLivenessState() === "live";
}

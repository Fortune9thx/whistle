import { useEffect, useState } from "react";

/**
 * A ticking wall-clock, in whole seconds since the epoch.
 *
 * Reading `Date.now()` directly during render produces a value that only
 * refreshes when something *else* re-renders the component -- so a page
 * left open across kickoff keeps offering actions the contract will
 * reject (betting after kickoff, for instance). Holding the clock in
 * state and advancing it on an interval makes every time-derived gate
 * re-evaluate on its own.
 */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    const id = setInterval(() => setNow(Math.floor(Date.now() / 1000)), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return now;
}

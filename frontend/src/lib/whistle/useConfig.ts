import { useEffect, useState } from "react";
import * as api from "./api";
import { useIsLive } from "./networkStatusContext";
import type { Config } from "./types";

/**
 * The live on-chain constitution.
 *
 * Every economic constant the UI shows or sends (bond sizes, the minimum
 * kickoff lead) is read from `get_config()` rather than duplicated as a
 * literal here. A redeploy that changes a constant then updates the UI
 * automatically instead of silently making it lie about what the
 * contract will accept.
 */
export function useConfig(): Config | null {
  const isLive = useIsLive();
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    if (!isLive) return;
    let cancelled = false;
    api.getConfig()
      .then((c) => !cancelled && setConfig(c))
      .catch(() => !cancelled && setConfig(null));
    return () => {
      cancelled = true;
    };
  }, [isLive]);

  return config;
}

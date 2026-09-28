import { CONTRACT_ADDRESS, explorerAddressUrl } from "../lib/whistle/network";
import { useLivenessState } from "../lib/whistle/networkStatusContext";

export function Banner() {
  const state = useLivenessState();

  if (state === "live") {
    return (
      <div className="banner banner-live">
        live &middot;{" "}
        <a href={explorerAddressUrl(CONTRACT_ADDRESS)} target="_blank" rel="noreferrer" className="mono">
          {CONTRACT_ADDRESS}
        </a>
      </div>
    );
  }
  if (state === "checking") return null;
  if (state === "no_address") {
    return <div className="banner banner-warn">Contract not deployed on Studio Next (61997).</div>;
  }
  if (state === "no_code") {
    return <div className="banner banner-warn">No code at this address. Studio Next was reset.</div>;
  }
  return <div className="banner banner-down">Cannot reach studio-dev.genlayer.com.</div>;
}

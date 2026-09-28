import { useWallet } from "../lib/whistle/walletContext";
import { formatGen, shortAddr } from "../lib/whistle/format";

export function WalletButton() {
  const { hasWallet, address, balanceWei, connecting, connect } = useWallet();

  if (address) {
    return (
      <div className="pill mono">
        {formatGen(balanceWei, 2)} GEN &middot; {shortAddr(address)}
      </div>
    );
  }

  if (!hasWallet) {
    return <span className="pill">No wallet detected</span>;
  }

  return (
    <button className="btn btn-primary btn-sm" onClick={connect} disabled={connecting}>
      {connecting ? "Connecting..." : "Connect"}
    </button>
  );
}

import { Link, useLocation } from "react-router-dom";
import { WalletButton } from "./WalletButton";

export function Nav() {
  const { pathname } = useLocation();
  const inApp = pathname.startsWith("/app");

  return (
    <header className="nav">
      <div className="container nav-inner">
        <Link to="/" className="wordmark">
          <span className="wordmark-dot" />
          WHISTLE
        </Link>
        {!inApp && (
          <nav className="nav-links">
            <a href="#how">How it settles</a>
            <a href="#faq">FAQ</a>
            <Link to="/app/docs">Docs</Link>
          </nav>
        )}
        <div className="nav-right">
          <Link to="/app" className="btn btn-ghost btn-sm">
            Open the board
          </Link>
          <WalletButton />
        </div>
      </div>
    </header>
  );
}

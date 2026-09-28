import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles/tokens.css";
import "./styles/app.css";
import { WalletProvider } from "./lib/whistle/WalletProvider";
import { NetworkStatusProvider } from "./lib/whistle/NetworkStatusProvider";
import { Shell } from "./Shell";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <NetworkStatusProvider>
        <WalletProvider>
          <Shell />
        </WalletProvider>
      </NetworkStatusProvider>
    </BrowserRouter>
  </StrictMode>
);

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./styles/tokens.css";
import "./styles/app.css";
import { WalletProvider } from "./lib/whistle/WalletProvider";
import { NetworkStatusProvider } from "./lib/whistle/NetworkStatusProvider";
import { Nav } from "./components/Nav";
import { Banner } from "./components/Banner";
import { Footer } from "./components/Footer";
import { Marketing } from "./routes/Marketing";
import { AppLayout } from "./routes/AppLayout";
import { Board } from "./routes/Board";
import { FixturePage } from "./routes/FixturePage";
import { CreateFixture } from "./routes/CreateFixture";
import { Portfolio } from "./routes/Portfolio";
import { Activity } from "./routes/Activity";
import { Docs } from "./routes/Docs";

function Shell() {
  return (
    <div className="app-shell">
      <Banner />
      <Nav />
      <main style={{ flex: 1 }}>
        <Routes>
          <Route path="/" element={<Marketing />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Board />} />
            <Route path="f/:id" element={<FixturePage />} />
            <Route path="create" element={<CreateFixture />} />
            <Route path="portfolio" element={<Portfolio />} />
            <Route path="activity" element={<Activity />} />
            <Route path="docs" element={<Docs />} />
          </Route>
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

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

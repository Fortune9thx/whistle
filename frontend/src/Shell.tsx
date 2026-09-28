import { Routes, Route } from "react-router-dom";
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

export function Shell() {
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

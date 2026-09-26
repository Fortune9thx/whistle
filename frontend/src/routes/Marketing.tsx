import { Link } from "react-router-dom";
import { FixtureTicket } from "../components/FixtureTicket";
import { Faq } from "../components/Faq";
import "./Marketing.css";

export function Marketing() {
  return (
    <div className="marketing">
      <section className="hero">
        <div className="hero-bloom" aria-hidden />
        <div className="container hero-inner">
          <h1 className="hero-title">
            When the whistle goes,
            <br />
            the desks must agree.
          </h1>
          <p className="hero-sub">
            Two publishers. One 90-minute scoreline. Integer pools.
            Conflict refunds both sides.
          </p>
          <Link to="/app" className="btn btn-primary">
            Open the board
          </Link>

          <div className="hero-stage">
            <FixtureTicket demo />
          </div>

          <div className="stat-row hero-facts">
            <div className="stat">
              <div className="stat-value">2</div>
              <div className="stat-label">publishers</div>
            </div>
            <div className="stat">
              <div className="stat-value">FT 90</div>
              <div className="stat-label">result type</div>
            </div>
            <div className="stat">
              <div className="stat-value">2%</div>
              <div className="stat-label">decisive fee</div>
            </div>
          </div>
        </div>
      </section>

      <section id="how" className="container feature-band">
        <h2 className="section-title">How it settles</h2>
        <div className="grid-2x2">
          <div className="card feature-card">
            <h3>Two locked desks, never a URL you supply</h3>
            <p className="mute">
              Every fixture is queried at fixed, registry-locked publisher
              endpoints. The model never fetches an arbitrary address.
            </p>
          </div>
          <div className="card feature-card">
            <h3>Code decides 1X2, never the model</h3>
            <p className="mute">
              The model extracts raw per-desk facts. A three-line, pure
              function derives HOME/DRAW/AWAY from the agreed scoreline.
            </p>
          </div>
          <div className="card feature-card">
            <h3>Conflict, LIVE, or postponed -&gt; refund</h3>
            <p className="mute">
              Anything short of two matching FT scorelines settles
              INCONCLUSIVE: full stake back, zero fee, no winner side.
            </p>
          </div>
          <div className="card feature-card">
            <h3>Appeal and recovery built in</h3>
            <p className="mute">
              Any bettor can appeal a decisive verdict. A stalled fixture
              can always be forced to a fee-free refund after 7 days.
            </p>
          </div>
        </div>
      </section>

      <section className="container final-cta">
        <div className="hero-bloom hero-bloom-small" aria-hidden />
        <h2 className="section-title">The scoreline is the product.</h2>
        <p className="mute" style={{ marginBottom: 24 }}>[settled.]</p>
        <Link to="/app" className="btn btn-primary">
          Open the board
        </Link>
      </section>

      <section className="container faq-band">
        <h2 className="section-title">FAQ</h2>
        <Faq />
      </section>
    </div>
  );
}

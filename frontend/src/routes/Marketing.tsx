import { Link } from "react-router-dom";
import { FixtureTicket } from "../components/FixtureTicket";
import { Faq } from "../components/Faq";
import "./Marketing.css";

const BOARD_PREVIEW = [
  { teams: "Real Madrid vs Bayern", state: "OPEN", focus: false },
  { teams: "Arsenal vs Inter", state: "PENDING", focus: true },
  { teams: "PSG vs Man City", state: "FINALIZED", focus: false },
];

export function Marketing() {
  return (
    <div className="marketing">
      <section className="hero">
        <div className="hero-bloom" aria-hidden />
        <div className="container hero-inner">
          <span className="hero-eyebrow">
            <span className="wordmark-dot" /> live on GenLayer Studio Next
          </span>
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

          <div className="stage-wrap">
            <div className="stage-window">
              <div className="stage-chrome">
                <span className="stage-dot" style={{ background: "#ff5f57" }} />
                <span className="stage-dot" style={{ background: "#febc2e" }} />
                <span className="stage-dot" style={{ background: "#28c840" }} />
                <span className="stage-chrome-url mono">app.whistle · studio-dev</span>
              </div>
              <div className="stage-body">
                <div className="stage-board-preview">
                  <div className="stage-board-heading">Board</div>
                  {BOARD_PREVIEW.map((row) => (
                    <div className={`stage-row ${row.focus ? "is-focus" : ""}`} key={row.teams}>
                      <span className="stage-row-teams">{row.teams}</span>
                      <span className="pill">{row.state}</span>
                    </div>
                  ))}
                </div>
                <div className="stage-ticket-pane">
                  <FixtureTicket demo />
                </div>
              </div>
            </div>
          </div>

          <div className="proof-row">
            <div className="container proof-inner">
              <span className="proof-item">
                <b>2</b> publishers
              </span>
              <span className="proof-item">
                <b>FT 90</b> result type
              </span>
              <span className="proof-item">
                <b>2%</b> decisive fee
              </span>
              <span className="proof-item">
                <b>0%</b> fee on refunds
              </span>
            </div>
          </div>
        </div>
      </section>

      <section id="how" className="container feature-band">
        <div className="section-eyebrow">How it settles</div>
        <h2 className="section-title">Four rules, nothing else.</h2>
        <div className="grid-2x2">
          <div className="card feature-card">
            <div className="feature-preview">
              <div className="mini-desks">
                <span className="mini-desk-chip">desk_a</span>
                <span className="mini-desk-link" title="locked, must match">&#128274;</span>
                <span className="mini-desk-chip">desk_b</span>
              </div>
            </div>
            <div className="feature-card-body">
              <h3>Two locked desks, never a URL you supply</h3>
              <p className="mute">
                Every fixture is queried at fixed, registry-locked publisher
                endpoints. The model never fetches an arbitrary address.
              </p>
            </div>
          </div>

          <div className="card feature-card">
            <div className="feature-preview">
              <div className="mini-code">
                <span className="tok-fn">derive_1x2</span>(2, 1)
                <br />
                &nbsp;&nbsp;<span className="tok-ret">→</span> <span className="tok-str">"HOME"</span>
              </div>
            </div>
            <div className="feature-card-body">
              <h3>Code decides 1X2, never the model</h3>
              <p className="mute">
                The model extracts raw per-desk facts. A three-line, pure
                function derives HOME/DRAW/AWAY from the agreed scoreline.
              </p>
            </div>
          </div>

          <div className="card feature-card">
            <div className="feature-preview">
              <div className="mini-refund">
                <span className="mini-refund-chip">2-1</span>
                <span className="mini-refund-chip">2-2</span>
                <span className="mini-refund-arrow">&rarr;</span>
                <span className="mini-refund-result">REFUND</span>
              </div>
            </div>
            <div className="feature-card-body">
              <h3>Conflict, LIVE, or postponed &rarr; refund</h3>
              <p className="mute">
                Anything short of two matching FT scorelines settles
                INCONCLUSIVE: full stake back, zero fee, no winner side.
              </p>
            </div>
          </div>

          <div className="card feature-card">
            <div className="feature-preview">
              <div className="mini-timeline">
                <div className="mini-timeline-row done">
                  <span className="mini-timeline-dot" />
                  resolve &middot; PENDING
                  <span className="mini-timeline-line" />
                </div>
                <div className="mini-timeline-row done">
                  <span className="mini-timeline-dot" />
                  appeal &middot; APPEALED
                  <span className="mini-timeline-line" />
                </div>
                <div className="mini-timeline-row">
                  <span className="mini-timeline-dot" />
                  lapse (1h) &middot; refund (7d)
                </div>
              </div>
            </div>
            <div className="feature-card-body">
              <h3>Appeal and recovery built in</h3>
              <p className="mute">
                Any bettor can appeal a decisive verdict. A stalled fixture
                can always be forced to a fee-free refund after 7 days.
              </p>
            </div>
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
        <div className="section-eyebrow">FAQ</div>
        <h2 className="section-title">Questions, answered.</h2>
        <Faq />
      </section>
    </div>
  );
}

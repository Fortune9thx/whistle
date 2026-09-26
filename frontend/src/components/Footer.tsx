export function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div className="footer-col">
            <div className="wordmark">
              <span className="wordmark-dot" />
              WHISTLE
            </div>
            <p className="mute" style={{ fontSize: 13, marginTop: 12, maxWidth: 280 }}>
              Two publishers. One 90-minute scoreline. Integer pools.
              Conflict refunds both sides.
            </p>
          </div>
          <div className="footer-col">
            <h4>Product</h4>
            <a href="/app">Board</a>
            <a href="/app/create">Create</a>
            <a href="/app/docs">Docs</a>
          </div>
          <div className="footer-col">
            <h4>Network</h4>
            <a href="https://explorer-studio-dev.genlayer.com" target="_blank" rel="noreferrer">
              Explorer
            </a>
            <a href="https://studio-dev.genlayer.com" target="_blank" rel="noreferrer">
              Studio Next
            </a>
          </div>
          <div className="footer-col">
            <h4>Repo</h4>
            <a href="https://github.com/Fortune9thx/whistle" target="_blank" rel="noreferrer">
              GitHub
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

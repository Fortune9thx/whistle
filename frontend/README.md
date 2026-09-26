# WHISTLE frontend

Vite + React + TypeScript. See the repo root [README.md](../README.md) for the product brief.

```bash
npm install
npm run dev      # dev server
npm run build    # production build (tsc -b && vite build)
```

`VITE_CONTRACT_ADDRESS` (see `.env.example`) points the app at a deployed
`Whistle` contract on Studio Next (chain 61997). Left empty, the app
shows an honest "not deployed" banner and every write is disabled --
there are no mock fixtures.

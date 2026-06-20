# Athlete Analytics OS — Frontend

Dark sports-analytics dashboard for a single athlete. React + TypeScript + Vite +
Tailwind v4 + Recharts + lucide-react + framer-motion. Mock data only (API-shaped, DB-ready).

Design decisions live in the root [`CLAUDE.md`](../CLAUDE.md).

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build
```

All mock data is isolated in `src/data/mockAthleteData.ts`; swap it for the backend's
`/entries`, `/metrics`, `/progress`, `/chat` endpoints later without touching the UI.

# Athlete Analytics OS — Frontend

White / green glassmorphism sports-analytics dashboard for a single athlete. React + TypeScript +
Vite + Tailwind v4 + Recharts + lucide-react + framer-motion. Mock data only (API-shaped, DB-ready).

Design decisions live in the root [`CLAUDE.md`](../CLAUDE.md).

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build
```

Booking payments use the backend Stripe Checkout endpoint. Set `STRIPE_SECRET_KEY`
and `FRONTEND_URL=http://localhost:5173` in `Backend/.env`, run the backend on
port `8000`, then pay with Stripe test card `4242 4242 4242 4242`. Do not put
Stripe secret keys in frontend env files.

All mock data is isolated in `src/data/mockAthleteData.ts`; swap it for the backend's
`/entries`, `/metrics`, `/progress`, `/chat` endpoints later without touching the UI.

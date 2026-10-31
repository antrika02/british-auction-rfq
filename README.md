# British Auction RFQ System

A Request for Quotation (RFQ) system with **British auction** bidding. Suppliers bid prices down, and if bids arrive near the closing time, the auction **extends automatically**, but it can never run past a hard **forced close time**.

- Three trigger types: any bid, any rank change, or a change of the lowest bidder (L1)
- Live updates: every bid, ranking change and new close time appears instantly in every open browser
- Every extension is logged with its reason
- Rules enforced in the application **and** in the database

## Quick start (Docker)

You need Docker Desktop. Then:

```bash
git clone https://github.com/antrika02/british-auction-rfq.git
cd british-auction-rfq
cp .env.example .env
docker compose up --build
```

In a second terminal, add demo auctions:

```bash
docker compose exec backend python scripts/seed.py --reset
```

| What | Where |
|---|---|
| App | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8001/docs |

## Try the demo

The seed script creates four auctions:

| Auction | State | What to look at |
|---|---|---|
| Delhi to Mumbai | Closed | Extended 3 times; read the activity log |
| Chennai to Kolkata | Force closed | An extension cut short, then one blocked, by the forced close |
| Pune to Hyderabad | **Active, closing soon** | The trigger window is already open. Place a bid that takes the lead and watch the timer jump. |
| Jaipur to Ahmedabad | Scheduled | Bidding has not opened yet |

Open the "Pune to Hyderabad" auction in two browser windows, bid in one, and watch the other update live. Rerun the seed script with `--reset` for fresh times at any moment.

## How it works

- **X** (trigger window): the last X minutes before close, when activity counts.
- **Y** (extension): minutes added when the trigger happens.
- **Forced close:** the hard stop. `new close = min(close + Y, forced close)`.

Full rules, a worked example and the reasoning behind each decision are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), which also has the architecture diagram and the database diagram.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/rfqs` | Create an RFQ (validates the times) |
| `GET` | `/api/rfqs` | List RFQs. Filters: `status`, `q`; paging: `limit`, `offset` |
| `GET` | `/api/rfqs/{id}` | Details: ranking, all bids, activity log, server time |
| `POST` | `/api/rfqs/{id}/bids` | Place a bid |
| `WS` | `/ws/rfqs` | Live updates for the listing |
| `WS` | `/ws/rfqs/{id}` | Live updates for one auction |
| `GET` | `/health` | Health check |

Errors always look like `{"error": {"code": "...", "message": "...", "details": [...]}}`.

## Tests

40 tests: the extension rules (pure, exact timestamps) and the API (real PostgreSQL, a fake clock, and 8 simultaneous bids).

```bash
docker compose up -d db
docker compose exec db psql -U auction -d auction -c "CREATE DATABASE auction_test;"
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -v
```

Tests use their own `auction_test` database, so they never touch your data.

## Development without Docker for the app

```bash
docker compose up -d db                                  # database on port 5433
cd backend && source .venv/bin/activate
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8001      # API
cd ../frontend && cp .env.example .env.local && npm install && npm run dev   # app
```

## Project layout

```
backend/
  app/
    extension.py   the auction rules (pure functions)
    services.py    create RFQ, place bid (one transaction)
    queries.py     listing and details
    broker.py      live-update broker
    routes/        REST and WebSocket endpoints
  db/schema.sql    tables, constraints, indexes
  scripts/seed.py  demo data
  tests/           extension and API tests
frontend/src/
  app/             listing, create form, details page
  components/      ranking board, bid form, activity log...
  lib/             API client, live-update hook, formatting
docs/ARCHITECTURE.md
docker-compose.yml
```

## Limitations and next steps

- No login: the assignment did not ask for it. Next step would be buyer and supplier accounts, so a bid is tied to a signed-in supplier instead of a typed carrier name.
- Live updates use an in-memory broker, so the API runs one worker. Replacing it with Redis pub/sub is described in the scaling section of the architecture document.
- Database changes are applied from `schema.sql` on first start. A migration tool such as Alembic would be the next step for a production system.

# NyaBot v0.3 — Migration / Deploy Notes

## Data source

Production data remains **Neon PostgreSQL**. `rests_data.json` from the repository is treated as an archival/local snapshot, not as the live source of truth.

- With `DATABASE_URL` set, Neon is loaded first.
- `ALLOW_JSON_BOOTSTRAP=1` is required to intentionally import the local JSON into an empty Neon state.
- Do **not** enable `ALLOW_JSON_BOOTSTRAP=1` on the normal production deployment when the current Neon database already contains player data.
- Local snapshots are still written as a recovery artifact after saves; they do not override a healthy Neon state.

## v0.3 business migration

The three removed starter business IDs are handled lazily and idempotently inside live player profiles:

- `bottles` → `smoothie_bar`
- `lemonade` → `food_truck`
- `shawarma` → `pizzeria`

Player purchase price, level, collection clocks and carry are preserved. If the replacement business is already owned, the removed business is compensated at the configured sale rate (80%). The migration never reads player state from `rests_data.json`.

## Business catalog

- Ordinary businesses: 1–16
- Donor businesses: 17–19
- `бизнес` / `бизнесы`: numbered catalog with no buttons
- `бизнес N`: concrete business card
- Unowned ordinary business: one `Купить` button
- Owned business: `Улучшить` and `Продать`
- Sale value: 80% of original purchase price

## Economy

Business tax defaults to 20% and is applied once at profit collection, after event/title/VIP modifiers. Mars is 80,000,000 coins with a 220,000 coins/hour base income. The post-Mars endgame businesses are the Lunar Corporation, Solar Station and Intergalactic Port (300,000 coins/hour base income).

## Stability

`bot.py` is the production entry point. It acquires the Neon singleton lock before importing the legacy application module, clears stale Telegram webhooks, supervises the single polling loop and treats Telegram 409 polling conflicts as a deployment/instance race instead of an immediate restart loop.

## Validation performed

- Python byte-compilation: all Python files
- JavaScript syntax check: `node --check miniapp/app.js`
- Existing quality suite: **24/24 PASS**
- v0.3 static contract: **PASS**
- v0.3 integrity suite: **PASS**
- Protected `rests_data.json`, `handlers/None` and `miniapp/None` hashes match the pre-v0.3 baseline
- No `non/` directory created or modified

Real Telegram/Railway runtime smoke testing still requires the production environment and credentials; no live deployment was performed from this workspace.

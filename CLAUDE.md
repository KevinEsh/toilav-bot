# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A platform that lets store owners manage their business through an AI-powered WhatsApp Business API chatbot. Customers interact entirely via WhatsApp; store owners manage catalog, orders, and customer interactions through a combination of the web UI (catalog, history, analytics) and a WhatsApp command interface (real-time order approvals, interventions, payment confirmations).

The project is currently built for a single store. The schema includes a `Store` table from the start, but multi-tenancy routing is not yet implemented — everything runs against one configured store.

## Development Commands

### Full stack (Docker)
```bash
docker-compose up          # Start all services
docker-compose up --build  # Rebuild images before starting
docker-compose down        # Stop all services
```

### Chatbot service (local development)
```bash
cd app/services/chatbot
uv sync --dev              # Install dependencies
uv run python main.py      # Run the service (port 8001)

# Tests
uv run pytest                                  # Run all tests
uv run pytest tests/test_routes.py             # Single file
uv run pytest tests/test_routes.py::test_foo   # Single test
```

### API service (local development)
```bash
cd app/services/api
uv run uvicorn main:app --reload --port 8000
```

### Frontend (local development)
```bash
cd app/services/frontend
npm install
npm run dev    # Vite dev server on port 5173
```

## Architecture

### Services and ports
| Service | Port | Code path |
|---|---|---|
| PostgreSQL | 5432 | Docker image |
| pgAdmin | 5433 | Docker image |
| REST API | 8000 | `app/services/api/` |
| Chatbot webhook | 8001 | `app/services/chatbot/` |
| Frontend | 5173 | `app/services/frontend/` |

### Chatbot message routing
Every incoming webhook message is routed based on `wa_id`:
- If `wa_id == OWNER_WA_ID` → **owner command parser**
- Otherwise → **customer conversation flow**

In owner context, messages starting with `/` are commands. Free-text messages while `Conversation.mode = HUMAN_TAKEOVER` are forwarded verbatim to the relevant customer via the WhatsApp API.

### Current chatbot implementation (technical)
1. WhatsApp Cloud API → `POST /webhook` (HMAC-SHA256 verified by `decorators/security.py`)
2. `routes.py` fires an async background task to avoid blocking the 200 OK response
3. `whatsapp_utils.py` → `UserMessageBuffer`: deduplicates by message ID (LRU, 50-cap), batches rapid messages with a 5-second debounce window, sorts by timestamp on flush
4. `yalti.py` → `pydantic-ai` Agent (`gpt-4o-mini`) with per-user conversation history in `_conversation_store` (currently in-memory — must be migrated to DB)
5. Response is WhatsApp-formatted (single `*asterisk*` bold, no markdown headers) then POSTed via `httpx` to the Graph API

### State machine — how it works
`Conversation.phase` (a DB enum) is the single source of truth for conversation state. The LLM never reads or writes it directly.

What changes per phase:
- **System prompt** — dynamically constructed from the current phase. The LLM only knows about its current job.
- **Available tools** — the agent is only registered with tools valid for the current phase. It cannot call `confirm_order()` while in `QA_LOOP` because that tool does not exist in that context.
- **Structured output** — for customer-side transitions, the LLM returns a structured Pydantic model (e.g. `customer_wants_to_confirm: bool`). The **code** validates preconditions and executes the transition if met. The LLM signals intent; the code decides.
- **Owner commands** — for owner-side transitions (`/approve`, `/payment-received`, etc.), the code executes the transition directly. The LLM is not involved.

The LLM can never move the conversation into an invalid phase. The worst it can do is say the wrong thing within a phase.

### Database schema
`app/services/database/chatbot_schema.py` is the single source of truth for the SQLModel schema. The `database-builder` Docker service runs `run_engine.py` on startup to create all tables.

Key models: `Store`, `Consumer`, `Product`, `Order`, `OrderItem`, `Conversation`, `Message`, `FAQ`, `Notification`, `Delivery`.

`Conversation` has two critical fields:
- `phase: ConversationPhase` — enum controlling the state machine
- `mode: ConversationMode` — `BOT` or `HUMAN_TAKEOVER`

### RAG (stub → pgvector)
`yalti.py::consultar_informacion` is the `@agent.tool` integration point for RAG. Currently returns a fallback string. Implementation target: `pgvector` extension on the existing PostgreSQL instance, with per-store embedding namespace. Products and FAQ are embedded on create/update. When a human-intervention Q&A pair is resolved, the answer is optionally embedded into the store's knowledge base (owner triggers this via `/answer`).

### Settings / environment
- Chatbot: `app/services/chatbot/config.py` — frozen `Settings` dataclass. Key vars: `WHATSAPP_ACCESS_TOKEN`, `APP_SECRET`, `PHONE_NUMBER_ID`, `OWNER_WA_ID`, `VERIFY_TOKEN`.
- DB/API: `.env` at repo root — `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`.

### Test setup
Tests in `app/services/chatbot/tests/`. `conftest.py` inserts the chatbot root into `sys.path` and sets all required env vars before any module import, so tests run without a real `.env`. `pytest.ini_options` sets `asyncio_mode = "auto"` and `pythonpath = ["."]`.

---

## Owner Command Interface

The store owner interacts with the bot via their personal WhatsApp number (`OWNER_WA_ID`). No separate notification UI or WebSocket infrastructure is needed — the existing send/receive pipeline handles both directions.

**Security:** owner commands are only processed if the message originates from `OWNER_WA_ID`. A command that references a conversation with no matching pending action is silently ignored.

**Aliases:** common commands have short aliases because owners will abbreviate.

**Bot acknowledgment:** every command triggers a confirmation reply to the owner (e.g. "✅ Orden de Juan aprobada. Notifiqué al cliente.").

**Pending queue:** multiple customers can simultaneously trigger intervention requests. The bot queues them. After an owner resolves one, the bot surfaces the next: "Tienes otra consulta pendiente de Ana García. ¿La atiendo yo o quieres intervenir?"

**Auto-resume:** after `/intervene`, if the owner has been inactive for 30 minutes, the bot asks "¿Retomo la conversación con [customer]? Responde /resume o /continue si aún lo estás atendiendo." After 15 more minutes with no response, the bot auto-resumes.

### Notification format
Notifications to the owner are structured and short:
```
🛍️ Nueva orden — *Juan López*

• 2x Almendras tostadas — $120
• 1x Nueces de la india — $85
Total: *$205*

📍 Calle 15 #45-23
⏰ Mañana, 2–4 pm
💳 Transferencia bancaria

/approve  |  /reject <motivo>
```
For knowledge-gap interventions, include the last 3 messages of context so the owner understands the conversation before answering.

### Full command reference

```
── KNOWLEDGE / INTERVENTION ──────────────────────────────────────
/answer <text>            Forward this text to the customer as the bot's answer.
                          Embeds the Q&A pair in the store's knowledge base.
  alias: /a <text>

/intervene                Silences the bot. Owner's free-text messages are
                          forwarded verbatim to the customer.
  alias: /takeover

/resume                   Returns control to the bot. Bot sends a soft
                          re-greeting to the customer.
  alias: /back, /continue-bot

── ORDER APPROVAL ────────────────────────────────────────────────
/approve                  Approves the pending order.
                          Bot notifies customer → APPROVED_PENDING_PAYMENT.
  alias: /ok

/reject <reason>          Rejects the order with a reason the bot relays
                          to the customer → CANCELLED → back to Q&A loop.
  alias: /no <reason>

── PAYMENT ───────────────────────────────────────────────────────
/payment-received         Confirms bank transfer arrived.
                          Bot notifies customer → PENDING_DELIVERY.
  alias: /paid

/payment-rejected <why>   Transfer not received or wrong amount.
                          Bot asks customer to retry and re-send evidence.

── DELIVERY ──────────────────────────────────────────────────────
/on-the-way               Order is out for delivery → DELIVERY_IN_COURSE.
                          Bot notifies customer. No further modifications allowed.
  alias: /delivery

/delivered                Order delivered → COMPLETED.
                          Bot sends closing/thank-you message to customer.
  alias: /done

/delivery-issue <note>    Something went wrong mid-delivery.
                          Bot tells customer to hold, silences itself.
                          Owner takes free-text control to resolve.

── DELIVERY ADDRESS CHANGE ───────────────────────────────────────
/address-ok               Acknowledges and confirms the address change to customer.
/address-rejected <why>   New address not serviceable. Bot informs customer,
                          original address is kept.

── UTILITY ───────────────────────────────────────────────────────
/pending                  Lists all conversations awaiting owner action,
                          with customer name and required action.

/status <name|number>     Shows current phase and last message of a specific
                          customer conversation.

/help                     Sends the command list to the owner.
```

---

## Chatbot Conversation Roadmap

The intended end-to-end flow. The bot is the sole consumer interface; the store owner acts via WhatsApp commands and the web UI (catalog, history).

### Phase 1 — Greeting
On first contact (or after a long idle period), the bot introduces itself and the store, lists the main things a customer can do, and closes with "¿En qué te puedo ayudar?". For returning customers, greets by name.

### Phase 2 — Q&A loop (`QA_LOOP`)
- Bot answers questions about products, prices, availability, delivery zones, payment methods, promotions, store hours, etc.
- Uses `consultar_informacion` (RAG) to look up real data before answering. Never invents facts.
- **Knowledge gap → owner intervention:** if the bot can't answer, it tells the customer to hold, sends the owner a structured notification with the question and last 3 messages of context.
  - Owner responds with `/answer <text>` → bot forwards to customer, embeds Q&A in knowledge base.
  - Owner responds with `/intervene` → bot silences itself, owner handles free-text. On `/resume`, bot takes back control.
  - Auto-resume after 30 minutes of owner inactivity.
- Loop continues until the customer initiates an order.

### Phase 3 — Order building (`ORDER_BUILDING`)
- Customer describes what they want (free-form). Bot resolves product names against the catalog (RAG/fuzzy match on `Product` table) and creates DB records: `Order(status=CONSUMER_REVIEWING)` + `[OrderItem(...), ...]`.
- Agent tools available in this phase: `add_item`, `remove_item`, `update_qty`, `get_order_summary`. Each tool call is a real DB operation; the bot always reads the summary from DB, never from its own memory.
- Bot presents the order summary and asks the customer to review.
- Customer requests changes → bot modifies `OrderItem` records, re-presents summary. Loop until customer confirms.
- Structured output field `customer_wants_to_confirm: bool` signals intent. Code validates order is non-empty before transitioning.

### Phase 4 — Collecting delivery & payment details (`COLLECTING_DETAILS`)
- **New customer:** bot collects full name, delivery address, delivery instructions, preferred delivery window (time range or exact datetime), and payment method. Saves to `Consumer` table.
- **Returning customer:** bot greets by name and asks "¿Entregamos a la misma dirección de siempre? ¿Mismo método de pago?" — pre-fills from stored data.
- Once confirmed, `Order` is updated with all details and status → `PENDING_STORE_APPROVAL`.

### Phase 5 — Store owner approval (`PENDING_APPROVAL`)
- Bot sends the owner a structured order notification with `/approve` and `/reject <motivo>` options.
- **`/approve`:** status → `APPROVED_PENDING_PAYMENT`. Bot notifies customer.
- **`/reject <reason>`:** bot relays the reason to the customer (out of stock, store closed, no delivery available, etc.), status → `CANCELLED`. Conversation returns to Q&A loop.

### Phase 6 — Payment (`PENDING_PAYMENT`)
- **Bank transfer:** bot sends the store's bank details (account number, bank name, account holder). Enters a loop asking the customer to send a screenshot of the transfer.
- **Screenshot received:** bot downloads the image from the WhatsApp API and forwards it to `OWNER_WA_ID` with caption "💸 [customer name] envió evidencia de transferencia. Revisa tu banco y confirma con /payment-received o /payment-rejected <motivo>". Bot tells customer "Recibí tu comprobante, lo estamos verificando 🙏".
- **"Done, please check":** same owner notification without the image.
- **`/payment-received`:** status → `PENDING_DELIVERY`. Bot notifies customer.
- **`/payment-rejected <why>`:** bot asks customer to retry.
- *(Other payment methods: flow TBD.)*

### Phase 7 — Pre-delivery (`PENDING_DELIVERY`)
- Customer can ask for order status. Bot responds that the order is being processed.
- **Address change:** allowed. Bot notifies owner (`/address-ok` or `/address-rejected <why>`), confirms outcome to customer.
- **Reception time change:** allowed. Same flow as address change.
- **Add more items:** not allowed on existing order. Bot instructs customer to place a new order.
- **Cancel:** not allowed at this stage.

### Phase 8 — Delivery in progress (`DELIVERY_IN_COURSE`)
- Triggered by owner `/on-the-way`. No further modifications allowed.
- Bot responds to any customer status query: "Tu pedido está en camino 🚚".
- If an unexpected issue arises, bot sends owner a notification and silences itself (`/delivery-issue` equivalent triggered automatically). Owner resolves via free-text. Bot watches.

### Phase 9 — Completed (`COMPLETED`)
- Triggered by owner `/delivered`. Bot sends a closing thank-you message and optionally asks for feedback.

### Key cross-cutting concerns
- **State transitions are always code, never LLM.** Customer-side transitions use structured output as a signal; code validates preconditions. Owner-side transitions are direct command handlers.
- **`Order.status` and `Conversation.phase` must stay in sync.** Any new status value must be reflected in both the schema enum and the bot's phase logic.
- **Conversation history must be persisted to DB** before the service is used in production. The current in-memory `_conversation_store` is lost on restart.
- **Never hardcode store-specific data** (bank info, business hours, owner number, product catalog) in logic. All of it must read from the `Store` DB record or `Settings`. This makes future multi-tenancy a routing layer addition, not a refactor.

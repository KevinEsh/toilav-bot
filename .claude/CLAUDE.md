# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. Codex will review your output once you're done

## Project Overview

A platform that lets store owners manage their business through an AI-powered WhatsApp Business API chatbot. Customers interact entirely via WhatsApp; store owners manage catalog, orders, and customer interactions through a combination of the web UI (catalog, history, analytics) and a WhatsApp command interface (real-time order approvals, interventions, payment confirmations).

The project is currently built for a single store. The schema includes a `Store` table from the start, but multi-tenancy routing is not yet implemented — everything runs against one configured store.

## Development Commands

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

## Repo Structure

```text
app/
  services/
    chatbot/               # FastAPI webhook service (port 8001)
      config.py            # frozen Settings dataclass + configure_logging()
      database.py          # SQLAlchemy async engine + get_session()
      dbutils.py           # TTLCache, DB loaders, upsert_customer(), order_summary()
      models.py            # Plain dataclasses mirroring DB rows (no ORM dep)
      queries.py           # Parameterized SQL text()/insert() objects — no raw f-strings
      router.py            # LLM phase classifier, validate_phase_transition()
      rules.py             # build_mega_prompt() — dynamic system prompt per phase
      routes.py            # FastAPI route handlers
      security.py          # HMAC-SHA256 webhook verification decorator
      whatsapp_client.py   # httpx wrapper for Graph API calls
      whatsapp_utils.py    # UserMessageBuffer (dedup + 5s debounce)
      yalti.py             # pydantic-ai Agent, all tools, agent_generate_response()
      tests/               # mocked-AsyncSession unit tests (no real DB needed)
    api/                   # REST API for dashboard (port 8000)
    database/
      chatbot_schema.py    # SQLModel schema — single source of truth for all tables
      run_engine.py        # Creates all tables on startup (run by database-builder service)
    frontend/              # React + Vite + shadcn/ui dashboard (port 5173)
```

## Architecture

### Services and ports

| Service | Port | Code path |
| --- | --- | --- |
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

1. WhatsApp Cloud API → `POST /webhook` (HMAC-SHA256 verified by `security.py`)
2. `routes.py` fires an async background task to avoid blocking the 200 OK response
3. `whatsapp_utils.py` → `UserMessageBuffer`: deduplicates by message ID (LRU, 50-cap), batches rapid messages with a 5s debounce window, sorts by timestamp on flush
4. `router.py` → `route_phase()`: LLM classifier that picks the conversation phase; skips the LLM call when the phase is stable and history already exists
5. `rules.py` → `build_mega_prompt()`: constructs the system prompt dynamically per phase
6. `yalti.py` → `pydantic-ai` Agent (`gpt-4o-mini`, temp=0.1) runs with the resolved phase's tools
   - Tools: `show_products`, `create_order`, `add_order_item`, `reduce_order_item`, `set_order_item_units`, `remove_order_item`, `cancel_order`, `escalate_to_staff`
   - `prepare` callbacks conditionally hide tools based on order state (no active order → item tools hidden)
   - `_once` set prevents duplicate calls to idempotent tools within a single turn
   - Fallback: `_direct_agent` (no tools) when request limit is exceeded
7. Conversation history persisted as JSONB via `dbutils.py`; `ConversationsCache` (LRU, 30-entry) avoids repeated deserialization
8. `models.py` plain dataclasses decouple the chatbot service from the shared SQLModel ORM
9. All DB writes use parameterized queries from `queries.py` via SQLAlchemy `AsyncSession`
10. Response is WhatsApp-formatted (single `*asterisk*` bold, no markdown headers) then POSTed via `whatsapp_client.py`

### State machine — how it works

`Conversation.phase` (a DB enum) is the single source of truth for conversation state. The LLM never reads or writes it directly.

What changes per phase:

- **System prompt** — dynamically constructed by `build_mega_prompt()`. The LLM only knows about its current job.
- **Available tools** — `prepare` callbacks expose only tools valid for the current state. The LLM cannot call an order-mutation tool when no order is active.
- **Structured output** — for customer-side transitions, the LLM returns a structured Pydantic model. The **code** validates preconditions and executes the transition if met. The LLM signals intent; the code decides.
- **Owner commands** — for owner-side transitions (`/approve`, `/payment-received`, etc.), the code executes the transition directly. The LLM is not involved.

The LLM can never move the conversation into an invalid phase. The worst it can do is say the wrong thing within a phase.

### Database schema

Source of truth: `app/services/database/chatbot_schema.py`

| Table | Purpose |
| --- | --- |
| `Customers` | WhatsApp users (`c_whatsapp_id` unique) |
| `Products` | Catalog items (`p_name` unique, price snapshot on order) |
| `Stores` | Store record with name, description, JSON properties |
| `Orders` | Customer purchases, tracks status through the order lifecycle |
| `OrderItems` | Line items; `oi_unit_price` is snapshot at order creation time |
| `Conversations` | One per customer; holds `cv_phase`, `cv_mode`, `cv_history` (JSONB) |
| `Messages` | Inbound/outbound log per customer |
| `Users` | Dashboard staff accounts |

Key enums:

- `OrderStatus`: `CONSUMER_REVIEWING → PENDING_STORE_APPROVAL → APPROVED_PENDING_PAYMENT → PENDING_DELIVERY → DELIVERY_IN_COURSE → COMPLETED / CANCELLED`
- `ConversationPhase`: `GREETING → QA_LOOP → ORDER_BUILDING → COLLECTING_DETAILS → PENDING_APPROVAL → PENDING_PAYMENT → PENDING_DELIVERY → COMPLETED`
- `ConversationMode`: `BOT | HUMAN_TAKEOVER`

`Order.status` and `Conversation.phase` must stay in sync — any new status value must be reflected in both.

### RAG (stub → pgvector)

`yalti.py::consultar_informacion` is the `@agent.tool` integration point for RAG. Currently returns a fallback string. Target: `pgvector` on the existing PostgreSQL instance, per-store embedding namespace. Products and FAQs embedded on create/update; `/answer` Q&A pairs embedded on resolution.

### Settings / environment

- Chatbot: `app/services/chatbot/config.py` — frozen `Settings` dataclass. Key vars: `WHATSAPP_ACCESS_TOKEN`, `APP_SECRET`, `PHONE_NUMBER_ID`, `OWNER_WA_ID`, `VERIFY_TOKEN`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (combined into `DATABASE_URL` at init).
- DB/API: `.env` at repo root — used by Docker Compose and the API service.

### Test setup

Tests in `app/services/chatbot/tests/`. `conftest.py` injects the chatbot root into `sys.path` and sets all required env vars before any module import — no real `.env` needed. `pytest.ini_options` sets `asyncio_mode = "auto"` and `pythonpath = ["."]`.

- All tests use `AsyncMock` sessions — no real DB connection required
- Error-case tests need no DB fixtures: validations fire before any write
- Helper pattern: `_make_ctx()` builds a minimal `RunContext`-like object with `customer`, `session`, `active_order_id`, `products`

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

```text
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

```text
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

- Customer describes what they want (free-form). Bot resolves product names against the catalog and creates DB records: `Order(status=CONSUMER_REVIEWING)` + `[OrderItem(...), ...]`.
- Tools available: `create_order`, `add_order_item`, `reduce_order_item`, `set_order_item_units`, `remove_order_item`. Each is a real DB operation; the bot always reads the summary from DB, never from its own memory.
- Bot presents the order summary and asks the customer to review. Customer requests changes → bot modifies records, re-presents. Loop until customer confirms.
- Structured output field `customer_wants_to_confirm: bool` signals intent. Code validates order is non-empty before transitioning.

### Phase 4 — Collecting delivery & payment details (`COLLECTING_DETAILS`)

- **New customer:** bot collects full name, delivery address, delivery instructions, preferred delivery window, and payment method. Saves to `Customers` table.
- **Returning customer:** bot greets by name and asks "¿Entregamos a la misma dirección de siempre? ¿Mismo método de pago?" — pre-fills from stored data.
- Once confirmed, `Order` is updated with all details and status → `PENDING_STORE_APPROVAL`.

### Phase 5 — Store owner approval (`PENDING_APPROVAL`)

- Bot sends the owner a structured order notification with `/approve` and `/reject <motivo>` options.
- **`/approve`:** status → `APPROVED_PENDING_PAYMENT`. Bot notifies customer.
- **`/reject <reason>`:** bot relays the reason to the customer, status → `CANCELLED`. Conversation returns to Q&A loop.

### Phase 6 — Payment (`PENDING_PAYMENT`)

- **Bank transfer:** bot sends the store's bank details. Enters a loop asking the customer to send a screenshot of the transfer.
- **Screenshot received:** bot forwards image to `OWNER_WA_ID` with confirmation prompt. Bot tells customer "Recibí tu comprobante, lo estamos verificando 🙏".
- **`/payment-received`:** status → `PENDING_DELIVERY`. Bot notifies customer.
- **`/payment-rejected <why>`:** bot asks customer to retry.
- *(Other payment methods: flow TBD.)*

### Phase 7 — Pre-delivery (`PENDING_DELIVERY`)

- Customer can ask for order status. Bot responds that the order is being processed.
- **Address / time change:** allowed. Bot notifies owner (`/address-ok` or `/address-rejected <why>`), confirms outcome to customer.
- **Add more items / cancel:** not allowed. Bot instructs customer to place a new order.

### Phase 8 — Delivery in progress (`DELIVERY_IN_COURSE`)

- Triggered by owner `/on-the-way`. No further modifications allowed.
- Bot responds to any customer status query: "Tu pedido está en camino 🚚".
- If an unexpected issue arises, bot silences itself and notifies owner. Owner resolves via free-text.

### Phase 9 — Completed (`COMPLETED`)

- Triggered by owner `/delivered`. Bot sends a closing thank-you message and optionally asks for feedback.

### Key cross-cutting concerns

- **State transitions are always code, never LLM.** Customer-side transitions use structured output as a signal; code validates preconditions. Owner-side transitions are direct command handlers.
- **`Order.status` and `Conversation.phase` must stay in sync.** Any new status value must be reflected in both the schema enum and the bot's phase logic.
- **Never hardcode store-specific data** (bank info, business hours, owner number, product catalog) in logic. All of it must read from the `Store` DB record or `Settings`. This makes future multi-tenancy a routing layer addition, not a refactor.

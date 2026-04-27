# Fix: _get_active_order

**Fecha:** 2026-04-21
**Archivo:** `app/services/chatbot/yalti.py`
**Tests:** `app/services/chatbot/tests/test_get_active_order.py` (5/5 ✅)

---

## Problema central

`_get_active_order` se llama al inicio de cada `agent_generate_response` para
poblar `ChatDeps.active_order_id`. Es el único pre-fetch que hacemos antes de
armar las deps del agente.

Si la consulta DB explota (engine caído, timeout, permisos), la excepción se
propagaba hasta el webhook → el cliente recibía un 500 sin respuesta del bot.

---

## Issues corregidos

| # | Issue | Riesgo original |
|---|-------|-----------------|
| 1 | Sin try/except en la consulta DB | Cualquier `OperationalError` / `TimeoutError` rompía la respuesta entera del agente |

---

## Decisión: fallback a `None`, no propagar la excepción

```python
try:
    with Session(engine) as session:
        return session.exec(...).first()
except Exception as e:
    logger.error("_get_active_order failed for c_id=%s: %s", c_id, e)
    return None
```

**Razón:** retornar `None` (el mismo valor que "no hay orden activa") permite
que el agente arranque. Los tools que requieren orden activa (`update_order`,
`cancel_order`) están protegidos por `_hide_when_no_order` — si no hay
`active_order_id`, simplemente no se registran y el LLM no los puede llamar.
Los tools que crean orden (`create_order`) tampoco se bloquean.

Si la DB está realmente caída, la siguiente operación transaccional fallará
con `ERROR_INTERNO` dentro del tool correspondiente — que es el contrato
correcto (el cliente ve "problema técnico, intenta de nuevo"). No queremos
duplicar ese manejo aquí.

**Trade-off conocido:** si la DB tiene un blip transitorio justo en este
momento, un cliente con orden activa podría ver sus tools de orden
"desaparecer" por un turno. El bot caería en Q&A loop. Es un degrade
aceptable vs. un 500 del webhook.

---

## Decisión: `except Exception`, no categorizar

A diferencia de `escalate_to_staff` (que distingue HTTP 4xx/5xx/timeout
porque el manejo varía), aquí **todo error DB tiene el mismo tratamiento**:
log + None. No hay valor en desambiguar `OperationalError` vs `TimeoutError`
vs `ProgrammingError` — todos implican que no pudimos leer el estado de la
orden, y la recuperación es idéntica.

---

## Tests — `tests/test_get_active_order.py` (5/5 ✅)

### Happy path
- [x] `test_returns_order_when_exists` — devuelve `Orders` cuando la query encuentra activo
- [x] `test_returns_none_when_no_active_order` — `first() == None` se propaga limpio

### Error handling
- [x] `test_db_operational_error_returns_none` — `sqlalchemy.exc.OperationalError` → None
- [x] `test_unexpected_error_returns_none` — excepción arbitraria → None
- [x] `test_session_construction_failure_returns_none` — fallo al abrir `Session` → None

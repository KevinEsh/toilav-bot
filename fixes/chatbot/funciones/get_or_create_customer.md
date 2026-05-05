# Fix: _get_or_create_customer

**Fecha:** 2026-04-21 (hardening inicial) — 2026-04-23 (race handling)
**Archivo:** `app/services/chatbot/whatsapp_utils.py`
**Tests:** `app/services/chatbot/tests/test_get_or_create_customer.py` (10/10 ✅)

---

## Hallazgo: duplicación

Antes de este fix existían **dos** `_get_or_create_customer`:

1. `whatsapp_utils.py:185` — la versión viva. Abre su propio `Session`, hace
   `commit()`, llama a `refresh()`. Invocada desde el pipeline del webhook
   en `process_incoming_messages`.
2. `yalti.py:82` — versión **huérfana** que tomaba `session` como argumento
   y usaba `flush()` en lugar de `commit()`. Ningún caller en el repo.

El backlog apuntaba a la de `yalti.py`, pero hardenearla no arreglaba nada
real. Se borró la dead code de `yalti.py` en este mismo commit y el fix
se aplicó a la versión viva en `whatsapp_utils.py`.

---

## Problema central

Primer paso del pipeline tras recibir un webhook. Si explota, el cliente
no recibe respuesta (ya que el `except Exception` del caller solo loguea).
Pero más grave: **un `wa_id` vacío colisiona a distintos clientes en un
mismo registro `Customers`**, porque el `SELECT ... WHERE c_whatsapp_id = ""`
encontraría al primer cliente creado con ese valor — y todas las
conversaciones subsecuentes con `wa_id=""` heredarían su historial, órdenes,
nombre. Corrupción permanente.

---

## Issues corregidos

| # | Issue | Riesgo original |
|---|-------|-----------------|
| 1 | Sin validación de `wa_id` vacío / whitespace / None | Colisión entre clientes distintos contra registro con `c_whatsapp_id=""` |
| 2 | Sin try/except en consulta + commit DB | Excepción de SQLAlchemy sin contexto en logs — difícil triangular fallos |
| 3 | `wa_id` no normalizado antes de persistir | `" 5215..."` y `"5215..."` creaban dos clientes distintos por diferencia de espacio |

---

## Decisión: `wa_id` vacío → `ValueError`, no silenciar

```python
if not wa_id or not wa_id.strip():
    raise ValueError("wa_id vacío — no se puede identificar al cliente")
```

No devolvemos `None` ni creamos un registro con placeholder. La WhatsApp
Cloud API **siempre** envía `contact.wa_id` en payloads legítimos; recibir
vacío indica payload malformado (test, replay, parser bug). Fallar ruidoso
es lo correcto — el caller en `process_incoming_messages` ya tiene un
`except Exception` que loguea sin crashear el worker.

---

## Decisión: normalizar con `.strip()` antes de query y create

```python
wa_id = wa_id.strip()
```

Garantiza que `"  5215...  "` y `"5215..."` se resuelvan al mismo registro.
No es un escenario probable con Meta, pero la regla es barata.

---

## Decisión: try/except con re-raise (no swallow)

```python
try:
    with Session(engine) as session:
        ...
except Exception as e:
    logger.error("_get_or_create_customer failed for wa_id=%s: %s", wa_id, e)
    raise
```

El `raise` final mantiene el contrato actual (el caller atrapa con su
`except Exception`). El valor agregado es el **log con `wa_id`** — sin eso,
la traza termina en internals de SQLAlchemy y no podemos triangular
qué cliente disparó el error. Swallow silencioso rompería el flujo del
webhook peor — el caller piensa que todo fue bien pero `customer` sería
`None`.

---

## Race handling (agregado 2026-04-23 — item #9)

Dos mensajes simultáneos del mismo `wa_id` nuevo caían en un race:
ambos leen `first()==None`, ambos `add+commit` → el segundo truena con
`IntegrityError` por constraint único en `c_whatsapp_id`. El
`except Exception` del caller tragaba el error y el mensaje del
perdedor se perdía sin respuesta.

### Fix elegido: `except IntegrityError → rollback → re-SELECT`

```python
try:
    session.commit()
except IntegrityError:
    session.rollback()
    customer = session.exec(
        select(Customers).where(Customers.c_whatsapp_id == wa_id)
    ).first()
    if customer is None:
        raise
```

Descartamos `SELECT ... FOR UPDATE`: requiere pesimismo en el caso
común (~0% de races) y no funciona igual en todos los engines. El
patrón rollback+re-SELECT es optimista — sólo paga costo cuando la
race efectivamente ocurre.

### Defensa: `if customer is None: raise`

Si el re-SELECT devuelve `None`, el `IntegrityError` **no** fue por la
race que nos interesa (podría ser otra constraint futura). Re-raise
en vez de silenciar — el outer `except Exception` loguea con wa_id.

### Por qué no tocamos el `OperationalError` del commit

El test `test_db_error_on_commit_reraises` sigue pasando porque
`OperationalError` no es subclase de `IntegrityError` — cae directo al
outer handler, comportamiento preservado.

---

## Tests — `tests/test_get_or_create_customer.py` (10/10 ✅)

### Validación
- [x] `test_empty_wa_id_raises` — `""` → ValueError
- [x] `test_none_wa_id_raises` — `None` → ValueError
- [x] `test_whitespace_wa_id_raises` — `"   \t  "` → ValueError
- [x] `test_wa_id_is_stripped_before_create` — `"  5215...  "` → cliente creado con `c_whatsapp_id="5215..."`

### Happy path
- [x] `test_returns_existing_customer` — cliente existe → no se llama `add`/`commit`
- [x] `test_creates_new_customer_when_not_found` — `first()==None` → `add` + `commit` llamados

### Errores
- [x] `test_db_error_on_select_reraises_with_log` — `OperationalError` en select → re-raise
- [x] `test_db_error_on_commit_reraises` — `OperationalError` en commit → re-raise

### Race condition
- [x] `test_integrity_error_triggers_reselect_and_returns_winner` — commit falla con IntegrityError → rollback + re-SELECT devuelve al ganador
- [x] `test_integrity_error_with_empty_reselect_reraises` — re-SELECT vacío (IntegrityError no era por race) → re-raise

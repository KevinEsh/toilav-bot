# Fix: escalate_to_staff

**Fecha:** 2026-04-20
**Archivo:** `app/services/chatbot/yalti.py`
**Tests:** `app/services/chatbot/tests/test_escalate_to_staff.py` (13/13 ✅)

---

## Problema central

`escalate_to_staff` era un stub: marcaba `_once`, logueaba el mensaje y devolvía
`"Función escalate_to_staff llamada."`. La implementación HTTP real estaba
comentada dentro de la misma función, sin validaciones ni manejo de errores
separado por tipo.

En producción, este tool es el único canal que tiene el bot para escalar al
dueño cuando no puede responder (gap de conocimiento, problema operativo).
Un stub significa que el cliente recibe un "listo, ya le avisé al dueño"
sin que nadie haya sido notificado realmente.

---

## Issues corregidos

| # | Issue | Riesgo original |
|---|-------|-----------------|
| 1 | Lógica HTTP comentada — dummy return al agente | Cliente recibe confirmación falsa; dueño nunca se entera |
| 2 | Sin validación de `message` vacío / whitespace | LLM podía disparar escalation sin contenido útil |
| 3 | Sin validación de credenciales (`OWNER_WA_ID`, `WHATSAPP_ACCESS_TOKEN`, `PHONE_NUMBER_ID`) | Llamada HTTP fallando ruidosamente en runtime en lugar de un error claro |
| 4 | Sin contexto del cliente en el mensaje al dueño | Owner recibía texto aislado sin saber quién pregunta |
| 5 | Manejo único de errores con `except Exception` | Timeouts y errores de red se confundían; mensaje único poco informativo |
| 6 | `_once` marcado antes de validar entrada | Un mensaje vacío "gastaba" la única escalation del turno |

---

## Decisión: `_once` se marca **antes** del HTTP pero **después** de validaciones

El guardia `if "escalate_to_staff" in ctx.deps._once` sigue siendo el primer
check. Pero el `_once.add(...)` ahora se mueve **después** de las validaciones
de entrada y de configuración:

```python
if "escalate_to_staff" in ctx.deps._once:
    return "El dueño ya fue notificado..."

# validaciones previas (message, OWNER_WA_ID, credentials)
# ...

ctx.deps._once.add("escalate_to_staff")  # solo llega aquí si la llamada va a proceder
```

**Razón:** si el LLM manda `message=""` o las credenciales no están, la llamada
retorna `ERROR_VALIDACION` o `ERROR_INTERNO`. Marcar `_once` en ese caso
**bloquearía un retry legítimo** del LLM dentro del mismo turno. El `_once`
sólo debe gastarse cuando efectivamente intentamos notificar al dueño.

Se marca **antes** del HTTP (no después del `response.raise_for_status()`)
porque una vez que enviamos el request, aunque falle a mitad de camino,
no queremos que el LLM vuelva a intentar en el mismo turno — duplicaría la
notificación en casos donde el POST llegó pero la respuesta se perdió.

---

## Decisión: error categorizado por tipo de excepción

```python
except httpx.HTTPStatusError as e:  # 4xx/5xx de Meta
except httpx.TimeoutException:      # red lenta / caída
except httpx.HTTPError as e:        # conexión, DNS, etc.
```

No usamos `except Exception` — queremos que un `AttributeError` o un bug del
código suba sin ser enmascarado como "no se pudo notificar al dueño". Sólo
errores de transporte HTTP/red deben convertirse a `ERROR_INTERNO`.

Todos devuelven `ERROR_INTERNO:` para que el LLM sepa que es fallo sistémico
y no deba reintentar en el mismo turno.

---

## Decisión: contexto del cliente en el mensaje al dueño

Antes (comentado): `body = message` tal cual viene del LLM.
Ahora:

```python
body = (
    f"🔔 Consulta de *{customer.c_name}* ({customer.c_whatsapp_id}):\n\n"
    f"{message.strip()}"
)
```

**Razón:** el dueño recibe mensajes de varios clientes. Sin el nombre y wa_id
no puede distinguir conversaciones ni responder rápidamente. El LLM ya incluye
contexto semántico en `message`, pero el *quién* lo agregamos en el código
para garantizar consistencia — no depende de que el LLM se acuerde.

**Cumple con feedback guardado:** no hay fallback tipo `customer.c_name or "Cliente"`
— el nombre se captura en onboarding y siempre está poblado cuando llegamos aquí.

---

## Decisión: llamada directa a `httpx`, no via `whatsapp_utils.send_message`

`whatsapp_utils.py` ya tiene `send_message()` + `encapsulate_text_message()`
que harían exactamente lo mismo. **No se usan** porque `whatsapp_utils`
importa de `yalti` (para `agent_generate_response`), creando un ciclo si
`yalti` importara de `whatsapp_utils`.

Romper el ciclo requeriría extraer los helpers a un tercer módulo — trabajo
fuera del alcance del backlog de hardening. La duplicación del POST (~15 líneas)
es aceptable. Si se extrae un `whatsapp_client.py` en el futuro, este sitio
se beneficiaría del refactor sin cambios de lógica.

---

## Contrato de errores

Sigue la convención de `create_order`/`update_order`/`cancel_order`:

- `ERROR_VALIDACION: ...` — el LLM puede corregir y reintentar (mensaje vacío).
- `ERROR_INTERNO: ...` — fallo sistémico. El LLM debe decirle al cliente que
  hubo un problema, sin reintentar en el mismo turno.
- Éxito → `"Notificación enviada al dueño de la tienda."`
- Re-entrada en mismo turno → `"El dueño ya fue notificado..."`

---

## Tests — `tests/test_escalate_to_staff.py` (13/13 ✅)

### Guards (sin HTTP)
- [x] `test_already_escalated_this_turn` — `_once` poblado → no llama POST
- [x] `test_empty_message` → `ERROR_VALIDACION`, no consume `_once`
- [x] `test_whitespace_only_message` → `ERROR_VALIDACION`
- [x] `test_missing_owner_wa_id` → `ERROR_INTERNO`, no consume `_once`
- [x] `test_missing_credentials` → `ERROR_INTERNO` si falta token o phone_id

### Errores HTTP / red
- [x] `test_http_4xx` — Meta devuelve 400 → `ERROR_INTERNO`
- [x] `test_http_5xx` — Meta devuelve 503 → `ERROR_INTERNO`
- [x] `test_timeout` — `httpx.TimeoutException` → `ERROR_INTERNO` con mención de timeout
- [x] `test_network_error` — `httpx.ConnectError` → `ERROR_INTERNO`

### Happy path
- [x] `test_returns_success_message` — marca `_once` y retorna confirmación
- [x] `test_payload_shape_and_url` — verifica URL, payload shape, headers, `c_name`+`wa_id` en body
- [x] `test_message_is_trimmed` — whitespace alrededor del mensaje no llega al body
- [x] `test_once_marker_blocks_second_call` — segunda llamada en mismo turno no toca red

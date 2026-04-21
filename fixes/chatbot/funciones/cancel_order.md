# Fix: cancel_order

**Fecha:** 2026-04-20
**Archivo:** `app/services/chatbot/yalti.py`
**Tests:** `app/services/chatbot/tests/test_cancel_order.py` (7/7 ✅)

---

## Problema central

`cancel_order` modifica `Order.o_status` sin validar que la orden exista en DB.
`session.get(Orders, o_id)` puede retornar `None` — el acceso directo a
`order.o_status = OrderStatus.CANCELLED` lanza `AttributeError` y la excepción
se propaga al agente sin manejo.

Adicionalmente, la función cancelaba órdenes en cualquier estado — incluso
`COMPLETED` o ya `CANCELLED` — lo que permitía revertir el estado final de
una orden entregada o duplicar el cambio de estado.

---

## Issues corregidos

| # | Issue | Riesgo original |
|---|-------|-----------------|
| 1 | `session.get(Orders, o_id)` puede retornar `None` | `AttributeError` al asignar `order.o_status` → crash propagado al agente |
| 2 | Sin `try/except` en escritura a DB | Excepciones de DB no manejadas propagadas al agente |
| 3 | Órdenes `COMPLETED` o `CANCELLED` podían re-cancelarse | Revertir estado final de una orden entregada / histórico inconsistente |
| 4 | `ctx.deps.active_order_id = None` se ejecutaba aunque el commit fallara | Estado del agente desincronizado con DB si fallaba la transacción |

---

## Decisión: bloquear cancelación de órdenes en estado terminal

`_get_active_order` ya filtra `CANCELLED` y `COMPLETED`, por lo que en el
flujo normal la tool jamás recibe una orden en esos estados. Sin embargo,
nunca es seguro asumir la invariante — el estado puede cambiar entre turnos
(el dueño puede marcar `/delivered` mientras el cliente mandaba "cancela").
La validación explícita es defensa en profundidad:

```python
if order.o_status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
    return (
        f"ERROR_VALIDACION: el pedido o_id={o_id} ya está en estado "
        f"{order.o_status.value} y no puede cancelarse."
    )
```

Devuelve `ERROR_VALIDACION` en lugar de `ERROR_INTERNO` porque es un estado
de negocio válido — no un bug de la aplicación.

---

## Decisión: limpiar `active_order_id` solo tras commit exitoso

`ctx.deps.active_order_id = None` se movió **fuera** del `with Session`,
pero dentro del bloque `try`, **después** del commit. Si el commit falla:

- La excepción se captura → `ERROR_INTERNO`.
- `active_order_id` permanece → el prepare `_hide_when_no_order` sigue
  mostrando las tools de orden activa → el LLM puede reintentar.

Si invertimos el orden (limpiar antes de commit), un fallo de DB deja al
agente creyendo que la orden fue cancelada cuando no lo fue.

---

## Contrato de error

```python
"ERROR_VALIDACION: ..."   # estado de negocio inválido (orden ya cerrada) → LLM informa
"ERROR_INTERNO: ..."      # fallo técnico (DB, orden no existe) → LLM informa, no reintenta
```

---

## Flujos por tipo de error

### Orden no existe en DB (edge: active_order_id desfasado)
```
1. LLM llama cancel_order()
2. session.get retorna None
3. Tool → "ERROR_INTERNO: no se encontró el pedido o_id=99."
4. LLM → cliente: "Hubo un problema con tu pedido, lo revisamos."
```

### Orden ya completada o cancelada
```
1. LLM llama cancel_order()
2. order.o_status == COMPLETED
3. Tool → "ERROR_VALIDACION: el pedido o_id=99 ya está en estado completed..."
4. LLM → cliente: "Tu pedido ya fue entregado, no se puede cancelar."
```

### Happy path
```
1. Cliente: "cancela mi pedido"
2. LLM llama cancel_order()
3. order.o_status = CANCELLED → commit
4. ctx.deps.active_order_id = None
5. Tool → "Pedido o_id=99 cancelado."
6. _hide_when_no_order oculta update_order/cancel_order de la siguiente llamada
```

---

## Tests — `tests/test_cancel_order.py` (7/7 ✅)

### Validaciones en DB
- [x] `test_order_not_found_in_db` — `session.get` retorna `None` → `ERROR_INTERNO`, sin commit, `active_order_id` intacto
- [x] `test_order_already_cancelled` — estado `CANCELLED` → `ERROR_VALIDACION`, sin commit
- [x] `test_order_already_completed` — estado `COMPLETED` → `ERROR_VALIDACION`, sin commit

### Happy path (DB mockeado)
- [x] `test_cancel_pending_approval_order` — `PENDING_STORE_APPROVAL` → `CANCELLED`, `active_order_id = None`, mensaje de éxito
- [x] `test_cancel_consumer_reviewing_order` — `CONSUMER_REVIEWING` → `CANCELLED`, commit llamado

### Error interno
- [x] `test_db_exception_on_get_returns_error_interno` — excepción en `session.get` → `ERROR_INTERNO`, `active_order_id` intacto
- [x] `test_db_exception_on_commit_returns_error_interno` — excepción en `commit` → `ERROR_INTERNO`, `active_order_id` intacto (no se limpió el estado)

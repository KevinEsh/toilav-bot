# Fix: update_order

**Fecha:** 2026-04-19  
**Archivo:** `app/services/chatbot/yalti.py`  
**Tests:** `app/services/chatbot/tests/test_update_order.py` (18/18 ✅)

---

## Issues corregidos

| # | Issue | Riesgo original |
|---|-------|-----------------|
| 1 | **Bug fatal:** `_order_summary(session, o_id)` — firma incorrecta | `TypeError` en cada llamada → crash garantizado |
| 2 | `session.get(Orders, o_id)` puede retornar `None` | `AttributeError` al hacer `order.o_subtotal = total` |
| 3 | `units < 1` no validado para `add`, `reduce_units`, `set_units` | Ítems con 0 o unidades negativas en DB |
| 4 | `p_id` validado solo dentro del `case "add"` (boilerplate) | Sin validación para `reduce_units`, `set_units`, `remove` |
| 5 | `action` desconocida solo detectada al final del match | Sin `ERROR_VALIDACION:` consistente |
| 6 | Orden puede quedar sin ítems tras `remove` o `reduce_units` | DB inconsistente; estado irrecuperable sin cancel |
| 7 | Docstring decía `'set_units'` pero código usaba `'update_units'` | LLM usaba acción incorrecta |
| 8 | Sin `try/except` en escritura a DB | Excepción no manejada propagada al agente |

---

## Decisión de diseño: validación de p_id fuera del match

La validación de `p_id` se hace **una sola vez antes del `match case`**, no dentro de cada rama.
Esto elimina el boilerplate y deja `product = PRODUCTS[p_id]` disponible como variable
para el caso `add` (ítem nuevo) sin necesitar un segundo `session.get(Products, p_id)`.

```python
# Antes del match — aplica a todas las acciones
if p_id not in PRODUCTS:
    return f"ERROR_VALIDACION: p_id={p_id} no existe en el catálogo."

product = PRODUCTS[p_id]

match action:
    case "add":
        if existing:
            existing.oi_units += units
        else:
            session.add(OrderItems(..., oi_unit_price=float(product.p_sale_price)))
    ...
```

---

## Contrato de error

```python
"ERROR_VALIDACION: ..."   # datos incorrectos → LLM pregunta al cliente y reintenta
"ERROR_INTERNO: ..."      # fallo técnico o estado inesperado en DB → informar, no reintentar
```

---

## Protección contra orden vacía

Tras hacer `session.flush()`, se consultan todos los ítems restantes. Si la lista queda vacía,
se hace `session.rollback()` y se retorna `ERROR_VALIDACION:` indicando usar `cancel_order`.

```python
session.flush()
all_items = session.exec(select(OrderItems).where(...)).all()

if not all_items:
    session.rollback()
    return "ERROR_VALIDACION: no puedes eliminar todos los ítems. Usa cancel_order si quieres cancelarlo."
```

Esto garantiza que la DB nunca tenga una orden con `o_total=0` y sin ítems.

---

## Flujos de retry por tipo de error

### Acción desconocida
```
1. LLM llama update_order(action="borrar", ...)
2. Tool → "ERROR_VALIDACION: acción 'borrar' desconocida. Usa: add, reduce_units, remove, set_units."
3. LLM corrige la acción y reintenta ✓
```

### p_id no en catálogo
```
1. LLM llama update_order(action="add", p_id=999, units=1)
2. Tool → "ERROR_VALIDACION: p_id=999 no existe en el catálogo."
3. LLM → cliente: "¿Cuál es el producto que quieres agregar?"
4. [siguiente turno] LLM reintenta con p_id correcto ✓
```

### Intento de dejar orden vacía
```
1. LLM llama update_order(action="remove", p_id=1)  [único ítem]
2. flush() → all_items=[] → rollback()
3. Tool → "ERROR_VALIDACION: no puedes eliminar todos los ítems. Usa cancel_order..."
4. LLM → cliente: "¿Quieres cancelar el pedido completo?"
5. Cliente confirma → LLM llama cancel_order() ✓
```

---

## Tests — `tests/test_update_order.py` (18/18 ✅)

### Validaciones de entrada (sin DB)
- [x] `test_unknown_action` — `action="borrar"` → `ERROR_VALIDACION:`
- [x] `test_unknown_p_id` — `p_id=999` → `ERROR_VALIDACION:` con `p_id=999`
- [x] `test_add_units_zero` — `action="add", units=0` → `ERROR_VALIDACION:`
- [x] `test_add_units_negative` — `action="add", units=-2` → `ERROR_VALIDACION:`
- [x] `test_reduce_units_zero` — `action="reduce_units", units=0` → `ERROR_VALIDACION:`
- [x] `test_set_units_zero` — `action="set_units", units=0` → `ERROR_VALIDACION:`
- [x] `test_remove_ignores_units_value` — `action="remove", units=0` válido si queda ≥1 ítem

### Validaciones en DB
- [x] `test_reduce_units_item_not_in_order` — ítem no existe en pedido → `ERROR_VALIDACION:`
- [x] `test_set_units_item_not_in_order` — ítem no existe en pedido → `ERROR_VALIDACION:`
- [x] `test_remove_item_not_in_order` — ítem no existe en pedido → `ERROR_VALIDACION:`
- [x] `test_order_not_found_in_db` — `session.get` retorna `None` → `ERROR_INTERNO:`
- [x] `test_last_item_removal_blocked` — eliminar único ítem → `ERROR_VALIDACION:` + rollback
- [x] `test_reduce_units_to_zero_leaves_no_items_blocked` — reduce deja orden vacía → `ERROR_VALIDACION:` + rollback

### Happy path (DB mockeado)
- [x] `test_add_new_item` — ítem nuevo agregado → retorna summary
- [x] `test_add_existing_item_increases_units` — ítem existente, `units` acumulados correctamente
- [x] `test_set_units` — `oi_units` cambia al valor exacto indicado
- [x] `test_remove_item_with_others_remaining` — `session.delete` llamado, retorna summary
- [x] `test_db_exception_returns_error_interno` — excepción en DB → `ERROR_INTERNO:`

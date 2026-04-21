# Fix: _order_summary

**Fecha:** 2026-04-20
**Archivo:** `app/services/chatbot/yalti.py`
**Tests:** `app/services/chatbot/tests/test_order_summary.py` (10/10 ✅)

---

## Problema central

`_order_summary` es el helper que produce el texto visible del pedido — lo consumen
`create_order` y `update_order`, y **cualquier artefacto que muestre al cliente o al
dueño el estado del carrito**. Un crash o un "None" renderizado aquí es una falla
visible al usuario final.

El código original tenía tres categorías de riesgo:

1. **KeyError** en productos que desaparecen del catálogo entre la creación y el resumen.
2. **Render sucio** — campos `Optional` del schema (`o_customer_notes`, `o_total`) que aparecían como la cadena `"None"` en el output al cliente.
3. **Comportamiento frágil** ante `order_items=[]` — no produce error, pero genera un mensaje malformado sin la línea de ítems.

---

## Issues corregidos

| # | Issue | Riesgo original |
|---|-------|-----------------|
| 1 | `PRODUCTS[oi.oi_p_id]` sin validar existencia | `KeyError` si un `p_id` persiste en DB pero ya no está en el catálogo cargado |
| 2 | `order.o_customer_notes` puede ser `None` (schema `Optional[str]`) | Output "📍: None" visible al cliente |
| 3 | `order.o_total` tipado como `float` pero persistido como `Numeric(10,2)` → `Decimal` en runtime | `:.0f` acepta Decimal, pero inconsistente con el resto del código que usa `float()` explícito |
| 4 | `order_items=[]` sin manejo | Mensaje sin la línea de ítems (header + total sueltos) — malformado |

---

## Decisión: **no** agregar fallback para `customer_name`

El `c_name` del cliente se captura una sola vez en el onboarding y queda asociado
a `c_whatsapp_id` en `Customers`. Cuando `_order_summary` se invoca, ya pasamos
esa etapa — el nombre siempre está poblado.

Agregar `customer_name or "Cliente"` enmascararía un bug del flujo de registro
en lugar de arreglarlo. Si llegara un `None` aquí, **queremos** que se vea raro
para detectarlo, no disfrazarlo con un genérico.

---

## Decisión: orden vacía devuelve mensaje, no error

`update_order` ya previene que una orden quede sin ítems (hace rollback y retorna
`ERROR_VALIDACION`), y `create_order` valida `order_items` no vacío antes de escribir
a DB. En el flujo normal `_order_summary` jamás recibe `[]`.

Pero al ser un helper reutilizable, agregar el early return es barato:

```python
if not order_items:
    return f"🛍️ Pedido — {customer_name}\n\n(sin ítems)\n\nTotal: $0"
```

Protege contra futuros llamadores (RAG, dashboard, scripts de debug) sin agregar
complejidad.

---

## Decisión: `float()` explícito en `o_total`

`Column(Numeric(10,2))` devuelve `Decimal` en runtime. Python acepta `Decimal`
en `:.0f`, por lo que el código original funcionaba por accidente. El fix lo
hace explícito para alinearlo con `update_order` y `create_order`, que ya hacían
`float(oi_unit_price)` / `float(order.o_total)`.

```python
total = float(order.o_total) if order.o_total is not None else 0.0
```

El `is not None` cubre el edge case teórico de una DB row con `o_total=NULL`.

---

## Tests — `tests/test_order_summary.py` (10/10 ✅)

### Fallbacks defensivos
- [x] `test_product_missing_in_catalog` — `p_id=999` no en PRODUCTS → "Producto #999", sin KeyError
- [x] `test_customer_notes_none` — `o_customer_notes=None` → "(sin notas)", no "None"
- [x] `test_customer_notes_empty_string` — `o_customer_notes=""` → "(sin notas)"
- [x] `test_empty_order_items` — `order_items=[]` → "(sin ítems)" + "Total: $0"
- [x] `test_o_total_none_fallback` — `o_total=None` → "Total: $0", no TypeError

### Tipos numéricos (DB devuelve Decimal)
- [x] `test_decimal_unit_price` — `oi_unit_price=Decimal("120.00")` → "240" con `:.0f`
- [x] `test_decimal_order_total` — `o_total=Decimal("305.50")` → float() aplicado correctamente

### Happy path
- [x] `test_single_item` — 1 ítem, nombre, dirección presentes en el output
- [x] `test_multiple_items_totals_computed_per_line` — `2x` y `1x` con subtotales por línea
- [x] `test_mixed_known_and_unknown_product` — ítem conocido + ítem huérfano renderizados juntos

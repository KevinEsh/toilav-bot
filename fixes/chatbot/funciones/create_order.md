# Fix: create_order

**Fecha:** 2026-04-19  
**Archivo:** `app/services/chatbot/yalti.py`  
**Tests:** `app/services/chatbot/tests/test_create_order.py` (13/13 ✅)

---

## Problema central

Cuando `create_order` recibe parámetros inválidos (dirección faltante, p_id inexistente, units=0),
necesita:
1. No escribir nada en la DB.
2. Retornar un error descriptivo al LLM.
3. Que el LLM obtenga la info faltante del cliente y **vuelva a llamar la tool** en el mismo loop,
   sin salir del agente ni perder el historial.

---

## Issues corregidos

| # | Issue | Riesgo original |
|---|-------|-----------------|
| 1 | `order_items=[]` no validado | Orden vacía en DB |
| 2 | `delivery_address=""` no validado | Orden sin dirección en DB |
| 3 | `PRODUCTS[item["p_id"]]` sin validar existencia | `KeyError` → crash |
| 4 | `units < 1` no validado | Ítems con cantidad inválida en DB |
| 5 | Estructura del dict no validada | `KeyError` en `item["p_id"]` o `item["units"]` |
| 6 | Sin `try/except` en escritura a DB | Excepción no manejada propagada al agente |
| 7 | `session.refresh(items[0])` sin validar lista vacía | `IndexError` si `order_items=[]` llegaba a DB |

---

## Mecanismo: Tool return como señal al LLM

pydantic-ai no tiene retry automático en tools como lo tiene Pydantic para estructuras de salida.
**La única forma de re-invocar una tool en el mismo loop es que el LLM decida hacerlo.**

Por eso el contrato de `create_order` retorna strings con prefijo `ERROR_VALIDACION:`.
El LLM lee ese string, entiende qué falta, pregunta al cliente, y vuelve a llamar la tool
con los parámetros corregidos — todo dentro del mismo `agent.run()`.

```
cliente → mensaje
  └─► agent.run()
        ├─ LLM llama create_order(items, address="")
        │     └─ tool retorna "ERROR_VALIDACION: delivery_address es obligatoria..."
        ├─ LLM lee el error
        ├─ LLM responde al cliente: "¿Cuál es tu dirección de entrega?"
        │     [cliente responde en siguiente turno]
        └─ [nuevo agent.run()] LLM llama create_order(items, address="Calle 15 #45")
              └─ tool retorna summary del pedido ✓
```

> **Nota:** La corrección del parámetro ocurre en un **nuevo turno** (nueva llamada a `agent.run()`),
> no dentro del mismo turn. El LLM no puede pausar mitad de un turn para esperar al cliente.

---

## Por qué no `ModelRetry` de pydantic-ai

`ModelRetry` está diseñado para errores de **formato/schema** de la respuesta estructurada
(`output_type`), no para errores de negocio dentro de una tool.
Si lanzáramos `ModelRetry` desde `create_order`, el agente reinventaría parámetros sin pedirle
nada al cliente — generando una dirección inventada o `units=1` por defecto.

---

## Contrato de error

```python
"ERROR_VALIDACION: ..."   # datos del cliente incompletos → LLM pregunta y reintenta
"ERROR_INTERNO: ..."      # fallo técnico → LLM informa al cliente, no reintenta
```

---

## Flujos de retry por tipo de error

### delivery_address vacía
```
1. LLM llama create_order(order_items=[...], delivery_address="")
2. Tool → "ERROR_VALIDACION: delivery_address es obligatoria..."
3. LLM → cliente: "¿Me das tu dirección de entrega?"
4. [siguiente turno] cliente: "Av. Juárez 123"
5. LLM llama create_order(..., delivery_address="Av. Juárez 123") ✓
```

### p_id inexistente
```
1. LLM llama create_order(order_items=[{"p_id": 999, "units": 2}], ...)
2. Tool → "ERROR_VALIDACION: Ítem 0: p_id=999 no existe en el catálogo."
3. LLM → cliente: "No encontré ese producto, ¿cuál quieres del catálogo?"
4. [siguiente turno] cliente confirma p_id válido
5. LLM llama create_order con p_id correcto ✓
```

### units inválidos
```
1. LLM llama create_order(order_items=[{"p_id": 3, "units": 0}], ...)
2. Tool → "ERROR_VALIDACION: Ítem 0 (p_id=3): units debe ser >= 1."
3. LLM → cliente: "¿Cuántas unidades deseas?"
4. [siguiente turno] cliente: "2"
5. LLM llama create_order con units=2 ✓
```

### ERROR_INTERNO (fallo técnico)
```
1. Exception en DB → Tool → "ERROR_INTERNO: No se pudo crear el pedido..."
2. LLM → cliente: "Hubo un problema técnico. Intenta de nuevo."
3. LLM NO reintenta (solo reintenta ante ERROR_VALIDACION)
```

---

## Idempotencia: _hide_when_order_exists

```python
async def _hide_when_order_exists(ctx, tool_def) -> ToolDefinition | None:
    return None if ctx.deps.active_order_id is not None else tool_def
```

- `ERROR_VALIDACION` → `active_order_id` sigue `None` → tool visible → LLM puede reintentar.
- Éxito → `active_order_id` se setea → tool desaparece → imposible crear doble orden.

---

## Tests — `tests/test_create_order.py` (13/13 ✅)

### Validaciones (sin DB)
- [x] `test_empty_order_items` — `order_items=[]` → `ERROR_VALIDACION:`
- [x] `test_empty_delivery_address` — `delivery_address=""` → `ERROR_VALIDACION:`
- [x] `test_whitespace_delivery_address` — `delivery_address="   "` → `ERROR_VALIDACION:`
- [x] `test_unknown_p_id` — `p_id=999` no existe en PRODUCTS → `ERROR_VALIDACION:` con `p_id=999`
- [x] `test_units_zero` — `units=0` → `ERROR_VALIDACION:`
- [x] `test_units_negative` — `units=-3` → `ERROR_VALIDACION:`
- [x] `test_item_not_a_dict` — ítem es string en lugar de dict → `ERROR_VALIDACION:`
- [x] `test_item_missing_units_field` — dict sin clave `units` → `ERROR_VALIDACION:`
- [x] `test_item_missing_p_id_field` — dict sin clave `p_id` → `ERROR_VALIDACION:`
- [x] `test_multiple_errors_all_reported` — múltiples ítems con error → todos reportados en un solo retorno

### Happy path (DB mockeado)
- [x] `test_creates_order_and_sets_active_order_id` — parámetros válidos → retorna summary, `active_order_id=42`
- [x] `test_active_order_id_stays_none_after_validation_error` — `ERROR_VALIDACION` no toca `active_order_id`
- [x] `test_db_exception_returns_error_interno` — excepción en DB → `ERROR_INTERNO:`, `active_order_id` sigue `None`

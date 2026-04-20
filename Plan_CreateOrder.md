# Plan: Retry de create_order tras fallo de validación

**Fecha:** 2026-04-19  
**Contexto:** pydantic-ai Agent con tool `create_order` en `yalti.py`

---

## Problema central

Cuando `create_order` recibe parámetros inválidos (dirección faltante, p_id inexistente, units=0),
necesita:
1. No escribir nada en la DB.
2. Retornar un error descriptivo al LLM.
3. Que el LLM obtenga la info faltante del cliente y **vuelva a llamar la tool** en el mismo loop,
   sin salir del agente ni perder el historial.

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
(output_type), no para errores de negocio dentro de una tool.
Si lanzáramos `ModelRetry` desde `create_order`, el agente reinventaría parámetros sin pedirle
nada al cliente — generando una dirección inventada o units=1 por defecto. Eso es exactamente
lo que queremos evitar.

---

## Diseño del contrato de error

```python
# Prefijos semánticos que el LLM interpreta como instrucciones de acción:
"ERROR_VALIDACION: ..."   # datos del cliente incompletos → preguntar y reintentar
"ERROR_INTERNO: ..."      # fallo técnico → informar al cliente, no reintentar
```

El docstring de la tool documenta explícitamente el comportamiento esperado:

```python
"""
Si esta función retorna un error de validación (string que empieza con "ERROR_VALIDACION:"),
NO debes crear el pedido. Primero obtén la información faltante del cliente y vuelve a llamar
esta función con los parámetros corregidos.
"""
```

---

## Flujo detallado por tipo de error

### Caso 1: delivery_address vacía

```
1. LLM llama create_order(order_items=[...], delivery_address="")
2. Tool retorna: "ERROR_VALIDACION: delivery_address es obligatoria. Pide al cliente su dirección."
3. LLM responde al cliente: "Para completar tu pedido, ¿me puedes dar tu dirección de entrega?"
4. [siguiente turno] cliente: "Av. Juárez 123, col. Centro"
5. LLM llama create_order(order_items=[...], delivery_address="Av. Juárez 123, col. Centro")
6. Tool retorna _order_summary ✓
```

### Caso 2: p_id inexistente en catálogo

```
1. LLM llama create_order(order_items=[{"p_id": 999, "units": 2}], ...)
2. Tool retorna: "ERROR_VALIDACION:\n- Ítem 0: p_id=999 no existe en el catálogo."
3. LLM responde: "No encontré ese producto. ¿Podrías confirmar cuál quieres del catálogo?"
4. [siguiente turno] cliente confirma producto válido
5. LLM llama create_order con p_id correcto ✓
```

### Caso 3: units inválidos

```
1. LLM llama create_order(order_items=[{"p_id": 3, "units": 0}], ...)
2. Tool retorna: "ERROR_VALIDACION:\n- Ítem 0 (p_id=3): units debe ser un entero >= 1."
3. LLM pregunta: "¿Cuántas unidades de ese producto deseas?"
4. [siguiente turno] cliente: "2"
5. LLM llama create_order con units=2 ✓
```

### Caso 4: ERROR_INTERNO (fallo técnico)

```
1. LLM llama create_order(...)
2. Exception en DB → Tool retorna: "ERROR_INTERNO: No se pudo crear el pedido..."
3. LLM informa al cliente: "Hubo un problema técnico. Intenta de nuevo."
4. LLM NO reintenta en ese mismo turno (la tool retornó ERROR_INTERNO, no ERROR_VALIDACION)
```

---

## La guarda _hide_when_order_exists garantiza idempotencia

```python
async def _hide_when_order_exists(ctx, tool_def) -> ToolDefinition | None:
    return None if ctx.deps.active_order_id is not None else tool_def
```

Si `create_order` falla con `ERROR_VALIDACION`, `ctx.deps.active_order_id` sigue siendo `None`
→ la tool permanece visible en el siguiente turno → el LLM puede reintentar.

Si `create_order` tiene éxito, `active_order_id` se setea → la tool desaparece del LLM
→ imposible crear una segunda orden accidentalmente.

---

## Extensión futura: retry dentro del mismo turn

Si en el futuro se quiere que el LLM resuelva ciertos errores sin salir al cliente
(e.g. normalizar un p_id por nombre fuzzy), se puede agregar una pre-validación ligera
antes de llamar la tool. Pero esto requiere una tool auxiliar de búsqueda y está fuera
del scope actual.

---

## Checklist de implementación

- [x] Validaciones de entrada en `create_order` (order_items, address, p_ids, units)
- [x] Prefijos `ERROR_VALIDACION:` y `ERROR_INTERNO:` en retornos de error
- [x] Docstring actualizado con instrucción de retry para el LLM
- [x] try/except en escritura a DB con log de error

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

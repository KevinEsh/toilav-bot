# Backlog de Robustecimiento del Bot

**Fecha creación:** 2026-04-19  
**Prioridad:** Alta (transacciones financieras)  
**Effort total estimado:** 4-5 horas

---

## 🔴 Críticas (Manejo de transacciones/dinero)

### 1. Robustecer `create_order` en yalti.py
**Estado:** ✅ Completado (2026-04-19)  
**Effort:** 30-45 min  
**Issues:**
- ❌ No valida si `order_items` está vacío
- ❌ No valida si `delivery_address` es cadena vacía
- ❌ Acceso directo a `PRODUCTS[item["p_id"]]` sin validar existencia → KeyError
- ❌ No valida si `units >= 1`
- ❌ No valida estructura esperada del dict
- ❌ No hay rollback explícito si commit falla
- ❌ Intenta refrescar `items[0]` sin validar si items es vacío

**Aceptación:**
- Todas las validaciones presentes
- Manejo de errores con try/except
- Tests que cubran casos edge

---

### 2. Robustecer `update_order` en yalti.py
**Estado:** ✅ Completado (2026-04-19)  
**Effort:** 30-45 min  
**Issues:**
- ❌ **BUG FATAL (L381):** `_order_summary(session, o_id)` pero espera `(order, order_items, customer_name)`
- ❌ No valida si `order` existe (session.get puede retornar None)
- ❌ No valida si `units >= 0`
- ❌ No valida si `p_id` existe en PRODUCTS
- ❌ No previene que orden quede vacía
- ❌ Docstring dice "set_units" pero código usa "update_units" (inconsistencia)
- ❌ Sin validación de límites en `reduce_units`

**Aceptación:**
- Bug L381 corregido
- Validaciones entrada presentes
- Orden nunca queda sin items
- Docstring y código consistentes

---

### 3. Robustecer `cancel_order` en yalti.py
**Estado:** ✅ Completado (2026-04-20)  
**Effort:** 10-15 min  
**Issues:**
- ❌ No valida que `order` existe antes de modificar
- ❌ Sin try/except en escritura a DB
- ❌ Permitía re-cancelar órdenes `COMPLETED` / `CANCELLED`
- ❌ `active_order_id` se limpiaba aunque el commit fallara

**Aceptación:**
- Validación presentes
- Guard contra estados terminales
- `active_order_id` limpiado sólo tras commit exitoso
- Tests: `tests/test_cancel_order.py` (7/7 ✅)

---

## 🟠 Altas (Logística/datos)

### 4. Robustecer `_order_summary` en yalti.py
**Estado:** ✅ Completado (2026-04-20)  
**Effort:** 15-20 min  
**Issues:**
- ❌ Acceso directo `PRODUCTS[oi.oi_p_id]` sin validar existencia → KeyError
- ❌ `o_customer_notes` nullable renderizaba como "None" al cliente
- ❌ `o_total` Decimal sin `float()` explícito (inconsistente con el resto)
- ❌ `order_items=[]` producía mensaje malformado

**Aceptación:**
- Validación presente con fallback
- "(sin notas)" / "(sin ítems)" como fallbacks visibles
- `float()` explícito para Decimal
- Tests: `tests/test_order_summary.py` (10/10 ✅)

---

### 5. Implementar `escalate_to_staff` en yalti.py
**Estado:** ✅ Completado (2026-04-20)  
**Effort:** 20-30 min  
**Issues:**
- ❌ Lógica real comentada (L439-462)
- ❌ Retorna solo dummy string
- ❌ Sin validación de `message` vacío
- ❌ Sin validación de credenciales / `OWNER_WA_ID`
- ❌ Sin contexto del cliente en el mensaje al dueño
- ❌ `_once` se marcaba antes de validar — gastaba la única escalation del turno

**Aceptación:**
- Código HTTP funcional (llamada directa a WhatsApp Graph API)
- Manejo por tipo de excepción: `HTTPStatusError`, `TimeoutException`, `HTTPError`
- Validaciones con contrato `ERROR_VALIDACION` / `ERROR_INTERNO`
- Nombre + wa_id del cliente incluidos en el body al dueño
- Tests: `tests/test_escalate_to_staff.py` (13/13 ✅)

---

## 🟡 Medias (Data integrity)

### 6. Robustecer `_get_active_order` en yalti.py
**Estado:** ✅ Completado (2026-04-21)  
**Effort:** 10 min  
**Issues:**
- ❌ Sin manejo de errores en consulta DB

**Aceptación:**
- Try/except con fallback a `None` (mismo semántico que "no hay orden activa")
- Log de la excepción para diagnóstico
- Tests: `tests/test_get_active_order.py` (5/5 ✅)

---

### 7. Robustecer `_get_or_create_customer`
**Estado:** ✅ Completado (2026-04-21)  
**Effort:** 10 min (real: 25 min — incluyó borrar duplicado en `yalti.py`)  
**Hallazgos durante el fix:**
- 🔎 **Duplicación:** existían dos versiones — una viva en `whatsapp_utils.py:185` (invocada desde el webhook) y una huérfana en `yalti.py:82`. Hardenear la de `yalti.py` no arreglaba nada real. **Dead code eliminada** en `yalti.py`; el hardening se aplicó a `whatsapp_utils.py`.
- 🔎 **Riesgo #1 identificado:** `wa_id=""` colapsaría clientes distintos en un mismo `Customers` vía `SELECT ... WHERE c_whatsapp_id=""` — corrupción permanente de historial/órdenes. Se agregó `ValueError` ruidoso.
- 🔎 **Riesgo #2 identificado:** falla de DB en el primer paso del pipeline sin log con contexto. Se agregó try/except con log + re-raise.
- 🔎 **Riesgo #3 fuera de alcance:** race condition en creación concurrente (ver item #9 nuevo).

**Issues corregidos:**
- ❌ Sin validación de `wa_id` (null/empty/whitespace) — podía colisionar clientes
- ❌ Sin normalización (`.strip()`) — espacios extras creaban duplicados
- ❌ Sin try/except — errores de DB sin contexto en logs

**Aceptación:**
- `ValueError` si `wa_id` vacío/whitespace/None
- `wa_id` normalizado con `.strip()` antes de query + create
- Try/except con `logger.error(..., wa_id=...)` y re-raise
- Dead code de `yalti.py` eliminada
- Tests: `tests/test_get_or_create_customer.py` (8/8 ✅)

---

### 8. Implementar `show_products` en yalti.py
**Estado:** Pendiente  
**Effort:** 30-45 min  
**Issues:**
- ❌ Retorna solo dummy implementation

**Aceptación:**
- Integración real con WhatsApp Carousel API
- Tests que validen formato

---

## Testing
**Estado:** Pendiente  
**Effort:** 1-1.5 horas  

Agregar tests en `app/services/chatbot/tests/` para:
- Casos edge de `create_order` (vacío, dirección vacía, producto inexistente)
- Casos edge de `update_order` (orden no existe, units negativo, orden vacía después de reducción)
- Validación de `_order_summary` con PRODUCTS faltantes

---

## 🆕 Items descubiertos durante el hardening

### 9. Race condition en `_get_or_create_customer`
**Estado:** Pendiente  
**Origen:** Descubierto durante el fix del item #7 (2026-04-21).  
**Effort:** 30-45 min  
**Archivo:** `app/services/chatbot/whatsapp_utils.py`

**Descripción:**
Dos mensajes simultáneos del mismo cliente **nuevo** (primer contacto) disparan un race:
1. Request A lee `SELECT ... FIRST()` → `None`.
2. Request B lee `SELECT ... FIRST()` → `None` (todavía no hay commit).
3. Request A hace `INSERT` + `COMMIT`.
4. Request B hace `INSERT` + `COMMIT` → `IntegrityError` por constraint único en `c_whatsapp_id`.

El `except Exception` en `process_incoming_messages` traga el error pero el mensaje del request B **se pierde sin respuesta al cliente**.

**Aceptación:**
- `except IntegrityError` específico que haga re-SELECT y use el registro ya creado por el otro request.
- Test que simule el race (concurrencia con threads o mock de `commit()` que la primera vez crashee con `IntegrityError`).
- Documentar en `fixes/chatbot/funciones/get_or_create_customer.md`.

**Impacto:** bajo (requiere clientes nuevos que manden ≥2 mensajes simultáneos en el debounce window de 5s). Pero el bug corrompe silenciosamente la experiencia del primer contacto.

---

### 10. Extraer `whatsapp_client.py` — romper ciclo de import
**Estado:** ✅ Completado (2026-04-21)  
**Origen:** Descubierto durante el fix de `escalate_to_staff` (item #5, 2026-04-20).  
**Effort:** 45-60 min (real: ~40 min)  
**Archivos:** `app/services/chatbot/whatsapp_client.py` (nuevo), `yalti.py`, `whatsapp_utils.py`

**Descripción:**
`yalti.py` necesita llamar a la WhatsApp Graph API pero no podía importar de `whatsapp_utils.py` (ciclo: `whatsapp_utils` importa `yalti`). Se extrajo la mecánica HTTP (URL, headers, POST + `raise_for_status`) a un módulo hoja sin dependencias hacia `yalti`/`whatsapp_utils`.

**Decisiones clave:**
- `post_message(payload, timeout=10.0)` **no atrapa** excepciones — las deja propagar al caller para que cada uno decida el mensaje de error específico (el de `escalate_to_staff` distingue timeout para mostrar "(timeout)" al LLM; un futuro `show_products` podría reintentar).
- `send_message` en `whatsapp_utils.py` **sigue stubbeada** (decisión del dueño para no spammear clientes reales durante desarrollo). Asimetría intencional con `escalate_to_staff` que sí manda real (para validar que las notificaciones llegan al teléfono del dev).
- Timeout expuesto como argumento — `show_products` con Carousel + imágenes probablemente necesite más de 10s.

**Aceptación cumplida:**
- Módulo `whatsapp_client.py` sin imports hacia `yalti`/`whatsapp_utils`
- `escalate_to_staff` delega en el cliente
- Tests: `tests/test_whatsapp_client.py` (9/9 ✅) + `tests/test_escalate_to_staff.py` sigue (13/13 ✅)
- Doc: `fixes/chatbot/funciones/whatsapp_client.md`

**Habilita:** item #8 (`show_products` Carousel) — ya tiene cliente compartido donde enganchar el POST sin duplicar nada.

---

## Notas

- **Modelos a usar:** Sonnet 4.6 (mejor análisis de seguridad vs Haiku, más eficiente que Opus)
- **Rama:** `agustin/deploy/update_order`
- **Base de datos:** SQLModel + PostgreSQL (validar integridad referencial)

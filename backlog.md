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
**Estado:** Pendiente  
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
**Estado:** Pendiente  
**Effort:** 10-15 min  
**Issues:**
- ❌ No valida que `order` existe antes de modificar

**Aceptación:**
- Validación presentes

---

## 🟠 Altas (Logística/datos)

### 4. Robustecer `_order_summary` en yalti.py
**Estado:** Pendiente  
**Effort:** 15-20 min  
**Issues:**
- ❌ Acceso directo `PRODUCTS[oi.oi_p_id]` sin validar existencia → KeyError

**Aceptación:**
- Validación presente con fallback

---

### 5. Implementar `escalate_to_staff` en yalti.py
**Estado:** Pendiente  
**Effort:** 20-30 min  
**Issues:**
- ❌ Lógica real comentada (L439-462)
- ❌ Retorna solo dummy string

**Aceptación:**
- Código descomentado y funcional
- Manejo de errores HTTP
- Tests que simulen envío a WhatsApp API

---

## 🟡 Medias (Data integrity)

### 6. Robustecer `_get_active_order` en yalti.py
**Estado:** Pendiente  
**Effort:** 10 min  
**Issues:**
- ❌ Sin manejo de errores en consulta DB

**Aceptación:**
- Try/except presente

---

### 7. Robustecer `_get_or_create_customer` en yalti.py
**Estado:** Pendiente  
**Effort:** 10 min  
**Issues:**
- ❌ Sin validación de `wa_id` (puede ser null/empty)

**Aceptación:**
- Validación presente

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

## Notas

- **Modelos a usar:** Sonnet 4.6 (mejor análisis de seguridad vs Haiku, más eficiente que Opus)
- **Rama:** `agustin/deploy/update_order`
- **Base de datos:** SQLModel + PostgreSQL (validar integridad referencial)

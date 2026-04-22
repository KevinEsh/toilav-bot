# Fix: show_products

**Fecha:** 2026-04-21
**Archivo:** `app/services/chatbot/yalti.py`
**Tests:** `app/services/chatbot/tests/test_show_products.py` (16/16 ✅)
**Backlog:** Item #8

---

## Problema

La función era un dummy que retornaba `"carrusel enviado al cliente"` sin
mandar nada al cliente. Para un bot de ventas, mostrar productos con
imagen + precio es el diferenciador visible #1 (impacta conversión
directamente).

---

## Diseño: image-per-product, **no** Carousel template

WhatsApp ofrece dos caminos para mostrar varios productos:

1. **Carousel/Product List templates** — requiere configurar un
   **Facebook Commerce Catalog**, mapear SKUs, y registrar la plantilla
   con Meta (review process). Feature completa, pero infra no existe.
2. **Mensaje image por producto** — payload `type: "image"` con `link`
   al `p_image_url` ya existente en la BD + `caption` con nombre/precio/
   descripción. Usa las credenciales del Graph API que ya tenemos.

Elegimos #2: cero infra adicional, el `Products.p_image_url` ya apunta a
MinIO, y el cliente ve la misma información. Cuando se active el
catálogo de Meta se puede reemplazar este bloque sin tocar callers.

---

## Decisión: cap de 5 productos

WhatsApp tolera ráfagas cortas pero marca spam si mandas 10 mensajes
encadenados desde el mismo número. 5 es el umbral práctico — además un
cliente ya no va a mirar más de 5 imágenes en secuencia sin perder el
hilo. El LLM tiene que curar (por eso el docstring dice "Máximo 5").

Expuesto como constante `_SHOW_PRODUCTS_CAP = 5` arriba de la tool para
que sea obvio y ajustable.

---

## Decisión: fallback a texto si no hay `p_image_url`

Un producto sin foto no debe romper el envío — cae a `type: "text"`
con el mismo caption. Así el seed de catálogo puede faltar imágenes sin
bloquear la venta. La forma del caption (`*Nombre* — $precio MXN\n\n
descripción`) es idéntica entre ambos tipos.

---

## Decisión: envío secuencial + break en el primer error

Mandar con `asyncio.gather()` sería más rápido pero complica:
- Orden de llegada no garantizado (el cliente ve los productos en orden
  aleatorio).
- Rate limits: WhatsApp puede devolver 429 si haces N POSTs en paralelo.
- Si uno falla y otros no, el estado parcial es raro de reportar.

Secuencial + break en el primer error es más simple y predecible. Si el
primer envío pasa y el segundo falla, reportamos "Se enviaron 1 de 2
productos" y marcamos `_once` (el cliente ya vio algo, no tiene sentido
reintentar).

---

## Decisión: `_once` marcado **después** del primer envío exitoso

Contraste con `escalate_to_staff`, donde `_once` se marca **antes** del
POST (para prevenir que reintente y duplique la notificación al dueño
en un mismo turno).

En `show_products` la lógica es distinta:
- Si **ningún** producto llegó (todos fallaron), el cliente no vio nada
  — el LLM debe poder reintentar o responder por texto. Por eso no
  marcamos `_once` en ese caso.
- Si **al menos uno** llegó, ya no reintentar en el mismo turno: se
  marca `_once` y la siguiente llamada devuelve "ya fueron enviados".

Esto se refleja en los tests `test_timeout_on_first_aborts_nothing_sent`
(no marca `_once`) y `test_partial_send_marks_once_and_reports` (sí
marca).

---

## Decisión: dedup preservando orden

`p_ids=[1, 2, 1, 2]` → `[1, 2]`. Evita mandar el mismo producto dos
veces si el LLM se equivoca. Usamos el truco idiomático:
```python
seen = set()
dedup = [p for p in p_ids if not (p in seen or seen.add(p))]
```

---

## Decisión: filtrado temprano de missing/unavailable

Tres buckets:
- `missing` — p_id no está en `PRODUCTS`
- `unavailable` — `p_is_available=False`
- `valid` — el resto

Si **nada** queda válido, `ERROR_VALIDACION` con detalle por bucket
(así el LLM sabe qué p_ids no son reales y cuáles están agotados, y
puede decidir reconsultar el catálogo o responder "eso no lo tenemos").

Si queda algo, se ignoran silenciosamente los inválidos — no vale la
pena avisar al LLM "ignoré estos" porque eso corrompe la confianza en
el resultado. El LLM asume que lo que pidió fue lo que se mandó (salvo
el cap de 5, que sí se reporta).

---

## Decisión: validar credenciales antes de cualquier POST

Mismo patrón que `escalate_to_staff` — `ERROR_INTERNO` si faltan
`WHATSAPP_ACCESS_TOKEN` o `PHONE_NUMBER_ID`. No intentar y fallar con
mensaje genérico; fallar rápido con log específico.

Nota: `OWNER_WA_ID` no aplica aquí porque `show_products` manda al
cliente, no al dueño.

---

## Tests — `tests/test_show_products.py` (16/16 ✅)

### Validaciones (`TestShowProductsGuards`)
- [x] `test_already_shown_this_turn` — `_once` pre-cargado bloquea HTTP
- [x] `test_empty_p_ids` — `[]` → `ERROR_VALIDACION`, no marca `_once`
- [x] `test_all_missing` — p_ids inexistentes → `ERROR_VALIDACION`
- [x] `test_all_unavailable` — `p_is_available=False` → `ERROR_VALIDACION`
- [x] `test_missing_credentials` — token vacío → `ERROR_INTERNO`

### Filtrado (`TestShowProductsFiltering`)
- [x] `test_mixed_valid_and_invalid_sends_only_valid` — `[1, 999, 3, 2]` envía sólo 1 y 2
- [x] `test_dedup_preserves_order` — `[1, 2, 1, 2]` → 2 envíos en orden
- [x] `test_cap_at_5` — 9 válidos → cappea a 5

### Payload (`TestShowProductsPayload`)
- [x] `test_image_payload_for_product_with_url` — `type: "image"` con link + caption
- [x] `test_text_fallback_without_image` — `type: "text"` si falta `p_image_url`
- [x] `test_caption_without_description` — sin description no deja `\n\n` colgante

### Errores HTTP (`TestShowProductsHttpErrors`)
- [x] `test_timeout_on_first_aborts_nothing_sent` — break, `_once` NO marcado
- [x] `test_http_error_on_first_aborts_nothing_sent` — 5xx → `ERROR_INTERNO`
- [x] `test_partial_send_marks_once_and_reports` — 1 OK + 1 fail → "1 de 2", `_once` sí marcado

### Happy path (`TestShowProductsHappyPath`)
- [x] `test_marks_once_on_success` — `_once` marcado tras envío OK
- [x] `test_second_call_blocked_by_once` — segundo llamado devuelve "ya fueron enviados"

---

## Habilitado por item #10

El ciclo de imports estaba roto por el item #10 (extracción de
`whatsapp_client.py`), así que `show_products` usa el mismo cliente que
`escalate_to_staff` sin duplicar URL/headers/manejo de excepciones.

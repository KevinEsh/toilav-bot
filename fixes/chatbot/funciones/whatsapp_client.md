# Fix: whatsapp_client (nuevo módulo)

**Fecha:** 2026-04-21
**Archivo:** `app/services/chatbot/whatsapp_client.py` (nuevo)
**Tests:** `app/services/chatbot/tests/test_whatsapp_client.py` (9/9 ✅)
**Backlog:** Item #10

---

## Problema central

Dos sitios hacían POST al API de WhatsApp Graph:

- `whatsapp_utils.py::send_message` — respuesta al cliente final (stub en dev).
- `yalti.py::escalate_to_staff` — notificación al dueño (real en dev).

Además `yalti.py` **no podía importar** de `whatsapp_utils.py` porque este
último importa `yalti.agent_generate_response` — ciclo. Por eso
`escalate_to_staff` duplicaba URL, headers, manejo de errores.

Item #8 (`show_products` con Carousel) iba a ser el 3er sitio. Sin un módulo
compartido, cada cambio al API (versión, headers, timeout, reintentos)
requeriría tocar 3 archivos en sincronía.

---

## Diseño

`whatsapp_client.py` es un módulo hoja — importa sólo de `config` y `httpx`,
no importa de `yalti` ni `whatsapp_utils`. Eso rompe el ciclo.

```python
async def post_message(payload: dict, timeout: float = 10.0) -> httpx.Response:
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    url = _messages_url()
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
    return response
```

---

## Decisión: el cliente **no** atrapa excepciones — las deja propagar

Cada caller tiene un mensaje de error distinto según el caso:
- `escalate_to_staff` retorna `"ERROR_INTERNO: no se pudo notificar al dueño (timeout)..."` para timeouts específicamente.
- Un futuro `show_products` podría reintentar en ciertos fallos, o decirle al cliente "catálogo temporalmente no disponible".

Si el cliente atrapara y convirtiera a `bool` o a una domain exception,
perderíamos la discriminación. Preferimos dejar propagar las `httpx.*`
excepciones (contrato explícito en el docstring).

Justificación adicional: el cliente tampoco loguea errores. Así el log
del caller tiene contexto específico (`c_id=...`, `o_id=...`) en vez de
un log genérico "WhatsApp POST failed".

---

## Decisión: preservar el stub de `send_message`

El usuario pidió explícitamente mantener `send_message` stubbeada (`print`
+ `return`) durante desarrollo para no spammear a clientes reales.

**Asimetría intencional:** `escalate_to_staff` sí hace POST real — durante
dev queremos validar que las escalations lleguen al teléfono del dev.

Cuando se decida activar el envío real al cliente final, basta con
reemplazar el cuerpo de `send_message` por:

```python
return await whatsapp_client.post_message(data)
```

El stub está anotado con comentarios explicando el contexto.

---

## Decisión: timeout como argumento, no hardcoded

`post_message(payload, timeout=10.0)` — el default cubre el caso común,
pero `show_products` podría usar un timeout mayor (payload con imágenes
es más pesado). Mejor exponerlo ahora que empezar a duplicar el cliente
otra vez.

---

## Cambio colateral: test de escalate_to_staff

`test_payload_shape_and_url` comprobaba URL + payload + headers en el
mismo test. Como URL y headers ahora son responsabilidad del cliente
(con sus propios tests), se redujo a `test_payload_shape` — verifica
sólo lo que escalate_to_staff construye: el `to`, `type`, y el body con
`c_name` + `wa_id` del cliente.

---

## Tests — `tests/test_whatsapp_client.py` (9/9 ✅)

### Happy path
- [x] `test_url_constructed_from_settings` — URL usa `WHATSAPP_API_VERSION` + `PHONE_NUMBER_ID`
- [x] `test_auth_header_uses_access_token` — `Bearer {WHATSAPP_ACCESS_TOKEN}`
- [x] `test_payload_passed_as_json` — payload llega intacto al `client.post(json=...)`
- [x] `test_default_timeout_is_10s` — timeout default
- [x] `test_custom_timeout` — override funciona
- [x] `test_returns_response_on_success` — devuelve el `httpx.Response`

### Propagación de excepciones
- [x] `test_http_error_propagates` — `HTTPStatusError` sube sin envolver
- [x] `test_timeout_propagates` — `TimeoutException` sube sin envolver
- [x] `test_network_error_propagates` — `ConnectError` sube como `HTTPError`

### Regresiones en callers
- `tests/test_escalate_to_staff.py` (13/13 ✅) — sin cambios de lógica, todos los tests previos siguen pasando porque el mock de `httpx.AsyncClient` intercepta igual aunque esté ahora detrás del cliente.

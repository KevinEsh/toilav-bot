-- ==========================================================================
-- SEED DATA FOR TOILAV-BOT (PostgreSQL syntax)
-- 10 customers with distinct WhatsApp typing styles
-- 10 products (Tremenda Nuez — nuts & gourmet snacks)
-- 2 stores, sales history, stock, orders, messages, FAQ, templates
-- ==========================================================================

-- Clear existing data (respecting FK order)
DELETE FROM messages;
DELETE FROM orderstatushistory;
DELETE FROM orderitems;
DELETE FROM orders;
DELETE FROM stocks;
DELETE FROM sales;
DELETE FROM faqitems;
DELETE FROM messagetemplates;
DELETE FROM products;
DELETE FROM stores;
DELETE FROM customers;
DELETE FROM users;

-- Reset sequences
ALTER SEQUENCE users_id_seq RESTART WITH 1;
ALTER SEQUENCE customers_id_seq RESTART WITH 1;
ALTER SEQUENCE products_id_seq RESTART WITH 1;
ALTER SEQUENCE stores_id_seq RESTART WITH 1;
ALTER SEQUENCE sales_id_seq RESTART WITH 1;
ALTER SEQUENCE stocks_id_seq RESTART WITH 1;
ALTER SEQUENCE orders_id_seq RESTART WITH 1;
ALTER SEQUENCE orderitems_id_seq RESTART WITH 1;
ALTER SEQUENCE orderstatushistory_id_seq RESTART WITH 1;
ALTER SEQUENCE messages_id_seq RESTART WITH 1;
ALTER SEQUENCE messagetemplates_id_seq RESTART WITH 1;
ALTER SEQUENCE faqitems_id_seq RESTART WITH 1;

-- ============================================================================
-- USERS (dashboard staff)
-- ============================================================================
INSERT INTO users (u_email, u_username, u_password_hash, u_role, u_is_active, u_last_login_at, u_created_at, u_updated_at) VALUES
('admin@toilav.com',    'admin_kevin',   '$2b$12$fakehash_admin_placeholder',   'ADMIN',   true,  '2026-03-10 08:00:00', '2025-01-01 00:00:00', '2026-03-10 08:00:00'),
('owner@toilav.com',    'dueño_carlos',  '$2b$12$fakehash_owner_placeholder',   'OWNER',   true,  '2026-03-11 10:30:00', '2025-01-01 00:00:00', '2026-03-11 10:30:00'),
('manager@toilav.com',  'mgr_lucia',     '$2b$12$fakehash_mgr_placeholder',     'MANAGER', true,  '2026-03-09 14:00:00', '2025-02-15 00:00:00', '2026-03-09 14:00:00'),
('staff1@toilav.com',   'staff_ana',     '$2b$12$fakehash_staff1_placeholder',  'STAFF',   true,  '2026-03-08 09:00:00', '2025-06-01 00:00:00', '2026-03-08 09:00:00'),
('staff2@toilav.com',   'staff_pedro',   '$2b$12$fakehash_staff2_placeholder',  'STAFF',   false, '2026-01-15 16:00:00', '2025-06-01 00:00:00', '2026-01-15 16:00:00');


-- ============================================================================
-- CUSTOMERS (10 with diverse profiles)
-- Typing styles:
--   1. Formal/polite        2. Slang/chilango      3. Typos everywhere
--   4. ALL CAPS shouter     5. Minimal/monosyllabic 6. Emoji-heavy
--   7. Voice-note style     8. Rude/impatient       9. Elderly/confused
--  10. English-speaker in MX
-- ============================================================================
INSERT INTO customers (c_phone, c_whatsapp_id, c_name, c_status, c_latitude, c_longitude, c_delivery_instructions, c_created_at, c_updated_at) VALUES
('+5215512345001', 'wa_001', 'María García López',     'ACTIVE',               19.4326,  -99.1332, 'Tocar el timbre dos veces, edificio B depto 4',                   '2025-06-15 10:00:00', '2026-03-01 10:00:00'),
('+5215512345002', 'wa_002', 'El Brayan',              'ACTIVE',               19.3600,  -99.0800, 'dejen cn el del estanquillo de la esquina',                        '2025-07-20 14:30:00', '2026-03-05 14:30:00'),
('+5215512345003', 'wa_003', 'Robeto Hdez',            'ACTIVE',               19.4200,  -99.1700, NULL,                                                               '2025-08-10 09:00:00', '2026-02-28 09:00:00'),
('+5215512345004', 'wa_004', 'LUPITA MARTINEZ',        'ACTIVE',               19.2900,  -99.1500, 'DEJAR EN LA PUERTA DE ENTRADA',                                    '2025-09-01 11:00:00', '2026-03-10 11:00:00'),
('+5215512345005', 'wa_005', 'Juan',                   'ACTIVE',               19.4500,  -99.1400, NULL,                                                               '2025-10-05 16:00:00', '2026-03-08 16:00:00'),
('+5215512345006', 'wa_006', 'Sofía Ramírez ✨',       'ACTIVE',               19.3800,  -99.1600, 'dejar con el portero porfis 🏢',                                   '2025-11-12 08:00:00', '2026-03-09 08:00:00'),
('+5215512345007', 'wa_007', 'Don Arturo Mendoza',     'ACTIVE',               19.4100,  -99.2000, 'es la casa azul junto a la farmacia, tiene un portón grande',      '2025-12-01 07:30:00', '2026-03-07 07:30:00'),
('+5215512345008', 'wa_008', 'Karen Vega',             'ACTIVE',               19.3500,  -99.1100, 'si no llegan en 30 min cancelo',                                   '2026-01-10 13:00:00', '2026-03-11 13:00:00'),
('+5215512345009', 'wa_009', 'Abuelita Concha',        'PENDING_VERIFICATION', 19.4000,  -99.1900, 'es la casa con el árbol de mangos, pregunten por Conchita',        '2026-02-14 10:00:00', '2026-03-06 10:00:00'),
('+5215512345010', 'wa_010', 'Mike Thompson',          'ACTIVE',               19.4270,  -99.1677, 'leave it at the front desk of WeWork Insurgentes',                 '2026-02-20 15:00:00', '2026-03-10 15:00:00');


-- ============================================================================
-- STORES
-- ============================================================================
INSERT INTO stores (s_name, s_description, s_properties, s_rag_text, s_longitude, s_latitude, s_created_at, s_updated_at) VALUES
('Tremenda Nuez Centro',  'Tienda principal en el centro de la CDMX. Especializada en nueces, mixes enchilados, charolas de regalo y snacks gourmet.', '{"address": "Calle Madero 42, Centro Histórico, CDMX", "phone": "+5215500001111", "hours": "9:00-21:00"}', 'Tremenda Nuez Centro es nuestra sucursal principal en el centro histórico de la CDMX. Ofrecemos nueces de la Comarca Lagunera, mixes enchilados y con chocolate, charolas de regalo y snacks gourmet. Horario de lunes a domingo de 9am a 9pm.', -99.1332, 19.4326, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('Tremenda Nuez Condesa', 'Sucursal en la Condesa. Charolas de regalo, snacks enchilados y nueces a granel.',                                              '{"address": "Av. Tamaulipas 78, Condesa, CDMX", "phone": "+5215500002222", "hours": "8:00-22:00"}',        'Tremenda Nuez Condesa es nuestra sucursal en la colonia Condesa. Manejamos charolas de regalo personalizadas, mixes enchilados y con chocolate, y nueces a granel. Horario de lunes a domingo de 8am a 10pm.',                                                                                                                           -99.1700, 19.4130, '2025-03-15 00:00:00', '2026-03-01 00:00:00');


-- ============================================================================
-- PRODUCTS (10 — Tremenda Nuez)
-- ============================================================================
INSERT INTO products (p_name, p_description, p_sale_price, p_currency, p_net_content, p_unit, p_image_url, p_properties, p_rag_text, p_is_available, p_created_at, p_updated_at) VALUES
('Arándano Enchilado',                'Arándanos deshidratados cubiertos con chile. Snack dulce-picante 100% natural. Bolsa individual de 100g.',                                              65.00,  'MXN', 100.0,  'GR',    NULL, '{"spice_level": "medium", "category": "dried_fruit"}',              'Arándano Enchilado: arándanos deshidratados con chile. Snack dulce-picante 100% natural. Bolsa de 100g. Precio: $65 MXN. Disponible.',                                    true, '2025-01-15 00:00:00', '2026-03-01 00:00:00'),
('Charola de Gomitas Enchiladas',     'Charola de regalo con variedad de gomitas enchiladas: aros de mango, botones, besos y más. Ideal para compartir o regalar.',                           450.00, 'MXN', 1.0,    'UNIT',  NULL, '{"category": "gift_tray", "contents": "assorted enchilada gummies"}','Charola de Gomitas Enchiladas: charola de regalo con gomitas enchiladas surtidas (aros de mango, botones, besos). Presentación con listón. Precio: $450 MXN. Disponible.', true, '2025-02-01 00:00:00', '2026-03-01 00:00:00'),
('Charola de Nueces Surtidas',        'Charola de regalo premium con surtido de nueces: nuez de Castilla, nuez de la India, almendras, pistaches y pecanas. Presentación elegante con listón.', 650.00, 'MXN', 1.0,    'UNIT',  NULL, '{"category": "gift_tray", "contents": "mixed premium nuts"}',       'Charola de Nueces Surtidas: charola de regalo premium con nuez de Castilla, nuez de la India, almendras, pistaches y pecanas. Precio: $650 MXN. Disponible.',             true, '2025-02-10 00:00:00', '2026-03-01 00:00:00'),
('Tremendo Mix Chocolate 1kg',        'Mezcla premium de nueces cubiertas con chocolate: almendras, pecanas, cacahuate y pasas chocolatadas. Bolsa de 1kg.',                                  520.00, 'MXN', 1000.0, 'GR',    NULL, '{"category": "mix", "flavor": "chocolate"}',                        'Tremendo Mix Chocolate 1kg: mezcla premium con almendras, pecanas, cacahuate y pasas cubiertos con chocolate. Bolsa de 1kg. Precio: $520 MXN. Disponible.',                true, '2025-03-01 00:00:00', '2026-03-01 00:00:00'),
('Tremendo Mix Enchilado 100g',       'Mezcla enchilada: nuez tostada, almendra, cacahuate español, arándano y mango deshidratado con chile. Presentación individual de 100g.',                65.00,  'MXN', 100.0,  'GR',    NULL, '{"category": "mix", "flavor": "enchilado", "size": "individual"}',  'Tremendo Mix Enchilado 100g: mezcla enchilada individual con nuez, almendra, cacahuate, arándano y mango deshidratado con chile. Precio: $65 MXN. Disponible.',            true, '2025-03-05 00:00:00', '2026-03-01 00:00:00'),
('Tremendo Mix Enchilado 1kg',        'Mezcla enchilada tamaño familiar: nuez, almendra, cacahuate español, arándano y mango deshidratado con chile. Bolsa de 1kg.',                           450.00, 'MXN', 1000.0, 'GR',    NULL, '{"category": "mix", "flavor": "enchilado", "size": "family"}',      'Tremendo Mix Enchilado 1kg: mezcla enchilada familiar con nuez, almendra, cacahuate, arándano y mango deshidratado con chile. Bolsa de 1kg. Precio: $450 MXN. Disponible.', true, '2025-03-05 00:00:00', '2026-03-01 00:00:00'),
('Nuez de Corazón 900g',              'Mitades enteras de nuez pecana de la Comarca Lagunera. 100% natural, sin sal ni aditivos. Bolsa de 900g.',                                             580.00, 'MXN', 900.0,  'GR',    NULL, '{"category": "nut", "type": "pecan_halves", "origin": "Comarca Lagunera"}', 'Nuez de Corazón 900g: mitades enteras de nuez pecana de la Comarca Lagunera, 100% natural. Bolsa de 900g. Precio: $580 MXN. Disponible.',                                true, '2025-03-10 00:00:00', '2026-03-01 00:00:00'),
('Nuez de la India 1kg',              'Nuez de la India (cashew) tostada. Ideal como snack o para cocinar. Bolsa de 1kg.',                                                                    620.00, 'MXN', 1000.0, 'GR',    NULL, '{"category": "nut", "type": "cashew"}',                             'Nuez de la India 1kg: cashews tostadas, ideales como snack o para cocinar. Bolsa de 1kg. Precio: $620 MXN. Disponible.',                                                   true, '2025-03-15 00:00:00', '2026-03-01 00:00:00'),
('Nuez Pedacería Extra Grande 900g',  'Pedacería de nuez pecana tamaño extra grande. Perfecta para repostería, postres y botana. Bolsa de 900g.',                                             480.00, 'MXN', 900.0,  'GR',    NULL, '{"category": "nut", "type": "pecan_pieces", "size": "XG"}',         'Nuez Pedacería Extra Grande 900g: pedacería de nuez pecana extra grande, ideal para repostería. Bolsa de 900g. Precio: $480 MXN. Disponible.',                             true, '2025-03-18 00:00:00', '2026-03-01 00:00:00'),
('Pistaches 1kg',                     'Pistaches con cáscara tostados y salados. 100% naturales. Bolsa de 1kg.',                                                                              750.00, 'MXN', 1000.0, 'GR',    NULL, '{"category": "nut", "type": "pistachio", "roasted": true, "salted": true}', 'Pistaches 1kg: pistaches con cáscara tostados y salados, 100% naturales. Bolsa de 1kg. Precio: $750 MXN. Disponible.',                                                  true, '2025-03-20 00:00:00', '2026-03-01 00:00:00');


-- ============================================================================
-- STOCKS (current inventory per store)
-- ============================================================================
INSERT INTO stocks (st_p_id, st_s_id, st_datetime, st_units, st_created_at, st_updated_at) VALUES
(1, 1, '2026-03-12 08:00:00', 120, '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(1, 2, '2026-03-12 08:00:00', 85,  '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(2, 1, '2026-03-12 08:00:00', 200, '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(2, 2, '2026-03-12 08:00:00', 150, '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(3, 1, '2026-03-12 08:00:00', 30,  '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(3, 2, '2026-03-12 08:00:00', 45,  '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(4, 1, '2026-03-12 08:00:00', 75,  '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(4, 2, '2026-03-12 08:00:00', 60,  '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(5, 1, '2026-03-12 08:00:00', 0,   '2026-03-12 08:00:00', '2026-03-12 08:00:00'),
(5, 2, '2026-03-12 08:00:00', 0,   '2026-03-12 08:00:00', '2026-03-12 08:00:00');


-- ============================================================================
-- SALES (history for analytics)
-- ============================================================================
INSERT INTO sales (sa_p_id, sa_s_id, sa_date, sa_units_sold, sa_created_at, sa_updated_at) VALUES
-- Arándano Enchilado (bestseller)
(1, 1, '2026-03-01', 15, '2026-03-01 23:00:00', '2026-03-01 23:00:00'),
(1, 1, '2026-03-05', 22, '2026-03-05 23:00:00', '2026-03-05 23:00:00'),
(1, 1, '2026-03-10', 18, '2026-03-10 23:00:00', '2026-03-10 23:00:00'),
(1, 2, '2026-03-01', 10, '2026-03-01 23:00:00', '2026-03-01 23:00:00'),
(1, 2, '2026-03-05', 14, '2026-03-05 23:00:00', '2026-03-05 23:00:00'),
-- Charola de Gomitas Enchiladas
(2, 1, '2026-03-02', 8,  '2026-03-02 23:00:00', '2026-03-02 23:00:00'),
(2, 1, '2026-03-08', 12, '2026-03-08 23:00:00', '2026-03-08 23:00:00'),
(2, 2, '2026-03-03', 6,  '2026-03-03 23:00:00', '2026-03-03 23:00:00'),
-- Charola de Nueces Surtidas
(3, 1, '2026-03-04', 3,  '2026-03-04 23:00:00', '2026-03-04 23:00:00'),
(3, 2, '2026-03-07', 5,  '2026-03-07 23:00:00', '2026-03-07 23:00:00'),
-- Tremendo Mix Chocolate 1kg
(4, 1, '2026-03-06', 10, '2026-03-06 23:00:00', '2026-03-06 23:00:00'),
(4, 2, '2026-03-09', 7,  '2026-03-09 23:00:00', '2026-03-09 23:00:00');


-- ============================================================================
-- ORDERS (varied statuses, edge cases)
-- ============================================================================
INSERT INTO orders (o_c_id, o_s_id, o_status, o_subtotal, o_discount_amount, o_shipping_amount, o_total, o_currency, o_payment_method, o_payment_status, o_customer_notes, o_internal_notes, o_estimated_delivery, o_delivered_at, o_cancelled_at, o_cancel_reason, o_created_at, o_updated_at) VALUES
-- Order 1: Delivered successfully (customer 1 - formal)
(1, 1, 'DELIVERED',   130.00, NULL,  50.00, 180.00, 'MXN', 'BANK_TRANSFER',    'COMPLETED', 'Por favor enviar factura al correo garcia.maria@email.com',   'Entrega sin problemas',       '2026-03-03 12:00:00', '2026-03-03 11:00:00', NULL, NULL, '2026-03-01 10:15:00', '2026-03-03 11:00:00'),
-- Order 2: Cancelled by customer (customer 2 - slang)
(2, 1, 'CANCELLED',   65.00,  NULL,  0.00,  65.00,  'MXN', 'CASH_ON_DELIVERY', 'CANCELLED', 'ahi al rato llego x el',                                      'Cliente no se presentó',      '2026-03-06 18:00:00', NULL,                  '2026-03-05 20:00:00', 'CUSTOMER_REQUEST', '2026-03-04 16:30:00', '2026-03-05 20:00:00'),
-- Order 3: Processing (customer 4 - ALL CAPS)
(4, 2, 'PROCESSING',  515.00, NULL,  50.00, 565.00, 'MXN', 'CREDIT_CARD',      'COMPLETED', 'NECESITO QUE LLEGUE ANTES DE LAS 3 PM!!!',                    NULL,                          '2026-03-13 15:00:00', NULL,                  NULL, NULL, '2026-03-11 09:45:00', '2026-03-11 14:00:00'),
-- Order 4: Pending payment (customer 6 - emoji)
(6, 1, 'PENDING',     650.00, NULL,  0.00,  650.00, 'MXN', 'MOBILE_PAYMENT',   'PENDING',   NULL,                                                           NULL,                          NULL,                  NULL,                  NULL, NULL, '2026-03-12 08:30:00', '2026-03-12 08:30:00'),
-- Order 5: Delivered with discount (customer 10 - english)
(10, 2, 'DELIVERED',  650.00, 65.00, 0.00,  585.00, 'MXN', 'CREDIT_CARD',      'COMPLETED', 'Can you include a gift note saying Happy Birthday Sofia?',     'Nota de regalo incluida',     '2026-03-08 14:00:00', '2026-03-08 12:30:00', NULL, NULL, '2026-03-06 11:00:00', '2026-03-08 12:30:00'),
-- Order 6: Out of stock cancellation (customer 8 - rude)
(8, 1, 'CANCELLED',   65.00,  NULL,  50.00, 115.00, 'MXN', 'DEBIT_CARD',       'REFUNDED',  'si no lo tienen para que lo ponen???',                         'Mix Enchilado 100g agotado, reembolso', '2026-03-10 10:00:00', NULL,         '2026-03-09 15:00:00', 'OUT_OF_STOCK',     '2026-03-09 08:00:00', '2026-03-09 15:00:00'),
-- Order 7: Shipped (customer 3 - typos)
(3, 1, 'SHIPPED',     65.00,  NULL,  50.00, 115.00, 'MXN', 'BANK_TRANSFER',    'COMPLETED', 'manden a la direcicon ke les di x fvr',                        NULL,                          '2026-03-14 12:00:00', NULL,                  NULL, NULL, '2026-03-11 07:20:00', '2026-03-12 06:00:00'),
-- Order 8: Large order, confirmed (customer 7 - elderly voice-note style)
(7, 2, 'CONFIRMED',   1230.00, NULL, 0.00,  1230.00,'MXN', 'CASH_ON_DELIVERY', 'PENDING',   'voy a ir a recogerlo a la tienda si se puede, si no me lo mandan a la casa azul', NULL, '2026-03-14 17:00:00', NULL, NULL, NULL, '2026-03-12 10:00:00', '2026-03-12 10:30:00'),
-- Order 9: Failed payment (customer 5 - minimal)
(5, 1, 'FAILED',      450.00, NULL,  50.00, 500.00, 'MXN', 'CREDIT_CARD',      'FAILED',    NULL,                                                           'Tarjeta declinada 2 veces',   NULL,                  NULL,                  NULL, NULL, '2026-03-10 19:00:00', '2026-03-10 19:05:00'),
-- Order 10: Refunded (customer 9 - confused elderly)
(9, 1, 'REFUNDED',    520.00, NULL,  50.00, 570.00, 'MXN', 'CASH_ON_DELIVERY', 'REFUNDED',  'creo que pedí el mix de chocolate pero no estoy segura',       'Abuelita confundida, se hizo reembolso completo por buena voluntad', '2026-03-07 10:00:00', '2026-03-07 09:00:00', NULL, NULL, '2026-03-05 08:00:00', '2026-03-07 12:00:00');


-- ============================================================================
-- ORDER ITEMS
-- ============================================================================
INSERT INTO orderitems (oi_o_id, oi_p_id, oi_units, oi_unit_price, oi_discount_amount, oi_created_at, oi_updated_at) VALUES
-- Order 1: 2x Arándano Enchilado
(1, 1, 2, 65.00,  NULL,  '2026-03-01 10:15:00', '2026-03-01 10:15:00'),
-- Order 2: 1x Arándano Enchilado (cancelled)
(2, 1, 1, 65.00,  NULL,  '2026-03-04 16:30:00', '2026-03-04 16:30:00'),
-- Order 3: 1x Arándano + 1x Charola Gomitas (CAPS customer)
(3, 1, 1, 65.00,  NULL,  '2026-03-11 09:45:00', '2026-03-11 09:45:00'),
(3, 2, 1, 450.00, NULL,  '2026-03-11 09:45:00', '2026-03-11 09:45:00'),
-- Order 4: 1x Charola de Nueces Surtidas
(4, 3, 1, 650.00, NULL,  '2026-03-12 08:30:00', '2026-03-12 08:30:00'),
-- Order 5: 1x Arándano + 1x Mix Chocolate + 1x Mix Enchilado (with 10% discount)
(5, 1, 1, 65.00,  6.50,  '2026-03-06 11:00:00', '2026-03-06 11:00:00'),
(5, 4, 1, 520.00, 52.00, '2026-03-06 11:00:00', '2026-03-06 11:00:00'),
(5, 5, 1, 65.00,  6.50,  '2026-03-06 11:00:00', '2026-03-06 11:00:00'),
-- Order 6: 1x Mix Enchilado 100g (out of stock)
(6, 5, 1, 65.00,  NULL,  '2026-03-09 08:00:00', '2026-03-09 08:00:00'),
-- Order 7: 1x Arándano Enchilado
(7, 1, 1, 65.00,  NULL,  '2026-03-11 07:20:00', '2026-03-11 07:20:00'),
-- Order 8: 2x Arándano + 1x Charola Nueces + 1x Charola Gomitas (big order from elderly)
(8, 1, 2, 65.00,  NULL,  '2026-03-12 10:00:00', '2026-03-12 10:00:00'),
(8, 3, 1, 650.00, NULL,  '2026-03-12 10:00:00', '2026-03-12 10:00:00'),
(8, 2, 1, 450.00, NULL,  '2026-03-12 10:00:00', '2026-03-12 10:00:00'),
-- Order 9: 1x Charola de Gomitas Enchiladas (payment failed)
(9, 2, 1, 450.00, NULL,  '2026-03-10 19:00:00', '2026-03-10 19:00:00'),
-- Order 10: 1x Tremendo Mix Chocolate 1kg (refunded)
(10, 4, 1, 520.00, NULL, '2026-03-05 08:00:00', '2026-03-05 08:00:00');


-- ============================================================================
-- ORDER STATUS HISTORY
-- ============================================================================
INSERT INTO orderstatushistory (osh_o_id, osh_status, osh_created_at, osh_updated_at) VALUES
-- Order 1 (delivered)
(1, 'PENDING',    '2026-03-01 10:15:00', '2026-03-01 10:15:00'),
(1, 'CONFIRMED',  '2026-03-01 10:30:00', '2026-03-01 10:30:00'),
(1, 'PROCESSING', '2026-03-02 08:00:00', '2026-03-02 08:00:00'),
(1, 'SHIPPED',    '2026-03-02 16:00:00', '2026-03-02 16:00:00'),
(1, 'DELIVERED',  '2026-03-03 11:00:00', '2026-03-03 11:00:00'),
-- Order 2 (cancelled)
(2, 'PENDING',    '2026-03-04 16:30:00', '2026-03-04 16:30:00'),
(2, 'CONFIRMED',  '2026-03-04 17:00:00', '2026-03-04 17:00:00'),
(2, 'CANCELLED',  '2026-03-05 20:00:00', '2026-03-05 20:00:00'),
-- Order 3 (processing)
(3, 'PENDING',    '2026-03-11 09:45:00', '2026-03-11 09:45:00'),
(3, 'CONFIRMED',  '2026-03-11 10:00:00', '2026-03-11 10:00:00'),
(3, 'PROCESSING', '2026-03-11 14:00:00', '2026-03-11 14:00:00'),
-- Order 4 (pending)
(4, 'PENDING',    '2026-03-12 08:30:00', '2026-03-12 08:30:00'),
-- Order 5 (delivered with discount)
(5, 'PENDING',    '2026-03-06 11:00:00', '2026-03-06 11:00:00'),
(5, 'CONFIRMED',  '2026-03-06 11:15:00', '2026-03-06 11:15:00'),
(5, 'PROCESSING', '2026-03-07 08:00:00', '2026-03-07 08:00:00'),
(5, 'SHIPPED',    '2026-03-07 14:00:00', '2026-03-07 14:00:00'),
(5, 'DELIVERED',  '2026-03-08 12:30:00', '2026-03-08 12:30:00'),
-- Order 6 (cancelled - out of stock)
(6, 'PENDING',    '2026-03-09 08:00:00', '2026-03-09 08:00:00'),
(6, 'CANCELLED',  '2026-03-09 15:00:00', '2026-03-09 15:00:00'),
-- Order 7 (shipped)
(7, 'PENDING',    '2026-03-11 07:20:00', '2026-03-11 07:20:00'),
(7, 'CONFIRMED',  '2026-03-11 07:45:00', '2026-03-11 07:45:00'),
(7, 'PROCESSING', '2026-03-11 15:00:00', '2026-03-11 15:00:00'),
(7, 'SHIPPED',    '2026-03-12 06:00:00', '2026-03-12 06:00:00'),
-- Order 8 (confirmed)
(8, 'PENDING',    '2026-03-12 10:00:00', '2026-03-12 10:00:00'),
(8, 'CONFIRMED',  '2026-03-12 10:30:00', '2026-03-12 10:30:00'),
-- Order 9 (failed)
(9, 'PENDING',    '2026-03-10 19:00:00', '2026-03-10 19:00:00'),
(9, 'FAILED',     '2026-03-10 19:05:00', '2026-03-10 19:05:00'),
-- Order 10 (refunded)
(10, 'PENDING',   '2026-03-05 08:00:00', '2026-03-05 08:00:00'),
(10, 'CONFIRMED', '2026-03-05 08:30:00', '2026-03-05 08:30:00'),
(10, 'DELIVERED', '2026-03-07 09:00:00', '2026-03-07 09:00:00'),
(10, 'REFUNDED',  '2026-03-07 12:00:00', '2026-03-07 12:00:00');


-- ============================================================================
-- MESSAGE TEMPLATES
-- ============================================================================
INSERT INTO messagetemplates (mt_name, mt_content, mt_created_at, mt_updated_at) VALUES
('welcome',         'Hola {{1}} 👋 ¡Bienvenido a Tremenda Nuez! Soy tu asistente virtual. ¿En qué te puedo ayudar hoy?',                       '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('order_confirmed', 'Hola {{1}}, tu pedido ha sido confirmado ✅. Te notificaremos cuando esté en camino.',                                     '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('order_shipped',   'Hola {{1}}, tu pedido ya está en camino 🚚. Estimamos que llegará el {{2}}.',                                              '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('order_delivered', 'Hola {{1}}, tu pedido ha sido entregado 📦✅. ¡Gracias por comprar en Tremenda Nuez! ¿Necesitas algo más?',                 '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('order_cancelled', 'Hola {{1}}, tu pedido ha sido cancelado. Motivo: {{2}}. Si tienes dudas, escríbenos.',                                     '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('payment_reminder','Hola {{1}}, tu pedido está pendiente de pago. Puedes pagar por {{2}}. Si ya pagaste, envíanos tu comprobante 🧾.',         '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('promo_general',   '🎉 ¡Hola {{1}}! Tenemos promociones especiales esta semana. Escríbenos para conocer nuestros descuentos.',                 '2025-01-01 00:00:00', '2025-01-01 00:00:00');


-- ============================================================================
-- FAQ ITEMS
-- ============================================================================
INSERT INTO faqitems (faq_category, faq_question, faq_answer, faq_keywords, faq_display_order, faq_view_count, faq_is_active, faq_created_at, faq_updated_at) VALUES
('ORDERS',    '¿Cómo hago un pedido?',                     'Puedes hacer tu pedido directamente por WhatsApp. Solo dime qué productos te interesan y yo te guío paso a paso para completar tu compra.',                           '["pedido", "ordenar", "comprar", "pedir"]',                   1, 45, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('ORDERS',    '¿Puedo cancelar mi pedido?',                 'Sí, puedes cancelar tu pedido siempre y cuando no haya sido enviado. Solo escríbeme y lo cancelamos.',                                                              '["cancelar", "cancelación", "anular"]',                       2, 30, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('SHIPPING',  '¿Cuánto tarda el envío?',                    'Los envíos dentro de CDMX tardan de 1 a 3 días hábiles. Para recoger en tienda, puedes pasar el mismo día después de la confirmación.',                             '["envío", "entrega", "cuánto tarda", "días"]',                1, 55, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('SHIPPING',  '¿Cuánto cuesta el envío?',                   'El envío tiene un costo de $50 MXN dentro de CDMX. Si tu pedido es mayor a $500 MXN, el envío es gratis. También puedes recoger gratis en tienda.',                '["costo envío", "precio envío", "shipping"]',                 2, 40, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('PAYMENTS',  '¿Qué métodos de pago aceptan?',              'Aceptamos transferencia bancaria, tarjeta de crédito/débito, pago móvil y pago contra entrega en efectivo.',                                                       '["pago", "pagar", "tarjeta", "transferencia", "efectivo"]',   1, 35, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('RETURNS',   '¿Puedo devolver un producto?',               'Sí, aceptamos devoluciones dentro de los 7 días posteriores a la entrega si el producto está sin abrir. Contáctanos para iniciar el proceso.',                     '["devolución", "devolver", "regresar", "reembolso"]',         1, 20, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('PRODUCTS',  '¿Los productos son artesanales?',            'Sí, todos nuestros productos son artesanales y de origen mexicano. Trabajamos directamente con productores locales de Oaxaca, Tabasco y otras regiones.',           '["artesanal", "natural", "orgánico", "origen"]',              1, 25, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('GENERAL',   '¿Cuál es el horario de atención?',           'Nuestro bot está disponible 24/7. Para atención con un humano, nuestro horario es de lunes a viernes de 9am a 6pm.',                                               '["horario", "hora", "atención", "abierto"]',                  1, 50, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('PROMOTIONS','¿Tienen descuentos o promociones?',          'Tenemos promociones frecuentes. Actualmente ofrecemos envío gratis en compras mayores a $500 MXN. Pregúntame por promociones vigentes.',                            '["descuento", "promo", "promoción", "oferta"]',               1, 38, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00'),
('ACCOUNT',   '¿Cómo actualizo mi dirección de entrega?',   'Solo envíame tu nueva dirección o comparte tu ubicación en tiempo real por WhatsApp y la actualizo en tu perfil.',                                                 '["dirección", "ubicación", "cambiar dirección"]',             1, 15, true, '2025-01-01 00:00:00', '2026-03-01 00:00:00');


-- ============================================================================
-- MESSAGES (comprehensive test data, ~120+ messages)
-- Each customer has a distinct typing personality
-- Edge cases: empty-ish messages, rapid fire, typos, mixed languages,
--   emojis, asking for unavailable products, wrong context, confusion,
--   complaints, status checks, multi-turn conversations
-- ============================================================================

-- --------------------------------------------------------------------------
-- CUSTOMER 1: María García (formal, polite, proper grammar)
-- Scenario: browses products → places order → asks for invoice → checks status → happy with delivery
-- --------------------------------------------------------------------------
INSERT INTO messages (m_c_id, m_direction, m_type, m_content, m_status, m_context_message_id, m_error_code, m_error_message, m_created_at) VALUES
(1, 'INBOUND',  'TEXT', 'Buenos días, me gustaría conocer su catálogo de productos, por favor.',                                  'READ',      NULL, NULL, NULL, '2026-03-01 09:00:00'),
(1, 'OUTBOUND', 'TEXT', 'Hola María 👋 ¡Bienvenida a Tremenda Nuez! Con gusto te comparto nuestro catálogo. Tenemos: 1) Arándano Enchilado 100g ($65), 2) Charola de Gomitas Enchiladas ($450), 3) Charola de Nueces Surtidas ($650), 4) Tremendo Mix Chocolate 1kg ($520). ¿Alguno te interesa?', 'DELIVERED', NULL, NULL, NULL, '2026-03-01 09:01:00'),
(1, 'INBOUND',  'TEXT', 'Muchas gracias. Me interesan 2 bolsitas de Arándano Enchilado, por favor. ¿Hacen envío a la colonia Centro?', 'READ',      NULL, NULL, NULL, '2026-03-01 09:05:00'),
(1, 'OUTBOUND', 'TEXT', '¡Claro que sí! 2 bolsitas de Arándano Enchilado: $130.00 MXN + $50 envío = $180.00 total. Hacemos envío a Centro. ¿Deseas confirmar tu pedido?', 'DELIVERED', NULL, NULL, NULL, '2026-03-01 09:06:00'),
(1, 'INBOUND',  'TEXT', 'Sí, por favor confírmelo. Pagaré por transferencia bancaria. ¿Me puede proporcionar los datos?',        'READ',      NULL, NULL, NULL, '2026-03-01 10:10:00'),
(1, 'OUTBOUND', 'TEXT', 'Tu pedido ha sido registrado ✅. Datos para transferencia: Banco XYZ, Cuenta: 1234567890, CLABE: 012345678901234567. Una vez que realices el pago, envíanos tu comprobante.', 'DELIVERED', NULL, NULL, NULL, '2026-03-01 10:12:00'),
(1, 'INBOUND',  'IMAGE', NULL,                                                                                                     'READ',      NULL, NULL, NULL, '2026-03-01 10:30:00'),
(1, 'OUTBOUND', 'TEXT', 'Comprobante recibido ✅. Tu pago ha sido verificado. Tu pedido será enviado mañana. Estimamos entrega para el 3 de marzo.', 'DELIVERED', NULL, NULL, NULL, '2026-03-01 10:35:00'),
(1, 'INBOUND',  'TEXT', 'Perfecto, muchas gracias. Una pregunta adicional: ¿es posible solicitar factura?',                       'READ',      NULL, NULL, NULL, '2026-03-01 10:40:00'),
(1, 'OUTBOUND', 'TEXT', '¡Por supuesto! Envíanos tus datos fiscales (RFC, razón social, correo y uso de CFDI) y te la generamos.', 'DELIVERED', NULL, NULL, NULL, '2026-03-01 10:41:00'),
(1, 'INBOUND',  'TEXT', 'Mi RFC es GALM900101ABC, razón social María García López, correo garcia.maria@email.com, uso CFDI: Gastos en general.', 'READ', NULL, NULL, NULL, '2026-03-01 10:50:00'),
(1, 'OUTBOUND', 'TEXT', 'Datos recibidos. Tu factura será enviada a garcia.maria@email.com una vez entregado el pedido. 📧',       'DELIVERED', NULL, NULL, NULL, '2026-03-01 10:52:00'),
(1, 'INBOUND',  'TEXT', '¿Podrían indicarme el estatus de mi pedido? Ya pasaron 2 días.',                                         'READ',      NULL, NULL, NULL, '2026-03-03 08:00:00'),
(1, 'OUTBOUND', 'TEXT', 'Tu pedido está en camino 🚚. El repartidor estará llegando hoy entre 10am y 12pm. ¿Hay alguien en casa para recibirlo?', 'DELIVERED', NULL, NULL, NULL, '2026-03-03 08:02:00'),
(1, 'INBOUND',  'TEXT', 'Sí, estaré en casa toda la mañana. Muchas gracias por la atención.',                                     'READ',      NULL, NULL, NULL, '2026-03-03 08:05:00'),
(1, 'INBOUND',  'TEXT', 'Ya recibí mi pedido. Todo en perfecto estado. ¡Riquísimos los arándanos enchilados! Felicidades por la calidad. Muy agradecida.', 'READ',   NULL, NULL, NULL, '2026-03-03 11:30:00'),
(1, 'OUTBOUND', 'TEXT', '¡Nos da mucho gusto, María! 😊 Gracias por tu compra y tus bonitas palabras. ¡Esperamos verte pronto por aquí!', 'DELIVERED', NULL, NULL, NULL, '2026-03-03 11:32:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 2: El Brayan (chilango slang, abbreviations, no punctuation)
-- Scenario: wants cheap stuff → argues about price → cancels → comes back later
-- --------------------------------------------------------------------------
(2, 'INBOUND',  'TEXT', 'q onda we q tienen d bueno',                                                                              'READ',      NULL, NULL, NULL, '2026-03-04 15:00:00'),
(2, 'OUTBOUND', 'TEXT', 'Hola 👋 ¡Bienvenido a Tremenda Nuez! Tenemos arándanos enchilados, mixes con chocolate, charolas de regalo, pistaches y más. ¿Qué se te antoja?', 'DELIVERED', NULL, NULL, NULL, '2026-03-04 15:01:00'),
(2, 'INBOUND',  'TEXT', 'nel we eso ta bien caro no tienen algo mas barato',                                                       'READ',      NULL, NULL, NULL, '2026-03-04 15:03:00'),
(2, 'INBOUND',  'TEXT', 'osea si m interesa el arandano enchilado pero 65 varos x una bolsita nmmss',                              'READ',      NULL, NULL, NULL, '2026-03-04 15:03:30'),
(2, 'OUTBOUND', 'TEXT', 'Entiendo. El arándano es 100% natural, deshidratado y cubierto con chile. La bolsita es de 100g y está rendidora. ¿Te gustaría probarlo?', 'DELIVERED', NULL, NULL, NULL, '2026-03-04 15:04:00'),
(2, 'INBOUND',  'TEXT', 'va pues mandame uno a ver si ta chido',                                                                    'READ',      NULL, NULL, NULL, '2026-03-04 16:25:00'),
(2, 'OUTBOUND', 'TEXT', '¡Sale! 1 Arándano Enchilado: $65 MXN. ¿Pago contra entrega o transferencia?',                              'DELIVERED', NULL, NULL, NULL, '2026-03-04 16:26:00'),
(2, 'INBOUND',  'TEXT', 'contra entrega we no confio en las transferencias jaja',                                                   'READ',      NULL, NULL, NULL, '2026-03-04 16:28:00'),
(2, 'OUTBOUND', 'TEXT', 'Listo, pedido registrado. Envío mañana. ¿La dirección del estanquillo de la esquina sigue siendo la correcta?', 'DELIVERED', NULL, NULL, NULL, '2026-03-04 16:30:00'),
(2, 'INBOUND',  'TEXT', 'si ahi mero',                                                                                              'READ',      NULL, NULL, NULL, '2026-03-04 16:31:00'),
(2, 'INBOUND',  'TEXT', 'oie sabes q ya no lo quiero cancela',                                                                      'READ',      NULL, NULL, NULL, '2026-03-05 19:50:00'),
(2, 'OUTBOUND', 'TEXT', 'Listo, tu pedido ha sido cancelado. Si cambias de opinión, aquí estamos. 👋',                               'DELIVERED', NULL, NULL, NULL, '2026-03-05 20:00:00'),
(2, 'INBOUND',  'TEXT', 'sii es q luego luego ps no tengo feria ahorita jajaja al rato compro',                                     'READ',      NULL, NULL, NULL, '2026-03-05 20:02:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 3: Robeto Hdez (lots of typos, misspellings, fast typing)
-- Scenario: orders arándano → asks about delivery → provides wrong info then corrects
-- --------------------------------------------------------------------------
(3, 'INBOUND',  'TEXT', 'ola buen dia, quisera pedir un arandano enchilado porfavor',                                              'READ',      NULL, NULL, NULL, '2026-03-11 07:00:00'),
(3, 'OUTBOUND', 'TEXT', 'Hola 👋 ¡Buenos días! Claro, tenemos el Arándano Enchilado a $65 MXN (bolsita de 100g). ¿Lo pedimos?',     'DELIVERED', NULL, NULL, NULL, '2026-03-11 07:01:00'),
(3, 'INBOUND',  'TEXT', 'si mandamelo porfas cuqnto cuesta el enbio??',                                                            'READ',      NULL, NULL, NULL, '2026-03-11 07:05:00'),
(3, 'OUTBOUND', 'TEXT', 'El envío dentro de CDMX es de $50 MXN. Total: $115 MXN. ¿A qué dirección lo enviamos?',                   'DELIVERED', NULL, NULL, NULL, '2026-03-11 07:06:00'),
(3, 'INBOUND',  'TEXT', 'a mi casa en iztacalco',                                                                                   'READ',      NULL, NULL, NULL, '2026-03-11 07:08:00'),
(3, 'OUTBOUND', 'TEXT', '¿Nos puedes dar la dirección completa? Calle, número, colonia y CP.',                                      'DELIVERED', NULL, NULL, NULL, '2026-03-11 07:09:00'),
(3, 'INBOUND',  'TEXT', 'calle rio frio 23 col agircola orientl cp 08500',                                                          'READ',      NULL, NULL, NULL, '2026-03-11 07:12:00'),
(3, 'INBOUND',  'TEXT', 'perdon es el 32 no 23 me ekivoque',                                                                       'READ',      NULL, NULL, NULL, '2026-03-11 07:12:30'),
(3, 'OUTBOUND', 'TEXT', 'Sin problema 👍. Confirmado: Calle Río Frío 32, Col. Agrícola Oriental, CP 08500. ¿Método de pago?',       'DELIVERED', NULL, NULL, NULL, '2026-03-11 07:13:00'),
(3, 'INBOUND',  'TEXT', 'tranferencia pro favor',                                                                                   'READ',      NULL, NULL, NULL, '2026-03-11 07:15:00'),
(3, 'OUTBOUND', 'TEXT', 'Datos: Banco XYZ, CLABE: 012345678901234567. Total: $115 MXN. Envíanos el comprobante cuando pagues.',     'DELIVERED', NULL, NULL, NULL, '2026-03-11 07:16:00'),
(3, 'INBOUND',  'IMAGE', NULL,                                                                                                      'READ',      NULL, NULL, NULL, '2026-03-11 07:30:00'),
(3, 'OUTBOUND', 'TEXT', 'Pago recibido ✅. Tu pedido será enviado hoy. ¡Gracias Roberto!',                                          'DELIVERED', NULL, NULL, NULL, '2026-03-11 07:45:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 4: LUPITA MARTINEZ (ALL CAPS, exclamation marks, demands)
-- Scenario: orders aggressively → complains about time → demands tracking
-- --------------------------------------------------------------------------
(4, 'INBOUND',  'TEXT', 'HOLA QUIERO COMPRAR EL ARANDANO ENCHILADO Y UNA CHAROLA DE GOMITAS CUANTO CUESTA',                       'READ',      NULL, NULL, NULL, '2026-03-11 09:30:00'),
(4, 'OUTBOUND', 'TEXT', 'Hola Lupita 👋 ¡El Arándano Enchilado: $65 MXN y la Charola de Gomitas Enchiladas: $450 MXN. ¿Los dos?',  'DELIVERED', NULL, NULL, NULL, '2026-03-11 09:31:00'),
(4, 'INBOUND',  'TEXT', 'SI LOS DOS!! Y QUE LLEGUE RAPIDO POR FAVOR NECESITO QUE LLEGUE ANTES DE LAS 3!!!',                       'READ',      NULL, NULL, NULL, '2026-03-11 09:33:00'),
(4, 'OUTBOUND', 'TEXT', '1 Arándano + 1 Charola Gomitas = $515 + $50 envío = $565. ¿Tienda Centro o Condesa? ¿Forma de pago?',     'DELIVERED', NULL, NULL, NULL, '2026-03-11 09:34:00'),
(4, 'INBOUND',  'TEXT', 'CONDESA Y CON TARJETA DE CREDITO',                                                                        'READ',      NULL, NULL, NULL, '2026-03-11 09:35:00'),
(4, 'OUTBOUND', 'TEXT', 'Perfecto, te enviaré el link de pago por aquí. Un momento.',                                               'DELIVERED', NULL, NULL, NULL, '2026-03-11 09:36:00'),
(4, 'OUTBOUND', 'INTERACTIVE', NULL,                                                                                                 'DELIVERED', NULL, NULL, NULL, '2026-03-11 09:37:00'),
(4, 'INBOUND',  'TEXT', 'YA PAGUE!! CUANDO LLEGA?? NECESITO CONFIRMACION',                                                         'READ',      NULL, NULL, NULL, '2026-03-11 09:45:00'),
(4, 'OUTBOUND', 'TEXT', 'Pago confirmado ✅. Tu pedido está siendo preparado. Estimamos entrega hoy entre 1pm y 3pm.',               'DELIVERED', NULL, NULL, NULL, '2026-03-11 09:46:00'),
(4, 'INBOUND',  'TEXT', 'YA SON LAS 2 Y NO LLEGA NADA!!! DONDE ESTA MI PEDIDO???',                                                 'READ',      NULL, NULL, NULL, '2026-03-11 14:00:00'),
(4, 'OUTBOUND', 'TEXT', 'Tu pedido está en preparación. Recuerda que el horario estimado era hasta las 3pm. Te mantenemos informada.', 'DELIVERED', NULL, NULL, NULL, '2026-03-11 14:02:00'),
(4, 'INBOUND',  'TEXT', 'QUIERO NUMERO DE RASTREO O ALGO QUE DIGA QUE YA VA EN CAMINO!!!',                                         'READ',      NULL, NULL, NULL, '2026-03-11 14:30:00'),
(4, 'OUTBOUND', 'TEXT', 'Entiendo tu preocupación. Tu pedido acaba de salir de la tienda. El repartidor llegará pronto. Te avisaremos en cuanto esté por llegar. 🚚', 'DELIVERED', NULL, NULL, NULL, '2026-03-11 14:32:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 5: Juan (minimal responses, monosyllabic)
-- Scenario: tries to buy → payment fails → gives up
-- --------------------------------------------------------------------------
(5, 'INBOUND',  'TEXT', 'hola',                                                                                                    'READ',      NULL, NULL, NULL, '2026-03-10 18:50:00'),
(5, 'OUTBOUND', 'TEXT', 'Hola 👋 ¡Bienvenido a Tremenda Nuez! ¿En qué te puedo ayudar?',                                           'DELIVERED', NULL, NULL, NULL, '2026-03-10 18:51:00'),
(5, 'INBOUND',  'TEXT', 'gomitas',                                                                                                  'READ',      NULL, NULL, NULL, '2026-03-10 18:52:00'),
(5, 'OUTBOUND', 'TEXT', '¿Te interesa la Charola de Gomitas Enchiladas? Son $450 MXN. ¿La pedimos?',                                'DELIVERED', NULL, NULL, NULL, '2026-03-10 18:53:00'),
(5, 'INBOUND',  'TEXT', 'si',                                                                                                       'READ',      NULL, NULL, NULL, '2026-03-10 18:54:00'),
(5, 'OUTBOUND', 'TEXT', '¿Envío ($50 MXN) o recoges en tienda?',                                                                   'DELIVERED', NULL, NULL, NULL, '2026-03-10 18:55:00'),
(5, 'INBOUND',  'TEXT', 'envio',                                                                                                    'READ',      NULL, NULL, NULL, '2026-03-10 18:56:00'),
(5, 'OUTBOUND', 'TEXT', 'Total: $500 MXN. ¿Forma de pago?',                                                                        'DELIVERED', NULL, NULL, NULL, '2026-03-10 18:57:00'),
(5, 'INBOUND',  'TEXT', 'tarjeta',                                                                                                  'READ',      NULL, NULL, NULL, '2026-03-10 18:58:00'),
(5, 'OUTBOUND', 'INTERACTIVE', NULL,                                                                                                 'DELIVERED', NULL, NULL, NULL, '2026-03-10 18:59:00'),
(5, 'OUTBOUND', 'TEXT', 'Tu pago no pudo ser procesado. ¿Deseas intentar con otra tarjeta o método de pago?',                       'DELIVERED', NULL, NULL, NULL, '2026-03-10 19:03:00'),
(5, 'INBOUND',  'TEXT', 'no',                                                                                                       'READ',      NULL, NULL, NULL, '2026-03-10 19:04:00'),
(5, 'OUTBOUND', 'TEXT', 'Entendido. Tu pedido ha sido cancelado. Si deseas intentar después, estamos aquí. 👋',                      'DELIVERED', NULL, NULL, NULL, '2026-03-10 19:05:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 6: Sofía Ramírez ✨ (emoji-heavy, affectionate, uses lots of stickers)
-- Scenario: wants gift tray → navigates product → places order → pending payment
-- --------------------------------------------------------------------------
(6, 'INBOUND',  'TEXT', 'holaaaa 💕✨ tienen charolas de regalo?? 🎁',                                                            'READ',      NULL, NULL, NULL, '2026-03-12 08:00:00'),
(6, 'OUTBOUND', 'TEXT', '¡Hola Sofi! 🌟 Sí, tenemos la Charola de Nueces Surtidas a $650 MXN. Trae nuez de Castilla, nuez de la India, almendras, pistaches y pecanas, presentación elegante con listón. ¿Te interesa?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 08:01:00'),
(6, 'INBOUND',  'STICKER', NULL,                                                                                                    'READ',      NULL, NULL, NULL, '2026-03-12 08:02:00'),
(6, 'INBOUND',  'TEXT', 'siiiii la quierooo 😍🤩 es para un regalito',                                                             'READ',      NULL, NULL, NULL, '2026-03-12 08:02:30'),
(6, 'OUTBOUND', 'TEXT', '¡Qué lindo regalo! 🎁 1 Charola de Nueces Surtidas = $650 MXN. Envío $50 o recoges gratis en tienda. ¿Qué prefieres?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 08:03:00'),
(6, 'INBOUND',  'TEXT', 'recojo en tienda 🏃‍♀️ en cual esta?',                                                                    'READ',      NULL, NULL, NULL, '2026-03-12 08:04:00'),
(6, 'OUTBOUND', 'TEXT', 'Tenemos dos tiendas:\n1️⃣ Tremenda Nuez Centro - Calle Madero 42 (9am-9pm)\n2️⃣ Tremenda Nuez Condesa - Av. Tamaulipas 78 (8am-10pm)\n¿Cuál te queda mejor?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 08:05:00'),
(6, 'INBOUND',  'TEXT', 'la del centro porfa 💖',                                                                                  'READ',      NULL, NULL, NULL, '2026-03-12 08:06:00'),
(6, 'OUTBOUND', 'TEXT', 'Pedido registrado: 1 Charola de Nueces Surtidas, recoger en Tremenda Nuez Centro. Total: $650 MXN. ¿Pagas por transferencia o en tienda?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 08:07:00'),
(6, 'INBOUND',  'TEXT', 'transfiero ahorita ✨ pasa los datos 🙏🏼',                                                               'READ',      NULL, NULL, NULL, '2026-03-12 08:08:00'),
(6, 'OUTBOUND', 'TEXT', 'Banco XYZ, CLABE: 012345678901234567. Total: $650 MXN. Cuando transfieras, envíanos el comprobante 🧾',    'DELIVERED', NULL, NULL, NULL, '2026-03-12 08:10:00'),
(6, 'INBOUND',  'TEXT', 'ayyy espera no encuentro mi app del banco 😭 al rato te mando el comprobante siii? 🙈',                   'READ',      NULL, NULL, NULL, '2026-03-12 08:25:00'),
(6, 'OUTBOUND', 'TEXT', '¡Claro, sin prisas! Tu pedido queda apartado. Solo envíanos el comprobante cuando puedas. 😊',              'DELIVERED', NULL, NULL, NULL, '2026-03-12 08:27:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 7: Don Arturo (elderly, long voice-note style, tells stories, confused about tech)
-- Scenario: wants to buy gifts for family → big order → asks many questions → picks up in store
-- --------------------------------------------------------------------------
(7, 'INBOUND',  'TEXT', 'Buenos días disculpe la molestia es que quiero preguntar si ustedes venden nueces porque mi hija me dijo que aquí vendían unas nueces muy buenas de la Comarca Lagunera y quiero comprar para mi familia que viene de visita el próximo fin de semana', 'READ', NULL, NULL, NULL, '2026-03-12 09:30:00'),
(7, 'OUTBOUND', 'TEXT', '¡Buenos días Don Arturo! No es ninguna molestia 😊. Sí, manejamos varias opciones. Tenemos el Arándano Enchilado a $65 MXN (100g) como botanita y la Charola de Nueces Surtidas a $650 MXN con nuez de Castilla, nuez de la India, almendras, pistaches y pecanas. ¿Qué le parece?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 09:32:00'),
(7, 'INBOUND',  'TEXT', 'Ay que bueno mira es que somos como 8 en la familia entonces quiero llevar suficiente y también me dijo mi nieta que tienen una charola de gomitas enchiladas que está muy rica para los nietos pero no sé si me alcance', 'READ', NULL, NULL, NULL, '2026-03-12 09:40:00'),
(7, 'OUTBOUND', 'TEXT', 'Para 8 personas le recomiendo: 2 bolsitas de Arándano Enchilado ($130) como botanita para todos, la Charola de Nueces Surtidas ($650) como centro de mesa y la Charola de Gomitas Enchiladas ($450) para los nietos. ¿Le armo el paquetito?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 09:42:00'),
(7, 'INBOUND',  'TEXT', 'Sí por favor póngame las 2 bolsitas de arándano la charola de nueces y la de gomitas para los nietos que les encantan las gomitas enchiladas entonces cuánto sería todo', 'READ', NULL, NULL, NULL, '2026-03-12 09:50:00'),
(7, 'OUTBOUND', 'TEXT', 'Su pedido:\n- 2x Arándano Enchilado: $130.00\n- 1x Charola de Nueces Surtidas: $650.00\n- 1x Charola de Gomitas Enchiladas: $450.00\n\nSubtotal: $1,230.00\nEnvío gratis (compra mayor a $500)\nTotal: $1,230.00 MXN\n\n¿Se lo enviamos o pasa a recoger?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 09:52:00'),
(7, 'INBOUND',  'TEXT', 'Mejor paso a recogerlo pero no sé cómo llegar a su tienda me puede mandar la dirección es que no sé usar muy bien el Google Maps mi nieta me ayuda pero ahorita no está', 'READ', NULL, NULL, NULL, '2026-03-12 09:55:00'),
(7, 'OUTBOUND', 'LOCATION', NULL,                                                                                                   'DELIVERED', NULL, NULL, NULL, '2026-03-12 09:56:00'),
(7, 'OUTBOUND', 'TEXT', 'Nuestra tienda Tremenda Nuez Condesa está en Av. Tamaulipas 78, Condesa. Se la comparto en el mapa de arriba. Es fácil de encontrar, está al lado de un OXXO. Horario: 8am a 10pm.', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 09:57:00'),
(7, 'INBOUND',  'TEXT', 'Ah ok sí creo que sé dónde es voy a ir mañana por la tarde y pago allá en la tienda se puede verdad pagar con efectivo ahí', 'READ', NULL, NULL, NULL, '2026-03-12 10:00:00'),
(7, 'OUTBOUND', 'TEXT', 'Sí, puede pagar en efectivo en la tienda sin problema. Su pedido estará listo para recoger mañana. Solo dé su nombre: Arturo Mendoza. ¡Lo esperamos! 😊', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 10:02:00'),
(7, 'INBOUND',  'TEXT', 'Muchas gracias jovencita que amable perdón por tantas preguntas es que ya estoy grande y estas cosas de la tecnología se me complican jaja pero muchas gracias', 'READ', NULL, NULL, NULL, '2026-03-12 10:05:00'),
(7, 'OUTBOUND', 'TEXT', 'No se preocupe Don Arturo, para eso estamos 🤗. ¡Lo esperamos mañana!',                                   'DELIVERED', NULL, NULL, NULL, '2026-03-12 10:06:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 8: Karen Vega (rude, impatient, threatens to cancel, complains)
-- Scenario: wants mix enchilado → out of stock → gets angry → demands refund → threatens bad review
-- --------------------------------------------------------------------------
(8, 'INBOUND',  'TEXT', 'oigan tienen el mix enchilado de 100g? lo vi en instagram',                                                'READ',      NULL, NULL, NULL, '2026-03-09 07:30:00'),
(8, 'OUTBOUND', 'TEXT', 'Hola Karen 👋 ¿Te refieres al Tremendo Mix Enchilado 100g? Lamentablemente está agotado por el momento, se nos acabó muy rápido.', 'DELIVERED', NULL, NULL, NULL, '2026-03-09 07:32:00'),
(8, 'INBOUND',  'TEXT', 'como que agotado si lo acaban de publicar?? lo quiero',                                                    'READ',      NULL, NULL, NULL, '2026-03-09 07:33:00'),
(8, 'OUTBOUND', 'TEXT', 'Sí, es nuestro snack más vendido y se agotó muy rápido. Puedo anotarte en la lista de espera para cuando tengamos nueva producción.', 'DELIVERED', NULL, NULL, NULL, '2026-03-09 07:34:00'),
(8, 'INBOUND',  'TEXT', 'no mms que mala onda, para q lo publican si no lo tienen',                                                 'READ',      NULL, NULL, NULL, '2026-03-09 07:35:00'),
(8, 'INBOUND',  'TEXT', 'ok ya vamonos ponme uno y cuando lo tengan me lo envían',                                                  'READ',      NULL, NULL, NULL, '2026-03-09 07:50:00'),
(8, 'OUTBOUND', 'TEXT', 'Entendido, te anotamos en lista de espera. Si te interesa algo más de nuestro catálogo mientras tanto, con gusto te ayudo.', 'DELIVERED', NULL, NULL, NULL, '2026-03-09 07:52:00'),
(8, 'INBOUND',  'TEXT', 'no nada mas el mix enchilado quiero. y cuanto tarda? porque si es mucho mejor me olvido',                  'READ',      NULL, NULL, NULL, '2026-03-09 07:53:00'),
(8, 'OUTBOUND', 'TEXT', 'Estamos preparando la nueva producción. Estimamos que en 2-3 semanas podríamos tener disponibilidad. Te avisamos por aquí.', 'DELIVERED', NULL, NULL, NULL, '2026-03-09 07:55:00'),
(8, 'INBOUND',  'TEXT', 'ok pues. si tardan mucho les pongo 1 estrella en google',                                                  'READ',      NULL, NULL, NULL, '2026-03-09 07:56:00'),
(8, 'OUTBOUND', 'TEXT', 'Entendemos tu frustración, Karen. Haremos lo posible por tenerlo pronto. Te mantenemos informada. 🙏',      'DELIVERED', NULL, NULL, NULL, '2026-03-09 07:58:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 9: Abuelita Concha (confused, repeats herself, wrong context, tech struggles)
-- Scenario: wants mix chocolate → doesn't understand how to pay → orders → asks for refund
-- --------------------------------------------------------------------------
(9, 'INBOUND',  'TEXT', 'Hola? Hola buenas tardes se oye? Es que no sé si se mandó el mensaje',                                    'READ',      NULL, NULL, NULL, '2026-03-05 07:00:00'),
(9, 'OUTBOUND', 'TEXT', '¡Hola! Sí se manda, Conchita 😊. Este es un chat de texto. ¿En qué le puedo ayudar?',                     'DELIVERED', NULL, NULL, NULL, '2026-03-05 07:01:00'),
(9, 'INBOUND',  'TEXT', 'Ay que bueno es que mi nieto me dijo que le escribiera aquí para comprar un mix de chocolate que está muy bueno', 'READ',  NULL, NULL, NULL, '2026-03-05 07:05:00'),
(9, 'INBOUND',  'TEXT', 'Hola? Siguen ahí?',                                                                                       'READ',      NULL, NULL, NULL, '2026-03-05 07:06:00'),
(9, 'OUTBOUND', 'TEXT', 'Sí aquí seguimos 😊. Tenemos el Tremendo Mix Chocolate 1kg a $520 MXN. Trae almendras, pecanas, cacahuate y pasas cubiertos con chocolate. ¿Se lo pedimos?', 'DELIVERED', NULL, NULL, NULL, '2026-03-05 07:07:00'),
(9, 'INBOUND',  'TEXT', 'Sí esos meros pero cómo le hago para pagar es que no tengo de esas aplicaciones del banco',                'READ',      NULL, NULL, NULL, '2026-03-05 07:10:00'),
(9, 'OUTBOUND', 'TEXT', 'No se preocupe, puede pagar contra entrega en efectivo. Cuando el repartidor llegue a su casa usted le paga. Solo necesito su dirección.',       'DELIVERED', NULL, NULL, NULL, '2026-03-05 07:11:00'),
(9, 'INBOUND',  'TEXT', 'Ah que bueno!! Pues es la casa con el árbol de mangos por la iglesia de la colonia Coyoacán. Pregunten por Conchita todos me conocen', 'READ',  NULL, NULL, NULL, '2026-03-05 07:15:00'),
(9, 'OUTBOUND', 'TEXT', '¿Nos puede dar la dirección con calle y número? Es para que el repartidor la encuentre sin problema.',      'DELIVERED', NULL, NULL, NULL, '2026-03-05 07:16:00'),
(9, 'INBOUND',  'TEXT', 'Ay es que no me sé la dirección bien déjeme le pregunto a mi vecina',                                      'READ',      NULL, NULL, NULL, '2026-03-05 07:18:00'),
(9, 'INBOUND',  'TEXT', 'Ya me dijo mi vecina es Calle Francisco Sosa 120 colonia Barrio de Santa Catarina Coyoacán',               'READ',      NULL, NULL, NULL, '2026-03-05 07:30:00'),
(9, 'OUTBOUND', 'TEXT', 'Gracias Conchita. Pedido: 1 Tremendo Mix Chocolate 1kg, envío a Calle Francisco Sosa 120, Barrio Santa Catarina, Coyoacán. Total: $570 ($520 + $50 envío). Pago contra entrega. ¿Correcto?', 'DELIVERED', NULL, NULL, NULL, '2026-03-05 07:32:00'),
(9, 'INBOUND',  'TEXT', 'Si creo que si',                                                                                           'READ',      NULL, NULL, NULL, '2026-03-05 07:35:00'),
(9, 'INBOUND',  'TEXT', 'Hay perdón creo que pedí el mix de chocolate pero no estoy segura a lo mejor era el de arándano. Mis nietos me dijeron chocolate verdad?', 'READ', NULL, NULL, NULL, '2026-03-05 08:00:00'),
(9, 'OUTBOUND', 'TEXT', 'Sí Conchita, pidió el Tremendo Mix Chocolate 1kg. ¿Quiere mantener el pedido o lo cambiamos por el Arándano Enchilado?', 'DELIVERED', NULL, NULL, NULL, '2026-03-05 08:02:00'),
(9, 'INBOUND',  'TEXT', 'Sí si déjelo así el de chocolate gracias',                                                                 'READ',      NULL, NULL, NULL, '2026-03-05 08:05:00'),
(9, 'INBOUND',  'TEXT', 'Ya llegó el mix pero sabe qué creo que no era este el que quería mi nieto. Se puede regresar?',           'READ', NULL, NULL, NULL, '2026-03-07 09:30:00'),
(9, 'OUTBOUND', 'TEXT', 'Claro Conchita, no se preocupe. Le hacemos la devolución completa de $570 MXN. El repartidor pasará a recoger la bolsa hoy. Lamentamos la confusión.', 'DELIVERED', NULL, NULL, NULL, '2026-03-07 09:35:00'),
(9, 'INBOUND',  'TEXT', 'Ay muchas gracias hijo son muy amables. Perdón por la molestia es que ya estoy viejita y se me confunden las cosas', 'READ', NULL, NULL, NULL, '2026-03-07 09:40:00'),
(9, 'OUTBOUND', 'TEXT', 'No se preocupe para nada, Conchita. Cuando su nieto le diga exactamente qué quiere, con gusto le ayudamos otra vez. ¡Que tenga bonito día! 🌸', 'DELIVERED', NULL, NULL, NULL, '2026-03-07 09:42:00'),

-- --------------------------------------------------------------------------
-- CUSTOMER 10: Mike Thompson (English speaker living in Mexico, mixes languages)
-- Scenario: birthday gift → uses English → asks about ingredients → orders with discount
-- --------------------------------------------------------------------------
(10, 'INBOUND',  'TEXT', 'Hey! Do you guys speak English? I want to order some stuff',                                              'READ',      NULL, NULL, NULL, '2026-03-06 10:30:00'),
(10, 'OUTBOUND', 'TEXT', 'Hi Mike! 👋 Yes, we can help you in English. What are you looking for?',                                   'DELIVERED', NULL, NULL, NULL, '2026-03-06 10:31:00'),
(10, 'INBOUND',  'TEXT', 'I want to get a birthday gift for my friend Sofia. She likes spicy snacks and chocolate. What do you recommend?', 'READ',  NULL, NULL, NULL, '2026-03-06 10:35:00'),
(10, 'OUTBOUND', 'TEXT', 'Great choices! I''d recommend:\n- Arándano Enchilado 100g ($65 MXN) - sweet & spicy dried cranberries\n- Tremendo Mix Chocolate 1kg ($520 MXN) - premium chocolate-covered nut mix\n\nWe also have Tremendo Mix Enchilado 100g ($65) if she likes a spicy nut mix. Want all three?', 'DELIVERED', NULL, NULL, NULL, '2026-03-06 10:36:00'),
(10, 'INBOUND',  'TEXT', 'Yeah all three sounds good. Does the chocolate mix have peanuts? She has a mild allergy',                  'READ',      NULL, NULL, NULL, '2026-03-06 10:40:00'),
(10, 'OUTBOUND', 'TEXT', 'Yes, the Tremendo Mix Chocolate contains peanuts (cacahuate) along with almonds, pecans and chocolate-covered raisins. If she has a peanut allergy, I''d recommend skipping it to be safe.', 'DELIVERED', NULL, NULL, NULL, '2026-03-06 10:41:00'),
(10, 'INBOUND',  'TEXT', 'Oh ok better skip the chocolate mix then. So just the arándano and the mix enchilado. Can you include a gift note saying Happy Birthday Sofia?', 'READ', NULL, NULL, NULL, '2026-03-06 10:45:00'),
(10, 'OUTBOUND', 'TEXT', 'Of course! ☺️ Your order:\n- 1x Arándano Enchilado: $65\n- 1x Tremendo Mix Enchilado 100g: $65\n- Gift note: "Happy Birthday Sofia"\n\nSubtotal: $130 MXN + pickup from Condesa is free. Would you like delivery ($50) or pickup?', 'DELIVERED', NULL, NULL, NULL, '2026-03-06 10:46:00'),
(10, 'INBOUND',  'TEXT', 'Hmm actually add the mix chocolate for me (not for the gift haha) and pickup at Condesa please',          'READ',      NULL, NULL, NULL, '2026-03-06 10:50:00'),
(10, 'OUTBOUND', 'TEXT', 'Updated order:\n- 1x Arándano Enchilado: $65 (gift)\n- 1x Tremendo Mix Enchilado 100g: $65 (gift)\n- 1x Tremendo Mix Chocolate 1kg: $520 (for you)\n- Gift note on arándano + mix enchilado\n\nSubtotal: $650 MXN. Pickup at Condesa, no shipping fee. Pay by card?', 'DELIVERED', NULL, NULL, NULL, '2026-03-06 10:52:00'),
(10, 'INBOUND',  'TEXT', 'wait do you have any promos? I saw something about 10% off on Instagram',                                  'READ',      NULL, NULL, NULL, '2026-03-06 10:55:00'),
(10, 'OUTBOUND', 'TEXT', 'Yes! We have a 10% off promo this week. Your new total:\n$650 - 10% = $585 MXN ✨\n\nShall I apply it?',     'DELIVERED', NULL, NULL, NULL, '2026-03-06 10:56:00'),
(10, 'INBOUND',  'TEXT', 'yes please! credit card. and make sure the mix chocolate is packaged separately so it doesnt mix with the gift lol', 'READ', NULL, NULL, NULL, '2026-03-06 10:58:00'),
(10, 'OUTBOUND', 'INTERACTIVE', NULL,                                                                                                'DELIVERED', NULL, NULL, NULL, '2026-03-06 10:59:00'),
(10, 'INBOUND',  'TEXT', 'paid!',                                                                                                   'READ',      NULL, NULL, NULL, '2026-03-06 11:02:00'),
(10, 'OUTBOUND', 'TEXT', 'Payment confirmed ✅. Your order is ready for pickup at Tremenda Nuez Condesa starting March 8. We''ll package the mix chocolate separately. Thanks Mike! 🙌', 'DELIVERED', NULL, NULL, NULL, '2026-03-06 11:03:00'),
(10, 'INBOUND',  'TEXT', 'Got it! Picked everything up. Sofia loved the arándano and the mix enchilado. Gracias!!',                  'READ',      NULL, NULL, NULL, '2026-03-08 13:00:00'),
(10, 'OUTBOUND', 'TEXT', 'That''s awesome to hear! 🎉 Glad Sofia enjoyed them. Thanks for choosing Tremenda Nuez, Mike!',            'DELIVERED', NULL, NULL, NULL, '2026-03-08 13:02:00'),

-- --------------------------------------------------------------------------
-- EDGE CASES: additional messages for testing robustness
-- --------------------------------------------------------------------------

-- Customer sends location (customer 6 testing location sharing)
(6, 'INBOUND',  'LOCATION', NULL,                                                                                                   'READ',      NULL, NULL, NULL, '2026-03-12 09:00:00'),
(6, 'OUTBOUND', 'TEXT', 'Recibimos tu ubicación 📍. ¿Quieres que actualicemos tu dirección de entrega?',                             'DELIVERED', NULL, NULL, NULL, '2026-03-12 09:01:00'),
(6, 'INBOUND',  'TEXT', 'nooo 🙈 fue sin querer jaja ignora eso',                                                                  'READ',      NULL, NULL, NULL, '2026-03-12 09:02:00'),

-- Customer sends audio/voice note (customer 7 trying to use voice)
(7, 'INBOUND',  'AUDIO', NULL,                                                                                                      'READ',      NULL, NULL, NULL, '2026-03-12 10:10:00'),
(7, 'OUTBOUND', 'TEXT', 'Don Arturo, recibimos su nota de voz, pero por el momento solo podemos responder mensajes de texto. ¿Nos puede escribir su pregunta?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 10:12:00'),
(7, 'INBOUND',  'TEXT', 'Ah perdón es que no sabía que era solo texto. Nada más quería confirmar que mañana paso por el pedido a la tienda de la Condesa', 'READ', NULL, NULL, NULL, '2026-03-12 10:15:00'),
(7, 'OUTBOUND', 'TEXT', 'Confirmado Don Arturo. Su pedido lo espera mañana en Tremenda Nuez Condesa (Av. Tamaulipas 78). ¡Hasta mañana! 😊', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 10:16:00'),

-- Rapid-fire messages (customer 2 sending multiple messages fast)
(2, 'INBOUND',  'TEXT', 'ey',                                                                                                       'READ',      NULL, NULL, NULL, '2026-03-12 11:00:00'),
(2, 'INBOUND',  'TEXT', 'ya tienen el mix?',                                                                                       'READ',      NULL, NULL, NULL, '2026-03-12 11:00:05'),
(2, 'INBOUND',  'TEXT', 'el enchilado de 100g',                                                                                    'READ',      NULL, NULL, NULL, '2026-03-12 11:00:08'),
(2, 'INBOUND',  'TEXT', 'tengo un amigo q dice q esta poca madre',                                                                  'READ',      NULL, NULL, NULL, '2026-03-12 11:00:12'),
(2, 'OUTBOUND', 'TEXT', '¡Hola de nuevo! Lo seguimos teniendo agotado por ahora 😕. Te aviso cuando llegue la nueva producción.',    'DELIVERED', NULL, NULL, NULL, '2026-03-12 11:01:00'),

-- Failed message delivery (outbound message that failed)
(3, 'OUTBOUND', 'TEXT', 'Roberto, tu pedido ya está por llegar. ¿Estás en casa?',                                                   'FAILED',    NULL, '131049', 'Message failed to send because more than 24 hours have passed since the customer last replied', '2026-03-13 08:00:00'),

-- Customer sends document (customer 1 sending invoice data as PDF)
(1, 'INBOUND',  'DOCUMENT', NULL,                                                                                                   'READ',      NULL, NULL, NULL, '2026-03-04 09:00:00'),
(1, 'OUTBOUND', 'TEXT', 'Recibimos tu documento, María. Lo revisaremos y te confirmamos. 📄',                                       'DELIVERED', NULL, NULL, NULL, '2026-03-04 09:02:00'),

-- Customer asks about unavailable product (customer 4)
(4, 'INBOUND',  'TEXT', 'OIGAN Y EL MIX ENCHILADO DE 100G QUE TENIAN YA LO TIENEN???',                                             'READ',      NULL, NULL, NULL, '2026-03-12 09:00:00'),
(4, 'OUTBOUND', 'TEXT', 'El Tremendo Mix Enchilado 100g sigue agotado. Esperamos nueva producción en 2-3 semanas. ¿Te anotamos en la lista de espera?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 09:02:00'),
(4, 'INBOUND',  'TEXT', 'SI PORFA Y AVISENME CUANDO LO TENGAN',                                                                     'READ',      NULL, NULL, NULL, '2026-03-12 09:03:00'),

-- Customer sends reaction to a message (customer 6)
(6, 'INBOUND',  'REACTION', NULL,                                                                                                   'READ',      NULL, NULL, NULL, '2026-03-12 09:30:00'),

-- Customer asks question outside business context (customer 5)
(5, 'INBOUND',  'TEXT', 'que hora es',                                                                                              'READ',      NULL, NULL, NULL, '2026-03-11 22:00:00'),
(5, 'OUTBOUND', 'TEXT', 'Hola Juan. Soy el asistente de Tremenda Nuez y te puedo ayudar con nuestros productos y pedidos. ¿Necesitas algo de nuestra tienda?', 'DELIVERED', NULL, NULL, NULL, '2026-03-11 22:01:00'),
(5, 'INBOUND',  'TEXT', 'no',                                                                                                       'READ',      NULL, NULL, NULL, '2026-03-11 22:02:00'),

-- Empty/whitespace message edge case (customer 3)
(3, 'INBOUND',  'TEXT', ' ',                                                                                                        'READ',      NULL, NULL, NULL, '2026-03-12 15:00:00'),
(3, 'OUTBOUND', 'TEXT', 'Hola Roberto, parece que tu mensaje llegó vacío. ¿En qué te puedo ayudar?',                                'DELIVERED', NULL, NULL, NULL, '2026-03-12 15:01:00'),

-- Customer asks about store hours (customer 9 - confused)
(9, 'INBOUND',  'TEXT', 'Bueno? Disculpe a qué hora abren es que quiero ir pero no sé si ya abrieron',                             'READ',      NULL, NULL, NULL, '2026-03-12 06:30:00'),
(9, 'OUTBOUND', 'TEXT', 'Buenos días Conchita 🌅. Tremenda Nuez Centro abre a las 9am y Tremenda Nuez Condesa a las 8am. ¿A cuál quiere ir?', 'DELIVERED', NULL, NULL, NULL, '2026-03-12 06:32:00'),
(9, 'INBOUND',  'TEXT', 'Y hoy es sábado o domingo? Es que ya me confundí',                                                         'READ',      NULL, NULL, NULL, '2026-03-12 06:35:00'),
(9, 'OUTBOUND', 'TEXT', 'Hoy es jueves 12 de marzo. Ambas tiendas están abiertas hoy. 😊',                                          'DELIVERED', NULL, NULL, NULL, '2026-03-12 06:36:00');

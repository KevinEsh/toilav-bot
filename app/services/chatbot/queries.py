from sqlalchemy import column, insert, table, text

update_order_status_query = text("""
UPDATE orders SET o_status = :o_status WHERE o_id = :o_id
""")

update_order_cancelled_with_reason_query = text(
    """UPDATE orders SET o_status = :o_status, o_cancel_reason = :o_cancel_reason WHERE o_id = :o_id
    """
)

get_order_query = text("""
    SELECT c.c_whatsapp_id, c.c_name, c.c_phone
    FROM orders o
    JOIN customers c ON c.c_id = o.o_c_id
    WHERE o.o_id = :o_id AND o.o_status = :o_status
    LIMIT 1
""")


insert_bulk_orderitems_query = insert(
    table(
        "orderitems",
        column("oi_o_id"),
        column("oi_p_id"),
        column("oi_units"),
        column("oi_unit_price"),
    )
)

insert_order_query = text("""
    INSERT INTO orders (o_c_id, o_s_id, o_status, o_customer_notes, o_subtotal, o_shipping_amount, o_total, o_currency)
    VALUES (:o_c_id, :o_s_id, :o_status, :o_customer_notes, 0, :o_shipping_amount, 0, :o_currency)
    RETURNING o_id
""")

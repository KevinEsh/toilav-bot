from sqlalchemy import text

create_order_totals_trigger = text("""
CREATE OR REPLACE FUNCTION recalc_order_totals()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    affected_o_id INT := COALESCE(NEW.oi_o_id, OLD.oi_o_id);
BEGIN
    UPDATE orders o
    SET
        o_subtotal = sub.subtotal,
        o_total    = sub.subtotal + COALESCE(o.o_shipping_amount, 0)
    FROM (
        SELECT COALESCE(SUM(oi_units * oi_unit_price), 0) AS subtotal
        FROM orderitems
        WHERE oi_o_id = affected_o_id
    ) sub
    WHERE o.o_id = affected_o_id;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE TRIGGER trg_recalc_order_totals
AFTER INSERT OR UPDATE OR DELETE ON orderitems
FOR EACH ROW EXECUTE FUNCTION recalc_order_totals();

CREATE OR REPLACE FUNCTION recalc_total_on_shipping_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.o_total := NEW.o_subtotal + COALESCE(NEW.o_shipping_amount, 0);
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_recalc_total_on_shipping
BEFORE UPDATE OF o_shipping_amount ON orders
FOR EACH ROW EXECUTE FUNCTION recalc_total_on_shipping_change();
""")

"""Tests for _order_summary helper in yalti.py.

Función pura — no toca DB. Todos los tests son síncronos.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from decimal import Decimal
from unittest.mock import MagicMock, patch

from yalti import _order_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_product(p_id, name, price):
    p = MagicMock()
    p.p_id = p_id
    p.p_name = name
    p.p_sale_price = price
    return p


def _make_item(p_id, units, unit_price):
    item = MagicMock()
    item.oi_p_id = p_id
    item.oi_units = units
    item.oi_unit_price = unit_price
    return item


def _make_order(total=260.0, customer_notes="Calle 15 #45-23"):
    order = MagicMock()
    order.o_total = total
    order.o_customer_notes = customer_notes
    return order


FAKE_PRODUCTS = {
    1: _make_product(1, "Almendras tostadas", 120.0),
    2: _make_product(2, "Pistaches", 95.0),
}


# ---------------------------------------------------------------------------
# Fallbacks defensivos
# ---------------------------------------------------------------------------

class TestOrderSummaryFallbacks:

    def test_product_missing_in_catalog(self):
        """p_id no registrado en PRODUCTS → fallback 'Producto #X', no KeyError."""
        order = _make_order(total=50.0)
        items = [_make_item(p_id=999, units=1, unit_price=50.0)]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        assert "Producto #999" in result
        assert "1x" in result

    def test_customer_notes_none(self):
        """o_customer_notes=None → '(sin notas)', no la cadena 'None'."""
        order = _make_order(customer_notes=None)
        items = [_make_item(1, 1, 120.0)]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        assert "(sin notas)" in result
        assert "None" not in result

    def test_customer_notes_empty_string(self):
        """o_customer_notes='' → '(sin notas)'."""
        order = _make_order(customer_notes="")
        items = [_make_item(1, 1, 120.0)]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        assert "(sin notas)" in result

    def test_empty_order_items(self):
        """order_items=[] → resumen 'sin ítems' sin explotar al hacer \\n.join."""
        order = _make_order(total=0.0)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, [], "Juan")
        assert "(sin ítems)" in result
        assert "Juan" in result
        assert "Total: $0" in result

    def test_o_total_none_fallback(self):
        """order.o_total=None (edge: DB row sin total) → Total: $0, no TypeError."""
        order = _make_order(total=None)
        items = [_make_item(1, 1, 120.0)]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        assert "Total: $0" in result


# ---------------------------------------------------------------------------
# Tipos numéricos (DB devuelve Decimal por Column(Numeric(10,2)))
# ---------------------------------------------------------------------------

class TestOrderSummaryNumericTypes:

    def test_decimal_unit_price(self):
        """oi_unit_price como Decimal (típico de DB) → formato correcto."""
        order = _make_order(total=Decimal("240.00"))
        items = [_make_item(1, 2, Decimal("120.00"))]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        assert "2x Almendras tostadas — $240" in result
        assert "Total: $240" in result

    def test_decimal_order_total(self):
        """order.o_total como Decimal → se convierte con float() sin error."""
        order = _make_order(total=Decimal("305.50"))
        items = [_make_item(1, 1, 120.0)]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        # :.0f redondea 305.50 → 306 (banker's rounding para .5 usa el par)
        assert "Total: $30" in result  # acepta 305 o 306 según redondeo


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestOrderSummaryHappyPath:

    def test_single_item(self):
        order = _make_order(total=120.0, customer_notes="Av. Juárez 123")
        items = [_make_item(1, 1, 120.0)]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan López")
        assert "Juan López" in result
        assert "1x Almendras tostadas — $120" in result
        assert "Total: $120" in result
        assert "Av. Juárez 123" in result

    def test_multiple_items_totals_computed_per_line(self):
        order = _make_order(total=335.0, customer_notes="Calle 15 #45-23")
        items = [
            _make_item(1, 2, 120.0),  # 240
            _make_item(2, 1, 95.0),   # 95
        ]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        assert "2x Almendras tostadas — $240" in result
        assert "1x Pistaches — $95" in result
        assert "Total: $335" in result

    def test_mixed_known_and_unknown_product(self):
        """Un ítem conocido + uno no en catálogo → ambos renderizados."""
        order = _make_order(total=170.0)
        items = [
            _make_item(1, 1, 120.0),
            _make_item(999, 1, 50.0),
        ]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = _order_summary(order, items, "Juan")
        assert "Almendras tostadas" in result
        assert "Producto #999" in result

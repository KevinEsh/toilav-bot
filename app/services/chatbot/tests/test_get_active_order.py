"""Tests for _get_active_order helper in yalti.py.

Mockea Session + select para evitar engine real.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from yalti import _get_active_order


def _make_session(first_return=None, exec_side_effect=None):
    """Session mock usable como context manager."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    if exec_side_effect is not None:
        session.exec.side_effect = exec_side_effect
    else:
        result = MagicMock()
        result.first.return_value = first_return
        session.exec.return_value = result
    return session


class TestGetActiveOrderHappyPath:

    def test_returns_order_when_exists(self):
        order = MagicMock(o_id=42)
        session = _make_session(first_return=order)
        with patch("yalti.Session", return_value=session):
            result = _get_active_order(c_id=1)
        assert result is order
        session.exec.assert_called_once()

    def test_returns_none_when_no_active_order(self):
        session = _make_session(first_return=None)
        with patch("yalti.Session", return_value=session):
            result = _get_active_order(c_id=1)
        assert result is None


class TestGetActiveOrderErrorHandling:

    def test_db_operational_error_returns_none(self):
        """DB caída → log + None, no propaga excepción."""
        session = _make_session(
            exec_side_effect=OperationalError("stmt", {}, Exception("connection refused"))
        )
        with patch("yalti.Session", return_value=session):
            result = _get_active_order(c_id=1)
        assert result is None

    def test_unexpected_error_returns_none(self):
        """Cualquier otra excepción también retorna None."""
        session = _make_session(exec_side_effect=RuntimeError("unexpected"))
        with patch("yalti.Session", return_value=session):
            result = _get_active_order(c_id=1)
        assert result is None

    def test_session_construction_failure_returns_none(self):
        """Falla al abrir el Session context manager → None."""
        with patch("yalti.Session", side_effect=RuntimeError("engine down")):
            result = _get_active_order(c_id=1)
        assert result is None

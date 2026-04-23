"""Tests for _get_or_create_customer in whatsapp_utils.py.

Mockea Session + select para no tocar DB real.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from whatsapp_utils import _get_or_create_customer


def _make_session(first_return=None, commit_side_effect=None, exec_side_effect=None):
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    if exec_side_effect is not None:
        session.exec.side_effect = exec_side_effect
    else:
        result = MagicMock()
        result.first.return_value = first_return
        session.exec.return_value = result
    if commit_side_effect is not None:
        session.commit.side_effect = commit_side_effect
    return session


# ---------------------------------------------------------------------------
# Validación de wa_id — protege contra colisión de clientes
# ---------------------------------------------------------------------------

class TestGetOrCreateCustomerValidation:

    def test_empty_wa_id_raises(self):
        with pytest.raises(ValueError, match="wa_id vacío"):
            _get_or_create_customer("", "Juan")

    def test_none_wa_id_raises(self):
        with pytest.raises(ValueError, match="wa_id vacío"):
            _get_or_create_customer(None, "Juan")  # type: ignore[arg-type]

    def test_whitespace_wa_id_raises(self):
        with pytest.raises(ValueError, match="wa_id vacío"):
            _get_or_create_customer("   \t  ", "Juan")

    def test_wa_id_is_stripped_before_create(self):
        """wa_id con whitespace alrededor se normaliza antes de crear el Customer."""
        session = _make_session(first_return=None)
        with patch("whatsapp_utils.Session", return_value=session):
            _get_or_create_customer("  5215512345678  ", "Juan")
        created = session.add.call_args.args[0]
        assert created.c_whatsapp_id == "5215512345678"
        assert created.c_phone == "5215512345678"


# ---------------------------------------------------------------------------
# Happy path + error handling
# ---------------------------------------------------------------------------

class TestGetOrCreateCustomerHappyPath:

    def test_returns_existing_customer(self):
        existing = MagicMock(c_id=1, c_whatsapp_id="5215512345678")
        session = _make_session(first_return=existing)
        with patch("whatsapp_utils.Session", return_value=session):
            result = _get_or_create_customer("5215512345678", "Juan")
        assert result is existing
        session.add.assert_not_called()
        session.commit.assert_not_called()

    def test_creates_new_customer_when_not_found(self):
        session = _make_session(first_return=None)
        with patch("whatsapp_utils.Session", return_value=session):
            _get_or_create_customer("5215512345678", "Juan")
        session.add.assert_called_once()
        session.commit.assert_called_once()


class TestGetOrCreateCustomerErrorHandling:

    def test_db_error_on_select_reraises_with_log(self):
        """OperationalError en el SELECT se loguea y re-propaga."""
        session = _make_session(
            exec_side_effect=OperationalError("stmt", {}, Exception("conn refused"))
        )
        with patch("whatsapp_utils.Session", return_value=session):
            with pytest.raises(OperationalError):
                _get_or_create_customer("5215512345678", "Juan")

    def test_db_error_on_commit_reraises(self):
        """Falla en commit distinta a IntegrityError se propaga al caller."""
        session = _make_session(
            first_return=None,
            commit_side_effect=OperationalError("stmt", {}, Exception("commit failed")),
        )
        with patch("whatsapp_utils.Session", return_value=session):
            with pytest.raises(OperationalError):
                _get_or_create_customer("5215512345678", "Juan")


# ---------------------------------------------------------------------------
# Race condition — concurrent first-contact creates
# ---------------------------------------------------------------------------

class TestGetOrCreateCustomerRace:

    def test_integrity_error_triggers_reselect_and_returns_winner(self):
        """SELECT(None) + commit(IntegrityError) → rollback + re-SELECT devuelve al ganador."""
        winner = MagicMock(c_id=42, c_whatsapp_id="5215512345678")
        first_result = MagicMock()
        first_result.first.return_value = None
        reselect_result = MagicMock()
        reselect_result.first.return_value = winner

        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.exec.side_effect = [first_result, reselect_result]
        session.commit.side_effect = IntegrityError("stmt", {}, Exception("duplicate key"))

        with patch("whatsapp_utils.Session", return_value=session):
            result = _get_or_create_customer("5215512345678", "Juan")

        assert result is winner
        session.rollback.assert_called_once()
        assert session.exec.call_count == 2

    def test_integrity_error_with_empty_reselect_reraises(self):
        """Si el re-SELECT no encuentra el registro (IntegrityError no era por race),
        re-raise el IntegrityError original para no tragar el error."""
        first_result = MagicMock()
        first_result.first.return_value = None
        reselect_result = MagicMock()
        reselect_result.first.return_value = None

        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.exec.side_effect = [first_result, reselect_result]
        session.commit.side_effect = IntegrityError("stmt", {}, Exception("other constraint"))

        with patch("whatsapp_utils.Session", return_value=session):
            with pytest.raises(IntegrityError):
                _get_or_create_customer("5215512345678", "Juan")

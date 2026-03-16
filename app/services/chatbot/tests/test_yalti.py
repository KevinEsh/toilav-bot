"""Tests for yalti module (pydantic_ai agent)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yalti import ChatDeps, _conversation_store, _get_history, agent_generate_response


class TestChatDeps:
    def test_creation(self):
        deps = ChatDeps(wa_id="123", customer_name="Juan")
        assert deps.wa_id == "123"
        assert deps.customer_name == "Juan"


class TestConversationStore:
    def setup_method(self):
        _conversation_store.clear()

    def test_get_history_creates_empty_list(self):
        history = _get_history("new_user")
        assert history == []
        assert "new_user" in _conversation_store

    def test_get_history_returns_same_list(self):
        h1 = _get_history("user_x")
        h1.append("message_1")
        h2 = _get_history("user_x")
        assert h2 == ["message_1"]
        assert h1 is h2

    def test_separate_histories_per_user(self):
        _get_history("user_a").append("msg_a")
        _get_history("user_b").append("msg_b")
        assert _get_history("user_a") == ["msg_a"]
        assert _get_history("user_b") == ["msg_b"]


class TestGenerateResponse:
    def setup_method(self):
        _conversation_store.clear()

    @pytest.mark.asyncio
    async def test_returns_string_response(self):
        """generate_response should return the agent's output as a string."""
        mock_result = MagicMock()
        mock_result.output = "¡Hola! ¿En qué te puedo ayudar?"
        mock_result.new_messages.return_value = [{"role": "assistant", "content": "¡Hola!"}]

        with patch("yalti.agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            response = await agent_generate_response("Hola", "wa_001", "Juan")

            assert response == "¡Hola! ¿En qué te puedo ayudar?"
            mock_agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_correct_deps(self):
        """generate_response should create ChatDeps with the right wa_id and name."""
        mock_result = MagicMock()
        mock_result.output = "Respuesta"
        mock_result.new_messages.return_value = []

        with patch("yalti.agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            await agent_generate_response("Test", "wa_002", "María")

            call_kwargs = mock_agent.run.call_args
            deps = call_kwargs.kwargs["deps"]
            assert isinstance(deps, ChatDeps)
            assert deps.wa_id == "wa_002"
            assert deps.customer_name == "María"

    @pytest.mark.asyncio
    async def test_accumulates_history(self):
        """Successive calls for the same wa_id should accumulate message history."""
        mock_result_1 = MagicMock()
        mock_result_1.output = "Primera respuesta"
        mock_result_1.new_messages.return_value = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
        ]

        mock_result_2 = MagicMock()
        mock_result_2.output = "Segunda respuesta"
        mock_result_2.new_messages.return_value = [
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "resp2"},
        ]

        with patch("yalti.agent") as mock_agent:
            mock_agent.run = AsyncMock(side_effect=[mock_result_1, mock_result_2])

            await agent_generate_response("Hola", "wa_003", "Pedro")
            await agent_generate_response("Precio", "wa_003", "Pedro")

            # After both calls, the conversation store should have all 4 messages
            assert len(_conversation_store["wa_003"]) == 4
            assert mock_agent.run.call_count == 2

    @pytest.mark.asyncio
    async def test_different_users_have_separate_history(self):
        """Messages from different users should not share history."""
        mock_result = MagicMock()
        mock_result.output = "OK"
        mock_result.new_messages.return_value = [{"role": "assistant", "content": "OK"}]

        with patch("yalti.agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            await agent_generate_response("Hola", "user_A", "Ana")
            await agent_generate_response("Hola", "user_B", "Bob")

            # Each user should have their own separate history with 1 message each
            assert "user_A" in _conversation_store
            assert "user_B" in _conversation_store
            assert _conversation_store["user_A"] is not _conversation_store["user_B"]
            assert len(_conversation_store["user_A"]) == 1
            assert len(_conversation_store["user_B"]) == 1

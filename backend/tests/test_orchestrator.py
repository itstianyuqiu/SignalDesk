from types import SimpleNamespace
import unittest
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.exc import IntegrityError

from app.services.copilot.orchestrator import _persist_turn_with_retry


class PersistTurnRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_message_position_conflict_with_new_positions(self) -> None:
        session = AsyncMock()
        session.add = Mock()
        session_id = uuid4()
        user_id = uuid4()
        chat = SimpleNamespace(id=session_id, user_id=user_id, metadata_={}, updated_at=None)

        session.get.return_value = chat
        session.flush.side_effect = [None, None, None, None]
        session.commit.side_effect = [
            IntegrityError(
                statement="insert into messages ...",
                params={},
                orig=Exception(
                    'duplicate key value violates unique constraint "messages_session_position_uidx"',
                ),
            ),
            None,
        ]

        with (
            patch(
                "app.services.copilot.orchestrator._next_message_position",
                new=AsyncMock(side_effect=[0, 2]),
            ),
            patch(
                "app.services.copilot.orchestrator._load_chat_session_for_update",
                new=AsyncMock(return_value=chat),
            ),
        ):
            user_row, assistant_row = await _persist_turn_with_retry(
                session,
                session_id=session_id,
                user_id=user_id,
                user_content="hello",
                user_metadata={"input_mode": "text"},
                assistant_content="world",
                assistant_metadata={"kind": "copilot_tools"},
                input_mode="text",
                voice_metadata=None,
                allow_retry=True,
            )

        self.assertEqual(session.commit.await_count, 2)
        session.rollback.assert_awaited_once()
        self.assertEqual(user_row.position, 2)
        self.assertEqual(assistant_row.position, 3)

from types import SimpleNamespace
import unittest
from uuid import uuid4
from unittest.mock import AsyncMock

from fastapi import HTTPException

from app.api.v1.copilot import list_session_messages


class CopilotApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_session_messages_rejects_non_copilot_sessions(self) -> None:
        session_id = uuid4()
        user_id = uuid4()
        session = AsyncMock()
        session.get.return_value = SimpleNamespace(
            id=session_id,
            user_id=user_id,
            channel="qa",
        )

        with self.assertRaises(HTTPException) as ctx:
            await list_session_messages(session_id, session, user_id)

        self.assertEqual(ctx.exception.status_code, 404)

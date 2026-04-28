import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from app.api.deps import get_current_user_id


class CurrentUserIdTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_current_user_id_decodes_without_database_access(self) -> None:
        expected = uuid4()
        with patch(
            "app.api.deps._decode_supabase_access_token",
            return_value={"sub": str(expected)},
        ):
            user_id = await get_current_user_id("token", object())

        self.assertIsInstance(user_id, UUID)
        self.assertEqual(user_id, expected)

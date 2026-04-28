import unittest

from sqlalchemy import UniqueConstraint

from app.models.chat import ChatMessage


class ChatModelTests(unittest.TestCase):
    def test_messages_table_has_unique_session_position_constraint(self) -> None:
        constraints = [
            constraint
            for constraint in ChatMessage.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        names = {constraint.name for constraint in constraints}
        self.assertIn("messages_session_position_uidx", names)

"""pgvector SQLAlchemy type that works with asyncpg's binary vector codec.

The stock ``pgvector.sqlalchemy.Vector`` bind processor emits text (``to_text()``).
asyncpg's registered ``vector`` codec encodes with ``Vector._to_db_binary``, which
expects a ``pgvector.Vector`` instance — passing a bracket string breaks encoding.
"""

from pgvector import Vector as PGVector
from pgvector.sqlalchemy.vector import VECTOR as _BaseVECTOR


class VECTOR(_BaseVECTOR):
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if getattr(dialect, "driver", None) == "asyncpg":
                if not isinstance(value, PGVector):
                    value = PGVector(value)
                if self.dim is not None and value.dimensions() != self.dim:
                    raise ValueError(
                        "expected %d dimensions, not %d" % (self.dim, value.dimensions())
                    )
                return value
            return PGVector._to_db(value, self.dim)

        return process

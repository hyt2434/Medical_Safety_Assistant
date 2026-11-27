"""Native UUID/aware timestamps, with a deterministic legacy-ID conversion.

Legacy names are identifiers, never UUID casts. The fixed namespace is part of
the migration contract. APIs return canonical UUID strings after migration.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid5
from sqlalchemy import DateTime, Uuid
from sqlalchemy.types import TypeDecorator

IDENTITY_NAMESPACE = UUID('fba7194e-d310-5f88-903f-e7827e106eca')


def identity_uuid(value):
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Nonempty legacy account ID required') from None
        return str(uuid5(IDENTITY_NAMESPACE, value))


class AccountUUID(TypeDecorator):
    impl = Uuid(as_uuid=False)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return identity_uuid(value)


class AwareTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Timezone-aware datetime required')
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        # SQLite cannot retain a zone; all bound values above are explicitly UTC.
        if value is not None and value.tzinfo is None and dialect.name == 'sqlite':
            value = value.replace(tzinfo=timezone.utc)
        return value

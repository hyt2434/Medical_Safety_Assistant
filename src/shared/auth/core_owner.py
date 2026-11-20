"""Explicit server-configured Auth -> existing Core identity, without schema changes."""
import json
import os
from uuid import UUID


def core_owner(account_id):
    bindings = json.loads(os.environ.get('CORE_USER_BINDINGS', '{}'))
    if not isinstance(bindings, dict):
        raise ValueError('CORE_USER_BINDINGS must be an account-to-UUID object')
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in bindings.items()):
        raise ValueError('Core binding keys and UUID values must be strings')
    owners = {key: UUID(value) for key, value in bindings.items()}
    if len(set(owners.values())) != len(owners):
        raise ValueError('Core identity bindings must not merge separate accounts')
    if account_id not in owners:
        raise PermissionError('Account has no provisioned Core identity')
    return owners[account_id]

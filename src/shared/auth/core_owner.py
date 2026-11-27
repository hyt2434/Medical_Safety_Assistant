"""One UUID identity in two stores; linking is server-only and retryable."""
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
    try:
        identity = UUID(str(account_id))
    except ValueError:
        raise PermissionError('Canonical Auth UUID required; migrate the account first') from None
    # Legacy bindings are migration input, never an alternative runtime owner.
    # A migrated account may retain a legacy key, but the two UUIDs must agree.
    if account_id in owners and owners[account_id] != identity:
        raise ValueError('Auth and Core UUID must be the same identity')
    return identity


def provision_core_identity(account_id, connection):
    """Provision only an existing Auth account; retry safely after either store fails.

    Called by trusted account provisioning, never by intake or a client-supplied
    owner. No distributed FK/transaction or duplicate mapping table is required:
    the existence of identity.users at the SAME UUID is the link's authority.
    """
    from sqlalchemy import select
    from shared.auth.db import initialize, transaction
    from shared.auth.models import User
    identity = core_owner(str(account_id))
    initialize()
    with transaction() as auth:
        account = auth.scalar(select(User).where(User.user_id == str(identity)))
        if account is None:
            raise PermissionError('Auth account must exist before Core provisioning')
        bindings = json.loads(os.environ.get('CORE_USER_BINDINGS', '{}'))
        if account.legacy_user_id in bindings and UUID(bindings[account.legacy_user_id]) != identity:
            raise ValueError('Migrate the legacy Auth account to its configured Core UUID before provisioning')
    with connection.transaction():
        connection.execute('INSERT INTO identity.users(id) VALUES (%s) ON CONFLICT(id) DO NOTHING', (identity,))
        if not connection.execute('SELECT 1 FROM identity.users WHERE id=%s', (identity,)).fetchone():
            raise RuntimeError('Core identity provisioning did not persist')
    return identity


def ensure_account(account_id, *, email, password, full_name, core_connection=None):
    """Trusted server/operator account provisioning with a stable request UUID.

    Auth commits first. A Core failure leaves an account that cannot use Core;
    retry with the same UUID completes the link without resetting any account,
    password, revoked role or existing clinical data. No patient-facing owner ID
    or cross-database FK is introduced.
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from shared.auth.db import initialize, transaction
    from shared.auth.models import User, UserRole, Role
    from shared.auth.passwords import hash_password
    from shared.auth.sessions import now, audit
    identity = str(UUID(str(account_id)))
    normalized_email = email.strip().lower()
    if not normalized_email or not full_name.strip() or not password:
        raise ValueError('Account email, name and password are required')
    initialize()
    with transaction() as db:
        if db.scalar(select(User.user_id).where(User.legacy_user_id == identity, User.user_id != identity)):
            raise ValueError('Provisioning UUID is a retained legacy identifier of another account')
        insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
        statement = insert(User).values(user_id=identity, email=normalized_email, password_hash=hash_password(password),
            full_name=full_name, account_status='active').on_conflict_do_nothing(index_elements=['user_id']).returning(User.user_id)
        created = db.execute(statement).scalar_one_or_none()
        account = db.scalar(select(User).where(User.user_id == identity))
        if account.email.lower() != normalized_email:
            raise ValueError('Provisioning UUID is already associated with a different account')
        if created:
            role = db.scalar(select(Role).where(Role.role_code == 'patient'))
            db.add(UserRole(user_id=identity, role_id=role.role_id, granted_at=now()))
            audit(db, None, 'account.created', target=identity)
    if core_connection is not None:
        provision_core_identity(identity, core_connection)
    return identity

"""Native identity/time types and non-overlapping, immutable grant history.

Validate every conversion before writing. PostgreSQL alters in place; SQLite's
limited ALTER support requires a transactional table rebuild from validated rows.
No source account, password, session, audit event or recorded grant is discarded.
"""
from datetime import datetime, timezone
import json
import os
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa
from shared.auth.types import identity_uuid, IDENTITY_NAMESPACE

revision = 'auth_004'
down_revision = 'auth_003'
branch_labels = None
depends_on = None

TIMES = {'user_roles': ('granted_at', 'expires_at', 'revoked_at'),
         'auth_sessions': ('expires_at',), 'audit_events': ('occurred_at',),
         'login_throttles': ('expires_at',)}
TABLES = ('users','roles','permissions','role_permissions','user_roles','auth_sessions','audit_events','login_throttles')


def native_metadata():
    """Frozen migration DDL, independent of future ORM model changes."""
    m = sa.MetaData()
    uid = lambda: sa.Uuid(as_uuid=False)
    instant = lambda: sa.DateTime(timezone=True)
    users = sa.Table('users', m,
        sa.Column('user_id', uid(), primary_key=True), sa.Column('legacy_user_id', sa.String(80), unique=True),
        sa.Column('email', sa.String(200), nullable=False, unique=True), sa.Column('password_hash', sa.Text, nullable=False),
        sa.Column('full_name', sa.String(200), nullable=False), sa.Column('account_status', sa.String(20), nullable=False),
        sa.CheckConstraint("account_status IN ('active','locked')"))
    sa.Index('uq_users_email_normalized', sa.func.lower(users.c.email), unique=True)
    sa.Table('roles',m,sa.Column('role_id',sa.Integer,primary_key=True),sa.Column('role_code',sa.String(40),nullable=False,unique=True),sa.Column('role_name',sa.String(100),nullable=False))
    sa.Table('permissions',m,sa.Column('code',sa.String(80),primary_key=True),sa.Column('description',sa.Text,nullable=False))
    sa.Table('role_permissions',m,
        sa.Column('role_id',sa.Integer,sa.ForeignKey('roles.role_id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('permission_code',sa.String(80),sa.ForeignKey('permissions.code',ondelete='RESTRICT'),primary_key=True))
    sa.Table('user_roles',m,sa.Column('grant_id',uid(),primary_key=True),
        sa.Column('user_id',uid(),sa.ForeignKey('users.user_id',ondelete='RESTRICT'),nullable=False,index=True),
        sa.Column('role_id',sa.Integer,sa.ForeignKey('roles.role_id',ondelete='RESTRICT'),nullable=False,index=True),
        sa.Column('granted_at',instant(),nullable=False),sa.Column('expires_at',instant()),sa.Column('revoked_at',instant()),
        sa.CheckConstraint('expires_at IS NULL OR expires_at > granted_at'),sa.CheckConstraint('revoked_at IS NULL OR revoked_at >= granted_at'))
    sa.Table('auth_sessions',m,sa.Column('token_hash',sa.String(64),primary_key=True),
        sa.Column('user_id',uid(),sa.ForeignKey('users.user_id',ondelete='CASCADE'),nullable=False,index=True),
        sa.Column('expires_at',instant(),nullable=False,index=True),sa.Column('active_context',sa.String(40)))
    sa.Table('audit_events',m,sa.Column('event_id',sa.Integer,primary_key=True),sa.Column('actor_user_id',uid()),
        sa.Column('action_code',sa.String(80),nullable=False),sa.Column('target_type',sa.String(80),nullable=False),
        sa.Column('target_id',sa.String(200),nullable=False),sa.Column('success',sa.Boolean(create_constraint=True,name='audit_success_boolean'),nullable=False),
        sa.Column('occurred_at',instant(),nullable=False,index=True))
    sa.Table('login_throttles',m,sa.Column('key_hash',sa.String(64),primary_key=True),sa.Column('attempts',sa.Integer,nullable=False),
        sa.Column('expires_at',instant(),nullable=False,index=True),sa.CheckConstraint('attempts >= 0'))
    return m


def converted_rows(bind):
    """Also used by migration tests; no database mutation until this succeeds."""
    data = {name: [dict(r) for r in bind.execute(sa.text(f'SELECT * FROM {name}')).mappings()]
            for name in TABLES}
    raw = json.loads(os.environ.get('AUTH_LEGACY_UUID_MAP', os.environ.get('CORE_USER_BINDINGS', '{}')))
    if not isinstance(raw, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in raw.items()):
        raise ValueError('Legacy UUID map must be an account-to-UUID object')
    explicit = {key: str(UUID(value)) for key, value in raw.items()}
    mapping = {r['user_id']: explicit.get(r['user_id'], identity_uuid(r['user_id'])) for r in data['users']}
    if len(set(mapping.values())) != len(mapping) or len(set(explicit.values())) != len(explicit):
        raise ValueError('Identity migration would merge separate accounts')
    zone = ZoneInfo(os.environ.get('AUTH_LEGACY_TIMEZONE', 'UTC'))
    # Old instant() explicitly interpreted naive strings as UTC; preserve that
    # contract unless the operator declares a different historic source zone.
    for table, rows in data.items():
        for i, row in enumerate(rows):
            for field in ('user_id', 'actor_user_id'):
                if row.get(field) is not None:
                    old = row[field]
                    row[field] = mapping.get(old, identity_uuid(old))
                    if table == 'users':
                        row['legacy_user_id'] = old if old != row[field] else None
            for field in TIMES.get(table, ()):
                value = row[field]
                if value is None:
                    continue
                try:
                    moment = value if isinstance(value, datetime) else datetime.fromisoformat(value)
                    if moment.tzinfo is None:
                        naive = moment
                        if moment.replace(tzinfo=zone, fold=0).utcoffset() != moment.replace(tzinfo=zone, fold=1).utcoffset():
                            raise ValueError('Ambiguous or nonexistent historic local time')
                        moment = moment.replace(tzinfo=zone)
                        if moment.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != naive:
                            raise ValueError('Nonexistent historic local time')
                    row[field] = moment.astimezone(timezone.utc)
                except (ValueError, TypeError, OverflowError) as error:
                    raise ValueError(f'Invalid historic time: {table} row {i + 1} {field}: {value!r}') from error
            if table == 'user_roles':
                row['grant_id'] = str(uuid5(IDENTITY_NAMESPACE, f"grant:{row['user_id']}:{row['role_id']}"))
                if ((row['expires_at'] is not None and row['expires_at'] <= row['granted_at']) or
                    (row['revoked_at'] is not None and row['revoked_at'] < row['granted_at'])):
                    raise ValueError(f'Invalid historic grant interval: {row["grant_id"]}')
            if table == 'audit_events':
                if row['success'] not in (0, 1, False, True):
                    raise ValueError(f'Invalid historic audit success: row {i + 1}')
                row['success'] = bool(row['success'])
    return data, mapping


def upgrade():
    bind = op.get_bind()
    data, mapping = converted_rows(bind)
    if bind.dialect.name == 'sqlite':
        # migrate() starts BEGIN IMMEDIATE before Alembic, including all DDL.
        # Child-first drop/rebuild is SQLite's ALTER implementation, not a DB reset.
        old = sa.MetaData()
        old.reflect(bind, only=TABLES)
        old.drop_all(bind)
        native = native_metadata()
        native.create_all(bind)
        for table in native.sorted_tables:
            if data[table.name]:
                bind.execute(table.insert(), data[table.name])
    else:
        inspector = sa.inspect(bind)
        foreign_keys = [(table, fk) for table in ('user_roles', 'auth_sessions')
                        for fk in inspector.get_foreign_keys(table) if fk['referred_table'] == 'users']
        for table, fk in foreign_keys:
            op.drop_constraint(fk['name'], table, type_='foreignkey')
        op.add_column('users', sa.Column('legacy_user_id', sa.String(80)))
        # Single CASE updates avoid collisions even if an old string happens to
        # equal another account's destination; detect that unsafe case first.
        if any(new in mapping and mapping[new] != new for new in mapping.values()):
            raise ValueError('Legacy IDs overlap destination UUIDs; explicit migration mapping required')
        for old_id, new_id in mapping.items():
            bind.execute(sa.text('UPDATE users SET user_id=:new,legacy_user_id=:legacy WHERE user_id=:old'),
                         {'new': new_id, 'legacy': old_id if old_id != new_id else None, 'old': old_id})
        for table, field in [('user_roles', 'user_id'), ('auth_sessions', 'user_id'), ('audit_events', 'actor_user_id')]:
            old_values = bind.execute(sa.text(f'SELECT DISTINCT {field} FROM {table} WHERE {field} IS NOT NULL')).scalars().all()
            for old_id in old_values:
                bind.execute(sa.text(f'UPDATE {table} SET {field}=:new WHERE {field}=:old'),
                             {'new': mapping.get(old_id, identity_uuid(old_id)), 'old': old_id})
        for table, field in [('users', 'user_id'), ('user_roles', 'user_id'), ('auth_sessions', 'user_id'), ('audit_events', 'actor_user_id')]:
            op.alter_column(table, field, type_=sa.Uuid(), postgresql_using=f'{field}::uuid')
        op.create_unique_constraint('uq_users_legacy_user_id', 'users', ['legacy_user_id'])
        for table, fk in foreign_keys:
            op.create_foreign_key(fk['name'], table, 'users', fk['constrained_columns'], fk['referred_columns'], ondelete=fk['options'].get('ondelete'))
        keys = {'user_roles': ('user_id', 'role_id'), 'auth_sessions': ('token_hash',),
                'audit_events': ('event_id',), 'login_throttles': ('key_hash',)}
        for table, fields in TIMES.items():
            for row in data[table]:
                where = ' AND '.join(f'{key}=:{key}' for key in keys[table])
                for field in fields:
                    bind.execute(sa.text(f'UPDATE {table} SET {field}=:converted WHERE {where}'),
                                 {**{k: row[k] for k in keys[table]}, 'converted': row[field].isoformat() if row[field] else None})
            for field in fields:
                op.alter_column(table, field, type_=sa.DateTime(timezone=True), postgresql_using=f'{field}::timestamptz')
        for constraint in inspector.get_check_constraints('audit_events'):
            if 'success' in constraint['sqltext']:
                op.drop_constraint(constraint['name'], 'audit_events', type_='check')
        op.alter_column('audit_events', 'success', type_=sa.Boolean(), postgresql_using='(success=1)')
        pk = inspector.get_pk_constraint('user_roles')['name']
        op.drop_constraint(pk, 'user_roles', type_='primary')
        op.add_column('user_roles', sa.Column('grant_id', sa.Uuid()))
        for row in data['user_roles']:
            bind.execute(sa.text('UPDATE user_roles SET grant_id=:id WHERE user_id=:user AND role_id=:role'),
                         {'id': row['grant_id'], 'user': row['user_id'], 'role': row['role_id']})
        op.alter_column('user_roles', 'grant_id', nullable=False)
        op.create_primary_key('user_roles_pkey', 'user_roles', ['grant_id'])
        op.create_index('ix_user_roles_user_id', 'user_roles', ['user_id'])
        op.create_check_constraint('grant_expiry_order', 'user_roles', 'expires_at IS NULL OR expires_at > granted_at')
        op.create_check_constraint('grant_revoke_order', 'user_roles', 'revoked_at IS NULL OR revoked_at >= granted_at')
        op.create_check_constraint('throttle_nonnegative', 'login_throttles', 'attempts >= 0')
    for name, rows in data.items():
        count = bind.execute(sa.text(f'SELECT count(*) FROM {name}')).scalar_one()
        if count != len(rows):
            raise RuntimeError('Auth migration count mismatch: ' + name)
    install_grant_guards(bind)
    install_last_admin_guards(bind)


def install_grant_guards(bind):
    if bind.dialect.name == 'postgresql':
        # No extension is necessary: serialize raw SQL writers with the same
        # advisory lock as API writes, then check exact half-open intervals.
        bind.exec_driver_sql('''CREATE FUNCTION auth_grant_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
         PERFORM pg_advisory_xact_lock(74031822);
         IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Role grant history cannot be deleted'; END IF;
         IF TG_OP='UPDATE' AND ((to_jsonb(NEW)-'revoked_at')<>(to_jsonb(OLD)-'revoked_at')
           OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL) THEN RAISE EXCEPTION 'Append a new role grant'; END IF;
         IF EXISTS(SELECT FROM user_roles g WHERE g.user_id=NEW.user_id AND g.role_id=NEW.role_id AND g.grant_id<>NEW.grant_id
           AND tstzrange(g.granted_at,least(g.expires_at,g.revoked_at),'[)') &&
               tstzrange(NEW.granted_at,least(NEW.expires_at,NEW.revoked_at),'[)')) THEN RAISE EXCEPTION 'Overlapping role grants'; END IF;
         RETURN NEW;
        END $$''')
        bind.exec_driver_sql('CREATE TRIGGER auth_grant_guard BEFORE INSERT OR UPDATE OR DELETE ON user_roles FOR EACH ROW EXECUTE FUNCTION auth_grant_guard()')
        # The lock is acquired before taking an INSERT statement snapshot too.
        # An exclusion constraint is the concurrency backstop when a statement
        # waited with an old snapshot (READ COMMITTED trigger queries refresh).
        bind.exec_driver_sql('CREATE EXTENSION IF NOT EXISTS btree_gist')
        bind.exec_driver_sql("ALTER TABLE user_roles ADD CONSTRAINT grant_intervals_no_overlap EXCLUDE USING gist (user_id WITH =, role_id WITH =, tstzrange(granted_at,least(expires_at,revoked_at),'[)') WITH &&)")
    else:
        end = lambda p: f"coalesce(CASE WHEN {p}.expires_at IS NULL THEN {p}.revoked_at WHEN {p}.revoked_at IS NULL THEN {p}.expires_at ELSE min({p}.expires_at,{p}.revoked_at) END,'9999-12-31')"
        for event in ('INSERT', 'UPDATE'):
            bind.exec_driver_sql(f'''CREATE TRIGGER grant_no_overlap_{event.lower()} BEFORE {event} ON user_roles BEGIN
            SELECT RAISE(ABORT,'Overlapping role grants') WHERE EXISTS(SELECT 1 FROM user_roles g
             WHERE g.user_id=NEW.user_id AND g.role_id=NEW.role_id AND g.grant_id<>NEW.grant_id
             AND g.granted_at<{end('NEW')} AND NEW.granted_at<{end('g')}); END''')
        bind.exec_driver_sql("""CREATE TRIGGER grant_immutable BEFORE UPDATE ON user_roles WHEN
          NEW.grant_id<>OLD.grant_id OR NEW.user_id<>OLD.user_id OR NEW.role_id<>OLD.role_id OR NEW.granted_at<>OLD.granted_at
          OR NEW.expires_at IS NOT OLD.expires_at OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
          BEGIN SELECT RAISE(ABORT,'Append a new role grant'); END""")
        bind.exec_driver_sql("CREATE TRIGGER grant_no_delete BEFORE DELETE ON user_roles BEGIN SELECT RAISE(ABORT,'Role grant history cannot be deleted'); END")


def downgrade():
    raise RuntimeError('Identity and grant history cannot be destructively downgraded')


def install_last_admin_guards(bind):
    if bind.dialect.name == 'postgresql':
        bind.exec_driver_sql('''CREATE FUNCTION auth_last_admin_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target uuid;
        BEGIN
         PERFORM pg_advisory_xact_lock(74031822);
         IF TG_TABLE_NAME='users' THEN
          IF OLD.account_status<>'active' OR NEW.account_status='active' THEN RETURN NEW; END IF;
          target:=OLD.user_id;
          IF NOT EXISTS(SELECT FROM user_roles g JOIN roles r USING(role_id) WHERE g.user_id=target AND r.role_code='admin'
             AND g.revoked_at IS NULL AND g.granted_at<=clock_timestamp() AND (g.expires_at IS NULL OR g.expires_at>clock_timestamp())) THEN RETURN NEW; END IF;
         ELSE
          IF NOT EXISTS(SELECT FROM roles WHERE role_id=NEW.role_id AND role_code='admin') THEN RETURN NEW; END IF;
          IF TG_OP='INSERT' AND (NEW.expires_at IS NULL OR NEW.revoked_at IS NOT NULL OR NEW.granted_at>clock_timestamp()) THEN RETURN NEW; END IF;
          IF TG_OP='UPDATE' AND (OLD.revoked_at IS NOT NULL OR OLD.granted_at>clock_timestamp()
             OR (OLD.expires_at IS NOT NULL AND OLD.expires_at<=clock_timestamp()) OR NEW.revoked_at IS NULL) THEN RETURN NEW; END IF;
          target:=NEW.user_id;
         END IF;
         IF NOT EXISTS(SELECT FROM user_roles g JOIN roles r USING(role_id) JOIN users u USING(user_id)
           WHERE r.role_code='admin' AND u.account_status='active' AND u.user_id<>target
            AND g.granted_at<=clock_timestamp() AND g.revoked_at IS NULL AND g.expires_at IS NULL)
          THEN RAISE EXCEPTION 'Cannot remove or expire the last permanent administrator'; END IF;
         RETURN NEW;
        END $$''')
        bind.exec_driver_sql('CREATE TRIGGER a_last_admin BEFORE INSERT OR UPDATE ON user_roles FOR EACH ROW EXECUTE FUNCTION auth_last_admin_guard()')
        bind.exec_driver_sql('CREATE TRIGGER a_last_admin BEFORE UPDATE OF account_status ON users FOR EACH ROW EXECUTE FUNCTION auth_last_admin_guard()')
        bind.exec_driver_sql("""CREATE FUNCTION auth_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN RAISE EXCEPTION 'Authentication audit is append-only'; END $$""")
        bind.exec_driver_sql('CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION auth_audit_immutable()')
    else:
        other_admin = """EXISTS(SELECT 1 FROM user_roles g JOIN roles r USING(role_id) JOIN users u USING(user_id)
          WHERE r.role_code='admin' AND u.account_status='active' AND u.user_id<>NEW.user_id
            AND g.granted_at<=strftime('%Y-%m-%d %H:%M:%f','now') AND g.revoked_at IS NULL AND g.expires_at IS NULL)"""
        bind.exec_driver_sql(f"""CREATE TRIGGER last_admin_revoke BEFORE UPDATE ON user_roles WHEN
          OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL AND OLD.granted_at<=strftime('%Y-%m-%d %H:%M:%f','now')
          AND (OLD.expires_at IS NULL OR OLD.expires_at>strftime('%Y-%m-%d %H:%M:%f','now'))
          AND EXISTS(SELECT 1 FROM roles WHERE role_id=NEW.role_id AND role_code='admin') AND NOT {other_admin}
          BEGIN SELECT RAISE(ABORT,'Cannot remove last permanent administrator'); END""")
        bind.exec_driver_sql(f"""CREATE TRIGGER last_admin_expiry BEFORE INSERT ON user_roles WHEN
          NEW.expires_at IS NOT NULL AND NEW.revoked_at IS NULL AND NEW.granted_at<=strftime('%Y-%m-%d %H:%M:%f','now')
          AND EXISTS(SELECT 1 FROM roles WHERE role_id=NEW.role_id AND role_code='admin') AND NOT {other_admin}
          BEGIN SELECT RAISE(ABORT,'Cannot expire last permanent administrator'); END""")
        bind.exec_driver_sql(f"""CREATE TRIGGER last_admin_lock BEFORE UPDATE OF account_status ON users WHEN
          OLD.account_status='active' AND NEW.account_status<>'active' AND EXISTS(SELECT 1 FROM user_roles g
            JOIN roles r USING(role_id) WHERE g.user_id=NEW.user_id AND r.role_code='admin'
            AND g.granted_at<=strftime('%Y-%m-%d %H:%M:%f','now') AND g.revoked_at IS NULL
            AND (g.expires_at IS NULL OR g.expires_at>strftime('%Y-%m-%d %H:%M:%f','now'))) AND NOT {other_admin}
          BEGIN SELECT RAISE(ABORT,'Cannot lock last permanent administrator'); END""")
        for action in ('UPDATE', 'DELETE'):
            bind.exec_driver_sql(f"CREATE TRIGGER audit_immutable_{action.lower()} BEFORE {action} ON audit_events BEGIN SELECT RAISE(ABORT,'Authentication audit is append-only'); END")

"""Database triggers that make audit_auditentry append-only: any UPDATE or DELETE of a row is refused by the database itself.

The model and queryset already raise ImmutableError, but raw SQL, a database console or a bug in another tool bypassed that. TRUNCATE is
not a row operation and is left alone (PostgreSQL's test flush uses it); a database owner can still DROP the trigger, so in production
also revoke UPDATE and DELETE on the table from the application's database role (docs/DEPLOYMENT.md).
"""
TABLE = "audit_auditentry"
MESSAGE = "audit_auditentry is append-only: rows cannot be changed or deleted"

SQLITE_CREATE = [
    f"CREATE TRIGGER {TABLE}_no_update BEFORE UPDATE ON {TABLE} BEGIN SELECT RAISE(ABORT, '{MESSAGE}'); END",
    f"CREATE TRIGGER {TABLE}_no_delete BEFORE DELETE ON {TABLE} BEGIN SELECT RAISE(ABORT, '{MESSAGE}'); END",
]
SQLITE_DROP = [f"DROP TRIGGER IF EXISTS {TABLE}_no_update", f"DROP TRIGGER IF EXISTS {TABLE}_no_delete"]

POSTGRES_CREATE = [
    f"CREATE OR REPLACE FUNCTION {TABLE}_append_only() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION '{MESSAGE}' USING ERRCODE = 'integrity_constraint_violation'; END; $$ LANGUAGE plpgsql",
    f"CREATE TRIGGER {TABLE}_append_only BEFORE UPDATE OR DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION {TABLE}_append_only()",
]
POSTGRES_DROP = [f"DROP TRIGGER IF EXISTS {TABLE}_append_only ON {TABLE}", f"DROP FUNCTION IF EXISTS {TABLE}_append_only()"]


def create(schema_editor):
    vendor = schema_editor.connection.vendor
    for sql in {"sqlite": SQLITE_CREATE, "postgresql": POSTGRES_CREATE}.get(vendor, []):
        schema_editor.execute(sql)


def drop(schema_editor):
    vendor = schema_editor.connection.vendor
    for sql in {"sqlite": SQLITE_DROP, "postgresql": POSTGRES_DROP}.get(vendor, []):
        schema_editor.execute(sql)

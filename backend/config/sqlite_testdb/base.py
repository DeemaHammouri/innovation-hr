"""SQLite for the test runs only: like the stock backend, but flushing the database (TransactionTestCase teardown, `flush`) is allowed to
empty the append-only audit table. The triggers are dropped and put back inside the same flush."""
from django.db.backends.sqlite3 import base as sqlite_base

from audit import triggers


class DatabaseOperations(sqlite_base.DatabaseOperations):
    def sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
        statements = super().sql_flush(style, tables, reset_sequences=reset_sequences, allow_cascade=allow_cascade)
        if triggers.TABLE not in tables:
            return statements
        return [*triggers.SQLITE_DROP, *statements, *triggers.SQLITE_CREATE]


class DatabaseWrapper(sqlite_base.DatabaseWrapper):
    ops_class = DatabaseOperations

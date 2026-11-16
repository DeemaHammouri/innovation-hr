import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "List the existing users (no passwords). Read-only: the database file is opened in read-only mode and nothing is written."

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("This read-only lister supports the SQLite file only.")
        path = str(db["NAME"]).replace("\\", "/")
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT u.email, u.full_name, d.name, r.key, u.is_active, u.must_change_password, u.is_superuser "
                "FROM accounts_user u LEFT JOIN accounts_department d ON d.id = u.department_id "
                "LEFT JOIN accounts_role r ON r.id = u.role_ref_id ORDER BY d.name, r.key, u.email"
            ).fetchall()
        except sqlite3.Error as e:
            raise CommandError(f"Could not read the users table ({e}). Has this database been migrated?")
        finally:
            con.close()
        self.stdout.write(f"{'email':36} {'name':24} {'department':16} {'role':18} active  must-change  superuser")
        for email, name, dept, role, active, must, sup in rows:
            self.stdout.write(f"{email:36} {name[:24]:24} {(dept or '-'):16} {(role or '-'):18} {'yes' if active else 'no':6}  {'yes' if must else 'no':11}  {'yes' if sup else 'no'}")
        self.stdout.write(f"{len(rows)} user(s).")

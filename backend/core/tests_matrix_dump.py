"""Developer tool, not a test: MATRIX_JSON=out.json python manage.py test core.tests_matrix_dump  writes the endpoint x role status table.
Used to prove a refactor changed nobody's access: dump before, dump after, compare."""
import json
import os
import unittest

from . import permission_audit
from .testing import RoleCase


@unittest.skipUnless(os.environ.get("MATRIX_JSON"), "set MATRIX_JSON to dump the permission matrix")
class DumpMatrix(RoleCase):
    def test_dump(self):
        table = permission_audit.matrix(self)
        rows = {f"{m.upper()} {u.replace('/api/v1/', '/api/')}": row for (m, u), row in table.items()}
        with open(os.environ["MATRIX_JSON"], "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1, sort_keys=True)

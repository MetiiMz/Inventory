# -*- coding: utf-8 -*-
"""
Django test runner that isolates real on-disk data dirs for the whole test run.

``setup_test_environment()`` points ``settings.IMG_DIR`` / ``settings.BACKUP_DIR``
and ``dbhelpers.IMG_DIR`` / ``dbhelpers.BACKUP_DIR`` / ``uploads.IMG_DIR`` at a
throwaway temp directory, so no test can ever delete or write into the real
``db/images/`` or ``db/backups/`` — even if a test forgets to patch those
constants itself.  Everything is removed in ``teardown_test_environment()``.

``DB_PATH`` is intentionally NOT redirected here: it is already controlled by
the ``TIKOTIME_DB`` environment variable (which tests point at a temp file),
and redirecting it here would decouple ``dbhelpers`` raw sqlite3 from Django's
ORM test database.
"""

import os
import tempfile
from unittest import mock

from django.conf import settings
from django.test.runner import DiscoverRunner


class SafeMediaTestRunner(DiscoverRunner):
    """Redirect image/backup dirs to temp locations for the entire test run."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._temp_root = tempfile.TemporaryDirectory()
        root = self._temp_root.name
        self.img_dir = os.path.join(root, "images")
        self.backup_dir = os.path.join(root, "backups")
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

        # ``dbhelpers`` and ``uploads`` bind these at import time, so
        # ``override_settings`` alone is not enough — patch them directly.
        from inventory import dbhelpers
        from inventory.api.services import uploads as uploads_mod

        self._patchers = [
            mock.patch.object(settings, "IMG_DIR", self.img_dir),
            mock.patch.object(settings, "BACKUP_DIR", self.backup_dir),
            mock.patch.object(dbhelpers, "IMG_DIR", self.img_dir),
            mock.patch.object(dbhelpers, "BACKUP_DIR", self.backup_dir),
            mock.patch.object(uploads_mod, "IMG_DIR", self.img_dir),
        ]
        for p in self._patchers:
            p.start()

    def teardown_test_environment(self, **kwargs):
        for p in reversed(getattr(self, "_patchers", [])):
            try:
                p.stop()
            except RuntimeError:
                pass
        temp_root = getattr(self, "_temp_root", None)
        if temp_root is not None:
            temp_root.cleanup()
        super().teardown_test_environment(**kwargs)

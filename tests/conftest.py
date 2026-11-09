"""Keep tests from writing into the project's real data directory."""
import os
import tempfile

os.environ.setdefault('DATAAUDIT_DATA_DIR', tempfile.mkdtemp(prefix='dataaudit-test-'))

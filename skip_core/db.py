"""Short transactions; migrations never run as a side effect of a query."""
import contextlib
import hashlib
import os
import sqlite3
from pathlib import Path
from .common import now
from .errors import CoreError, require

MIGRATIONS = Path(__file__).with_name('migrations')


def default_path():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    elif __import__('sys').platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    return Path(os.environ.get('SKIP_DATA_ROOT', base / 'SKIP')) / 'skip.db'


def statements(sql):
    current = ''
    for line in sql.splitlines(True):
        current += line
        if sqlite3.complete_statement(current):
            yield current
            current = ''
    require(not current.strip(), 'RECOVERY_REQUIRED', 'Incomplete migration')


class Database:
    def __init__(self, path, *, create=False):
        self.path = Path(path).absolute()
        require(not self.path.is_symlink(), 'RECOVERY_REQUIRED', 'Database symlink is not allowed')
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        require(create or self.path.is_file(), 'NOT_INITIALIZED', 'Connect SKIP to initialize the database')
        mode = 'rwc' if create else 'rw'
        self.connection = sqlite3.connect(self.path.as_uri() + '?mode=' + mode, uri=True,
                                          isolation_level=None, timeout=3)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.execute('PRAGMA busy_timeout=3000')
        require(self.connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1,
                'UNSUPPORTED_SCHEMA', 'SQLite foreign keys are required')
        try:
            if create:
                self._migrate()
                if os.name != 'nt':
                    self.path.chmod(0o600)
            self._check_schema()
            if create:
                require(self.connection.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal',
                        'RECOVERY_REQUIRED', 'WAL unavailable')
            self.connection.execute('PRAGMA synchronous=FULL')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def migrations():
        return [(int(p.name.split('_')[0]), p.read_text(), hashlib.sha256(p.read_bytes()).hexdigest())
                for p in sorted(MIGRATIONS.glob('*.sql'))]

    def _check_schema(self):
        try:
            actual = {r['version']: r['checksum'] for r in self.connection.execute('SELECT * FROM schema_migrations')}
        except sqlite3.DatabaseError as e:
            raise CoreError('UNSUPPORTED_SCHEMA', 'Database schema is unavailable') from e
        expected = {v: h for v, _, h in self.migrations()}
        require(actual == expected, 'UNSUPPORTED_SCHEMA', 'Schema version/checksum mismatch; use a compatible Core')

    def _migrate(self):
        with self.transaction():
            exists = self.connection.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
            applied = dict(self.connection.execute('SELECT version,checksum FROM schema_migrations')) if exists else {}
            migrations = self.migrations()
            expected = {v: h for v, _, h in migrations}
            require(all(expected.get(v) == h for v, h in applied.items()), 'UNSUPPORTED_SCHEMA', 'Unknown migration')
            for version, sql, checksum in migrations:
                if version not in applied:
                    for statement in statements(sql):
                        self.connection.execute(statement)
                    self.connection.execute('INSERT INTO schema_migrations VALUES(?,?,?)', (version, checksum, now()))

    @contextlib.contextmanager
    def transaction(self, *, write=True):
        require(not self.connection.in_transaction, 'CONFLICT', 'Nested transaction')
        require(self.connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1,
                'RECOVERY_REQUIRED', 'Foreign keys disabled')
        try:
            self.connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield self.connection
            self.connection.execute('COMMIT')
        except BaseException as exc:
            if self.connection.in_transaction:
                self.connection.execute('ROLLBACK')
            if isinstance(exc, sqlite3.IntegrityError):
                raise CoreError('CONFLICT', 'Record constraint rejected the change: ' + str(exc)) from exc
            if isinstance(exc, sqlite3.OperationalError):
                code = 'CONFLICT' if 'locked' in str(exc).lower() else 'RECOVERY_REQUIRED'
                raise CoreError(code, 'Database operation could not complete') from exc
            raise

    def backup(self, target):
        target = Path(target).absolute()
        require(not target.exists(), 'CONFLICT', 'Backup destination already exists')
        # O_EXCL prevents overwriting a raced-in destination.
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        other = sqlite3.connect(target)
        try:
            self.connection.backup(other)
            require(other.execute('PRAGMA integrity_check').fetchone()[0] == 'ok' and
                    not other.execute('PRAGMA foreign_key_check').fetchall(), 'RECOVERY_REQUIRED', 'Backup validation failed')
        finally:
            other.close()
        return {'status': 'backed_up', 'path': str(target)}

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def restore(backup_path, destination):
    """Rehearse recovery into a NEW DB. Never overwrite active user records."""
    with Database(backup_path) as source:
        require(source.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and
                not source.connection.execute('PRAGMA foreign_key_check').fetchall(),
                'RECOVERY_REQUIRED','Backup integrity check failed')
        source.backup(destination)
    with Database(destination) as restored:
        restored._check_schema()
    return {'status':'restored','path':str(destination),'activated':False}

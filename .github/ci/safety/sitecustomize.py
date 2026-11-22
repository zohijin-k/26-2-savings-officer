"""Block network and non-synthetic SQLite during tests, including spawn workers."""
from pathlib import Path
import os, socket, sqlite3
ROOT = Path(os.environ['CI_SYNTHETIC_ROOT']).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
def blocked(*args, **kwargs): raise PermissionError('Synthetic CI forbids network connections')
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
_connect = sqlite3.connect
def connect(database, *args, **kwargs):
    value = str(database)
    if value != ':memory:' and not value.startswith('file::memory:'):
        path = Path(value.removeprefix('file:').split('?')[0]).resolve()
        if not path.is_relative_to(ROOT): raise PermissionError('Synthetic CI SQLite boundary')
    return _connect(database, *args, **kwargs)
sqlite3.connect = connect
sqlite3.dbapi2.connect = connect

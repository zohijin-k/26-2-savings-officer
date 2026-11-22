"""Sealed temporary synthetic fixtures only. No production connection option."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .core import Application, Document, VersionProof, classify, summarize
from .policy import REPOSITORY, requirements


class FixtureError(ValueError):
    """Closed error message: never interpolate DB contents, IDs or paths."""


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        result = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
        return result.hexdigest()


def contained(root: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    path = root / relative
    if '..' in Path(relative).parts or any(p.is_symlink() for p in [path, *path.parents]):
        return None
    if not path.resolve().is_relative_to(root) or not path.is_file() or path.stat().st_nlink != 1:
        return None
    return path


def original_file(root: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or not Path(relative).parts or Path(relative).parts[0] != 'storage':
        return None
    return contained(root, relative)


def validate_fixture(root: Path) -> dict:
    root = root.absolute()
    allowed = {Path('/private/tmp').resolve(), Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve()}
    if any(p.is_symlink() for p in [root, *root.parents]) or not root.is_dir():
        raise FixtureError('A sealed temporary synthetic fixture is required')
    if not any(root.resolve().is_relative_to(p) and root.resolve() != p for p in allowed):
        raise FixtureError('A sealed temporary synthetic fixture is required')
    marker = contained(root, 'fixture.json')
    if marker is None:
        raise FixtureError('Synthetic fixture marker missing')
    try:
        manifest = json.loads(marker.read_text())
        if (manifest['kind'] != 'PHASE4A_GENERATED_SYNTHETIC_V1'
                or manifest['repository'] != REPOSITORY
                or manifest['database'] != 'synthetic.sqlite3'
                or not isinstance(manifest['files'], dict)):
            raise FixtureError('Synthetic fixture contract mismatch')
        if set(manifest['files']) != {str(p.relative_to(root)) for p in root.rglob('*')
                                      if p.is_file() and p != marker}:
            raise FixtureError('Unsealed fixture files')
        if 'synthetic.sqlite3' not in manifest['files']:
            raise FixtureError('Synthetic database missing')
        for name, expected in manifest['files'].items():
            file = contained(root, name)
            if file is None or digest(file) != expected:
                raise FixtureError('Synthetic fixture integrity mismatch')
        if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
            raise FixtureError('Private synthetic fixture permissions required')
        return manifest
    except (KeyError, TypeError, OSError, ValueError) as exc:
        raise FixtureError('Invalid synthetic fixture') from exc


@contextmanager
def readonly_connection(root: Path):
    validate_fixture(root)
    connection = sqlite3.connect((root / 'synthetic.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.enable_load_extension(False)
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                   sqlite3.SQLITE_RECURSIVE}
        # Even if future reader code accidentally adds a mutation, SQLite denies
        # it. ATTACH, writable PRAGMAs, transactions, DDL and DML are not allowed.
        connection.set_authorizer(lambda action, _a, _b, _c, _d:
                                  sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        yield connection
    finally:
        connection.close()


def columns(connection, table: str) -> set[str]:
    # Table names are internal literals, never fixture inputs.
    exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return set()
    # LIMIT 0 obtains column metadata without fetching any personal values.
    cursor = connection.execute('SELECT * FROM "' + table + '" LIMIT 0')
    return {column[0] for column in cursor.description}


def rows(connection, table: str, fields: tuple[str, ...]) -> tuple[list[dict], bool]:
    available = columns(connection, table)
    if not available:
        return [], True
    projection = ','.join('"' + f + '"' if f in available else 'NULL AS "' + f + '"' for f in fields)
    return [dict(r) for r in connection.execute('SELECT ' + projection + ' FROM "' + table + '"')], not set(fields).issubset(available)


def object_json(value) -> dict | None:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, dict) else None
    except (TypeError, ValueError):
        return None


def audit(root: Path) -> tuple[dict, tuple]:
    """No file is parsed as a document; synthetic bytes are only hashed."""
    root = root.absolute()
    try:
        with readonly_connection(root) as conn:
            sentinel = conn.execute('SELECT kind FROM phase4a_fixture').fetchall()
            if [r['kind'] for r in sentinel] != ['SYNTHETIC_ONLY']:
                raise FixtureError('Synthetic database sentinel missing')
            for table, keys in (('application', {'id'}), ('document', {'id', 'application_id'}),
                                ('review', {'application_id'})):
                if not keys.issubset(columns(conn, table)):
                    raise FixtureError('Required relationship schema missing')
            apps, am = rows(conn, 'application', ('id', 'program_code', 'status', 'submitted_at',
                                                 'criteria_version', 'doc_context_json'))
            docs, dm = rows(conn, 'document', ('id', 'application_id', 'slot_key', 'stage1_status',
                                              'uploaded_at', 'file_path', 'source_file_path',
                                              'page_index', 'doc_type'))
            reviews, rm = rows(conn, 'review', ('application_id', 'final_status', 'created_at'))
            criteria, _ = rows(conn, 'programcriteriaversion', ('program_code', 'version', 'criteria_json'))
            subsidy, sm = rows(conn, 'subsidyitem', ('application_id', 'item_type', 'count_index',
                                                   'linked_interview_index'))
            snapshots = {}
            if REPOSITORY == 'youth' and {'application_id', 'snapshot_json', 'posting_id'}.issubset(columns(conn, 'programapplicationsnapshot')):
                for r in conn.execute("SELECT application_id, posting_id, json_extract(snapshot_json, '$.requirements') AS requirements FROM programapplicationsnapshot"):
                    snapshots[r['application_id']] = (r['posting_id'], {'requirements': json.loads(r['requirements'])} if r['requirements'] else None)
        versions_path = contained(root, 'submission_versions.json')
        versions = json.loads(versions_path.read_text()) if versions_path else []
        results = []
        for app in sorted(apps, key=lambda r: r['id']):
            normalized = []
            proofs = []
            for d in (d for d in docs if d['application_id'] == app['id']):
                path = original_file(root, d['file_path'])
                source = original_file(root, d['source_file_path']) if d['source_file_path'] else None
                file_state = 'present' if path and (not d['source_file_path'] or source) else 'missing_or_invalid'
                merged = bool(d['source_file_path'] or d['page_index'] is not None
                              or '_merged' in Path(d['file_path'] or '').parts)
                normalized.append(Document(d['id'], d['slot_key'] or '', d['stage1_status'],
                    d['uploaded_at'], file_state, merged, d['doc_type']))
                candidates = [v for v in versions if v.get('application_id') == app['id'] and v.get('document_id') == d['id']]
                for v in candidates:
                    old = contained(root, v.get('version_path'))
                    valid = bool(old and path and v.get('submitted_at') == app['submitted_at']
                                 and v.get('binding') == 'SYNTHETIC_INDEPENDENT_SUBMISSION_VERSION'
                                 and v.get('submitted_sha256') == digest(old))
                    proofs.append(VersionProof(d['id'], v.get('submitted_sha256', ''),
                                               digest(path) if path else '', valid))
            matched = [c for c in criteria if c['program_code'] == app['program_code'] and c['version'] == app['criteria_version']]
            frozen = object_json(matched[0]['criteria_json']) if len(matched) == 1 else None
            snapshot_pair = snapshots.get(app['id'])
            snapshot = None
            if snapshot_pair and app['program_code'] == 'posting_' + str(snapshot_pair[0]):
                snapshot = snapshot_pair[1]
            reqs = requirements(app['program_code'] or '', object_json(app['doc_context_json']) or {},
                frozen, [s for s in subsidy if s['application_id'] == app['id']], snapshot)
            result = classify(Application(app['id'], app['submitted_at'], tuple(normalized),
                tuple(r['final_status'] for r in reviews if r['application_id'] == app['id']),
                reqs, tuple(proofs), am or dm or rm or (sm and app['program_code'] == 'job_package'),
                REPOSITORY == 'youth' and (app['program_code'] or '').startswith('posting_')))
            results.append(result)
        summary = summarize(tuple(results))
        app_ids = {a['id'] for a in apps}
        summary['orphan_documents'] = sum(d['application_id'] not in app_ids for d in docs)
        summary['orphan_reviews'] = sum(r['application_id'] not in app_ids for r in reviews)
        summary['collection_review_required'] = bool(summary['orphan_documents'] or summary['orphan_reviews'])
        # Re-check the sealed inputs after execution, also detecting concurrent
        # replacement. Consistent read-only production snapshots remain future work.
        validate_fixture(root)
        return summary, tuple(results)
    except (sqlite3.Error, OSError, TypeError, KeyError, ValueError) as exc:
        raise FixtureError('Synthetic audit failed closed') from exc

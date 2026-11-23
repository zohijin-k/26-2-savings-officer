"""심사 기록이 없는 신청 건을 DB와 업로드 저장소에서 지운다. **파괴적 스크립트다.**

Review가 있는 신청은 보존 정책으로 거부한다. 승인된 오프라인 정비 절차는 별도다.

저장소 루트에서:

    PYTHONIOENCODING=utf-8 python -m demo.backend.tools.delete_application --list
    PYTHONIOENCODING=utf-8 python -m demo.backend.tools.delete_application DS-2026-000005
    PYTHONIOENCODING=utf-8 python -m demo.backend.tools.delete_application DS-2026-000005 --yes

대상은 신청번호(application_no) 또는 DB id(숫자)로 지정한다. `--yes` 없이 실행하면
무엇을 지울지 출력만 하고 아무것도 바꾸지 않는다.

지우는 것:
  - DB: application 행 + 그 신청 건을 가리키는 consent·document·subsidyitem·
        review·reviewsummary 행 (한 트랜잭션)
  - 파일: storage/documents/<신청번호>/, storage/signatures/<신청번호>/,
          storage/signatures/<신청번호>_*.*, storage/forms_exports/<신청번호>.pdf,
          그리고 DB에 기록된 경로 중 storage/ 안에 있는 파일
  storage/ 밖의 경로나 다른 신청 건이 참조하는 파일은 건드리지 않는다.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from sqlmodel import select

from .. import models
from ..api.common import STORAGE

CHILD_TABLES = (
    models.Consent,
    models.Document,
    models.SubsidyItem,
    models.Review,
    models.ReviewSummary,
)


def _inside_storage(path: Path) -> bool:
    root = STORAGE.resolve()
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return root in resolved.parents and not path.is_symlink()


def _recorded_paths(app, rows) -> list[str]:
    values = [app.written_forms_archive_path, (app.identity_json or {}).get("pledge_signature_path")]
    for row in rows:
        values += [getattr(row, "signature_path", None), getattr(row, "file_path", None),
                   getattr(row, "source_file_path", None)]
    return [v for v in values if v]


def _find_app(session, target: str):
    if target.isdigit():
        return session.get(models.Application, int(target))
    return session.exec(
        select(models.Application).where(models.Application.application_no == target)
    ).first()


def _name(app) -> str:
    return (app.identity_json or {}).get("name") or (app.form1_json or {}).get("name") or "-"


def list_apps() -> None:
    with models.get_session() as s:
        for app in s.exec(select(models.Application).order_by(models.Application.id)):
            print(f"{app.id:>4}  {app.application_no:<20} {app.status:<10} {_name(app)}")


def plan(session, app):
    """(자식 행 목록, 지울 파일 목록, 지울 폴더 목록)"""
    rows = []
    for table in CHILD_TABLES:
        rows += session.exec(select(table).where(table.application_id == app.id)).all()

    # 다른 신청 건이 참조하는 파일은 보호한다.
    protected: set[Path] = set()
    for other in session.exec(select(models.Application).where(models.Application.id != app.id)):
        other_rows = []
        for table in (models.Consent, models.Document):
            other_rows += session.exec(select(table).where(table.application_id == other.id)).all()
        protected.update((STORAGE.parent / p).resolve() for p in _recorded_paths(other, other_rows))

    no = app.application_no
    files: set[Path] = {STORAGE.parent / p for p in _recorded_paths(app, rows)}
    files.update((STORAGE / "signatures").glob(f"{no}_*"))
    files.update((STORAGE / "forms_exports").glob(f"{no}.pdf*"))
    folders = [f for f in (STORAGE / "documents" / no, STORAGE / "signatures" / no) if f.is_dir()]
    for folder in folders:
        files.update(p for p in folder.rglob("*") if p.is_file())

    files = {f for f in files if f.is_file() and _inside_storage(f) and f.resolve() not in protected}
    folders = [f for f in folders if _inside_storage(f)]
    return rows, sorted(files), folders


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="신청 건 하나를 DB·저장소에서 지운다.")
    p.add_argument("target", nargs="?", help="신청번호(DS-...) 또는 DB id")
    p.add_argument("--list", action="store_true", help="신청 건 목록만 출력")
    p.add_argument("--yes", action="store_true", help="실제로 지운다(없으면 미리보기만)")
    args = p.parse_args(argv)

    if args.list or not args.target:
        list_apps()
        return 0

    with models.get_session() as s:
        app = _find_app(s, args.target)
        if app is None:
            print(f"신청 건을 찾지 못했습니다: {args.target}", file=sys.stderr)
            return 1
        rows, files, folders = plan(s, app)

        print(f"대상: id={app.id} {app.application_no} ({_name(app)}, {app.status})")
        counts: dict[str, int] = {}
        for r in rows:
            counts[type(r).__tablename__] = counts.get(type(r).__tablename__, 0) + 1
        print("DB 행: application 1" + "".join(f", {k} {v}" for k, v in counts.items()))
        print(f"파일 {len(files)}개:")
        for f in files:
            print(f"  {f.relative_to(STORAGE.parent)}")

        if not args.yes:
            print("\n미리보기입니다. 실제로 지우려면 --yes 를 붙여 다시 실행하세요.")
            return 0

        if any(isinstance(r, models.Review) for r in rows):
            print("심사 기록 보존 정책으로 삭제할 수 없습니다. 별도 오프라인 정비 절차가 필요합니다.", file=sys.stderr)
            return 2

        for r in rows:
            s.delete(r)
        s.flush()
        s.delete(app)
        s.commit()

    for f in files:
        f.unlink(missing_ok=True)
    for folder in folders:
        shutil.rmtree(folder, ignore_errors=True)
    print("\n삭제했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

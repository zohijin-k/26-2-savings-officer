"""신청자 저장소의 백엔드 변경을 이 저장소에 3방향 규칙으로 합친다.

사용 (저장소 루트에서):
    python .trellis/tasks/11-17-unified-backend/apply_merge.py plan     # 무엇을 할지만 출력
    python .trellis/tasks/11-17-unified-backend/apply_merge.py apply    # 작업 트리에 적용
    python .trellis/tasks/11-17-unified-backend/apply_merge.py check    # 적용 결과가 규칙과 같은지 대조

세 저장소가 나란히 있어야 한다. 내용은 작업 트리가 아니라 git에 저장된 것에서 읽는다.
    B  ../26-2-capstone            archive/main-before-split   (분리 전 코드)
    A  ../26-2-savings-applicant   614dd7b
    O  이 저장소                   f6d9827  (병합 전 main)

규칙: A만 바꾼 파일은 A, O만 바꾼 파일은 O, 양쪽이 바꾼 파일은 git merge-file,
A가 새로 만든 파일은 가져온다. 대상은 SUBTREES 아래의 추적 파일뿐이다.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = next((parent for parent in HERE.parents if (parent / ".trellis").is_dir() and (parent / "demo").is_dir()),
            Path.cwd())
SIBLINGS = REPO.parent
SOURCES = {
    "B": (SIBLINGS / "26-2-capstone", "archive/main-before-split"),
    "A": (SIBLINGS / "26-2-savings-applicant", "614dd7b"),
    "O": (REPO, "f6d9827"),
}
SUBTREES = ("demo/backend/", "demo/fixtures/", ".trellis/spec/backend/")
# 규칙에서 빼고 O의 것을 그대로 두는 파일. 이유는 design.md 3절에 적는다.
KEEP_OFFICER: frozenset[str] = frozenset()
# 규칙 적용 뒤 손으로 고치는 파일. check가 허용한다.
# 시험 3개는 changed-test-expectations.md의 B 표, 규격 2개는 연결 실행 규격과 그 목차 줄이다.
LOCAL_EDITS = frozenset({
    "demo/backend/tests/test_payment_paging.py",
    "demo/backend/tests/test_payment_paging_refinement.py",
    "demo/backend/tests/test_quality_assessment_parity.py",
    ".trellis/spec/backend/index.md",
    ".trellis/spec/backend/unified-backend.md",
})


def git(repo: Path, *args: str, check: bool = True) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *args], capture_output=True)
    if check and done.returncode:
        raise SystemExit(f"git {' '.join(args)} 실패: {done.stderr.decode('utf-8', 'replace')[:300]}")
    return done.stdout


def tree(side: str) -> dict[str, str]:
    repo, ref = SOURCES[side]
    listing = git(repo, "ls-tree", "-r", "-z", ref).decode("utf-8")
    found = {}
    for row in listing.split("\0"):
        if not row:
            continue
        meta, name = row.split("\t", 1)
        if name.startswith(SUBTREES):
            found[name] = meta.split()[2]
    return found


def blob(side: str, name: str) -> bytes:
    repo, ref = SOURCES[side]
    return git(repo, "show", f"{ref}:{name}")


def merge(name: str) -> tuple[bytes, int]:
    with tempfile.TemporaryDirectory() as folder:
        paths = []
        for side in ("A", "B", "O"):
            path = Path(folder) / side
            path.write_bytes(blob(side, name))
            paths.append(str(path))
        done = subprocess.run(["git", "merge-file", "-p", "-L", "applicant", "-L", "before-split", "-L", "officer",
                               *paths], capture_output=True)
        return done.stdout, done.returncode


def plan() -> dict[str, list[str]]:
    a, b, o = tree("A"), tree("B"), tree("O")
    out: dict[str, list[str]] = {key: [] for key in ("take_applicant", "add_applicant", "merge", "keep_officer_listed",
                                                      "needs_decision")}
    for name in sorted(set(a) | set(o)):
        in_a, in_b, in_o = name in a, name in b, name in o
        if in_a and in_o and a[name] == o[name]:
            continue
        if name in KEEP_OFFICER:
            out["keep_officer_listed"].append(name)
            continue
        if in_a and not in_o:
            if not in_b:
                out["add_applicant"].append(name)
            elif a[name] != b[name]:
                out["needs_decision"].append(f"{name} (담당자가 지움, 신청자가 바꿈)")
            continue
        if in_o and not in_a:
            if in_b and o[name] != b[name]:
                out["needs_decision"].append(f"{name} (신청자가 지움, 담당자가 바꿈)")
            elif in_b:
                out["needs_decision"].append(f"{name} (신청자가 지움)")
            continue
        if not in_b:
            out["needs_decision"].append(f"{name} (양쪽이 따로 만든 파일)")
        elif a[name] != b[name] and o[name] == b[name]:
            out["take_applicant"].append(name)
        elif a[name] != b[name] and o[name] != b[name]:
            out["merge"].append(name)
    return out


def expected(todo: dict[str, list[str]]) -> dict[str, bytes]:
    result = {name: blob("A", name) for name in todo["take_applicant"] + todo["add_applicant"]}
    for name in todo["merge"]:
        content, conflicts = merge(name)
        if conflicts:
            raise SystemExit(f"병합 충돌 {conflicts}곳: {name}")
        result[name] = content
    return result


def object_id(data: bytes) -> str:
    done = subprocess.run(["git", "hash-object", "--stdin"], input=data, capture_output=True, check=True)
    return done.stdout.decode().strip()


def main(mode: str) -> int:
    for side, (repo, ref) in SOURCES.items():
        if not (repo / ".git").exists():
            raise SystemExit(f"{side} 저장소가 없다: {repo}")
        git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    todo = plan()
    for key, names in todo.items():
        print(f"[{key}] {len(names)}개")
        for name in names:
            print("   ", name)
    if todo["needs_decision"]:
        print("사람이 정해야 하는 파일이 있어 멈춘다.")
        return 2
    if mode == "plan":
        return 0
    wanted = expected(todo)
    if mode == "apply":
        for name, data in wanted.items():
            target = REPO / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        print(f"적용: {len(wanted)}개 파일")
        return 0
    wrong = []
    for name, data in wanted.items():
        if name in LOCAL_EDITS:
            continue
        target = REPO / name
        actual = git(REPO, "hash-object", str(target), check=False).decode().strip() if target.is_file() else ""
        if actual != object_id(data):
            wrong.append(name)
    changed = {line[3:] for line in git(REPO, "status", "--porcelain", "--untracked-files=all", "--",
                                         *[prefix.rstrip("/") for prefix in SUBTREES]).decode("utf-8").splitlines()}
    extra = sorted(name for name in changed if name not in wanted and name not in LOCAL_EDITS)
    print(f"대조: 규칙과 다른 파일 {len(wrong)}개, 규칙에 없는데 바뀐 파일 {len(extra)}개, "
          f"손으로 고친 파일 {len(changed & LOCAL_EDITS)}개")
    for name in wrong + extra:
        print("   ", name)
    return 1 if wrong or extra else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("plan", "apply", "check") else "plan"))

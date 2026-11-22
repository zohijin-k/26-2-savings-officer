"""Value-free tracked-file and dependency-source checks; not a complete secret scanner."""
from pathlib import Path
import json, re, subprocess, sys
root = Path(sys.argv[1]).resolve()
files = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
failures = []
patterns = [rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', rb'gh[pousr]_[A-Za-z0-9]{36,}', rb'github_pat_[A-Za-z0-9_]{50,}', rb'AKIA[0-9A-Z]{16}']
for name in filter(None, files):
    path = root / name
    if path.is_symlink(): failures.append((name, 'tracked symlink requires review')); continue
    if name.endswith(('.db', '.sqlite', '.sqlite3', '.pem', '.key')) or Path(name).name == '.env': failures.append((name, 'sensitive file class'))
    data = path.read_bytes()
    if any(re.search(pattern, data) for pattern in patterns): failures.append((name, 'credential signature'))
lock = json.loads((root / 'demo/frontend/package-lock.json').read_text())
for name, package in lock.get('packages', {}).items():
    resolved = package.get('resolved', '')
    if resolved and not resolved.startswith('https://registry.npmjs.org/'):
        failures.append((name, 'unexpected npm package source'))
    if resolved and not package.get('integrity'): failures.append((name, 'npm integrity missing'))
for name in files:
    if not name.startswith('.github/workflows/') or not name.endswith(('.yml', '.yaml')): continue
    text = (root / name).read_text()
    if 'pull_request_target' in text or 'secrets.' in text or re.search(r'permissions:.*write', text): failures.append((name, 'unsafe workflow capability'))
    for action in re.findall(r'uses:\s*([^\s#]+)', text):
        if not re.fullmatch(r'actions/[A-Za-z0-9_-]+@[a-f0-9]{40}', action): failures.append((name, 'action not SHA pinned'))
print(json.dumps({'files_checked':len(files)-1, 'findings':failures}))
raise SystemExit(bool(failures))

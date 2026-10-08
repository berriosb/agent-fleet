#!/usr/bin/env bash
# scripts/verify.sh — Verificación consolidada de agent-fleet.
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "==> [verify] 1/3 Checking conventions sync with vault..."
python3 scripts/sync-conventions.py --check

echo "==> [verify] 2/3 Validating skills frontmatter, YAML, and CJK integrity..."
python3 -c "
import glob, sys, yaml, re

bad = []
files = set(glob.glob('**/*.yml', recursive=True) + glob.glob('.github/**/*.yml', recursive=True) + glob.glob('**/*.yaml', recursive=True))
for f in files:
    try:
        yaml.safe_load(open(f))
    except Exception as e:
        bad.append((f, str(e)))

skills = glob.glob('skills/**/SKILL.md', recursive=True)
for s in skills:
    content = open(s).read()
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        bad.append((s, 'Missing YAML frontmatter'))
        continue
    try:
        data = yaml.safe_load(m.group(1))
        if not isinstance(data, dict) or 'name' not in data:
            bad.append((s, \"Frontmatter missing 'name' field\"))
    except Exception as e:
        bad.append((s, f'Frontmatter YAML parse error: {e}'))

for f in skills + glob.glob('*.md'):
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            c = re.findall(r'[\u4e00-\u9fff]', fp.read())
            if c:
                bad.append((f, f'{len(c)} CJK glyphs found'))
    except Exception:
        pass

if bad:
    for f, e in bad:
        print(f'ERROR: {f}: {e}', file=sys.stderr)
    sys.exit(1)
print(f'OK: {len(files)} YAML configs, {len(skills)} skills frontmatter, 0 CJK glyphs.')
"

echo "==> [verify] 3/3 Running pre-push-qa runner..."
./skills/pre-push-qa/scripts/run.sh

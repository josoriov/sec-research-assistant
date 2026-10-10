"""Verification must use Compose's resolved bucket, not parse .env itself."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).resolve().parents[2] / "db" / "verify.sh"


@pytest.mark.parametrize("bucket", ["bronze", "quoted-archive", "override-archive"])
def test_verify_uses_compose_resolved_bucket(tmp_path, bucket):
    (tmp_path / ".env").write_text('MINIO_BUCKET="raw-value"\n')
    compose = tmp_path / "compose.py"
    compose.write_text('''import os, subprocess, sys
args = sys.argv[1:]
if args[0] == 'exec':
    sys.stdin.read()
elif 'app' in args:
    env = dict(os.environ, MINIO_BUCKET=os.environ['RESOLVED_BUCKET'])
    sys.exit(subprocess.run(args[args.index('app') + 1:], env=env, check=False).returncode)
else:
    assert args[-2:] == ['ls', 'local/' + os.environ['RESOLVED_BUCKET']], args
    sys.exit(int(os.environ.get('BUCKET_MISSING', '0')))
''')
    env = dict(os.environ, COMPOSE=f"{sys.executable} {compose}", RESOLVED_BUCKET=bucket)
    result = subprocess.run(["sh", str(VERIFY)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert f"{bucket} bucket reachable" in result.stdout
    env["BUCKET_MISSING"] = "1"
    result = subprocess.run(["sh", str(VERIFY)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode != 0

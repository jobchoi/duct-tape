"""Command dispatch with a fake Docker executable; never starts real services."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_docker_dispatch_is_scoped_and_preserves_exit_codes(tmp_path):
    compose = tmp_path / 'path with spaces' / 'compose.duct-tape.yml'
    compose.parent.mkdir()
    compose.write_text('services: {}')
    docker = tmp_path / 'docker'
    docker.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                      'print(json.dumps(sys.argv[1:]))\n'
                      'sys.exit(int(os.environ.get("FAKE_EXIT", "0")))\n')
    docker.chmod(0o755)
    env = dict(os.environ, PATH=str(tmp_path)+os.pathsep+os.environ['PATH'],
               DUCT_COMPOSE_FILE=str(compose))
    actions = {
        'start': ['up', '-d', 'duct-tape'],
        'stop': ['stop', 'duct-tape'],
        'restart': ['restart', 'duct-tape'],
        'status': ['ps', '-a', 'duct-tape'],
        'logs': ['logs', '--tail=80', '--follow', 'duct-tape'],
        'build': ['up', '-d', '--build', 'duct-tape'],
    }
    for action, expected in actions.items():
        result = subprocess.run(['bash', str(ROOT/'manage.sh'), 'docker', action],
                                cwd=tmp_path, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert '실행 명령:' in result.stdout
        assert json.loads(result.stdout.splitlines()[-1]) == ['compose', '-f', str(compose), *expected]
    env['FAKE_EXIT'] = '17'
    result = subprocess.run(['bash', str(ROOT/'manage.sh'), 'docker', 'start'],
                            env=env, capture_output=True)
    assert result.returncode == 17
    curl = tmp_path / 'curl'
    curl.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    curl.chmod(0o755)
    result = subprocess.run(['bash', str(ROOT/'manage.sh'), 'docker', 'check'],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout.splitlines()[-1]) == [
        '--fail', '--silent', '--show-error', '--max-time', '10',
        'http://127.0.0.1:8000/api/config']
    result = subprocess.run(['bash', str(ROOT/'manage.sh'), 'docker', 'delete'],
                            env=env, capture_output=True)
    assert result.returncode == 2
    compose.unlink()
    result = subprocess.run(['bash', str(ROOT/'manage.sh'), 'docker', 'start'],
                            env=env, capture_output=True)
    assert result.returncode == 1

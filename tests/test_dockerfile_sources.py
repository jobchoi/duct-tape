"""Keep local Docker build inputs in sync with the repository."""

import json
from pathlib import Path
import shlex


def test_dockerfile_copy_sources_exist():
    root = Path(__file__).resolve().parents[1]
    for line in (root / "Dockerfile").read_text().splitlines():
        instruction, _, arguments = line.strip().partition(" ")
        if instruction.upper() != "COPY":
            continue
        parts = json.loads(arguments) if arguments.startswith("[") else shlex.split(arguments)
        assert not parts[0].startswith("--"), "Handle COPY options before checking its sources"
        for source in parts[:-1]:
            assert list(root.glob(source.rstrip("/"))), f"Missing Docker COPY source: {source}"

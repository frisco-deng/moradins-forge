"""Scan maintained files without ingesting ignored private runtime artifacts."""

from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile


def source_files(root):
    root = Path(root).resolve()
    identity = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if identity.returncode or Path(identity.stdout.strip()).resolve() != root:
        raise ValueError("source_secret_scan_requires_native_repository_identity")
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=True,
    )
    names = sorted(set(os.fsdecode(n) for n in result.stdout.split(b"\0") if n))
    rows = {}
    total = 0
    for name in names:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe_source_path")
        path = root / relative
        if path.is_symlink():
            rows[name] = os.fsencode(os.readlink(path))
        elif path.is_file():
            if (
                path.stat().st_size > 16 * 1024 * 1024
                or total + path.stat().st_size > 256 * 1024 * 1024
            ):
                raise ValueError("maintained_source_over_scan_bound:" + name)
            rows[name] = path.read_bytes()
            total += len(rows[name])
        elif not path.exists():
            rows[name] = None
        else:
            raise ValueError("unsupported_source_file:" + name)
    if not any(data is not None for data in rows.values()):
        raise ValueError("maintained_source_empty")
    return rows


def snapshot(root, target):
    rows = source_files(root)
    for name, data in rows.items():
        if data is None:
            continue
        path = Path(target) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {
        name: hashlib.sha256(data).hexdigest() if data is not None else None
        for name, data in rows.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="source-", dir=args.output_dir
    ) as temporary:
        files = snapshot(args.repo_root, Path(temporary))
        r = subprocess.run(
            [
                "gitleaks",
                "dir",
                temporary,
                "--redact",
                "--no-banner",
                "--report-format",
                "json",
                "--report-path",
                str(args.report.resolve()),
                "--config",
                str(
                    (
                        args.repo_root / "tooling/configs/gitleaks/gitleaks.toml"
                    ).resolve()
                ),
            ]
        )
        current = {
            name: hashlib.sha256(data).hexdigest() if data is not None else None
            for name, data in source_files(args.repo_root).items()
        }
        if files != current:
            raise ValueError("source_changed_during_secret_scan")
    (args.output_dir / "source-receipt.json").write_text(
        json.dumps(
            {
                "schema_version": "source-secret-scan-v1",
                "files": files,
                "scanner_exit": r.returncode,
                "scope": "Tracked plus nonignored untracked maintained files; tracked evidence retained. No parent Git identity or ignored runtime ingestion.",
            },
            indent=2,
        )
        + "\n"
    )
    return r.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "unavailable", "reason": str(error)}))
        raise SystemExit(2)

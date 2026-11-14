"""Verify an exact private archive and published source before retiring a checkout."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile


def verify_archive_retirement(canonical: Path, target: Path, head: str, proof: dict) -> None:
    if proof.get("retirement_authorized") is not True or proof.get("head") != head:
        raise ValueError("archive_retirement_authority_or_head_mismatch")
    archive = Path(proof["archive_path"])
    if not archive.is_absolute() or archive.is_symlink() or archive.resolve().is_relative_to(target.resolve()):
        raise ValueError("archive_path_unsafe")
    info = archive.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("archive_must_be_private_and_owned")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != proof.get("archive_sha256"):
            raise ValueError("archive_hash_mismatch")
    ref = str(proof["published_ref"])
    if not ref.startswith(("refs/heads/", "refs/tags/")) or any(char in ref for char in "*?[\\\n\r"):
        raise ValueError("invalid_preserved_ref")
    remote = subprocess.run(["git", "-C", str(canonical), "ls-remote", "--exit-code", "origin", ref],
                            capture_output=True, text=True, timeout=30, check=True)
    if [head, ref] not in [line.split() for line in remote.stdout.splitlines()]:
        raise ValueError("exact_head_not_published")
    with tarfile.open(archive, "r:gz") as bundle:
        archived_names = set()
        for member in bundle:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("unsafe_archive_member")
            if name != PurePosixPath("."):
                if str(name) in archived_names:
                    raise ValueError("duplicate_archive_member")
                archived_names.add(str(name))
    current_names = set()
    def unreadable(error):
        raise error
    for directory, dirs, files in os.walk(target, followlinks=False, onerror=unreadable):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            if path == target / ".git":
                continue
            current_names.add(path.relative_to(target).as_posix())
        if Path(directory) == target:
            dirs[:] = [name for name in dirs if name != ".git"]
    if current_names != archived_names:
        raise ValueError("archive_member_set_changed")
    # Compare all non-Git bytes and metadata, including ignored evidence. No extraction.
    compared = subprocess.run(["tar", "--compare", "--gzip", "--file", str(archive), "--exclude=./.git",
                               "--directory", str(target), "."], capture_output=True, text=True, timeout=300)
    if compared.returncode:
        raise ValueError("archive_snapshot_changed_or_unreadable")

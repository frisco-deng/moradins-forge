"""Resolve exact Pacman archive identities without following fallback hosts."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Callable, Any
from urllib.parse import quote, unquote


class _ArchiveLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.links.update(unquote(value) for key, value in attrs if key == "href" and value)


def resolve_pacman_archive(
    package: str, filename_version: str, native_arch: str, *, run: Callable[..., Any]
) -> tuple[str, str]:
    """Use a bounded official index; HTTP redirects do not establish existence.

    Inputs are identity-validated by the owning downloader. This only selects
    an exact filename. Package metadata and detached signatures remain required.
    """
    root = "https://archive.archlinux.org/packages/" + quote(package[0], safe="") + "/" + quote(package, safe="") + "/"
    result = run(
        ["curl", "--fail", "--silent", "--show-error", "--proto", "=https",
         "--max-redirs", "0", "--max-time", "30", "--max-filesize", "1048576",
         "--write-out", "\n%{http_code}", "--", root],
        timeout=40,
    )
    body, separator, status = result.stdout.rpartition("\n")
    if result.returncode != 0 or not separator or status != "200" or len(body.encode()) > 1048576:
        raise ValueError(f"rollback archive identity discovery failed: {package} at {filename_version}")
    parser = _ArchiveLinks()
    parser.feed(body)
    matches = []
    for arch in (native_arch, "any"):
        filename = f"{package}-{filename_version}-{arch}.pkg.tar.zst"
        if filename in parser.links:
            matches.append((root + quote(filename, safe=""), arch))
    if len(matches) != 1:
        raise ValueError(f"rollback archive identity is unavailable or ambiguous: {package} at {filename_version}")
    return matches[0]

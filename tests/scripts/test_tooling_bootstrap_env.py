from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_PATH = REPO_ROOT / "tooling" / "bin" / "bootstrap_env.py"


def load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("bootstrap_env", BOOTSTRAP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_download_url_allows_only_pinned_https_tool_urls() -> None:
    module = load_bootstrap_module()
    url = next(iter(module.ALLOWED_DOWNLOAD_URLS))

    assert module._validate_download_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://github.com/example/tool.tar.gz",
        "https://example.com/tool.tar.gz",
        "https://user:pass@github.com/example/tool.tar.gz",
    ],
)
def test_download_url_rejects_unpinned_or_unsafe_urls(url: str) -> None:
    module = load_bootstrap_module()

    with pytest.raises(SystemExit):
        module._validate_download_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/org/tool.tar.gz",
        "https://objects.githubusercontent.com/github-production-release-asset/tool",
        "https://release-assets.githubusercontent.com/github-production-release-asset/tool",
    ],
)
def test_redirect_url_allows_github_release_hosts(url: str) -> None:
    module = load_bootstrap_module()

    module._validate_redirect_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/tool",
        "http://release-assets.githubusercontent.com/tool",
        "https://example.com/tool",
        "https://user:pass@release-assets.githubusercontent.com/tool",
    ],
)
def test_redirect_url_rejects_unsafe_hosts_and_schemes(url: str) -> None:
    module = load_bootstrap_module()

    with pytest.raises(SystemExit):
        module._validate_redirect_url(url)

.PHONY: lint-py lint-md test test-py ui-test ui-build payload-validate payload-smoke template-validate template-smoke forge-explain forge-readiness forge-brief forge-plan forge-adopt-dry-run forge-adopt forge-verify forge-smoke public-export public-portability-check

PUBLIC_EXPORT_DIR ?= /tmp/moradin-forge-public-export-check
PUBLIC_SIDECAR_SMOKE_DIR ?= /tmp/moradin-forge-sidecar-smoke-check

lint-py:
	UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .

lint-md:
	UV_CACHE_DIR=/tmp/uv-cache uv run pymarkdownlnt --enable-extensions front-matter --disable-rules "*" --enable-rules md022 scan --recurse --exclude .git --exclude .venv --exclude node_modules --exclude dist .

test-py:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run pytest

test: test-py

ui-test:
	npm --prefix dev_tracker/ui run test

ui-build:
	npm --prefix dev_tracker/ui run build

payload-validate:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py validate

payload-smoke:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py smoke-test

template-validate: payload-validate

template-smoke: payload-smoke

forge-explain forge-brief:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py explain

forge-readiness:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py readiness

forge-plan forge-adopt-dry-run:
	@if [ -z "$(TARGET)" ]; then \
		echo "Usage: make $@ TARGET=<repo-path>"; \
		exit 1; \
	fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py plan --target "$(TARGET)" --write-install-request

forge-adopt:
	@if [ -z "$(TARGET)" ] || [ "$(APPROVE)" != "1" ]; then \
		echo "Usage: make forge-adopt TARGET=<repo-path> APPROVE=1 [OVERWRITE=1] [PATCH_AGENTS=1]"; \
		exit 1; \
	fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py apply --target "$(TARGET)" --approve $(if $(OVERWRITE),--overwrite-sidecar,) $(if $(PATCH_AGENTS),--patch-agents,) --write-install-request

forge-verify:
	@if [ -z "$(TARGET)" ]; then \
		echo "Usage: make forge-verify TARGET=<repo-path>"; \
		exit 1; \
	fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py verify --target "$(TARGET)"

forge-smoke:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py sidecar-smoke --output "$(PUBLIC_SIDECAR_SMOKE_DIR)" --force

public-export:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py export --output "$(PUBLIC_EXPORT_DIR)" --force --init-git

public-portability-check:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py check --output "$(PUBLIC_EXPORT_DIR)" --sidecar-output "$(PUBLIC_SIDECAR_SMOKE_DIR)" --force --init-git

# BEGIN workspace-tooling
-include tooling/make/tooling.mk
# END workspace-tooling

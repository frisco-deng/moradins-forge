.PHONY: lint-py lint-md test test-py ui-test ui-build payload-validate payload-smoke template-validate template-smoke forge-explain forge-readiness forge-brief forge-onboard forge-tooling-suite forge-tooling-suite-plan forge-tooling-suite-apply forge-tooling-suite-bundle forge-tooling-suite-verify forge-tooling-suite-rollback forge-tooling-plan forge-tooling-update-plan forge-tooling-apply forge-tooling-bundle forge-tooling-rollback forge-plan forge-adopt-dry-run forge-adopt forge-verify forge-upgrade-plan forge-upgrade forge-upgrade-rollback forge-rollback forge-smoke forge-dogfood-smoke forge-release-artifacts public-export public-portability-check

PUBLIC_EXPORT_DIR ?= /tmp/moradin-forge-public-export-check
PUBLIC_SIDECAR_SMOKE_DIR ?= /tmp/moradin-forge-sidecar-smoke-check
WORKSPACE ?=
PLAN ?=
PLAN_SHA256 ?=
OUTPUT ?=
RECEIPT ?=
APPROVE_RECEIPT_SHA256 ?=
AGENT_FILES ?=
CREATE_AGENT_FILES ?=
UPGRADE_ID ?=
PROFILE ?=
SELECT ?=
EXCLUDE ?=
CONTAINER_ENGINE ?=

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

forge-onboard:
	@if [ -z "$(WORKSPACE)" ]; then echo "Usage: make forge-onboard WORKSPACE=<workspace-path>"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py onboard --workspace "$(WORKSPACE)"

forge-tooling-suite:
	install/tooling-suite.sh

forge-tooling-suite-plan:
	@if [ -z "$(OUTPUT)" ]; then echo "Usage: make forge-tooling-suite-plan OUTPUT=<plan.json> [PROFILE=practical|extended] [SELECT='tool ...']"; exit 1; fi
	@if [ -z "$(PROFILE)" ] && [ -z "$(SELECT)" ]; then echo "Set PROFILE=practical|extended or SELECT='tool ...'"; exit 1; fi
	install/tooling-suite.sh plan $(if $(PROFILE),--profile "$(PROFILE)",--custom) $(foreach tool,$(SELECT),--select "$(tool)") $(foreach tool,$(EXCLUDE),--exclude "$(tool)") $(if $(CONTAINER_ENGINE),--container-engine "$(CONTAINER_ENGINE)",) --output "$(OUTPUT)"

forge-tooling-suite-apply:
	@if [ -z "$(PLAN)" ] || [ -z "$(PLAN_SHA256)" ]; then echo "Usage: make forge-tooling-suite-apply PLAN=<plan.json> PLAN_SHA256=<digest>"; exit 1; fi
	install/tooling-suite.sh apply --plan "$(PLAN)" --approve-plan-sha256 "$(PLAN_SHA256)"

forge-tooling-suite-bundle:
	@if [ -z "$(PLAN)" ] || [ -z "$(OUTPUT)" ]; then echo "Usage: make forge-tooling-suite-bundle PLAN=<plan.json> OUTPUT=<bundle-path>"; exit 1; fi
	install/tooling-suite.sh bundle --plan "$(PLAN)" --output "$(OUTPUT)"

forge-tooling-suite-verify:
	install/tooling-suite.sh verify --receipt "$(if $(RECEIPT),$(RECEIPT),latest)"

forge-tooling-suite-rollback:
	@if [ -z "$(RECEIPT)" ] || [ -z "$(APPROVE_RECEIPT_SHA256)" ]; then echo "Usage: make forge-tooling-suite-rollback RECEIPT=<receipt.json> APPROVE_RECEIPT_SHA256=<digest>"; exit 1; fi
	install/tooling-suite.sh rollback --receipt "$(RECEIPT)" --approve-receipt-sha256 "$(APPROVE_RECEIPT_SHA256)"

forge-tooling-plan:
	@if [ -z "$(WORKSPACE)" ]; then echo "Usage: make forge-tooling-plan WORKSPACE=<workspace-path>"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-plan --workspace "$(WORKSPACE)"

forge-tooling-update-plan:
	@if [ -z "$(WORKSPACE)" ]; then echo "Usage: make forge-tooling-update-plan WORKSPACE=<workspace-path>"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-update-plan --workspace "$(WORKSPACE)"

forge-tooling-apply:
	@if [ -z "$(PLAN)" ] || [ -z "$(PLAN_SHA256)" ]; then echo "Usage: make forge-tooling-apply PLAN=<plan.json> PLAN_SHA256=<digest>"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-apply --plan "$(PLAN)" --approve-plan-sha256 "$(PLAN_SHA256)"

forge-tooling-bundle:
	@if [ -z "$(PLAN)" ] || [ -z "$(OUTPUT)" ]; then echo "Usage: make forge-tooling-bundle PLAN=<plan.json> OUTPUT=<bundle-path>"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-bundle --plan "$(PLAN)" --output "$(OUTPUT)"

forge-tooling-rollback:
	@if [ -z "$(RECEIPT)" ] || [ "$(APPROVE)" != "1" ]; then echo "Usage: make forge-tooling-rollback RECEIPT=<receipt.json> APPROVE=1"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-rollback --receipt "$(RECEIPT)" --approve

forge-plan forge-adopt-dry-run:
	@if [ -z "$(TARGET)" ]; then \
		echo "Usage: make $@ TARGET=<repo-path>"; \
		exit 1; \
	fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py plan --target "$(TARGET)" --write-install-request

forge-adopt:
	@if [ -z "$(TARGET)" ] || [ "$(APPROVE)" != "1" ]; then \
		echo "Usage: make forge-adopt TARGET=<repo-path> APPROVE=1 [AGENT_FILES='AGENTS.md CLAUDE.md']"; \
		exit 1; \
	fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py apply --target "$(TARGET)" --approve $(if $(OVERWRITE),--overwrite-sidecar,) $(if $(PATCH_AGENTS),--patch-agents,) $(foreach file,$(AGENT_FILES),--approve-agent-file $(file)) $(foreach file,$(CREATE_AGENT_FILES),--create-agent-file $(file)) --write-install-request

forge-verify:
	@if [ -z "$(TARGET)" ]; then \
		echo "Usage: make forge-verify TARGET=<repo-path>"; \
		exit 1; \
	fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py verify --target "$(TARGET)"

forge-upgrade-plan:
	@if [ -z "$(TARGET)" ]; then echo "Usage: make forge-upgrade-plan TARGET=<repo-path>"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py upgrade-plan --target "$(TARGET)"

forge-upgrade:
	@if [ -z "$(TARGET)" ] || [ -z "$(PLAN)" ] || [ -z "$(PLAN_SHA256)" ]; then echo "Usage: make forge-upgrade TARGET=<repo-path> PLAN=<plan.json> PLAN_SHA256=<digest>"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py upgrade --target "$(TARGET)" --plan "$(PLAN)" --approve-plan-sha256 "$(PLAN_SHA256)"

forge-upgrade-rollback:
	@if [ -z "$(TARGET)" ] || [ -z "$(UPGRADE_ID)" ] || [ "$(APPROVE)" != "1" ]; then echo "Usage: make forge-upgrade-rollback TARGET=<repo-path> UPGRADE_ID=<id> APPROVE=1"; exit 1; fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py upgrade-rollback --target "$(TARGET)" --upgrade-id "$(UPGRADE_ID)" --approve

forge-rollback:
	@if [ -z "$(TARGET)" ] || [ "$(APPROVE)" != "1" ]; then \
		echo "Usage: make forge-rollback TARGET=<repo-path> APPROVE=1"; \
		exit 1; \
	fi
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py rollback --target "$(TARGET)" --approve

forge-smoke:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py sidecar-smoke --output "$(PUBLIC_SIDECAR_SMOKE_DIR)" --force

forge-dogfood-smoke:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_dogfood.py

forge-release-artifacts:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_dogfood.py --release-output artifacts/release

public-export:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py export --output "$(PUBLIC_EXPORT_DIR)" --force --init-git

public-portability-check:
	PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py check --output "$(PUBLIC_EXPORT_DIR)" --sidecar-output "$(PUBLIC_SIDECAR_SMOKE_DIR)" --force --init-git

# BEGIN workspace-tooling
-include tooling/make/tooling.mk
# END workspace-tooling

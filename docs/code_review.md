# Code Review Flow

This repo is the first governance reference implementation for the shared review
pack.

## Protected Branches

- `dev` is the current integration truth for practical validation.
- `main` stays behind until explicit human `dev -> main` signoff.
- Implementation work belongs on scoped `feature/*`, `fix/*`, `docs/*`,
  `chore/*`, or `harness/*` branches, not directly on `dev` or `main`.

## Default Local Review Loop

1. From the workspace root, run `cd <forge-root>`.
2. Run `make repo-brief TOOLING_SUMMARY_ONLY=1`.
3. Run `make verify-fast`.
4. Run `make review-ready TOOLING_SUMMARY_ONLY=1`.
5. Use `REVIEW_READY_SCOPE=full make review-ready TOOLING_SUMMARY_ONLY=1` only
   when container, SBOM, or CI-local detail is needed.

## PR Lane vs CI Lane

- `make review-ready` is the normal PR handoff surface.
- `make verify-ci` and `make release-check` keep release-evidence integrity in
  the heavier CI and release lane.
- Do not move release-evidence requirements back into the default PR loop.
- For Moradin Harness migration PRs, run `make pr-hardening` after refreshing
  release and review gates so reviewers can inspect the dirty-set grouping,
  known warnings, and rollback notes from one control artifact.

## Governance Pack

- Feature PR template: `.github/PULL_REQUEST_TEMPLATE/feature.md`
- Promotion PR template: `.github/PULL_REQUEST_TEMPLATE/promotion.md`
- CODEOWNERS: `.github/CODEOWNERS`
- Shared checklist source: `../../shared-tooling-source/configs/github/review_checklist.md`
- Public-candidate prep source:
  `../../shared-tooling-source/configs/github/public_candidate_checklist.md`

## Human Gate

- Human review is required before merge into `dev`.
- Human review is required again before `dev -> main`.
- `@codex` can assist with draft review and CI triage, but it is not the merge
  gate.
- Branch-hygiene waivers may clear PR handoff only when scoped and expiring;
  waived branches still require cleanup or renewed human approval before
  `dev -> main`.

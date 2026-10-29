# Changelog

## Unreleased

- Replace the version-specific launcher with `python -m mneme_asterion`, preserving configuration preflight and service behavior.
- Present project results in the README and keep versioned experiment details in the evaluation documentation.
- Align configuration, deployment, and failure-handling documentation with V4.1.


## v4.1.0 — 2026-10-29

- Add bounded model retries and stage-specific fallbacks for extraction and retrieval.
- Validate model responses and preserve unknown update decisions without caching them as facts.
- Record successful write order atomically for idempotent updates and streaming memory.
- Preserve all withdrawal controls, process model inputs in batches, and attach source metadata to fallback evidence.
- Select fallback excerpts around query matches instead of truncating each source from its beginning.


## v4.0.2 — 2026-10-28

- Organize service, retrieval and scoped-state modules under `mneme_asterion/`; retain `run_v4.py` as the root entry point.
- Replace experimental filename suffixes with functional module names and consolidate the identical state-projection modules.
- Update imports and repository-relative resource lookup while preserving model prompts, parameters and memory processing logic.
- Document the small-benchmark workflow, its upstream repository, and ten-seed results in the README.

## v4.0.1 — 2026-10-28

- Reorganize public documentation around architecture, configuration, API, evaluation, and deployment.
- Move tests into `tests/` and add an isolated offline test runner.
- Allow local configuration and existing databases during startup; keep distribution scanning as a separate command.
- Support `run_v4.py --help` without a configuration file.
- Publish compact experiment statistics and a score-recomputation command.
- Keep the v4.0 memory algorithm and model profile unchanged.

## v4.0 — 2026-10-28

- Publish the full Mneme-Asterion ScopedState V4 text-memory system, based on the attributed AMI rc3 reproduction.
- Retain the evaluated repaired core: raw evidence recovery, verified quotations, withdrawal filtering, and person/attribute-scoped state interpretation.
- Include the interleaved-session ordering and conditional-restoration fixes already deployed and evaluated.
- Add a guarded V4 launch entry, method identity validation in synthetic smoke, and an explicit open-QA limitation for the legacy sequential evaluation helper.
- Preserve author attribution, MIT license, source hashes, and synthetic tests.
- Results: repaired V4 LoCoMo-Refined five independent-build rounds, 85.30 ± 0.67. Historical frozen-version results are identified separately.
- Previous v0 source and workbench remain available in Git history at a2f9ca273caa237025add32ea181d5b30a7a45d4.

## v0

Attributed AMI baseline and initial small-benchmark workbench. See the previous commit for its complete source and change log.

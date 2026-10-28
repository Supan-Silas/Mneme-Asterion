# Changelog

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

"""Offline raw-source sampling without historical runs, DOCX or credentials."""
import argparse
from collections import Counter
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
from pathlib import Path
import socket
import sys
from unittest.mock import patch

# Permit direct execution without installing into the AMI environment.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_benchmark.benchmarks import LOADERS
from memory_benchmark.pipeline.prepare import code_identity, data_paths, prepare
from memory_benchmark.pipeline.resampling import (
    index_sources, leaf_requirements, select, select_histories, expand_histories,
)
from memory_benchmark.runtime.artifacts import file_hash, read_json, write_json, write_rows
from memory_benchmark.runtime.sources import verify_source_manifest

ALGORITHM = "history-first-leaf-reservation-v1"


@contextmanager
def offline():
    def denied(*args, **kwargs):
        raise RuntimeError("Network forbidden during source sampling/preparation")
    with patch.object(socket.socket, "connect", denied), patch.object(socket.socket, "connect_ex", denied), \
            patch.object(socket, "create_connection", denied):
        yield


def resolve_suite(path):
    path = Path(path).resolve()
    suite = read_json(path)
    for config in suite["benchmarks"].values():
        if any(k in config for k in ("question_ids", "episode_ids", "episode_limit", "session_limit", "question_limit")):
            raise ValueError("Use a complete source suite, without preselected IDs or limits")
        for key in ("data_dir", "data_file", "source_manifest", "source_snapshot"):
            if key in config:
                candidate = Path(config[key])
                config[key] = str((candidate if candidate.is_absolute() else path.parent / candidate).resolve())
    return suite


def validate_rules(rules, benchmarks, seeds):
    required = {"algorithm", "initial_history_counts", "max_questions_per_family",
                "min_questions_per_available_leaf", "min_questions_per_round",
                "max_history_instances_per_round", "beam_length_filter"}
    if set(rules) - required - {"expected_eligible_questions"} or not required <= set(rules):
        raise ValueError("Unknown or missing sampling rule")
    if rules["algorithm"] != ALGORITHM or rules["beam_length_filter"] not in ("100K", "500K", "1M"):
        raise ValueError("Unsupported algorithm or BEAM split")
    for key in required - {"algorithm", "initial_history_counts", "beam_length_filter"}:
        if type(rules[key]) is not int or rules[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    limits = rules["initial_history_counts"]
    if set(limits) != set(benchmarks) or any(type(n) is not int or n <= 0 for n in limits.values()):
        raise ValueError("Initial history counts must cover each source with a positive integer")
    if sum(limits.values()) > rules["max_history_instances_per_round"]:
        raise ValueError("Initial history counts exceed the history cap")
    if "expected_eligible_questions" in rules and (type(rules["expected_eligible_questions"]) is not int or rules["expected_eligible_questions"] <= 0):
        raise ValueError("Expected eligible count must be a positive integer")
    if not seeds or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Use one or more distinct integer seeds")


def draw(index, rules, seed):
    pool = [q for q in index if q["benchmark"] != "beam" or q["length_split"] == rules["beam_length_filter"]]
    expected = rules.get("expected_eligible_questions")
    if expected is not None and len(pool) != expected:
        raise ValueError(f"Eligible source count differs: expected {expected}, got {len(pool)}")
    requirements = leaf_requirements(index, rules["min_questions_per_available_leaf"])
    available = Counter(q["leaf"] for q in pool)
    if any(available[leaf] < n for leaf, n in requirements.items()):
        raise ValueError("BEAM length filter makes leaf minimums infeasible")
    initial = select_histories(pool, rules["initial_history_counts"], seed)
    if Counter(h["benchmark"] for h in initial) != rules["initial_history_counts"]:
        raise ValueError("Source pool cannot supply requested initial histories")
    histories, additions = expand_histories(pool, initial, seed, rules["max_questions_per_family"],
        requirements, rules["min_questions_per_round"], rules["max_history_instances_per_round"])
    allowed = {(h["benchmark"], h["source_unit_id"]) for h in histories}
    eligible = [q for q in pool if (q["benchmark"], q["source_unit_id"]) in allowed]
    chosen = select(eligible, rules["max_questions_per_family"], seed, requirements)
    counts = Counter(q["leaf"] for q in chosen)
    if len(chosen) < rules["min_questions_per_round"] or any(counts[leaf] < n for leaf, n in requirements.items()):
        raise ValueError("Question minimum not satisfied")
    if len({(q["benchmark"], q["qa_id"]) for q in chosen}) != len(chosen):
        raise ValueError("Duplicate selected question")
    if any(n > rules["max_questions_per_family"] for n in Counter(q["family"] for q in chosen).values()):
        raise ValueError("Family cap exceeded")
    if len(histories) > rules["max_history_instances_per_round"]:
        raise ValueError("History cap exceeded")
    if chosen != select(list(reversed(eligible)), rules["max_questions_per_family"], seed, requirements):
        raise ValueError("Selection changed with input order")
    return histories, additions, chosen


def verify_native(suite, chosen):
    """Validate IDs, capabilities and source units using the actual full-history loaders."""
    expected = {(q["benchmark"], q["qa_id"]): q for q in chosen}
    found = set()
    for name, config in suite["benchmarks"].items():
        ids = {ident for benchmark, ident in expected if benchmark == name}
        if not ids:
            continue
        for case in LOADERS[name](config, question_ids=ids):
            if {q.qa_id for q in case.queries} != {t.qa_id for t in case.targets}:
                raise ValueError("Native query/target mismatch")
            for target in case.targets:
                key = name, target.qa_id
                if key not in expected or key in found:
                    raise ValueError("Unexpected or duplicate native question")
                record = expected[key]
                if case.history.episode_id != record["source_unit_id"] or list(target.capability_leaves) != [record["leaf"]]:
                    raise ValueError("Native question/history/capability association changed")
                found.add(key)
    if found != set(expected):
        raise ValueError("Selected native questions missing")


def run(suite_path, rules_path, output, seeds, runtime_path=None):
    with offline():
        return _run(suite_path, rules_path, output, seeds, runtime_path)


def _run(suite_path, rules_path, output, seeds, runtime_path=None):
    suite = resolve_suite(suite_path)
    rules = read_json(rules_path)
    validate_rules(rules, suite["benchmarks"], seeds)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Choose a new output directory; previous samples are immutable")
    # Hash before indexing, then verify again at the end to detect source mutation.
    sources, versions = {}, {}
    for name, config in suite["benchmarks"].items():
        hashes = {str(p.resolve()): file_hash(p) for p in data_paths(name, config)}
        verify_source_manifest(config, hashes)
        sources.update(hashes)
        if config.get("source_manifest"):
            manifest = read_json(config["source_manifest"])
            sources[config["source_manifest"]] = file_hash(config["source_manifest"])
            versions[name] = {k: manifest.get(k) for k in ("repo_id", "revision")}
    index, indexed_files = index_sources(suite)
    if not {str(p.resolve()) for p in indexed_files} <= sources.keys():
        raise ValueError("Index contains an unverified source file")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "source_suite.json", suite)
    write_json(output / "rules.json", rules)
    write_json(output / "inventory.json", {"source_sha256": sources, "versions": versions,
        "by_benchmark": dict(Counter(q["benchmark"] for q in index)), "questions": len(index),
        "framework": code_identity(), "entrypoint_sha256": file_hash(__file__),
        "suite_sha256": file_hash(suite_path), "rules_sha256": file_hash(rules_path)})
    write_rows(output / "candidate_questions.jsonl", index)
    rounds = {}
    runtime = read_json(runtime_path) if runtime_path else None
    for seed in seeds:
        histories, additions, chosen = draw(index, rules, seed)
        if (histories, additions, chosen) != draw(list(reversed(index)), rules, seed):
            raise ValueError("History selection changed with input order")
        verify_native(suite, chosen)
        folder = output / f"seed-{seed}"
        folder.mkdir()
        ids = {name: sorted(q["qa_id"] for q in chosen if q["benchmark"] == name)
               for name in sorted({q["benchmark"] for q in chosen})}
        selected_suite = copy.deepcopy(suite)
        selected_suite.pop("question_bank_expected_counts", None)
        selected_suite.update(suite_id=f"small-benchmark-seed-{seed}", scope="pilot",
                              purpose="independent_history_first_sample")
        selected_suite["benchmarks"] = {name: {**suite["benchmarks"][name], "question_ids": values} for name, values in ids.items()}
        write_json(folder / "suite.json", selected_suite)
        write_json(folder / "question_ids.json", ids)
        write_json(folder / "selected_histories.json", histories)
        write_json(folder / "history_additions.json", additions)
        write_rows(folder / "selected_questions.jsonl", chosen)
        if runtime is not None:
            prepare(selected_suite, {**runtime, "seed": seed}, folder / "prepared")
        rounds[str(seed)] = {"questions": len(chosen), "selected_histories": len(histories),
            "used_histories": len({(q["benchmark"], q["source_unit_id"]) for q in chosen}),
            "by_benchmark": dict(Counter(q["benchmark"] for q in chosen)),
            "by_leaf": dict(Counter(q["leaf"] for q in chosen)),
            "by_family": dict(Counter(q["family"] for q in chosen)),
            "question_ids_sha256": file_hash(folder / "question_ids.json"),
            "selected_questions_sha256": file_hash(folder / "selected_questions.jsonl"),
            "native_associations_verified": True}
    if any(file_hash(path) != digest for path, digest in sources.items()):
        raise ValueError("Source changed during sampling; discard this incomplete output")
    summary = {"status": "complete", "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": ALGORITHM, "seeds": seeds, "rules": rules, "rounds": rounds,
        "inventory_sha256": file_hash(output / "inventory.json"), "model_api_calls": 0,
        "network_disabled": True, "history_truncated": False, "within_round_replacement": False,
        "between_round_overlap_allowed": True, "prepared": runtime is not None}
    write_json(output / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--rules", type=Path, default=ROOT / "configs/sampling/s_benchmark_v1.json")
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-runtime", type=Path,
                        help="Also prepare selected full histories/queries/targets offline using this runtime JSON")
    args = parser.parse_args(argv)
    with offline():
        result = run(args.suite, args.rules, args.output, args.seeds, args.prepare_runtime)
    print({"status": result["status"], "output": str(args.output.resolve()), "model_api_calls": 0})


if __name__ == "__main__":
    main()

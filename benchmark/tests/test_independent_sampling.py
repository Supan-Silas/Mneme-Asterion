"""Synthetic source integration tests: never read real benchmark or held-out data."""
from collections import Counter
import copy
import csv
import hashlib
from pathlib import Path
import socket
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from memory_benchmark.pipeline.prepare import data_paths, verify_prepared, prepare
from memory_benchmark.runtime.artifacts import file_hash, read_json, rows, write_json, write_rows
from memory_benchmark.runtime.sources import manifest_key, verify_source_manifest
from scripts.sample_small_benchmark import draw, offline, run, resolve_suite, validate_rules
from test_pipeline import fixtures
from memory_benchmark.benchmarks import native_contract


def csv_file(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def synthetic_sources(root):
    import pyarrow as pa
    import pyarrow.parquet as pq
    suite = fixtures(root)
    locomo = root / 'locomo/questions.jsonl'
    question = list(rows(locomo))[0]
    write_rows(locomo, [{**question, 'qa_id': f'q{i}'} for i in range(8)])
    cl = root / 'cl/CL-bench.jsonl'
    write_rows(cl, [{'metadata': {'task_id': 'task', 'context_id': 'ctx', 'context_category': 'Rule System Application'},
                    'messages': [{'role': 'system', 'content': '系统规则'}, {'role': 'user', 'content': '任务'}], 'rubrics': ['GOLD']}])
    suite['benchmarks']['clbench'] = {'data_file': str(cl)}
    v1 = root / 'v1'
    csv_file(v1 / 'questions_32k.csv', [{'persona_id': 'p', 'shared_context_id': 'c', 'end_index_in_shared_context': '1',
        'question_id': 'q', 'question_type': 'recall_user_shared_facts', 'user_question_or_message': '问题',
        'all_options': "['(a) 一', '(b) 二']", 'correct_answer': '(a)'}])
    write_rows(v1 / 'shared_contexts_32k.jsonl', [{'c': [{'role': 'user', 'content': '过去'}, {'role': 'user', 'content': 'FUTURE_SENTINEL'}]}])
    suite['benchmarks']['personamem_v1'] = {'data_dir': str(v1)}
    v2 = root / 'v2'
    csv_file(v2 / 'benchmark/text/benchmark.csv', [{'persona_id': 'p', 'chat_history_32k_link': 'data/history.json',
        'pref_type': 'neutral_preferences', 'user_query': "{'role':'user','content':'问题'}", 'preference': 'GOLD'}])
    write_json(v2 / 'data/history.json', {'chat_history': [{'role': 'user', 'content': '偏好'}, {'role': 'assistant', 'content': '收到'}]})
    suite['benchmarks']['personamem_v2'] = {'data_dir': str(v2)}
    beam = root / 'beam/data'
    beam.mkdir(parents=True)
    for split in ('100K', '500K'):
        table = pa.Table.from_pylist([{'conversation_id': 1, 'chat': [[{'role': 'user', 'content': '完整历史'}], [{'role': 'assistant', 'content': '末尾'}]],
            'probing_questions': repr({'information_extraction': [{'question': 'Q', 'rubric': ['GOLD']}]})}])
        pq.write_table(table, beam / f'{split}-00000-of-00001.parquet')
    suite['benchmarks']['beam'] = {'data_dir': str(beam)}
    for name, config in suite['benchmarks'].items():
        paths = data_paths(name, config)
        manifest = root / f'{name}.manifest.json'
        # Test Windows-origin manifests even on other platforms.
        write_json(manifest, {'repo_id': 'synthetic', 'revision': 'test', 'files': [
            {'path': p.relative_to(root).as_posix().replace('/', '\\'), 'sha256': file_hash(p)} for p in paths]})
        config.update(source_snapshot=str(root), source_manifest=str(manifest))
    rules = {'algorithm': 'history-first-leaf-reservation-v1', 'initial_history_counts': {name: 1 for name in suite['benchmarks']},
        'max_questions_per_family': 2, 'min_questions_per_available_leaf': 1, 'min_questions_per_round': 6,
        'max_history_instances_per_round': 10, 'beam_length_filter': '100K', 'expected_eligible_questions': 13}
    write_json(root / 'suite.json', suite)
    write_json(root / 'rules.json', rules)
    write_json(root / 'runtime.json', {'seed': 0})
    return suite, rules


class IndependentSamplingTests(unittest.TestCase):
    def test_six_sources_replay_prepare_and_full_native_histories(self):
        with tempfile.TemporaryDirectory(prefix='benchmark-中文-') as temp, offline():
            root = Path(temp)
            suite, rules = synthetic_sources(root)
            first = run(root / 'suite.json', root / 'rules.json', root / 'one', [101, 102], root / 'runtime.json')
            second = run(root / 'suite.json', root / 'rules.json', root / 'two', [101])
            self.assertEqual(first['rounds']['101']['question_ids_sha256'], second['rounds']['101']['question_ids_sha256'])
            self.assertFalse((root / 'prepared-99-local').exists())
            for seed in [101, 102]:
                folder = root / 'one' / f'seed-{seed}'
                ids = read_json(folder / 'question_ids.json')
                manifest = verify_prepared(folder / 'prepared')
                self.assertEqual({b: sorted(c['items']) for b, c in manifest['benchmarks'].items()}, ids)
                self.assertEqual(len(ids['locomo_refined']), 2)  # Not all eight source questions.
                cases = {c['benchmark']: c for c in rows(folder / 'prepared/cases.jsonl')}
                for name, expected_sessions in [('locomo_refined', 2), ('longmemeval_s', 2), ('beam', 2)]:
                    history = read_json(folder / 'prepared' / cases[name]['history'])
                    self.assertEqual(len(history['sessions']), expected_sessions)
                history = read_json(folder / 'prepared' / cases['personamem_v1']['history'])
                self.assertNotIn('FUTURE_SENTINEL', str(history))
                chosen = list(rows(folder / 'selected_questions.jsonl'))
                self.assertTrue(all(q['length_split'] == '100K' for q in chosen if q['benchmark'] == 'beam'))
                self.assertTrue(all(n <= 2 for n in Counter(q['family'] for q in chosen).values()))
            with self.assertRaises(FileExistsError):
                run(root / 'suite.json', root / 'rules.json', root / 'one', [101])

    def test_corrupt_source_rejected_before_sampling(self):
        with tempfile.TemporaryDirectory() as temp, offline():
            root = Path(temp)
            synthetic_sources(root)
            with (root / 'cl/CL-bench.jsonl').open('a', encoding='utf-8') as stream:
                stream.write('\n')
            with self.assertRaisesRegex(ValueError, 'Pinned public source'):
                run(root / 'suite.json', root / 'rules.json', root / 'out', [101])
            self.assertFalse((root / 'out').exists())

    def test_paths_and_missing_selected_id(self):
        self.assertEqual(manifest_key(r'data\history.json'), 'data/history.json')
        for invalid in ['../secret', 'C:/secret', '/secret']:
            with self.assertRaises(ValueError):
                manifest_key(invalid)
        with tempfile.TemporaryDirectory() as temp, offline():
            root = Path(temp)
            suite = fixtures(root)
            suite['benchmarks'] = {'locomo_refined': {**suite['benchmarks']['locomo_refined'], 'question_ids': ['q1', 'missing']}}
            with self.assertRaisesRegex(ValueError, 'question IDs missing'):
                prepare(suite, {}, root / 'out')

    def test_invalid_rules_and_preselection_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suite, rules = synthetic_sources(root)
            validate_rules(rules, suite['benchmarks'], [1])
            for seeds in ([], [1, 1], [True]):
                with self.assertRaises(ValueError):
                    validate_rules(rules, suite['benchmarks'], seeds)
            bad = copy.deepcopy(rules)
            bad['max_history_instances_per_round'] = 5
            with self.assertRaises(ValueError):
                validate_rules(bad, suite['benchmarks'], [1])
            suite['benchmarks']['beam']['question_ids'] = ['fixed']
            write_json(root / 'suite.json', suite)
            with self.assertRaisesRegex(ValueError, 'complete source suite'):
                resolve_suite(root / 'suite.json')

    def test_offline_guard(self):
        with offline(), self.assertRaisesRegex(RuntimeError, 'Network forbidden'):
            socket.create_connection(('example.com', 443))

    def test_cli_from_other_directory_with_relative_source_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suite, _ = synthetic_sources(root)
            for config in suite['benchmarks'].values():
                for key in ('data_dir', 'data_file', 'source_snapshot', 'source_manifest'):
                    if key in config:
                        config[key] = Path(config[key]).relative_to(root).as_posix()
            write_json(root / 'suite.json', suite)
            script = Path(__file__).resolve().parents[1] / 'scripts/sample_small_benchmark.py'
            result = subprocess.run([sys.executable, str(script), '--suite', str(root / 'suite.json'),
                '--rules', str(root / 'rules.json'), '--seeds', '303', '--output', str(root / 'out')],
                cwd=root, env=os.environ.copy(), capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(read_json(root / 'out/summary.json')['seeds'], [303])

    def test_native_contract_accepts_only_line_ending_conversion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = b'def user_query_text(row):\n    return row["query"]\n'
            path = root / 'sources/aml/personamem/pipeline_v2.py'
            path.parent.mkdir(parents=True)
            write_json(root / 'sources/source_audit.json', {'sources': {
                'data/personamem/pipeline_v2.py': {'sha256': hashlib.sha256(source).hexdigest()}}})
            path.write_bytes(source.replace(b'\n', b'\r\n'))
            native_contract.contract.cache_clear()
            try:
                with patch.object(native_contract, 'ROOT', root):
                    self.assertEqual(native_contract.contract('personamem_v2').user_query_text({'query': '中文'}), '中文')
                    native_contract.contract.cache_clear()
                    path.write_bytes(source.replace(b'return row', b'return 1 or row'))
                    with self.assertRaisesRegex(ValueError, 'source changed'):
                        native_contract.contract('personamem_v2')
            finally:
                native_contract.contract.cache_clear()


if __name__ == '__main__':
    unittest.main()

"""State transition and raw-journal ordering regressions."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mneme_e import raw_store
from mneme_asterion.state.projection import finalize
from mneme_asterion.state.withdrawal import withdrawal_state


def record(i, body, role='user', speaker='user'):
    return dict(id=str(i), role=role, speaker=speaker, body=body,
                text=body, source_ids=[str(i)])


class ReviewRegressions(unittest.TestCase):
    def run_state(self, last):
        raw = [record(0, 'My project color is RED.'),
               record(1, 'Please forget my project color.'), record(2, last)]
        audit = withdrawal_state(raw, len)[1]
        evidence = [dict(id='e', text='My project color is RED.', source_ids=['0'])]
        return finalize('What is my project color?', evidence, raw, audit)

    def test_conditional_restoration_remains_withdrawn(self):
        out, trace = self.run_state('Please remember my project color again if I confirm tomorrow.')
        self.assertTrue(trace['states'][0]['active_withdrawal'])
        self.assertNotIn('RED', str(out))

    def test_question_does_not_restore(self):
        _, trace = self.run_state('Please remember my project color again?')
        self.assertTrue(trace['states'][0]['active_withdrawal'])

    def test_quoted_restoration_does_not_restore(self):
        _, trace = self.run_state('Please remember my project color again "as an example".')
        self.assertTrue(trace['states'][0]['active_withdrawal'])

    def test_explicit_restoration_is_preserved(self):
        out, trace = self.run_state('Please remember my project color again: BLUE.')
        self.assertFalse(trace['states'][0]['active_withdrawal'])
        self.assertIn('BLUE', str(out))
        self.assertNotIn('RED', str(out))

    def test_interleaved_sessions_preserve_successful_input_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'order.sqlite3')
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE requests (user_id TEXT, request_id TEXT)')
            db.execute('CREATE TABLE request_commits (commit_seq INTEGER PRIMARY KEY, user_id TEXT, request_id TEXT)')
            db.execute('CREATE TABLE e_raw_requests (seq INTEGER PRIMARY KEY, user_id TEXT, request_id TEXT, payload TEXT)')
            bodies = ['My project color is RED.', 'Please forget my project color.',
                      'Please remember my project color again: BLUE.']
            for i, (session, body) in enumerate(zip(['a', 'b', 'a'], bodies)):
                payload = dict(session_id=session, request_id=str(i), messages=[dict(role='user', content=body)])
                db.execute('INSERT INTO requests VALUES (?,?)', ('u', str(i)))
                db.execute('INSERT INTO request_commits VALUES (?,?,?)', (i, 'u', str(i)))
                db.execute('INSERT INTO e_raw_requests VALUES (?,?,?,?)', (i, 'u', str(i), json.dumps(payload)))
            db.commit()
            db.close()
            with patch.object(raw_store.config, 'DB_PATH', path):
                history = raw_store.history('u')
                self.assertEqual([m['text'] for s in history['sessions'] for m in s['messages']], bodies)
                self.assertEqual(raw_store.history('other')['sessions'], [])

    def test_no_control_preserves_evidence(self):
        evidence = [dict(id='e', text='Unrelated source.', source_ids=['s'])]
        out, trace = finalize('What is my project color?', evidence, [], {'audits': []})
        self.assertEqual(out, evidence)
        self.assertTrue(trace['scoped_parity'])


if __name__ == '__main__':
    unittest.main()

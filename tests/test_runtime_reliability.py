"""Fault injection against real HTTP handlers, real SQLite and real validators.

No provider traffic. Synthetic memories only. Run separately or via discovery.
"""
import concurrent.futures
import copy
import contextlib
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from tests import test_http as fixture
from app import config, llm, store, updates, runtime, embed
from fastapi.testclient import TestClient
from memory_benchmark.pipeline.context import GPTTokenizer
from mneme_asterion.state.policy import generate_state_policy, add_policy_notice
from mneme_asterion.state.withdrawal import generate_withdrawal
from mneme_asterion.state.projection import finalize
import httpx
import openai

s = fixture.s


def reply(value, finish='stop', refusal=None):
    return NS(choices=[NS(message=NS(content=value, refusal=refusal), finish_reason=finish)])


class Replies:
    def __init__(self, values):
        self.values, self.count, self.requests = values, 0, []
        self.chat = self.completions = self
    def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        value = self.values[min(self.count, len(self.values)-1)]
        self.count += 1
        if isinstance(value, Exception): raise value
        return reply(value) if isinstance(value, str) else value


def raw(n, text):
    return dict(id=str(n), body=text, text=text, role='user', speaker='user',
                source_ids=[str(n)], session=0, message=n, timestamp=None)


class RuntimeReliability(unittest.TestCase):
    def test_explicit_old_value_retry_does_not_accept_other_number(self):
        record=dict(old_value='12',new_value='18')
        validate=updates.replacement_validator(record,[NS(content='The semi-perimeter is 28.')])
        bad=json.dumps({'memories':[dict(n=0,value='28',compared_to_new='DIFFERENT')]})
        good=json.dumps({'memories':[dict(n=0,replaced=False,value=None)]})
        client=Replies([bad]*config.PROVIDER_ATTEMPTS+[good])
        with patch.object(llm,'_get_client',return_value=client),patch.object(runtime.time,'sleep'):
            self.assertEqual(llm.verify_replaced_v2('12 replaced by 18',['The semi-perimeter is 28.'],validate_replacement=validate),[])
        self.assertIn('OLD_VALUE',client.requests[-1]['messages'][1]['content'])
        self.assertEqual(client.count,config.PROVIDER_ATTEMPTS+1)

    def test_explicit_old_value_uncertain_is_not_negative(self):
        validate=updates.replacement_validator(dict(old_value='12',new_value='18'),[NS(content='The semi-perimeter is 28.')])
        invalid=json.dumps({'memories':[dict(n=0,replaced=None,value=None)]})
        with patch.object(llm,'_get_client',return_value=Replies([invalid])),patch.object(runtime.time,'sleep'),runtime.request_scope():
            self.assertIsNone(llm.verify_replaced_v2('12 replaced by 18',['The semi-perimeter is 28.'],validate_replacement=validate))

    def test_source_span_copies_timestamps_and_no_fabrication(self):
        from mneme_asterion.retrieval.quotes import source_lines,expand_source_spans
        body='if you add a tile\n13:30\ndraw a mission card\n'
        self.assertEqual(''.join(source_lines(body)),body)
        value={'scope':{'operation':'fact'},'supports':[dict(source_id='0',start_line=0,end_line=2)]}
        self.assertEqual(expand_source_spans(value,[raw(0,body)],'Question')['supports'][0]['quote'],body)
        for a,z in [(True,2),(-1,2),(0,3),(2,1)]:
            value['supports'][0].update(start_line=a,end_line=z)
            with self.assertRaises(AssertionError):expand_source_spans(value,[raw(0,body)],'Question')

    def test_source_span_rejects_parent_id_with_actionable_feedback(self):
        from mneme_asterion.retrieval.quotes import expand_source_spans
        source=raw(0,'An exact source.');source['source_ids']=['parent-message']
        value={'scope':{'operation':'fact'},'supports':[dict(source_id='parent-message',start_line=0,end_line=0)]}
        with self.assertRaisesRegex(AssertionError,'allowed list'):
            expand_source_spans(value,[source],'Question')

    def test_source_span_prompt_has_one_identifier_namespace(self):
        from mneme_asterion.retrieval.quotes import select_source_spans
        source=raw(0,'An exact source.');source['source_ids']=['parent-message']
        def call(prompt,stage,validate):
            data=json.loads(prompt.rsplit('\n',1)[1]);entry=data['CANDIDATES'][0]
            self.assertEqual(entry['source_id'],'0');self.assertNotIn('source_ids',entry);self.assertNotIn('id',entry)
            value={'scope':dict(operation='fact',requested_relation='test'), 'supports':[dict(source_id='0',start_line=0,end_line=0,purpose='premise',reason='Relevant exact evidence.')]}
            validate(value);return value
        out,_=select_source_spans({},[source],'Question','',call)
        self.assertEqual(out['supports'][0]['quote'],source['body'])

    def test_compound_scope_rejected_with_single_enum_feedback(self):
        from mneme_asterion.retrieval.planning import scope_check,SCOPE_SELECT
        value={'scope':dict(subject_quote='Question',requested_relation='count and attribute',operation='count|fact'),'supports':[]}
        with self.assertRaisesRegex(AssertionError,'exactly one string'):
            scope_check(value,[],'Question','')
        value['scope']['operation']='other'
        scope_check(value,[],'Question','')
        self.assertNotIn('fact|list|count',SCOPE_SELECT)

    def test_source_span_fallback_only_schema_failure(self):
        from mneme_asterion.retrieval.quotes import generate_r1q
        question='What is my color?';body='My color is violet.';seen=[]
        def call(prompt,stage,valid):
            seen.append(stage)
            if stage=='R1_E_plan':v={'needed':True,'queries':['color']}
            elif stage=='R1Q_scope_select':raise llm.UpstreamUnavailable(503,1,'invalid upstream response: R1Q_scope_select')
            else:
                payload=json.loads(prompt.rsplit('\n',1)[1]);source=payload['CANDIDATES'][0]
                v={'scope':dict(operation='fact',requested_relation='color'),'supports':[dict(source_id=source['source_id'],start_line=0,end_line=len(source['lines'])-1,purpose='premise',reason='Explicit stated user color.')]}
            valid(v);return v
        out,trace=generate_r1q(question,[],[raw(0,body)],call,self.tok)
        self.assertIn('violet',str(out));self.assertTrue(trace['source_span_retry']['same_candidates'])
        self.assertEqual(seen,['R1_E_plan','R1Q_scope_select','R1Q_source_span_select'])
        def unavailable(prompt,stage,valid):
            if stage=='R1_E_plan':return {'needed':True,'queries':['color']}
            raise llm.UpstreamUnavailable(503,1,'upstream temporarily unavailable')
        with self.assertRaises(llm.UpstreamUnavailable):generate_r1q(question,[],[raw(0,body)],unavailable,self.tok)

    def test_replacement_gate_retries_before_persisting(self):
        self.add('gate-db','old','I live in Rome. I once visited Oslo.');self.add('gate-db','new','I now live in Paris.')
        index=store.get('gate-db');old,new=[i for i in index.items if i.kind=='raw']
        record=dict(id='gate-update',item_id=new.id,subject='User',attribute='location',new_value='Paris',old_value='Rome')
        bodies=[json.dumps({'memories':[dict(n=0,value=value,compared_to_new='DIFFERENT')]}) for value in ['Oslo','Rome']]
        client=Replies(bodies)
        with patch.object(updates,'candidates',return_value=[index.by_id[old.id]]),patch.object(updates,'_chunk_facts',return_value=True),patch.object(llm,'_get_client',return_value=client),patch.object(runtime.time,'sleep'):
            out,complete=updates.resolve(index,'gate-db',[record])
        self.assertTrue(complete);self.assertEqual(client.count,2);self.assertIn(old.id,out['gate-update'])
        self.assertIn('existing replacement gate',client.requests[1]['messages'][-1]['content'])
        self.assertEqual(store.get_checks('gate-db')[('gate-update',old.id)],(True,'Rome'))

    def test_replacement_gate_batch_offsets(self):
        checked=[]
        class Verifier:
            def __init__(self):self.chat=self.completions=self
            def create(self,**kw):
                import re
                indices=re.findall(r'^(\d+) \| ',kw['messages'][1]['content'],re.MULTILINE)
                return reply(json.dumps({'memories':[dict(n=int(n),value='violet',compared_to_new='DIFFERENT') for n in indices]}))
        with patch.object(llm,'_get_client',return_value=Verifier()):
            result=llm.verify_replaced_v2('new amber',['violet']*17,validate_replacement=lambda n,q:checked.append(n))
        self.assertEqual(checked,list(range(17)));self.assertEqual(len(result),17)

    def test_one_statement_two_distinct_updates(self):
        values=[dict(statement=0,subject='me',attribute=attribute,new_value=value,old_value=None,subject_is_user=True,relative=False,current='My '+attribute+' is '+value) for attribute,value in [('charisma','15'),('intelligence','13')]]
        client=Replies([json.dumps({'updates':values})])
        text='Change charisma to 15 and intelligence to 13.'
        with patch.object(llm,'_get_client',return_value=client):
            got=llm.extract_updates('0 | I: '+text,[(0,text)])
        self.assertEqual(len(got),2);self.assertEqual([x['statement'] for x in got],[0,0])

    def test_same_attribute_duplicate_rejected(self):
        value=dict(statement=0,subject='me',attribute='color',new_value='blue',old_value=None,subject_is_user=True,relative=False,current='My color is blue')
        client=Replies([json.dumps({'updates':[value,value]})])
        with patch.object(llm,'_get_client',return_value=client),patch.object(runtime.time,'sleep'),runtime.request_scope():
            self.assertEqual(llm.extract_updates('0 | I: My color is blue',[(0,'My color is blue')]), [])

    def test_quote_unique_linewrap_returns_exact_original(self):
        from mneme_asterion.retrieval.quotes import reconcile_quotes
        source=raw(0,'The higher sum\nwould be the predicted winner.')
        value={'supports':[dict(source_id='0',quote='The higher sum would be the predicted winner.')]}
        got=reconcile_quotes(value,[source])
        self.assertEqual(got['supports'][0]['quote'],source['body'])
        self.assertEqual(got['literal_identity_repair']['dropped'],[])

    def test_quote_linewrap_does_not_repair_word_or_ambiguous_changes(self):
        from mneme_asterion.retrieval.quotes import reconcile_quotes
        for quote,body in [('higher sum','lower sum'),('a b','a\nb and a\tb'),('28 cm','28 meters')]:
            got=reconcile_quotes({'supports':[dict(source_id='0',quote=quote)]},[raw(0,body)])
            self.assertEqual(got['supports'],[])
            self.assertTrue(got['literal_identity_repair']['dropped'])

    def test_verifier_feedback_identifies_exact_numbered_source(self):
        bad=json.dumps({'memories':[dict(n=0,value='s = 28 cm',compared_to_new='DIFFERENT')]})
        good=json.dumps({'memories':[dict(n=0,value='28',compared_to_new='DIFFERENT')]})
        client=Replies([bad,good])
        with patch.object(llm,'_get_client',return_value=client),patch.object(runtime.time,'sleep'):
            result=llm.verify_replaced_v2('New value 18',[r's = 28 \text{ cm}'])
        self.assertEqual(result,[(0,'28')])
        self.assertIn('exact_memory',client.requests[1]['messages'][-1]['content'])
        self.assertIn('LaTeX',client.requests[1]['messages'][-1]['content'])

    def test_verifier_reports_all_bad_quotes_and_missing_indices(self):
        bad=json.dumps({'memories':[dict(n=n,value='s = 15 cm',compared_to_new='DIFFERENT') for n in range(2)]})
        missing=json.dumps({'memories':[dict(n=0,value='15',compared_to_new='DIFFERENT')]})
        good=json.dumps({'memories':[dict(n=n,value='15',compared_to_new='DIFFERENT') for n in range(2)]})
        client=Replies([bad,missing,good])
        with patch.object(llm,'_get_client',return_value=client),patch.object(runtime.time,'sleep'):
            self.assertEqual(llm.verify_replaced_v2('New value 18',[r's = (8+10+12)/2 = 15 \text{ cm}']*2),[(0,'15'),(1,'15')])
        feedback=client.requests[1]['messages'][-1]['content']
        self.assertIn('"n": 0',feedback);self.assertIn('"n": 1',feedback)
        self.assertIn('missing n=[1]',client.requests[2]['messages'][-1]['content'])

    def test_empty_candidates_preserves_base_without_selector(self):
        from mneme_asterion.retrieval.quotes import generate_r1q
        base=[{'id':'rule','text':'Only use numbered lists.'}]
        client=Replies([json.dumps({'needed':True,'queries':['printer']})])
        with patch.object(llm,'_get_client',return_value=client):
            result,trace=generate_r1q('Compare these printers.',base,[],s.call,self.tok)
        self.assertEqual(result,base)
        self.assertTrue(trace['no_candidate_parity'])
        self.assertEqual(client.count,1)

    def test_intent_assistant_rejected_then_user_retry(self):
        numbered='0 | Assistant: My color is blue.\n1 | I: My color is amber.'
        bad=json.dumps({'statements':[dict(turn=0,label='CORRECTION',quote='My color is blue.')]})
        good=json.dumps({'statements':[dict(turn=1,label='CORRECTION',quote='My color is amber.')]})
        client=Replies([bad,good])
        with patch.object(llm,'_get_client',return_value=client),patch.object(runtime.time,'sleep'):
            self.assertEqual(llm.classify_update_intent(numbered)[0]['turn'],1)
        self.assertEqual(client.count,2)

    def test_intent_identical_duplicate_is_one_statement(self):
        entry=dict(turn=0,label='CORRECTION',quote='My color is amber.')
        with patch.object(llm,'_get_client',return_value=Replies([json.dumps({'statements':[entry,entry]})])):
            self.assertEqual(len(llm.classify_update_intent('0 | I: My color is amber.')),1)

    def test_markdown_escape_recovers_exact_source_not_paraphrase(self):
        source=r"It's get\_data\_loaders, not get\_loader!"
        self.assertEqual(llm._source_value("get_data_loaders",source,'new_value'),r'get\_data\_loaders')
        with self.assertRaises(runtime.InvalidResponse):llm._source_value('fetch_data_loader',source,'new_value')
        with self.assertRaises(runtime.InvalidResponse):llm._source_value('a_b',r'a\_b and a\_b','new_value')

    def test_update_value_recovers_only_unique_whitespace_source_span(self):
        source='I renamed it to “Multi-path\nUncertainty-aware Score Distributions Learning".'
        value='“Multi-path Uncertainty-aware Score Distributions Learning'
        self.assertEqual(llm._source_value(value,source,'new_value'),'“Multi-path\nUncertainty-aware Score Distributions Learning')
        with self.assertRaises(runtime.InvalidResponse):llm._source_value('Different Learning',source,'new_value')
        with self.assertRaises(runtime.InvalidResponse):llm._source_value('Multi path',source,'new_value')
        with self.assertRaises(runtime.InvalidResponse):llm._source_value('two words','two\nwords and two\twords','new_value')

    def test_update_value_error_names_field_and_original_source(self):
        with self.assertRaises(runtime.InvalidResponse) as raised:
            llm._source_value('teal','I prefer amber.','new_value')
        self.assertIn('new_value',str(raised.exception))
        self.assertIn('I prefer amber.',str(raised.exception))

    def test_withdrawal_repair_feedback_keeps_invalid_edits_rejected(self):
        from mneme_asterion.state.withdrawal import normalize_edits,edit_rejection_message
        base=[{'id':'e','text':'I like protest marches.'}];controls=[raw(0,'Forget that I like protest marches.')]
        value={'edits':[dict(evidence_id='e',control_id='0',span='I like protest rallies.',control_quote='I like protest marches')]}
        result=normalize_edits(value,base,controls)
        self.assertEqual(result['edits'],[])
        self.assertEqual(len(result['dropped_nonliteral']),1)
        feedback=edit_rejection_message(result['dropped_nonliteral'],base,controls)
        self.assertIn('I like protest marches.',feedback)
        self.assertIn('nonunique_or_missing_literal_span',feedback)
        self.assertIn('Do not invent',feedback)

    def test_quote_error_echoes_only_proposed_candidate_bodies(self):
        from mneme_asterion.retrieval.quotes import quote_rejection_message
        text=quote_rejection_message([{'proposal':{'source_id':'0'},'reason':'quote_not_in_any_candidate'}],[raw(0,'Actual quoted sentence.'),raw(1,'Unselected unrelated sentence.')])
        self.assertIn('Actual quoted sentence.',text)
        self.assertNotIn('Unselected unrelated sentence.',text)
        self.assertIn('Allowed candidate IDs',text)

    def test_duplicate_literal_fragments_merge_without_losing_quotes(self):
        from mneme_asterion.retrieval.quotes import reconcile_quotes
        source=raw(0,'Use good form. Ask a trainer. Start small.')
        value={'supports':[{'source_id':'0','quote':'Use good form.'},{'source_id':'0','quote':'Start small.'}]}
        result=reconcile_quotes(value,[source])
        self.assertEqual(result['supports'][0]['quote'],source['body'])
        self.assertEqual(len(result['supports']),1)
        self.assertEqual(result['literal_identity_repair']['dropped'],[])
        value['supports'].append({'source_id':'0','quote':'Invented safety advice.'})
        result=reconcile_quotes(value,[source])
        self.assertEqual(result['literal_identity_repair']['dropped'][0]['reason'],'quote_not_in_any_candidate')

    def test_duplicate_fragment_does_not_merge_ambiguous_locations(self):
        from mneme_asterion.retrieval.quotes import reconcile_quotes
        source=raw(0,'Start small. Rest. Start small. Use good form.')
        value={'supports':[{'source_id':'0','quote':'Start small.'},{'source_id':'0','quote':'Use good form.'}]}
        result=reconcile_quotes(value,[source])
        self.assertEqual(result['literal_identity_repair']['dropped'][0]['reason'],'ambiguous_duplicate_fragment')
        value['supports'][1]['quote']='Start small.'
        result=reconcile_quotes(value,[source])
        self.assertEqual(len(result['supports']),1)
        self.assertEqual(result['literal_identity_repair']['dropped'],[])

    def test_scope_retry_offers_only_literal_question_not_an_answer(self):
        from mneme_asterion.retrieval.planning import scope_check
        value={'supports':[], 'scope':{'subject_quote':'an invented paraphrase','requested_relation':'time','operation':'time'}}
        question='When was the old area flooded?'
        with self.assertRaisesRegex(AssertionError,question.replace('?','\\?')):
            scope_check(value,[],question,'')
        value['scope']['subject_quote']=question
        scope_check(value,[],question,'')

    def test_fact_cap_preserves_original_policy_after_full_validation(self):
        with patch.object(config,'LLM_MAX_FACTS',2):
            self.assertEqual(llm._facts_payload({'facts':['a','b','c']}),['a','b'])
            with self.assertRaises(runtime.InvalidResponse):llm._facts_payload({'facts':['a','b',None]})
            with self.assertRaises(runtime.InvalidResponse):llm._facts_payload({'facts':['a','b',{}]})

    def test_retry_feedback_and_truncation_budget(self):
        captured=[]
        def create(**kw):
            captured.append({**kw,'messages':[dict(m) for m in kw['messages']]})
            return reply('{"x":1}', 'length' if len(captured)==1 else 'stop')
        client=NS(chat=NS(completions=NS(create=create)))
        messages=[{'role':'user','content':'Return JSON x'}]
        with patch.object(llm,'_get_client',return_value=client):
            out=runtime.chat('test',messages,500,json.loads)
        self.assertEqual(out,{'x':1})
        self.assertEqual(len(messages),1)
        self.assertEqual(len(captured[0]['messages']),1)
        self.assertEqual(len(captured[1]['messages']),3)
        self.assertEqual(captured[1]['max_tokens'],1012)
        self.assertIn('copied exactly',captured[1]['messages'][-1]['content'])

    def test_targeted_quote_retry_preserves_source_validation(self):
        client=Replies(['{"statements":[{"turn":0,"label":"NEW_INFO","quote":"Everything is fine."}]}',
                        '{"statements":[{"turn":0,"label":"NEW_INFO","quote":"It is fine,"}]}'])
        with patch.object(llm,'_get_client',return_value=client):
            result=llm.classify_update_intent('0 | I: It is fine, but I will check.')
        self.assertEqual(result[0]['quote'],'It is fine,')
        feedback=client.requests[-1]['messages'][-1]['content']
        self.assertIn('exact_source',feedback)
        self.assertIn('It is fine, but I will check.',feedback)
        self.assertEqual(client.count,2)

    def test_quote_boundary_alignment_is_literal_and_unique(self):
        client=Replies(['{"statements":[{"turn":0,"label":"NEW_INFO","quote":"...Doctors said everything is fine..."}]}'])
        with patch.object(llm,'_get_client',return_value=client):
            result=llm.classify_update_intent('0 | I: Doctors said everything is fine, but I will check.')
        self.assertEqual(result[0]['quote'],'Doctors said everything is fine')
        self.assertEqual(client.count,1)
        for source in ['0 | I: Doctors said everything is NOT fine.',
                       '0 | I: Doctors said everything is fine, Doctors said everything is fine,']:
            client=Replies(['{"statements":[{"turn":0,"label":"NEW_INFO","quote":"...Doctors said everything is fine..."}]}'])
            with patch.object(llm,'_get_client',return_value=client), runtime.request_scope():
                self.assertEqual(llm.classify_update_intent(source), [])

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.stack = contextlib.ExitStack()
        cls.stack.enter_context(patch.object(config, 'DB_PATH', str(Path(cls.tmp.name)/'memory.sqlite3')))
        cls.stack.enter_context(patch.object(config, 'RETRY_BASE', 0))
        cls.stack.enter_context(patch.object(config, 'RETRY_AFTER', 0))
        cls.stack.enter_context(patch.object(config, 'PROVIDER_ATTEMPTS', 3))
        if store._conn is not None:
            try: store._conn.close()
            except Exception: pass
        store._conn = None; store._cache.clear(); store._cached_items = 0
        updates._resolved.clear(); updates._scope_cache.clear()
        cls.client = cls.stack.enter_context(TestClient(s.app, raise_server_exceptions=False))
        cls.headers = {'Authorization':'Bearer offline-test'}
        cls.tok = GPTTokenizer('gpt-4o-mini')

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()
        store._conn.close(); store._conn = None
        cls.tmp.cleanup()

    def add(self, user, rid, text):
        return self.client.post('/add', headers=self.headers, json=dict(
            user_id=user, request_id=rid, session_id='s', messages=[dict(role='user',content=text)]))

    def history(self, user):
        return [m['text'] for session in s.raw_store.history(user)['sessions'] for m in session['messages']]

    def test_01_invalid_facts_degrade_to_durable_raw(self):
        for i, value in enumerate(['', '{}', '{"facts":null}', '{"facts":[null,42]}',
                                   '{"facts":[{"text":"x"}]}', '{"facts":["x"]',
                                   reply('{"facts":["x"]}', 'length'),
                                   reply('{"facts":["x"]}', refusal='refused')]):
            with self.subTest(response=i):
                client = Replies([value]); user = 'badfacts'+str(i)
                with patch.object(llm, '_get_client', return_value=client), patch.object(updates, 'detect', return_value=[]):
                    response = self.add(user, 'a', 'I live in Rome.')
                self.assertEqual(response.status_code, 200)
                self.assertTrue(store.request_seen('a', user))
                self.assertEqual(self.history(user), ['I live in Rome.'])
                self.assertTrue(store.get(user).items)
                self.assertTrue(all(i.kind == 'raw' for i in store.get(user).items))
                self.assertEqual(client.count, 3)

    def test_02_valid_empty_extraction_is_success(self):
        with patch.object(llm, '_get_client', return_value=Replies(['{"facts":[]}'])), patch.object(updates, 'detect', return_value=[]):
            self.assertEqual(self.add('empty-valid', 'a', 'Hello.').status_code, 200)
        self.assertEqual(self.history('empty-valid'), ['Hello.'])
        self.assertEqual([i.kind for i in store.get('empty-valid').items], ['raw'])

    def test_03_retry_same_id_after_failure_then_deduplicate(self):
        with patch.object(s.original.native, 'encode_or_unavailable', side_effect=llm.UpstreamUnavailable(503,1,'embedding fault')):
            self.assertEqual(self.add('retry', 'a', 'I live in Rome.').status_code, 503)
        self.assertEqual(self.add('retry', 'a', 'I live in Rome.').status_code, 200)
        before = len(store.get('retry').items)
        with patch.object(llm, '_get_client', side_effect=AssertionError('duplicate called provider')):
            self.assertEqual(self.add('retry', 'a', 'I live in Rome.').status_code, 200)
        self.assertEqual(len(store.get('retry').items), before)
        self.assertEqual(self.add('retry', 'a', 'Different.').status_code, 409)

    def test_04_failed_update_detection_blocks_commit(self):
        with patch.object(llm, 'classify_update_intent', return_value=None):
            response = self.add('intent-failed', 'a', 'My address changed to Rome.')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(store.request_seen('a','intent-failed'))
        self.assertEqual(self.history('intent-failed'), [])

    def test_05_missing_update_fields_are_unknown(self):
        for body in ['{}', '{"statements":[null]}', '{"statements":[{"turn":0,"label":"GARBAGE","quote":"x"}]}']:
            with self.subTest(body=body), patch.object(llm, '_get_client', return_value=Replies([body])):
                self.assertEqual(llm.classify_update_intent('0 | I: x'), [])
        with patch.object(llm, '_get_client', return_value=Replies(['{"updates":[]}'])):
            self.assertEqual(llm.extract_updates('0 | I: Update my address to Rome.', [(0,'Update my address to Rome.')]), [])

    def test_06_complete_verdict_required(self):
        memories = ['My color is violet.', 'My color is amber.']
        for body in ['{}', '{"memories":[]}', '{"memories":[{"n":0,"value":"violet","compared_to_new":"DIFFERENT"}]}',
                     '{"memories":[{"n":0,"value":null,"compared_to_new":"OTHER"},{"n":0,"value":null,"compared_to_new":"OTHER"}]}',
                     '{"memories":[{"n":0,"value":"invented","compared_to_new":"DIFFERENT"},{"n":1,"value":null,"compared_to_new":"OTHER"}]}']:
            with self.subTest(body=body), patch.object(llm, '_get_client', return_value=Replies([body])):
                self.assertIsNone(llm.verify_replaced_v2('new amber', memories))
        valid = '{"memories":[{"n":0,"value":"violet","compared_to_new":"DIFFERENT"},{"n":1,"value":"amber","compared_to_new":"SAME"}]}'
        with patch.object(llm, '_get_client', return_value=Replies([valid])):
            self.assertEqual(llm.verify_replaced_v2('new amber', memories), [(0,'violet')])

    def test_07_unknown_verification_never_persists_negative(self):
        self.add('verify-db', 'old', 'I live in Rome.'); self.add('verify-db', 'new', 'I now live in Paris.')
        index = store.get('verify-db'); old,new = [i for i in index.items if i.kind=='raw']
        record = dict(id='update-db', item_id=new.id, subject='User',attribute='location',new_value='Paris',old_value='Rome')
        with patch.object(updates,'candidates',return_value=[index.by_id[old.id]]), patch.object(llm,'_get_client',return_value=Replies(['{}'])):
            _,complete = updates.resolve(index,'verify-db',[record])
        self.assertFalse(complete); self.assertNotIn(('update-db',old.id), store.get_checks('verify-db'))
        body = '{"memories":[{"n":0,"value":"Rome","compared_to_new":"DIFFERENT"}]}'
        client=Replies([body])
        with patch.object(updates,'candidates',return_value=[index.by_id[old.id]]), patch.object(updates,'_chunk_facts',return_value=True), patch.object(llm,'_get_client',return_value=client):
            out,complete=updates.resolve(index,'verify-db',[record])
        self.assertTrue(complete); self.assertEqual(client.count,1); self.assertIn(old.id,out['update-db'])

    def test_08_invalid_notice_no_empty_recovery(self):
        history=[raw(0,'My project color is violet.'),raw(1,'Please forget my project color.')]
        with patch.object(llm,'_get_client',return_value=Replies(['not json'])):
            with self.assertRaises(llm.UpstreamUnavailable):
                add_policy_notice('What is my project color?',[],history,s.call,self.tok)

    def test_09_invalid_deletion_no_empty_recovery(self):
        history=[raw(0,'My project color is violet.'),raw(1,'Please forget my project color.')]
        base=[dict(id='e',text='My project color is violet.',source_ids=['0'])]
        value=json.dumps({'edits':[dict(evidence_id='bad',span='nonexistent',control_id='bad',control_quote='nonexistent')]})
        with patch.object(llm,'_get_client',return_value=Replies([value])):
            with self.assertRaises(llm.UpstreamUnavailable):
                generate_withdrawal('What is my project color?',base,history,s.call,self.tok)

    def test_10_compound_withdrawal_fault_never_returns_old_value(self):
        self.add('compound','a','My project color is violet.');self.add('compound','b','Please forget my project color.')
        base=[dict(id='e',text='My project color is violet.',source_ids=['0'])]
        # Real P2 chain; skip only native retrieval and R1Q to target P2 failure.
        with patch.object(s.original.native,'search',return_value={'data':[{'id':'e','content':base[0]['text']}]}), \
             patch.object(s,'generate_r1q',return_value=(base,{})), patch.object(llm,'_get_client',return_value=Replies(['not json'])):
            response=self.client.post('/search',headers=self.headers,json=dict(user_id='compound',query='What is my project color and what are my hobbies?',top_k=100))
        self.assertEqual(response.status_code,200); self.assertNotIn('violet',response.text);self.assertEqual(response.json()['data'][0]['id'],'rc15-state-unavailable')

    def test_11_valid_empty_and_valid_repair_still_allowed(self):
        client=Replies(['{"relevant_control_ids":[],"reason":"unrelated"}'])
        history=[raw(0,'Please forget my project color.')]
        with patch.object(llm,'_get_client',return_value=client):
            evidence,_=add_policy_notice('What is the weather?',[],history,s.call,self.tok)
        self.assertEqual(evidence,[]);self.assertEqual(client.count,1)

    def test_12_schema_retry_does_not_use_stale_value(self):
        calls=[]
        def valid(v):
            calls.append(v);raise ValueError('invalid')
        valid.recover=lambda v: self.fail('recovery must never be called')
        with patch.object(llm,'_get_client',return_value=Replies(['{"old":true}','bad','bad'])):
            with self.assertRaises(llm.UpstreamUnavailable):s.call('sys\n{}','test',valid)
        self.assertEqual(calls,[{'old':True}])

    def test_13_network_retry_then_success_and_retry_after(self):
        response=httpx.Response(429,request=httpx.Request('POST','https://fixture.invalid'),headers={'retry-after':'2'})
        err=openai.RateLimitError('fixture',response=response,body=None)
        client=Replies([err,'{"ok":true}'])
        with patch.object(llm,'_get_client',return_value=client), patch.object(runtime.time,'sleep') as sleep:
            self.assertEqual(s.call('sys\n{}','test',lambda v:None),{'ok':True})
        self.assertEqual(client.count,2);self.assertEqual(sleep.call_args.args[0],2)

    def test_14_permanent_errors_never_retry(self):
        for code,kind in [(400,openai.BadRequestError),(401,openai.AuthenticationError),(403,openai.PermissionDeniedError),(404,openai.NotFoundError)]:
            response=httpx.Response(code,request=httpx.Request('POST','https://fixture.invalid'))
            client=Replies([kind('SECRET_BODY_MUST_NOT_LEAK',response=response,body=None)])
            with self.subTest(code=code),patch.object(llm,'_get_client',return_value=client):
                with self.assertRaises(runtime.PermanentProviderError):s.call('sys\n{}','test',lambda v:None)
            self.assertEqual(client.count,1)

    def test_15_deadline_prevents_new_calls_and_commit(self):
        with runtime.request_scope():
            runtime._state.get().deadline=time.monotonic()-1
            with patch.object(llm,'_get_client',side_effect=AssertionError('must not call provider')):
                with self.assertRaises(llm.UpstreamUnavailable):s.call('sys\n{}','test',lambda v:None)

    def test_16_capacity_wait_is_bounded(self):
        gate=threading.Semaphore(0);started=time.monotonic()
        with patch.object(config,'GATE_WAIT',0.02):
            with self.assertRaises(llm.UpstreamUnavailable):
                with runtime.acquire(gate,'test'):self.fail('entered full gate')
        self.assertLess(time.monotonic()-started,0.5)

    def test_17_backoff_does_not_hold_slot(self):
        gate=threading.Semaphore(1);error=openai.APITimeoutError(request=httpx.Request('POST','https://fixture.invalid'))
        client=Replies([error,'{"ok":true}'])
        def sleep(_):
            self.assertTrue(gate.acquire(blocking=False));gate.release()
        with patch.object(llm,'_gate',gate),patch.object(llm,'_get_client',return_value=client),patch.object(runtime.time,'sleep',side_effect=sleep):
            s.call('sys\n{}','test',lambda v:None)

    def test_18_failed_add_interleaved_restore_uses_commit_order(self):
        uid='ordered';self.add(uid,'initial','My project color is violet.')
        with patch.object(s.original.native,'encode_or_unavailable',side_effect=llm.UpstreamUnavailable(503,1,'fixture')):
            self.assertEqual(self.add(uid,'withdraw','Please forget my project color.').status_code,503)
        self.assertEqual(self.add(uid,'restore','Please remember my project color again: amber.').status_code,200)
        self.assertEqual(self.add(uid,'withdraw','Please forget my project color.').status_code,200)
        bodies=self.history(uid)
        self.assertEqual(bodies,['My project color is violet.','Please remember my project color again: amber.','Please forget my project color.'])
        with patch.object(llm,'_get_client',side_effect=AssertionError('duplicate')):
            self.assertEqual(self.add(uid,'withdraw','Please forget my project color.').status_code,200)
        self.assertEqual(self.history(uid),bodies)
        # Use the public adapter with actual persisted raw history and database.
        from mneme_asterion.state.adapter import apply
        from e_core.methods import raw_records
        raw_data=raw_records(s.raw_store.history(uid),self.tok.count)
        evidence=[dict(id='a',text='My project color is amber.',source_ids=[])]
        out,trace=apply('What is my project color?',evidence,raw_data,config.DB_PATH,uid,self.tok.count)
        self.assertNotIn('amber',str(out))

    def test_19_atomic_rollback_does_not_leak_into_later_commit(self):
        original=store._insert_updates
        def fail(*args):raise sqlite3.OperationalError('injected after item writes')
        rec=[dict(id='dummy')]
        with patch.object(updates,'detect',return_value=rec),patch.object(config,'UPDATE_RENDER',False),patch.object(store,'_insert_updates',side_effect=fail):
            response=self.add('atomic','failed','I live in Rome.')
        self.assertEqual(response.status_code,500)
        self.assertEqual(store._conn.execute("SELECT COUNT(*) FROM items WHERE user_id='atomic'").fetchone()[0],0)
        self.add('another','ok','Unrelated valid text.')
        self.assertEqual(store._conn.execute("SELECT COUNT(*) FROM items WHERE user_id='atomic'").fetchone()[0],0)
        self.assertFalse(store.request_seen('failed','atomic'));self.assertEqual(self.history('atomic'),[])

    def test_20_restart_reloads_order_and_idempotence(self):
        uid='restart';self.add(uid,'a','First.');self.add(uid,'b','Second.')
        store._conn.close();store._conn=None;store._cache.clear();store._cached_items=0
        store.init();s.raw_store.init()
        self.assertTrue(store.request_seen('a',uid));self.assertEqual(self.history(uid),['First.','Second.'])

    def test_21_user_lock_has_no_bucket_collision(self):
        with s.original.user_lock('collision-11'):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                def other():
                    with s.original.user_lock('collision-16'):return True
                self.assertTrue(pool.submit(other).result(timeout=0.5))

    def test_22_future_drains_before_failed_add_returns(self):
        entered=threading.Event();release=threading.Event()
        def detect(_):entered.set();release.wait(2);return []
        def extract(_):
            self.assertTrue(entered.wait(1));raise llm.UpstreamUnavailable(503,1,'fixture')
        with patch.object(updates,'detect',side_effect=detect),patch.object(llm,'extract_facts',side_effect=extract),concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(self.add,'drain','a','I live in Rome.')
            self.assertTrue(entered.wait(1));time.sleep(.03);self.assertFalse(pending.done())
            release.set();self.assertEqual(pending.result(timeout=2).status_code,503)
        self.assertFalse(store.request_seen('a','drain'))

    def test_23_multiline_source_indices_are_not_line_indices(self):
        numbered='0 | I: line one\nline two\n1 | I: Update my color to amber.'
        body='{"statements":[{"turn":1,"label":"EXPLICIT_REPLACEMENT","quote":"Update my color to amber."}]}'
        with patch.object(llm,'_get_client',return_value=Replies([body])):
            self.assertEqual(llm.classify_update_intent(numbered)[0]['turn'],1)

    def test_24_provider_failure_does_not_expose_secrets(self):
        response=httpx.Response(401,request=httpx.Request('POST','https://fixture.invalid'))
        err=openai.AuthenticationError('SECRET_RESPONSE',response=response,body=None)
        with patch.object(llm,'_get_client',return_value=Replies([err])),patch.object(updates,'detect',return_value=[]):
            response=self.add('auth-failed','a','Hello.')
        self.assertEqual(response.status_code,502)
        self.assertFalse(response.json()['detail']['retryable']);self.assertNotIn('SECRET_RESPONSE',response.text)

    def test_25_embedding_invalid_vectors_not_persisted(self):
        fake=NS(embeddings=NS(create=lambda **kw:NS(data=[])))
        with patch.object(embed,'_get_remote_client',return_value=(fake,threading.Semaphore(1))):
            with self.assertRaises(llm.UpstreamUnavailable):embed._encode_remote(['source'])

    def test_26_request_context_reaches_detection_thread(self):
        with runtime.request_scope():
            state=runtime._state.get()
            with patch.object(updates,'detect',side_effect=lambda _:runtime._state.get()):
                self.assertIs(updates.start_detection([]).result(timeout=1),state)

    def test_27_rejected_old_database_untouched(self):
        path=Path(self.tmp.name)/'legacy.sqlite3';db=sqlite3.connect(path)
        db.execute('CREATE TABLE requests (user_id TEXT,request_id TEXT)');db.execute("INSERT INTO requests VALUES ('old','old')");db.commit();db.close()
        live=store._conn;store._conn=None
        try:
            with patch.object(config,'DB_PATH',str(path)),self.assertRaises(RuntimeError):store.init()
        finally:store._conn=live
        with contextlib.closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT * FROM requests').fetchall(),[('old','old')])
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[('requests',)])

    def test_28_verifier_batches_cover_every_input(self):
        class Verifier:
            def __init__(self):self.chat=self.completions=self;self.sizes=[]
            def create(self,**kw):
                import re
                numbers=re.findall(r'^(\d+) \| ',kw['messages'][1]['content'],re.MULTILINE)
                self.sizes.append((len(numbers),kw['max_tokens']))
                return reply(json.dumps({'memories':[dict(n=int(n),value=None,compared_to_new='OTHER') for n in numbers]}))
        client=Verifier()
        with patch.object(llm,'_get_client',return_value=client):
            self.assertEqual(llm.verify_replaced_v2('new value',['other']*20),[])
        self.assertEqual([n for n,_ in client.sizes],[8,8,4])
        self.assertTrue(all(tokens>=128+192*n for n,tokens in client.sizes))

    def test_29_valid_source_repair_not_disabled(self):
        from mneme_asterion.retrieval.quotes import generate_r1q
        body='My project color is violet.';question='What is my project color?'
        source=raw(0,body)
        choice={'scope':{'subject_quote':question,'requested_relation':'project color','operation':'fact'},
                'supports':[dict(source_id='wrong-id',quote=body,purpose='premise',reason='Exact personal project color source.') ]}
        responses=Replies([json.dumps({'needed':True,'queries':['project color']}),json.dumps(choice)])
        with patch.object(llm,'_get_client',return_value=responses):
            out,trace=generate_r1q(question,[],[source],s.call,self.tok)
        self.assertTrue(out);self.assertIn('violet',str(out));self.assertEqual(responses.count,2)

    def test_30_concurrent_same_write_has_single_commit(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:self.add('duplicate-parallel','a','My color is blue.'),range(4)))
        self.assertEqual([r.status_code for r in responses],[200]*4)
        self.assertEqual(self.history('duplicate-parallel'),['My color is blue.'])
        self.assertEqual(store._conn.execute("SELECT COUNT(*) FROM request_commits WHERE user_id='duplicate-parallel'").fetchone()[0],1)

    def test_31_isolation_same_request_ids(self):
        self.add('scope-a','same','My color is blue.');self.add('scope-b','same','My color is green.')
        self.assertEqual(self.history('scope-a'),['My color is blue.'])
        self.assertEqual(self.history('scope-b'),['My color is green.'])
        self.assertTrue(set(i.id for i in store.get('scope-a').items).isdisjoint(i.id for i in store.get('scope-b').items))

    def test_32_http_deadline_after_provider_returns_prevents_commit(self):
        def slow(_):time.sleep(.03);return ['My color is blue.']
        with patch.object(config,'REQUEST_TIMEOUT',.01),patch.object(llm,'extract_facts',side_effect=slow),patch.object(updates,'detect',return_value=[]):
            response=self.add('late','a','My color is blue.')
        self.assertEqual(response.status_code,503);self.assertFalse(store.request_seen('a','late'))

    def test_33_failed_scope_does_not_reuse_cached_success(self):
        updates._scope_cache.clear()
        with patch.object(llm,'_get_client',return_value=Replies(['{}'])), runtime.request_scope():
            with self.assertRaises(llm.UpstreamUnavailable):updates.question_protected('What is my project color?',None)
        self.assertEqual(len(updates._scope_cache),0)

    def test_34_valid_update_then_current_search(self):
        numbered='0 | I: Please update my project color to amber.'
        extracted=json.dumps({'updates':[dict(statement=0,subject='me',attribute='project color',new_value='amber',
            old_value=None,relative=False,subject_is_user=True,current='My project color is amber.')]})
        with patch.object(llm,'_get_client',return_value=Replies([extracted])):
            result=llm.extract_updates(numbered,[(0,'Please update my project color to amber.')])
        self.assertEqual(result[0]['new_value'],'amber')

    def test_35_single_stage_retry_does_not_repeat_finished_planner(self):
        from mneme_asterion.retrieval.quotes import generate_r1q
        question='What is my project color?';body='My project color is violet.'
        valid={'scope':dict(subject_quote=question,requested_relation='color',operation='fact'),'supports':[]}
        error=openai.APITimeoutError(request=httpx.Request('POST','https://fixture.invalid'))
        responses=Replies([json.dumps({'needed':True,'queries':['color']}),error,json.dumps(valid)])
        with patch.object(llm,'_get_client',return_value=responses),patch.object(runtime.time,'sleep'):
            generate_r1q(question,[],[raw(0,body)],s.call,self.tok)
        self.assertEqual(responses.count,3)
        self.assertEqual(responses.requests[1]['messages'],responses.requests[2]['messages'])
        self.assertNotEqual(responses.requests[0]['messages'],responses.requests[1]['messages'])


if __name__=='__main__':unittest.main()

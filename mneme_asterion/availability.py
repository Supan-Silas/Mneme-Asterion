"""Deterministic source-only fallback; withdrawal uncertainty never releases evidence."""
import re
from app import llm
from app.availability import enrichment_budget, note

def matched_window(body, words, tok, budget=200):
    """One contiguous source window, anchored on an actual query match."""
    matches = [m for m in re.finditer(r'\w+', body) if m.group().casefold() in words]
    if not matches:
        return ''
    if tok.count(body) <= budget:
        return body
    best = None
    for match in matches:
        # Expand around the match on whitespace boundaries; never splice text.
        start, end = match.span()
        if tok.count(body[start:end]) > budget:
            continue
        boundaries = sorted(set([0, len(body), start, end] +
                                [m.end() for m in re.finditer(r'\s+', body)]))
        left = max(x for x in boundaries if x <= start)
        right = min(x for x in boundaries if x >= end)
        while True:
            options = []
            ls = [x for x in boundaries if x < left]
            rs = [x for x in boundaries if x > right]
            if ls: options.append((ls[-1], right))
            if rs: options.append((left, rs[0]))
            options = [(a,b) for a,b in options if tok.count(body[a:b]) <= budget]
            if not options: break
            left,right = min(options, key=lambda ab: (abs((start-ab[0])-(ab[1]-end)), ab[0]))
        text=body[left:right]
        score=len(words & set(re.findall(r'\w+',text.casefold())))
        candidate=(score, len(text), -left, text)
        if best is None or candidate[:3] > best[:3]: best=candidate
    return best[3] if best else ''

def literal_fallback(question, base, raw, tok):
    words = set(re.findall(r'\w+', question.casefold()))
    scored = []
    for position, record in enumerate(raw):
        body = record.get('body', '')
        score = len(words & set(re.findall(r'\w+', body.casefold())))
        if score:
            scored.append((score, -position, record))
    supplements = []
    for _, _, record in sorted(scored, key=lambda x: (x[0], x[1]), reverse=True)[:3]:
        body = matched_window(record['body'], words, tok)
        if body:
            # JSON quoting makes each provenance field unambiguous.
            import json
            provenance=json.dumps({'speaker':record.get('speaker', record.get('role','unknown')),
                'role':record.get('role','unknown'),'time':record.get('source_time'),
                'source_ids':record.get('source_ids',[record['id']])},ensure_ascii=False)
            supplements.append({'id':'rc15-raw-'+str(record['id']), 'text':'[Source '+provenance+']\n'+body,
                'source_ids':list(record.get('source_ids', [record['id']])),
                'metadata':{'fallback':'literal_lexical'}, 'timestamp':record.get('timestamp')})
    return (supplements + list(base))[:100]

def retrieve(fn, question, base, raw, call, tok):
    try:
        with enrichment_budget(90):
            return fn(question, base, raw, call, tok)
    except llm.UpstreamUnavailable as exc:
        note('retrieval.enrichment', exc)
        return literal_fallback(question, base, raw, tok), {'degraded':True}

def protect(fn, question, evidence, raw, call, tok):
    try:
        with enrichment_budget(90):
            return fn(question, evidence, raw, call, tok)
    except llm.UpstreamUnavailable as exc:
        note('withdrawal.protection', exc)
        # Unknown semantic scope can include paraphrased copies. Dropping only
        # keyword matches cannot guarantee protection. Suppress this response's
        # evidence, not the stored memory; a later query can recover normally.
        return [{'id':'rc15-state-unavailable',
                 'text':'[Memory availability notice] Memory evidence is temporarily withheld because its withdrawal/privacy processing could not be completed. Do not reconstruct personal values from missing evidence.',
                 'source_ids':[], 'metadata':{'fallback':'privacy_withheld'}, 'timestamp':None}], {'degraded':True}

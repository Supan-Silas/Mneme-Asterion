"""Optional postprocessor for portable P2; no model calls or DB writes."""
from mneme_asterion.state.withdrawal import withdrawal_state
from mneme_asterion.state.projection import finalize
from mneme_asterion.provenance import request_source_map,attach
def apply(query,evidence,raw,db_path,user_id,count):
 _,audit=withdrawal_state(raw,count)
 # Check activation first; most requests preserve P2 byte-for-byte and avoid
 # the provenance SQL read entirely.
 _,preflight=finalize(query,evidence,raw,audit)
 if preflight['scoped_parity']:return list(evidence),preflight
 enriched,proof=attach(evidence,request_source_map(db_path,raw,user_id=user_id))
 out,trace=finalize(query,enriched,raw,audit)
 return out,{**trace,'provenance':proof}

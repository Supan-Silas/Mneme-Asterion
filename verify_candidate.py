"""Offline candidate acceptance. Each module has an independent mocked process."""
from pathlib import Path
import subprocess,sys,json,re,os
R=Path(__file__).resolve().parent
modules=['test_release','test_state_echo','test_state_policy','test_state_withdrawal','test_repair_v1','test_quote_repair','test_http','test_scoped','test_state_v4','test_publication_regressions']
results=[]
env={**os.environ,'TIKTOKEN_CACHE_DIR':str(R/'tokenizer-cache'), 'PYTHONUTF8':'1'}
for module in modules:
 try:
  p=subprocess.run([sys.executable,'-m','unittest',module],cwd=R,capture_output=True,text=True,env=env,timeout=120)
 except subprocess.TimeoutExpired:
  results.append({'module':module,'passed':False,'tests':0,'error':'offline_test_timeout_120s'})
  continue
 matches=re.findall(r'Ran (\d+) tests?',p.stdout+p.stderr)
 results.append({'module':module,'passed':p.returncode==0,'tests':int(matches[-1]) if matches else None,'output':p.stdout+p.stderr})
print(json.dumps({'passed':all(x['passed'] for x in results),'tests':sum(x['tests'] or 0 for x in results),'results':results},ensure_ascii=False,indent=2))
raise SystemExit(0 if all(x['passed'] for x in results) else 1)

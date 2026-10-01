"""Verify the claim/episode chain and rebuild the complete registered final analysis."""
from pathlib import Path
import hashlib
import json
import math
import sys

ROOT=Path(__file__).resolve().parent
FROZEN=ROOT/'frozen'
sys.path.insert(0,str(FROZEN/'source/src'))
import rcrps
from rcrps.inversereserve_final_v1 import analyze_final_rows

def equal(a,b):
    if isinstance(a,float) and isinstance(b,(int,float)):
        return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b

def main():
    if not Path(rcrps.__file__).resolve().is_relative_to(FROZEN/'source/src'):
        raise RuntimeError('Historical analysis must use its frozen source')
    manifest=json.loads((ROOT/'frozen_manifest.json').read_text())
    for record in manifest['files']:
        if hashlib.sha256((FROZEN/record['path']).read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('Frozen content changed: '+record['path'])
    result=json.loads((FROZEN/'result.json').read_text())
    protocol=json.loads((FROZEN/'protocol.json').read_text())
    rows=[]
    for episode_id,digest in result['claim_manifest'].items():
        claim_path=FROZEN/'claims'/f'{episode_id}.json'
        if hashlib.sha256(claim_path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Claim binding mismatch: '+episode_id)
        claim=json.loads(claim_path.read_text())
        episode_path=FROZEN/'episodes'/f'{episode_id}.json'
        if claim['status']!='complete' or hashlib.sha256(episode_path.read_bytes()).hexdigest()!=claim['episode_sha256']:
            raise ValueError('Incomplete or changed episode: '+episode_id)
        rows.append(json.loads(episode_path.read_text()))
    analysis=analyze_final_rows(rows,protocol,all_claims_complete=True)
    for key,value in analysis.items():
        if not equal(value,result[key]):
            raise ValueError('Reconstructed analysis differs: '+key)
    print(json.dumps({'verified_files':len(manifest['files']),'episodes':len(rows),
      'scientific_source_commit':manifest['scientific_source_commit'],
      'bootstrap_samples':protocol['statistics']['bootstrap_samples'],
      'passed':analysis['passed'],'successes':{k:v['success'] for k,v in analysis['metrics'].items()}},indent=2))

if __name__=='__main__':main()

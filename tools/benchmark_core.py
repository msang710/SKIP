"""Synthetic local baseline, not a production latency guarantee."""
import json
from pathlib import Path
import statistics
import time
from tests.core.helpers import Fixture

f=Fixture();results=[]
try:
    count=0
    for target in (100,1000,10000):
        while count<target:f.request();count+=1
        samples=[]
        for _ in range(10):
            start=time.perf_counter()
            result=f.core.query('status',{'limit':30},f.actor(),f.ctx)
            samples.append((time.perf_counter()-start)*1000)
        results.append({'goals':count,'samples':10,'median_ms':round(statistics.median(samples),3),'max_ms':round(max(samples),3),
                        'returned_goals':len(result['data']['goals']),'page_continues':bool(result['data']['next_cursor'])})
    out={'kind':'synthetic_local_baseline','results':results,'production_claim':False}
    print(json.dumps(out))
    target=Path('.build/core-benchmark.json');target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(out,indent=2)+'\n')
finally:f.close()

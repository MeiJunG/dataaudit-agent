"""Export the exact active analysis, with bounded JSON and no environment credentials."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def save_analysis_record(history, directory, max_bytes=1024*1024):
    state = history or {}
    entry = next((e for e in state.get('entries',[]) if e['id']==state.get('active_id')),None)
    if entry is None:
        return None
    keys = ('step','tool','arguments','status','duration_ms','structured_result','report_markdown','result','routing','tool_routing','requested_arguments','argument_resolution','data_origin')
    record = {'schema_version':1, 'run_id':entry['id'], 'parent_run_id':entry.get('parent_id'),
              'question':entry['question'], 'answer':entry['answer'],
              'metadata':{k:v for k,v in entry.get('metadata',{}).items() if k in {'model','dataset','reference'}},
              'tools':[{k:e[k] for k in keys if k in e} for e in entry['trace']]}
    payload = (json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False,default=str)+'\n').encode()
    if len(payload) > max_bytes:
        return None
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    path = directory / ('analysis-'+hashlib.sha256(payload).hexdigest()+'.json')
    if not path.exists():
        path.write_bytes(payload)
    return path

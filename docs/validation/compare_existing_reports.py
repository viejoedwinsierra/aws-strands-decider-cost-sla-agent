#!/usr/bin/env python3
"""Audita los artefactos de comparación existentes, sin ejecutar inferencia."""
import csv,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2]
base=root/'reports'/'comparison'
try:
 rows=list(csv.DictReader((base/'comparison_by_run.csv').open(encoding='utf-8-sig',newline='')))
 summary=json.loads((base/'comparison_summary.json').read_text(encoding='utf-8'))
 assert len(rows)==20, f'Expected 20 comparison rows; got {len(rows)}'
 assert rows and all(rows), 'Empty comparison rows'
 print('COMPARISON_OFFLINE_VALIDATED',len(rows),'rows')
 print('SUMMARY_KEYS',list(summary))
except (OSError,ValueError,AssertionError) as exc:
 print('COMPARISON_OFFLINE_FAILED:',exc,file=sys.stderr);sys.exit(1)

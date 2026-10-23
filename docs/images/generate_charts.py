#!/usr/bin/env python3
"""Regenerate selected InfraVita charts from published reports; offline, no inference."""
from pathlib import Path
import csv,json,collections
from statistics import mean
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
def save(name):
    plt.tight_layout();plt.savefig(HERE/name,format='svg',bbox_inches='tight');plt.close()
with (ROOT/'reports/comparison/comparison_by_run.csv').open(newline='',encoding='utf-8') as f:
    rows=list(csv.DictReader(f))
for metric,name,label in [('latency_p95_ms','latency_by_scenario.svg','p95 latency (ms)'),('throughput_rps','throughput_by_scenario.svg','Throughput (requests/s)')]:
    fig,ax=plt.subplots(figsize=(10,4.7))
    for ex in ('EXP-001','EXP-002'):
        campaigns=sorted({r['campaign'] for r in rows if r['experiment']==ex})
        for n,ca in enumerate(campaigns,1):
            rr=sorted([r for r in rows if r['experiment']==ex and r['campaign']==ca],key=lambda r:r['scenario'])
            ax.plot(range(1,len(rr)+1),[float(r[metric]) for r in rr],marker='o',label=f'{ex} campaign {n}')
    ax.set_xticks(range(1,6),['01 (10)','02 (100)','03 (200)','04 (300)','05 (500)'])
    ax.set_xlabel('Scenario (configured users; historical design)');ax.set_ylabel(label)
    ax.set_title('Observed '+('p95 latency' if metric.startswith('latency') else 'throughput')+' by load scenario')
    ax.grid(alpha=.2);ax.legend(ncol=2,fontsize=8);save(name)
measurements=[]
for exp in ('001','002'):
    d=json.loads((ROOT/f'reports/local_model/exp{exp}_local.json').read_text())
    for run in d['decisions']:
        for m in run.get('telemetry_contract',{}).get('measurements',[]):
            if m.get('phase')=='RUN': measurements.append({**m,'experiment':f'EXP-{exp}','scenario':run['scenario_id']})
for metric,src,agg,name in [('cpu_utilization','cloudwatch','Average.mean','cpu_by_instance.svg'),('memory_utilization','linux_ssm','mean','memory_by_instance.svg')]:
    mm=[m for m in measurements if m.get('metric')==metric and m.get('source')==src and m.get('aggregation')==agg and isinstance(m.get('value'),(int,float))]
    ids=sorted({(m['experiment'],m.get('instance_id','unknown')) for m in mm})
    fig,ax=plt.subplots(figsize=(10,4.8))
    for exp in ('EXP-001','EXP-002'):
        for i,pair in enumerate([p for p in ids if p[0]==exp],1):
            by=collections.defaultdict(list)
            for m in mm:
                if (m['experiment'],m.get('instance_id','unknown'))==pair:
                    by[int(m['scenario'].split('-')[-1])].append(float(m['value']))
            xs=sorted(by);ax.plot(xs,[mean(by[x]) for x in xs],marker='o',label=f'{exp} / instance {i}')
    ax.set_xticks(range(1,6),['01','02','03','04','05']);ax.set_xlabel('Load scenario (mean of available campaigns)')
    ax.set_ylabel('Utilization (%)');ax.set_title(f'Observed {"CPU" if metric.startswith("cpu") else "memory"} — {src} RUN-phase mean')
    ax.grid(alpha=.2);ax.legend(fontsize=8,ncol=2);save(name)
fig,ax=plt.subplots(figsize=(8,4.5));xx=[0,1]
ax.bar([x-.2 for x in xx],[580,150],width=.4,label='CloudWatch observations')
ax.bar([x+.2 for x in xx],[42,18],width=.4,label='Linux SSM snapshots')
ax.set_xticks(xx,['EXP-001','EXP-002']);ax.set_ylabel('Recorded observations / snapshots')
ax.set_title('Historical telemetry evidence coverage (not completeness)');ax.legend();save('telemetry_coverage.svg')
fig,ax=plt.subplots(figsize=(8,4.5));ax.bar([-.18,.82],[80,50],width=.36,label='Raw agreement')
ax.bar([.18,1.18],[80,100],width=.36,label='Effective agreement after policy')
ax.set_xticks([0,1],['EXP-001','EXP-002']);ax.set_ylim(0,110);ax.set_ylabel('Agreement (%)')
ax.set_title('Paired model agreement (10 runs per experiment)');ax.legend();save('model_agreement.svg')
fig,ax=plt.subplots(figsize=(8.5,3.5))
for i,label in enumerate(['Baseline infrastructure (unmeasured)','Incremental workload (unmeasured)','Operations and change (unmeasured)']):ax.barh([1],[1],left=i,label=label)
ax.set_xlim(0,3);ax.set_yticks([1],['Conceptual cost layers']);ax.set_xticks([])
ax.set_title('Cost decomposition — illustration only, no USD measurements')
ax.legend(loc='lower center',bbox_to_anchor=(.5,-.4),ncol=1,fontsize=8);save('cost_baseline_concept.svg')
print('CHARTS_REGENERATED_OFFLINE')

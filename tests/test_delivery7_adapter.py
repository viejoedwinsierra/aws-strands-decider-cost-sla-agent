import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from src.analysis.telemetry_exp002 import summarize_exp002


def test_exp002_observed_window_and_missing_cpu():
    with TemporaryDirectory() as temp:
        root = Path(temp); campaign = root/'campaign'; run = root/'run'
        campaign.mkdir(); run.mkdir()
        (campaign/'ec2_inventory.json').write_text(json.dumps({'instances': [
            {'instance_id':'i-work','role':'workload-server'},
            {'instance_id':'i-load','role':'load-generator'}]}))
        (run/'exp002_stats_history.csv').write_text('Timestamp,User Count,Name\n1000,1,Aggregated\n1060,2,Aggregated\n')
        (run/'cloudwatch_workload_CPUUtilization.json').write_text(json.dumps({
            'Datapoints':[{'Timestamp':'1970-01-01T00:16:40Z','Average':25.0}]}))
        (run/'linux_RUN_workload.json').write_text(json.dumps({
            'timestamp_utc':'1970-01-01T00:17:10Z','memory_total_kib':1000,'memory_available_kib':700}))
        data = summarize_exp002(campaign,run,'test-run')
        assert data['cloudwatch']['i-work']['CPUUtilization']['Average']['mean'] == 25
        assert data['linux']['i-work']['memory_utilization_percent']['sample_count'] == 1
        assert data['linux']['i-work']['cpu_utilization_percent']['mean'] is None
        assert data['window']['quality'] == 'observed_samples_not_exact_execution_boundaries'

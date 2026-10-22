#!/usr/bin/env python3
"""Offline regression for EXP-001 normalization; no AWS calls."""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZER = ROOT / 'experiments/exp001_capacity/metrics/normalize_locust.py'
RESULTS = ROOT / 'experiments/exp001_capacity/results'


def run_test():
    # The normalizer's output path is fixed under results. Use a temporary
    # run directory inside that tree; remove only the directory created here.
    import uuid
    run_id = 'phasec_v2_test_' + uuid.uuid4().hex[:12]
    target = RESULTS / run_id
    target.mkdir(parents=True, exist_ok=False)
    try:
        manifest = {'experiment_id': 'EXP-001', 'run_id': run_id,
                    'configuration': {'users': 200, 'spawn_rate_users_per_second': 10,
                                      'configured_duration_seconds': 180},
                    'infrastructure': {'target_private_ip': '10.0.1.38'}}
        (target / 'run_manifest.json').write_text(json.dumps(manifest))
        with (target / 'exp001_stats.csv').open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['Name', 'Request Count',
                'Failure Count', 'Requests/s', '50%', '95%', '99%',
                'Average Response Time', 'Max Response Time'])
            writer.writeheader()
            writer.writerow({'Name': 'Aggregated', 'Request Count': 100,
                'Failure Count': 0, 'Requests/s': 20, '50%': 3, '95%': 9,
                '99%': 21, 'Average Response Time': 5, 'Max Response Time': 42})
        cmd = [sys.executable, str(NORMALIZER), '--run-id', run_id]
        success = subprocess.run(cmd, capture_output=True, text=True)
        assert success.returncode == 0, success.stderr
        normalized = json.loads((target / 'metrics_normalized.json').read_text())
        assert normalized['configuration']['configured_duration_seconds'] == 180
        assert normalized['configuration']['users'] == 200
        mismatch = subprocess.run(cmd + ['--duration', '60'], capture_output=True, text=True)
        assert mismatch.returncode != 0, 'Mismatched duration was accepted'
        print('PHASE_C_V2_OFFLINE_REGRESSION_PASS')
    finally:
        import shutil
        shutil.rmtree(target)


if __name__ == '__main__':
    run_test()

"""Computational efficiency from verified normalized HTTP and EC2 evidence."""
import math


def _number(value, *, minimum=0, strict=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > minimum if strict else value >= minimum))


def calculate(observations, computational_cost, http_instance_id=None):
    """Attribute service compute only to the HTTP EC2, never to Locust.

    Error rate is the fraction of unsuccessful requests; derived successful
    requests are an estimate and are not rounded to a fictitious count.
    """
    instances = computational_cost.get('instances', [])
    matches = [x for x in instances if x.get('instance_id') == http_instance_id] if http_instance_id else []
    http = matches[0] if len(matches) == 1 else None
    count = observations.get('request_count')
    error = observations.get('error_rate')
    if not _number(count) or not _number(error) or error > 1:
        successful = None
    else:
        successful = count * (1 - error)
    cpu = http.get('cpu_used_vcpu_seconds_estimated') if http else None
    mem = http.get('memory_used_gib_seconds_estimated') if http else None
    if cpu is not None and not _number(cpu):
        raise ValueError('Invalid CPU estimate')
    if mem is not None and not _number(mem):
        raise ValueError('Invalid memory estimate')
    denominator = successful if successful is not None and successful > 0 else None
    return {
        'schema_version': '1.0', 'http_instance_id': http_instance_id,
        'attribution': 'http_service_only', 'locust_excluded': True,
        'successful_requests_estimated': successful,
        'cpu_vcpu_seconds_per_successful_request_estimated': cpu / denominator if cpu is not None and denominator else None,
        'memory_gib_seconds_per_successful_request_estimated': mem / denominator if mem is not None and denominator else None,
        'latency_p95_ms': observations.get('latency_p95_ms'),
        'throughput_rps': observations.get('throughput_rps'),
        'error_rate': error if _number(error) and error <= 1 else None,
        'quality': 'estimated' if denominator and cpu is not None else 'insufficient_evidence',
        'limitations': ['Uses run-average resource estimates, not a time integral.',
                        'Successful requests estimated from request_count and error_rate.',
                        'Missing role attribution or measurements are never imputed.'],
    }

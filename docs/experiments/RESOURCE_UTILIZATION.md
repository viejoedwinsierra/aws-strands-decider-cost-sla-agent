# CPU, memory and resource interpretation

The historical JSON reports contain per-run `telemetry_contract.measurements` for CPU and memory, tagged by `instance_id`, `source`, `aggregation`, and phase. The charts below use those **existing observations**, not simulated utilization values.

## CPU utilization

![Observed CPU](../images/cpu_by_instance.svg)

**Method:** CloudWatch `cpu_utilization`, `aggregation=Average.mean`, `phase=RUN`, grouped by experiment and anonymized instance ID. These are run-level aggregate measurements, not continuous CPU time series. Low percentages cannot prove that the service was overprovisioned, because workload bottlenecks, CPU credits, I/O, memory, application/database contention and short test duration were not fully characterized.

## Memory utilization

![Observed memory](../images/memory_by_instance.svg)

**Method:** Linux SSM `memory_utilization`, `aggregation=mean`, `phase=RUN`. Memory measurements are derived from Linux snapshots and are not native EC2 CloudWatch memory metrics. Some runs or instances may lack a matching measurement; gaps remain gaps.

## Observability coverage

![Telemetry coverage](../images/telemetry_coverage.svg)

The reports record 730 CloudWatch observations and 60 Linux snapshots across 20 unique runs. These counts indicate captured evidence, **not sampling completeness**. To establish reliable saturation, future tests need longer windows, synchronized telemetry and explicit service/instance role attribution.

## What cannot be concluded

- No defensible minimum or maximum long-term CPU/memory utilization from these short aggregates.
- No validated CPU/memory bottleneck diagnosis for every load scenario.
- No numeric infrastructure baseline cost, monetary savings or proven right-sizing opportunity.
- No production SLA PASS/FAIL claim for EXP-002.

See [Results](RESULTADOS_Y_ESTADISTICAS.md) and [Future architecture](../architecture/VISION_Y_EVOLUCION.md).

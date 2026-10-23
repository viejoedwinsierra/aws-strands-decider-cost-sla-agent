# Delivery 9 — Historical architecture

The earlier architecture connected AWS experiments to a decision agent via historical evidence. The final documented architecture extends this with a local Strands Decider 2B provider, Bedrock Nova Micro, and a deterministic `computational-v1` policy that can override unsupported actions.

![Current architecture](../images/architecture.svg)

The system separates experiment orchestration, evidence collection, inference, and governed output. It does not execute automated scaling changes. For implementation details, see [Architecture and evolution](../architecture/VISION_Y_EVOLUCION.md) and [Deployment](../operations/INFRASTRUCTURE_DEPLOYMENT.md).

The original uploaded historical architecture text is retained in `SOURCE_DOCUMENTATION_ARCHIVE.zip` for audit; this page is an English editorial summary.

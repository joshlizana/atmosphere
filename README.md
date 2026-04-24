# Atmosphere

Atmosphere is a streaming lakehouse for Bluesky public data. It tails the
Jetstream firehose, lands every commit as typed rows in an Apache Iceberg
warehouse on SeaweedFS, and enriches the stream with profile data fetched from
the XRPC API and multilingual sentiment scores computed on post text. A
dbt-duckdb DAG builds a dimensional core and analytical marts on top of bronze;
ClickHouse attaches the Iceberg catalog read-only and serves those marts to
scheduled Quarto reports and Grafana dashboards.

Jetstream is the single source of truth. Iceberg is the durable projection of
that firehose — append-only at bronze, rebuildable at silver and gold.
ClickHouse is a pure query engine over Iceberg, with an S3 filesystem cache as
its only acceleration mechanism; nothing is ever materialized into MergeTree.
Recovery is Jetstream's 24-hour cursor replay, and nothing else — there are no
backfill pipelines and no historical import path.

## Architecture

Data flows left to right: Spout tails Jetstream on four endpoints and produces
to per-collection Redpanda topics; Flink validates every message against a
Pydantic model, normalizes into 3NF, and commits bronze tables to Iceberg
through Lakekeeper; Sleuth hydrates unseen DIDs via the XRPC API; Oracle runs
XLM-RoBERTa sentiment on posts on the host GPU; dbt-duckdb builds silver and
gold back into Iceberg; ClickHouse serves reads to Quarto and Grafana. The
governance plane sits orthogonal: OpenMetadata captures catalog and lineage via
OpenLineage events pushed from every producer, and Prometheus, Loki, and
Grafana cover metrics and logs for every container. See
[`.claude/context/architecture.md`](.claude/context/architecture.md) for the
full picture including component-level diagrams, and the rest of
[`.claude/context/`](.claude/context/) for per-component design notes.

## Current state

The repo is in milestone M0 — scaffolding, CI, and host prep. No services run
yet, and nothing in the design doc is implemented beyond directory structure
and tooling. The platform is delivered in fifteen milestones (M0 through M14);
the full roadmap lives in
[`.claude/context/roadmap.md`](.claude/context/roadmap.md) and tracks the
dependency graph from empty repo to production-ready platform.

## Getting started

- See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the local development loop —
  the platform builds and deploys on the host, with no CI image pipeline.
- See [`docs/host-prep-nvidia.md`](docs/host-prep-nvidia.md) for NVIDIA
  Container Toolkit setup; Oracle requires GPU passthrough from the host.
- See [`.claude/context/`](.claude/context/) for the design docs —
  [`project-overview.md`](.claude/context/project-overview.md) is the best
  starting point, followed by [`architecture.md`](.claude/context/architecture.md)
  and the per-component files.
- Issues are tracked in the Linear project `Atmosphere`.

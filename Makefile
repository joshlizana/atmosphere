# Atmosphere platform — operator convenience targets.
# One-command primitives for the bring-up → teardown → full-reset lifecycle.
# See .claude/context/operations.md §Volumes and storage for the `nuke`
# design reference. Recipe lines are tab-indented (GNU Make requires tabs).

.PHONY: up down nuke

## up: Pre-flight + first-boot init (init.sh), then tier-by-tier service bring-up with health-gating (up.sh).
up:
	./scripts/init.sh && ./scripts/up.sh

## down: Stop services and remove containers; volumes and .env persist (reversible with `make up`).
down:
	docker compose down

## nuke: Full reset — destroy containers, named volumes, legacy ./data bind dir, and generated .env.
nuke:
	docker compose down -v --remove-orphans || true
	rm -rf ./data
	rm -f .env

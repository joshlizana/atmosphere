---
id: 01KQ0PW8YP9KTFBA733M1NS7G5
type: incident
name: 20260424T1723Z-rpk-set-flag-not-stripped-by-redpanda-v26
created_at: 2026-04-24T17:23Z
created_by: log/01KQ0PW8YP9KTFBA733M1NS7G5
component: helm
---

## Purpose
Records the M1 smoke-Probe re-run incident where Scout's source-reading-grounded recommendation to replace the rejected `--admin-addr=0.0.0.0:9644` flag with two `--set=redpanda.admin[0].address=0.0.0.0` and `--set=redpanda.admin[0].port=9644` pairs failed in the actual container because `rpk redpanda start` did NOT strip the `--set=...port=...` pair from argv before handing it to the Seastar broker binary, producing the same crash-loop one line deeper; captures the contradicted claim, the observed binary rejection, the unverified root-cause hypotheses, and the lesson that CLI-wrapper behavior needs live-test confirmation rather than source-reading alone.

## 2026-04-24T17:23Z — initial
- agent: log/01KQ0PW8YP9KTFBA733M1NS7G5
- refs: [[research/JDL-66/redpanda-admin-api-listener-v26]], [[research/JDL-66/redpanda-compose-single-broker-2026]], [[files/JDL-66/compose-yml]]

What happened. The M1 smoke Probe's first re-run (task `a3f2804c93ee37e65`) surfaced a Redpanda crash-loop rooted in the `--admin-addr=0.0.0.0:9644` flag being rejected by the `docker.redpanda.com/redpandadata/redpanda:v26.1.6` broker binary (Seastar parser: `unrecognised option '--admin-addr=0.0.0.0:9644'`). Scout v2 researched the canonical v26.1.x pattern ([[research/JDL-66/redpanda-admin-api-listener-v26]], commit `e2d950d`) and recommended replacing `--admin-addr` with two `--set=redpanda.admin[0].address=0.0.0.0` / `--set=redpanda.admin[0].port=9644` lines, grounded in a source-code reading of `src/go/rpk/pkg/cli/redpanda/start.go` at the v26.1.6 tag. Claim: `parseConfigKvs` at lines 108–122 of that file strips `--set` pairs from argv before handing off to cobra, applying each pair through the same `config.Set` path that `rpk redpanda config set` uses. Scout's confidence in the recommendation was high; bracket-index notation was documented for a sibling property (`redpanda.kafka_api[0].port=9092`); the mechanism looked sound. ^p001

Forge applied the fix at commit `d895987`. Probe re-ran the suite (`ac4532c54ddded668`) against the patched `compose.yml`. Empirical result: same crash-loop signature as before, one line deeper — `ERROR  main - cli_parser.cc:46 - Argument parse error: unrecognised option '--set=redpanda.admin[0].port=9644'`. Container stderr clearly shows `rpk redpanda start` forwarding the `--set=redpanda.admin[0].port=9644` argument unchanged to `/opt/redpanda/bin/redpanda`, not stripping it. The broker binary rejects it and exits. The address-side of the pair (`--set=redpanda.admin[0].address=0.0.0.0`) may or may not have been applied — the binary exits on the first fatal parse error and the address pair is never reached. ^p002

Root cause hypothesis (unverified). Either (a) `parseConfigKvs` is conditional on argv order in a way the Scout didn't catch, (b) the v26.1.6 behavior diverged from what the source-file reading suggested, (c) rpk only strips ONE `--set` pair per invocation and passes the second through, or (d) the source-file reading was wrong. Any of these would explain why the fix held in the Scout's mental model but failed in the actual container. Distinguishing among them requires live experimentation against the same `v26.1.6` image — running `rpk redpanda start` with one `--set` versus two, observing which specific pair gets forwarded to the broker, and reconciling the behavior against the `start.go` source at the tagged commit. ^p003

Lesson. For wrapper-tool behavior (rpk wrapping a Seastar broker, any `kubectl`-style thin-wrapping scenario), source-code reading alone is not sufficient ground truth. The Scout must live-test the candidate syntax in an actual container and confirm the broker accepts it before the recommendation is treated as canonical. This applies to every future Scout invocation that involves CLI wrapper behavior — the abstraction between the user-facing command and the underlying binary is the most common place for source-reading to mislead. ^p004

Scope of harm. None reached main. Probe caught the failure on re-run before any push. Platform never operated with the broken config; `make up` fails cleanly at the tier-1 health wait and containers don't accept traffic. The fix (Scout v3 with live-test mandate + Forge v2) is in progress. ^p005

Related preventive measure. Future Scout invocations researching CLI tool behavior should include a live-test mandate in the Topic field: "Verify the recommended syntax by running the container / binary with candidate flags and checking exit code + stderr for parse errors." ^p006

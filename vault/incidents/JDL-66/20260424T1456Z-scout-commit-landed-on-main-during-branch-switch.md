---
id: 01KPZZWCSCVQ524NQ4RXY7JRHD
type: incident
name: 20260424T1456Z-scout-commit-landed-on-main-during-branch-switch
created_at: 2026-04-24T14:56Z
created_by: log/01KPZZWCSCVQ524NQ4RXY7JRHD
component: helm
---

## Purpose
Records the M1 outer-loop incident where a background Scout's research commit landed on `main` instead of the M1 branch because Helm checked out `main` for an unrelated chore while the Scout was still in flight, and documents the non-destructive recovery and the preventive feedback memory added to Helm.

## 2026-04-24T14:56Z — initial
- agent: log/01KPZZWCSCVQ524NQ4RXY7JRHD
- refs: [[decisions/JDL-66/20260424T1236Z-seaweedfs-s3-credentials-via-env-vars]], [[research/JDL-66/redpanda-compose-single-broker-2026]]

What happened. During M1 outer-loop research for JDL-66, Helm launched three Scouts in parallel while on branch `JDL-66-m1-shared-infrastructure-online` (Postgres compose, SeaweedFS compose, Redpanda compose). The Postgres and SeaweedFS Scouts completed within ~5 minutes and committed their research notes to the M1 branch successfully (`dc4c26a`, `6d3d042`). Mid-flight, Helm checked out `main` to make a chore-class edit for the skill-loading fix — six `.claude/skills/*/SKILL.md` files, removing `disable-model-invocation: true` — work that ultimately produced no commits because `.claude/` is gitignored. During that chore window the Redpanda Scout finished (~9.7 minute runtime, slowest of the three) and committed its 239-line research note as `4383563` onto `main`, not onto the M1 branch. Helm then returned to the M1 branch and continued the outer loop, unaware the research note was missing from the branch, and the subsequent `scripts/up.sh` Forge flagged the Redpanda research file as absent in its response — which surfaced the gap. ^p001

Recovery. `git cherry-pick 4383563` onto the M1 branch successfully applied the commit with no conflict — the research note is a new file. `git branch -f main 1102a38` rewound the local `main` pointer to match `origin/main` (the commit ancestry on `origin/main` was untouched because nothing had been pushed; the reflog preserves `4383563` for a further week even though no ref currently references it). Both operations non-destructive in the platform sense. The Redpanda research note is now present at `vault/research/JDL-66/redpanda-compose-single-broker-2026.md` on the M1 branch and will ship with the JDL-66 PR as intended. ^p002

Root cause. Subagents operate in the same working directory Helm is in at commit time, not the one they were launched from. A mid-flight branch switch by Helm causes any subsequent agent commit to land on the wrong branch. In this case, the `main` checkout was motivated by chore isolation — which is the right instinct — but unsafe because Scouts were still running. ^p003

Preventive measure. Added a new Helm feedback memory (`feedback_no_branch_switch_during_subagents.md`) covering the rule: never `git checkout` / `git switch` while any subagent is in flight. If a branch change is urgent, surface to user and either wait for subagents to drain or accept the cleanup cost explicitly. ^p004

Scope of harm. None reached `origin`. Nothing was pushed. The M1 PR, once opened, carries the full four-Scout research corpus as designed. The session-local `main` was rewound before any push could have leaked the errant commit. ^p005

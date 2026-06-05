import json,pathlib
out=pathlib.Path('C:/data/works/FX/logs/audit/AUDIT-2026-0530-001/verification/verify_meta.json')
out.parent.mkdir(parents=True,exist_ok=True)
logical_flaws = [
  {"finding_id": "DE-403 always-FIRING expression is conditionally not unconditionally true",
   "flaw": "The always-FIRING characterization requires at least one H1/H4 LIVE strategy to be present. Paper-only or M1-only environments do not trigger the alert. M1 strategies produce age_sec approximately equal to the 60s threshold creating flapping not constant FIRING. Accurate: in production with at least one H1/H4 LIVE strategy FxFeatureStorestaleHigh fires continuously after the second bar because age_sec H1=3600s >> threshold 60s is mathematically certain. The absolute expression in DE-403 is used as severity justification but is technically imprecise.",
   "evidence": "alerting_rules.yml line 99: max(fx_feature_staleness_sec) > 60 for 3m. live_store.py lines 431-446: age_sec equals current monotonic minus last bar monotonic giving approximately H1 bar interval 3600s. DE-403 body states constantly FIRING without qualifying that this requires H1/H4 presence."},
  {"finding_id": "RE-401/DM-402 canonical conflict unresolved between clusters B and C",
   "flaw": "Cluster B declared RE-401 canonical severity=medium. Cluster C declared DM-402 canonical severity=HIGH. The final report leaves both open as RE-401 (or DM-402) without resolving the conflict, creating tracking overhead in the next audit-loop closure phase.",
   "evidence": "summary_AUDIT-2026-0530-001.md line 34: cluster B is RE-401 canonical medium, cluster C is DM-402 canonical high, final verdict is high. Canonical ID is not determined. cluster_b_fts_infra.json line 23: RE-401 canonical. cluster_c_fts_data_ops.json line 13: DM-402 canonical."},
  {"finding_id": "PA-401 post_fix_defect classification overstates yesterday-commit causation",
   "flaw": "PA-401 is counted in the 5-of-6 yesterday-commit-caused post_fix_defect statistic but is quasi-post_fix (portation omission) not a defect created by yesterday commit. The main.py EventBus ordering bug pre-existed; 9998a7a exposed it by fixing only runner.py without porting the fix to main.py.",
   "evidence": "PA-401 regression_of: AUDIT-2026-0529-003 C-01 runner.py fix only main.py not updated. Commit 9998a7a did not create the main.py bug. Accurate post_fix_defect count is 4/24 = 16.7% not 5/24 = 20.8%."},
  {"finding_id": "RE-403 downgrade premise rests on unverified PTRC orphan-trade behavior",
   "flaw": "Cluster B downgraded RE-403 from high to medium based on the 1-position PTRC constraint preventing double-entry. This is not verified for the orphan trade scenario where entry_rollback sets open_trade_id=None.",
   "evidence": "cluster_b_fts_infra.json line 342: 1-position PTRC constraint makes immediate risk low. In RE-402 scenario entry_rollback sets open_trade_id=None and PTRC may see the slot as FLAT permitting a new entry. The compound RE-402 plus RE-403 double-entry scenario without pyramiding was not quantitatively evaluated before the downgrade."},
  {"finding_id": "DE-408 re-evaluation incomplete after evidence correction",
   "flaw": "Cluster C correctly identified backfill_missing exists at candle_fetcher.py:416 contradicting DE-408 evidence. However whether backfill_missing is auto-integrated with poll_latest was not verified before confirming medium severity.",
   "evidence": "cluster_c_fts_data_ops.json: CandleFetcher.backfill_missing() at candle_fetcher.py:416 exists and fault/test_oanda_reconnect_backfill.py tests it. If auto-called after poll_latest severity may drop to low. The logical consequence of the evidence correction was not fully resolved."}
]
bias_corrections = [
  {"finding_id": "CSR-402 downgrade underestimates atlas-loop improvement-rate miscalculation risk",
   "direction": "under",
   "rationale": "Cluster A downgrade to medium is justified by Live presence=0 and 4-None pattern count=0. However during the 6.1.0/6.2.0 schema mixing period atlas-loop compares new strategies (FLOOR 0.90 baseline) against old strategies (FLOOR 0.70 baseline) causing new strategies to score systematically lower and producing false stagnation signals. The downgrade rationale characterizes this risk as limited but the operational impact on ATLAS-loop efficiency is underweighted. QA-401 independently flags the same issue as medium."},
  {"finding_id": "PA-405 and PA-410 side-effect classified informational rather than should_consider",
   "direction": "over",
   "rationale": "Cluster B correctly disproved the skip claim via line number comparison showing 1547 and 1551 are less than 1632. Downgrade to low is correct for the primary claim. However the PA-405 side-effect where silence_sec accumulates during OANDA outage and consumes the 12h throttle upon recovery is a real low-severity operational issue that warrants should_consider not informational."},
  {"finding_id": "RE-401 final severity high conflates SRE urgency with technical severity",
   "direction": "over",
   "rationale": "Cluster C rated DM-402 HIGH from SRE perspective because OANDA degradation is undetectable. Cluster B rated RE-401 medium because the defect is observation-only with zero trade flow impact. Final report confirmed high conflating SRE urgency with technical severity. Technical severity is medium. SRE urgency is high (3-line fix). The conflation matters for cross-audit severity inflation tracking."},
  {"finding_id": "DE-403 and DE-410 potential post_fix_defect double-counting",
   "direction": "over",
   "rationale": "DE-410 warmup-transition false staleness is resolved as a side effect of DE-403 fix when the alerting threshold is raised to 7200s or greater. Cluster C noted: fix DE-403 first then re-evaluate DE-410. If DE-410 is counted separately in post_fix_defect totals the count is overstated. The final report does not clarify whether DE-410 is included in the post_fix_defect count."}
]
canonical_resolution = {
  "DM-402_vs_RE-401": {
    "decision": "Adopt RE-401 as canonical ID. Close DE-402 and DM-402 as duplicates. Technical severity: medium. SRE urgency: high.",
    "rationale": "RE-401 covers all 3 instantiation sites runner.py:343, main.py:335, forward_test.py:239 making it the most comprehensive finding. DM-402 lists only runner.py and main.py as primary evidence. Cluster B RE-401 canonical judgment is logically superior. Technical severity is medium since observation-only with zero trade flow impact is confirmed by all three teams. SRE urgency is high because the 3-line fix enables INC-2026-0526-style degradation detection. Note: scripts/live_preflight.py line 35 may be a 4th missing injection site and must be verified during the fix."
  }
}
missed_critical_areas = [
  {"area": "scripts/live_preflight.py OANDABroker instantiation missing metrics= argument, potential 4th site for RE-401",
   "potential_issue": "live_preflight.py line 35 instantiates OANDABroker without metrics=. RE-401 identified 3 sites but scripts/ was excluded from scope leaving this potential 4th site unexamined. live_preflight.py connects to production OANDA API.",
   "evidence_or_suspicion": "Confirmed by reading scripts/live_preflight.py line 35: broker = OANDABroker(api_key=api_key, account_id=account_id, base_url=base_url) with no metrics argument. RE-401 suggested_fix specifies 3 sites only due to scripts/ scope exclusion.",
   "adoption_level": "should_consider"},
  {"area": "scripts/ production environment guard inconsistency across 6 operational scripts, 2nd consecutive miss from AUDIT-0529-001 structural gap 2",
   "potential_issue": "live_order_test.py, oanda_position_inspect.py, oanda_transactions_inspect.py, live_signal_probe.py connect to OANDA API without consistent OANDA_ENVIRONMENT=live guard. live_preflight.py has env branching on lines 22-27 but other scripts were not checked. Risk of accidental production connection.",
   "evidence_or_suspicion": "AUDIT-2026-0529-001 identified this as structural gap 2. AUDIT-2026-0530-001 all 7 experts and 3 devil-advocates excluded scripts/ from scope again. Two consecutive misses confirms structural blind spot in audit process.",
   "adoption_level": "should_consider"},
  {"area": "parity.yml CI missing explicit permissions declaration, 2nd consecutive miss from AUDIT-0529-001 structural gap 7",
   "potential_issue": "parity.yml has no permissions block. GITHUB_TOKEN write permissions depend on repository-level settings and are not explicitly constrained to read-only. Security intent is not documented.",
   "evidence_or_suspicion": "Confirmed by reading parity.yml in full: zero occurrences of the permissions keyword. AUDIT-2026-0529-001 identified this as structural gap 7. Same omission in current audit.",
   "adoption_level": "informational"},
  {"area": "pyproject.toml dependency version upper bounds absent, 2nd consecutive miss from AUDIT-0529-001 structural gap 4",
   "potential_issue": "All 14 core dependencies use >= constraints only with no upper bounds. Major version bumps in aiohttp, pydantic, or fastapi could silently break installation. prometheus-client is optional-only; production startup without monitoring extra leaves Prometheus behavior undefined.",
   "evidence_or_suspicion": "Confirmed by reading pyproject.toml: all core dependencies use >= only with no upper bounds. AUDIT-2026-0529-001 identified this as structural gap 4. Same omission in current audit.",
   "adoption_level": "informational"},
  {"area": "AuditLogger and StateManager JSONL rotation guarantee unclear, 2nd consecutive miss from AUDIT-0529-001 structural gap 6",
   "potential_issue": "logger.py implements RotatingFileHandler (100MB x 10 backups) for app logging but whether AuditLogger and StateManager.append_jsonl share this rotation or grow unbounded is unverified. Windows 11 disk pressure risk.",
   "evidence_or_suspicion": "Confirmed logger.py lines 19-20: _DEFAULT_MAX_BYTES=100MB _DEFAULT_BACKUP_COUNT=10. AuditLogger and StateManager JSONL rotation was not examined in this audit. AUDIT-2026-0529-001 identified this as structural gap 6. Same omission.",
   "adoption_level": "informational"},
  {"area": "ATLAS/scripts/backfill_v6_2_0_soft_score.py confirmed absent by actual file check",
   "potential_issue": "The backfill script mandated by QA-301 change:spec step 6 does not exist. All 1452 strategies remain at schema 6.1.0 without recomputation under FLOOR=0.90. 8 strategies would flip PASS to FAIL on recomputation. atlas-loop improvement-rate calculations are distorted during the transition period.",
   "evidence_or_suspicion": "Executed glob ATLAS/scripts/backfill_v6_2_0* and confirmed NOT FOUND. 71 scripts exist in ATLAS/scripts/ including backfill_v* for prior schema versions but v6_2_0 is absent. Commit 05ae8595 explicitly deferred backfill per spec_change_log.md. CSR-402 and QA-403 both flag this; this meta-check reinforces with actual file verification.",
   "adoption_level": "must_fix"},
  {"area": "Time synchronization NTP Windows 11 vs ubuntu CI impact on OANDA timestamp comparisons, 2nd consecutive miss from AUDIT-0529-001 structural gap 5",
   "potential_issue": "FTS compares OANDA API UTC timestamps against host system time in multiple locations. Windows 11 W32tm accuracy is typically plus-minus 100ms but can drift on sync failure. DEV environment (Windows 11 Pro) and CI (ubuntu-latest) have different NTP accuracy profiles.",
   "evidence_or_suspicion": "Platform confirmed as Windows 11 Pro. CI confirmed as ubuntu-latest. No team member examined NTP or timezone handling in either audit round. DE-306 uses UTC 22:00 fixed close time; host clock drift effect on weekend_seconds boundary calculations was not examined.",
   "adoption_level": "informational"}
]
suggested_fix_feasibility = [
  {"finding_id": "RE-401/DM-402/DE-402 canonical RE-401",
   "claim": "3-line fix: add metrics=self._metrics to runner.py:343, main.py:335, forward_test.py:239",
   "reality": "3-line fix is accurate for the 3 identified sites. scripts/live_preflight.py may be a 4th missing site making it a 4-line fix. forward_test.py self._metrics existence must be verified. Including AST structural test total scope is 3-4 lines plus one new test file. The 3-line claim is a lower-bound estimate."},
  {"finding_id": "PA-401 main.py initialize() ordering fix",
   "claim": "Change main.py initialize() order: EventBus.start() then EmailNotifier.start() then Gate publish",
   "reality": "The runner.py C-01 fix (lines 500-525) provides a precedent. However main.py initialize() is 430+ lines and moving EventBus and EmailNotifier startup earlier may require reviewing initialization order of dependent components. Actual change could be 50-100 lines. The label understates scope."},
  {"finding_id": "RE-402 entry_rollback OANDA close path addition",
   "claim": "Add best-effort OANDA cancel/close on entry_rollback. KillSwitch candidate on failure.",
   "reality": "Final report provides fix direction only without implementation size estimate. Adding RE-404 retry plus OANDA close attempt plus CRITICAL alert requires approximately 50-100 lines in strategy_slot.py plus a new fault test file. Close by instrument plus units plus entry_time matching adds 30-50 additional lines. Combined with RE-404 realistic scope is 3-5 files and 100-200 lines. Classifying as immediate must_fix without this estimate risks implementation delay."},
  {"finding_id": "DE-403 observe_feature_staleness semantics fix",
   "claim": "alerting_rules.yml threshold TF-specific branching OR observe_feature_staleness semantics overhaul",
   "reality": "Short-term workaround (alerting_rules.yml threshold change from 60 to 7200) requires 1-2 lines. Root fix spans live_store.py, metrics.py, and alerting_rules.yml as medium-scale refactor. Final report does not specify whether workaround alone closes the must_fix requirement or root fix is required. This ambiguity should be resolved before implementation begins."},
  {"finding_id": "PA-407 main.py deprecation ADR advancement",
   "claim": "PA-307 ADR advancement as design decision requiring separate session",
   "reality": "The bootstrap extraction option B (new trading_platform/core/bootstrap/__init__.py consolidating set_metrics_collector loop and LIVE Gate handling) is a mid-scale refactor (5-10 files, 200-400 lines) that does not require an ADR decision. The ADR-required framing may prevent consideration of this intermediate option that would prevent PA-401-type one-side-only fix omissions without requiring full main.py deprecation."}
]
overall = (
  "Comparison with AUDIT-2026-0529-001: "
  "(1) Finding count 81 to 68 (-13) reflects scope difference not quality difference. "
  "Previous audit targeted existing codebase broadly; current audit targeted 3 yesterday commits specifically. "
  "(2) post_fix_defect discovery improved from 0 to 5. Quantifying that 5 of 24 fix items (20.8%) introduced new defects is genuine improvement. "
  "However PA-401 is quasi-post_fix (portation omission) not pure post_fix_defect so accurate rate is 4/24 = 16.7%. "
  "(3) Deduplication 3 findings same as previous but RE-401/DM-402/DE-402 canonical conflict between clusters B and C was left unresolved in the final report which is lower quality on this dimension. "
  "(4) devil-advocate detection of PA-405/PA-410 causal errors via line number comparison represents precision improvement over previous DM-306 all-3-paths-dead overstatement pattern. "
  "(5) Of 7 structural gaps identified in AUDIT-2026-0529-001 five remained unaddressed in this audit: scripts/ environment guards, CI permissions, pyproject upper bounds, NTP, and log rotation. "
  "The backfill_v6_2_0 absence was reinforced by actual file check in this meta-verification. "
  "Two consecutive misses on all 5 gaps confirms structural blind spots in audit team scope selection. "
  "Overall: roughly equivalent to previous audit. "
  "Clear improvements in post_fix_defect detection and causal error identification. "
  "Clear issues in canonical conflict resolution and persistence of structural scope blind spots."
)
d = {
  "verifier": "devil-advocate (meta round 2)",
  "audit_id": "AUDIT-2026-0530-001",
  "verified_at": "2026-05-30",
  "target_commits": {"atlas": "15d62e62", "fts": "d1e73b1 / 9998a7a"},
  "logical_flaws": logical_flaws,
  "bias_corrections": bias_corrections,
  "canonical_resolution": canonical_resolution,
  "missed_critical_areas": missed_critical_areas,
  "suggested_fix_feasibility": suggested_fix_feasibility,
  "overall_quality_assessment": overall,
  "summary": {
    "logical_flaws_count": 5,
    "bias_corrections_count": 4,
    "missed_areas_count": 7
  }
}
out.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print("Written:", out)
print("Size bytes:", out.stat().st_size)

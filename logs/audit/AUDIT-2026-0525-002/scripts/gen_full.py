import json, pathlib
OUT = pathlib.Path("C:/data/works/FX/logs/audit/AUDIT-2026-0525-002/validation_fts_core.json")
ip = "_in_position"
bp = "_bars_in_position"
po = "_position"
id_ = "_intended_direction"
dqe = "DataQualityEngine"
ptrc_cls = "PreTradeRiskControl"
occ = "OandaCurrencyConverter"
def mk(i,o,v,a,r,ad,rat): return {"id":i,"original_severity":o,"validated":v,"adjusted_severity":a,"reproducible":r,"adoption_level":ad,"rationale":rat}
results = [
  mk("PA-101","high","true","high",True,"must_fix",
     f"strategy_slot.py:1287: hasattr(self.strategy,{ip}) guard confirmed. "
     f"ATLAS-2026-0501-004/strategy.py:210-212: {po}/{bp} defined, {ip} absent. "
     f"ATLAS-2026-0511-059/strategy.py:61: {id_}/{bp} defined, {ip} absent. "
     f"grep imported 60 strategies: {ip} 0 matches, {bp} 25 matches. "
     "Restore block dead code for all 60 strategies. "
     f"{id_}-type partially rescued via strategy_slot.py:1262. "
     f"{po}+{bp} type (0501-004 etc) left FLAT after restart. "
     "Live: max_hold never fires, double-entry risk immediate. must_fix."),
  mk("PA-102","high","true","high",True,"must_fix",
     "runner.py:324-329: return await _bus_ref.health_status() confirmed. "
     "memory_adapter.py:253: def health_status(self) sync def returns dict. "
     "redis_adapter.py:384: def health_status(self) sync def returns dict. "
     "Awaiting dict raises TypeError. except Exception: return False. "
     "health_check.py:43: event_bus in CRITICAL_COMPONENTS. PROBER_UNHEALTHY_THRESHOLD=3. "
     "After 30s event_bus permanently unhealthy, system reports unhealthy continuously. "
     "main.py:494-500 uses sync call correctly. Only UnifiedRunner has await mismatch. "
     "DM-102 independently detected identical bug at identical file:line. must_fix."),
  mk("PA-103","high","downgraded","medium",False,"should_consider",
     "main.py:231: live_mode = self._settings.env == Environment.PRODUCTION confirmed. "
     "config/settings.py: env field default=Environment.RESEARCH. "
     ".env: no ENV= line present (grep confirms 0 matches). "
     "Current: env==RESEARCH, live_mode always False, trigger never fires. "
     "Theoretical defect: no restore_positions in main.py vs runner.py:389-391. "
     "Downgraded high->medium: actual risk low until ENV=production added to .env. "
     "should_consider: document main.py as dev/paper-only in ops manual."),
  mk("PA-104","low","true","low",True,"should_consider",
     "strategy_slot.py:999 LIVE exit: correlation_id=str(uuid.uuid4()) new uuid confirmed. "
     "strategy_slot.py:1074 PAPER exit: same new uuid. "
     "strategy_slot.py:1041 FillEvent: exit_correlation_id used correctly. "
     "FillEvent cid unified by DM-009. SignalEvent->OrderEvent exit chain broken. "
     "FILL correct, audit trail 2/3 achieved. low severity appropriate."),
  mk("PA-105","low","true","low",False,"informational",
     "redis_adapter.py:249-258: on Redis publish exception fallback to _dispatch_local confirmed. "
     "redis_adapter.py:260-265: _dispatch_local delivers without dedup check. "
     "redis_adapter.py:489-547: _dispatch uses dedup LRU/SETNX for double-processing block. "
     "Partial-success case (Redis delivered but client timeout) may cause double-processing. "
     "Low probability in normal operation. informational: re-evaluate on Redis cluster adoption."),
  mk("PA-106","low","true","low",False,"informational",
     "strategy_slot.py:558-573: bind_contextvars + finally unbind_contextvars confirmed. "
     "strategy_slot.py:847-858 exit: with bound_contextvars() context manager confirmed. "
     "bind/unbind does not restore prior value if cid already bound before call. "
     "Current: no cid bound before entry, no actual harm. "
     "informational: future nesting change could cause contextvars leak."),
  mk("PA-107","low","true","low",False,"informational",
     "docs/SHARED_CONTRACT.md:50-63: SANDBOX_BUILTINS listed as shared API confirmed. "
     "loader.py:663-664: import only, no reverse dependency. "
     "loader.py:50-66: AST allowlist and SANDBOX_BUILTINS dual-maintenance structure confirmed. "
     "informational: add snapshot regression test to enforce allowlist sync."),
  mk("PA-108","low","true","low",False,"informational",
     "loader.py:675-692: inspect.getmembers alphabetical class order confirmed. "
     "loader.py:686-690: WARN log on multiple classes confirmed. "
     "loader.py:693-698: sys.modules.pop() on success path confirmed (FTS-PA-09). "
     "All current imported strategies define exactly one Strategy subclass. "
     "informational: re-evaluate if ATLAS export adds mixin/base classes."),
  mk("RE-101","high","true","high",True,"must_fix",
     f"runner.py:291: self._ptrc = {ptrc_cls}() no-arg confirmed. "
     f"main.py:81: self._ptrc = {ptrc_cls}() no-arg confirmed. "
     "ptrc.py:151-154: _unsafe_static_in_live = isinstance(StaticCurrencyConverter) and OANDA_ENVIRONMENT==live. "
     ".env: OANDA_ENVIRONMENT=live, no ENV= line. "
     f"grep {occ}( trading_platform/ -> 0 matches (class definition only, never injected). "
     "ATLAS-2026-0511-059/runner_config.json: execution_mode=live, instrument=EUR_USD, fixed_units=10000. "
     "ptrc.py:218-254: EUR_USD quote=USD != account=JPY, 0.5 fail-safe REJECT on every evaluate(). "
     "strategy_slot.py:642-653: REJECT has WARNING+orders_rejected++ only, no RiskAlertEvent. "
     "EUR_USD live strategy permanently all-REJECT, silent dead strategy in production. "
     "must_fix: live-funded strategy ATLAS-2026-0511-059 zero trades since commit 3dbf087."),
  mk("RE-102","medium","true","medium",True,"should_consider",
     "risk_supervisor.py:630-639: daily_unrealized_pnl passed as 0 to RiskState confirmed. "
     "ptrc.py:447-460: _check_max_daily_loss uses realized+SL estimate only. "
     "risk_supervisor.py:407-433: can_open_position checks realized only. "
     "risk_supervisor.py:858-947: _evaluate_unrealized_warning Email-only, no blocking. "
     "RE-002 realized-only design user-approved. Unrealized loss >10% does not block new entries. "
     "should_consider: soft-block new entries when is_unrealized_warning_active=True."),
  mk("RE-103","low","upgraded","low",False,"should_consider",
     "ptrc.py:60-92: _fire_ptrc_audit discards loop.create_task return value, no reference held. "
     "ptrc.py:92: no add_done_callback confirmed. "
     "RE-101 permanent REJECT causes high-frequency _fire_ptrc_audit invocations every bar. "
     "CLAUDE.md: risk rejections must be in Audit Log - requirement conflict. "
     "adoption_level informational->should_consider: GC loss risk verifiably elevated under RE-101. "
     "severity remains low: actual GC loss is load/GC-timing dependent and unproven."),
  mk("RE-104","low","true","low",False,"informational",
     "client.py:337-353: clientExtensions.id idempotency design confirmed. "
     "client.py:364-381: duplicate reject classified as generic 4xx confirmed. "
     "broker_gateway.py:252-281: success=False FAILED transition confirmed. "
     "strategy_slot.py:665-676: fill failure treated as REJECTED confirmed. "
     "retry_enabled defaults False, limited actual impact. "
     "informational: prerequisite for retry_enabled=True in ADR-0003 phase."),
  mk("DE-101","high","true","high",True,"must_fix",
     "main.py:318: BarBuilder() without quality_engine arg confirmed. "
     "main.py:334: CandleFetcher() without quality_engine arg confirmed. "
     "main.py:459: OANDAStreamReceiver() without quality_engine arg confirmed. "
     "bar_builder.py:239: if is_complete and self._quality_engine is not None -- None skips DE-002. "
     f"grep {dqe}( trading_platform/ -> 0 matches (tests only). "
     "DE-002 (commit 61c1f86) forced-publish + RiskAlert dead code in production. "
     "Parity tests 65 PASS (forced-publish path unreachable in production). "
     "Violates Data Quality First (CLAUDE.md principle-7) and DE-002 production_impact=yes. "
     "must_fix: DE-002 entirely inert in production despite unit test coverage."),
  mk("DE-102","low","true","low",False,"should_consider",
     "quality_engine.py:283: self._last_bars[bar.instrument] = bar updated on every validate_bar. "
     "quality_engine.py:571-606: _check_price_jump uses last_bar.close as reference. "
     "quality_engine.py:485-509: _check_timestamp_order uses last_bar.bar_time. "
     "If DE-101 fixed and BarBuilder+CandleFetcher share one instance, "
     "two sources interleave _last_bars for same instrument causing false positives. "
     "Currently non-occurring since DE-101 means no injection. "
     "should_consider: design decision required when fixing DE-101."),
  mk("DE-103","info","true","info",True,"informational",
     "ATLAS vectorbt_engine.py:342-377: _SimpleFeatureStore uses full df, no quality filter. "
     "data_loader.py:399-506: check_data_quality report-only, no bar drop. "
     "bar_builder.py:242-258: FAIL bars get forced_publish (not dropped). "
     "Parity tests 65 PASS. DE-002 direction confirmed consistent with ATLAS BT. "
     "informational: correctness confirmation recorded."),
  mk("DE-104","info","true","info",True,"informational",
     "DE-001/004/005/006 verified no regression. "
     "stream_receiver.py:340-377: DE-001 time parse + fallback. "
     "bar_builder.py:435-463: FTS-DATA-012 reverse tick guards monotonicity. "
     "candle_fetcher.py:453-463: _is_incomplete_candle only True for complete is False. "
     "candle_fetcher.py:247,438: bt <= last deduplication guard. "
     "Parity 65 PASS including 5 buffer-trim cases. informational: no-regression confirmed."),
]
data = {
  "validator": "devil-advocate",
  "cluster": "fts_core",
  "session": "AUDIT-2026-0525-002",
  "validation_date": "2026-05-25",
  "scope": "platform-architect (PA-101~108), risk-execution-engineer (RE-101~104), data-engineer (DE-101~104)",
  "summary": {
    "total_findings": 16,
    "false_count": 0,
    "severity_adjustments": [
      {"id":"PA-103","direction":"downgraded","severity_from":"high","severity_to":"medium",
       "reason":".env has no ENV= line, env defaults to RESEARCH, live_mode always False in current deployment."},
      {"id":"RE-103","direction":"adoption_level_upgraded","adoption_from":"informational","adoption_to":"should_consider",
       "reason":"RE-101 permanent REJECT causes high-frequency _fire_ptrc_audit invocations, elevating GC audit loss risk."}
    ],
    "high_findings_verdicts": {
      f"PA-101": f"validated=true, must_fix: hasattr {ip} always False for 60 strategies, {bp}/{po} not restored after restart",
      "PA-102": "validated=true, must_fix: await sync dict causes TypeError, event_bus permanently unhealthy, DM-102 cross-confirmed",
      f"RE-101": f"validated=true, must_fix: EUR_USD live strategy ATLAS-2026-0511-059 permanently REJECTed, {occ} never injected, silent dead strategy",
      f"DE-101": f"validated=true, must_fix: {dqe} never instantiated in trading_platform/ (grep 0 matches), DE-002 dead code in production"
    }
  },
  "results": results,
  "cross_cluster_notes": [
    "PA-102 independently confirmed by DM-102 (runner.py:324-328, memory_adapter.py:253, redis_adapter.py:384).",
    "RE-103 adoption_level upgrade contingent on RE-101 high-freq REJECT. Revert to informational after RE-101 fix.",
    "PA-103 becomes high-severity the moment ENV=production added to .env. Ops manual must document main.py as dev/paper-only."
  ]
}
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("written", len(results), "results to", OUT)

# FX システム修正 実行プレイブック

**作成日**: 2026-05-21
**親計画**: `remediation_plan_2026_0521.md` v2
**位置付け**: 各 PR の実行手順・diff スケッチ・検証ゲートを集約した実行用ドキュメント
**実装ポリシー**: 各 PR 着手前にユーザー確認 / 完了は v2 計画全 PR マージ後 / 全完了後に再監査実施

---

## PR 一覧と依存関係

```
PR0 [A-0]: 発火頻度実測 + ロールバック基準確定          [計測のみ、コード変更なし]
   └─ PR0.5 [PRE]: kill_switch 15% → 5% (rule_change記録)
       └─ PR1 [A-2]: BarBuilder truth_source 強制化
           └─ PR2 [A-1-1]: OrderSubmissionGuard 抽出 + SnapshotWriter 配線 + H-PLAT-4 ADR
               └─ PR3 [A-1-3 + M-PLAT-3 + X-2]: 通貨換算 + grep 網羅
                   └─ PR4 [A-1-2]: KillSwitch 配線 (REV-1 設計)
                       └─ PR5 [A-3 + A-4 + A-5]: ドキュメント・戦略設定
                           └─ PR6 [A-6, 旧B-1]: on_fill 12戦略 + FillEvent 型統一
                               └─ PR6.5 [POST]: kill_switch 5% → 15% (rule_change記録)
─────── A フェーズ完了 ───────
PR7  [B-2]: テスト補強 (REV-7)
PR8  [B-3]: Event Bus / Strategy Loader
PR9  [B-4]: 監視・運用 4件
PR10 [B-5]: H-EXEC 系 + REV-8 _processed_fills 設計改訂
PR11 [REV-11]: Position Reconciler 強化 ※実際は A-1 と並走想定だが、計画上はここに記載
PR12 [B-6]: H-DATA 系
PR13 [B-7]: SMA50/200 Live 確認 (発火頻度は PR0 で完了済み)
─────── B フェーズ完了 ───────
PR14-N: フェーズ C 各項目 (Medium、必要に応じてグループ化)
─────── C フェーズ完了 ───────
全 PR マージ後: 再監査セッション実施
```

---

## PR0: A-0 発火頻度実測 + ロールバック基準確定 [REV-3 must_fix]

**目的**: A フェーズで使用するロールバック判断基準を事前に数値化

**コード変更**: なし（計測スクリプトの実行と記録のみ）

### 実施内容
1. `scripts/measure_signal_frequency.py` を新規作成（コード変更を伴うため別 PR で）
   - ATLAS L1 BT の trade_log から各 LIVE 戦略の月平均発火数を集計
   - 直近 30 日 Live ログ (`unified_runner.jsonl`) から実際の発火回数を集計
2. `docs/rollback_thresholds.md` を新規作成し、戦略別ロールバック基準を記録:

```markdown
| 戦略ID | TF | 期待発火間隔 | ロールバック判定: X時間沈黙 |
|---|---|---|---|
| 0511-059 | H1 | 30 日/件 | 60 日 |
| 0510-002 | H4 | 1.5 日/件 | 72 時間 |
| 0507-038 | H4 | 1 日/件 | 72 時間 |
| ... | | | |
```

3. PTRC 拒否率基準値の記録 (`logs/unified_runner.jsonl` の `ptrc_reject` カウントから直近 30 日平均)
4. `docs/runbook/rollback_criteria.md` を新規作成

### 検証ゲート
- 23 LIVE 戦略全件で発火間隔が記録されていること
- 「24時間 Order 未発出」を盲目的にロールバック基準としない方針が文書化されていること

### Live 影響
**なし**（計測のみ）

### 見積もり
4-6 時間

---

## PR0.5: kill_switch 15% → 5% 変更 [REV-6]

**目的**: A フェーズ作業中の安全マージン確保（正式な制限値変更）

### コード変更

**ファイル**: `core/models/risk.py:190`
```python
# 旧
max_total_exposure_ratio: float = 8.0
kill_switch_daily_loss: float = 0.15

# 新
max_total_exposure_ratio: float = 8.0
kill_switch_daily_loss: float = 0.05  # PR0.5: A-1 防壁配線中の保守値 (元 0.15)
```

**ファイル**: `logs/rule_change/2026-05-XX_kill_switch_lower.jsonl` を新規作成:
```jsonl
{"timestamp":"2026-05-XX","type":"hard_limit_change","field":"kill_switch_daily_loss","old":0.15,"new":0.05,"reason":"A-1 phase safety margin","approver":"<user>","planned_revert_pr":"PR6.5"}
```

### コミットメッセージ
`[change:spec] kill_switch_daily_loss 0.15→0.05 (A-1 防壁配線中の保守値)`

### 検証ゲート
- `tests/risk_engine/test_hard_limits.py` が新値で PASS
- rule_change ログが正しく記録されていること

### Live 影響
**あり** — Kill Switch が早めに発動する可能性。A フェーズ作業中は保守側に振る意図のため許容

### Rollback
PR6.5 で元値に戻す（恒久 revert ではなく、A フェーズ完了後に正式戻し）

### 見積もり
1 時間

---

## PR1: A-2 BarBuilder truth_source 強制化 [REV-10 順序入替で先行]

**目的**: BT/Live 数値乖離の真因候補を解消。後続 PR のテスト基盤を安定化

### コード変更

**ファイル**: `data/market_data/bar_builder.py:80`
```python
# 旧
def __init__(
    self,
    ...,
    truth_source: str = "tick_aggregation",
):

# 新
def __init__(
    self,
    ...,
    truth_source: str = "oanda_candle",  # PR1: production デフォルトを OANDA 公式 candle に
):
```

**ファイル**: `config/settings.py`
```python
# 新規追加
class TradingSettings(BaseSettings):
    BAR_TRUTH_SOURCE: Literal["oanda_candle", "tick_aggregation"] = "oanda_candle"

    @field_validator("BAR_TRUTH_SOURCE")
    def validate_truth_source_for_env(cls, v, info):
        if os.getenv("ENV") == "production" and v != "oanda_candle":
            raise ValueError(
                f"production 環境では truth_source='oanda_candle' 必須 (got {v})"
            )
        return v
```

**ファイル**: `scripts/run_unified.py` 起動時 fail-fast 検証追加

### テスト追加

**ファイル**: `tests/parity/test_bar_source_parity.py` 拡張
- `test_production_env_rejects_tick_aggregation`: ENV=production + tick_aggregation 設定で起動失敗
- `test_oanda_candle_default`: BarBuilder デフォルト引数が "oanda_candle"

### 検証ゲート
- `pytest tests/parity/` 全件 PASS
- `pytest tests/integration/` の bar_close 時刻依存テストが新 truth_source で PASS
- Paper モードで 1 時間試運転、bar 数が想定通り生成されること

### Live 影響
**大** — 既存環境が `tick_aggregation` のまま起動できなくなる。展開前に環境変数の確認必須

### Rollback
revert で OK（環境変数で対応可能）

### 見積もり
2-4 時間

---

## PR2: A-1-1 OrderSubmissionGuard 抽出 + SnapshotWriter 配線 [REV-9]

**目的**: UnifiedRunner 経路で Trade Context Snapshot 永続化を必須化。同時に二重実装の負債回避

### コード変更

#### 新規クラス: `core/execution_engine/order_submission_guard.py`
```python
class OrderSubmissionGuard:
    """Coordinator と StrategySlot 双方が共通利用する fail-closed ガード。

    REV-9 (H-PLAT-4 整合): X-1 中期で StrategySlot 削除されても Guard は残る
    """
    def __init__(self, snapshot_writer: SnapshotWriter):
        self._snapshot_writer = snapshot_writer

    async def submit_with_guard(self, order: Order, broker_gateway: BrokerGateway) -> BrokerFillResult:
        # 1. SnapshotWriter で context_snapshot 永続化 (fail-closed)
        try:
            await asyncio.to_thread(self._snapshot_writer.write_or_raise, order.context_snapshot)
        except SnapshotWriteError as e:
            logger.error("snapshot_write_failed", order_id=order.id, error=str(e))
            return BrokerFillResult(success=False, reject_reason="snapshot_persistence_failure")

        # 2. SnapshotWriter 成功時のみ発注
        return await broker_gateway.submit(order)
```

#### 修正: `core/execution_engine/coordinator.py:322-348`
```python
# 旧: write_or_raise + submit を直接呼び
# 新: self._order_guard.submit_with_guard(order, self._broker_gateway) に置換
```

#### 修正: `core/unified_runner/strategy_slot.py:_handle_entry, _handle_exit`
```python
# 旧
fill = await self.gateway.submit(order)

# 新
fill = await self._order_guard.submit_with_guard(order, self.gateway)
```

#### 修正: `core/unified_runner/runner.py:_setup_slot`
```python
# OrderSubmissionGuard をシングルトンで構築し、Slot コンストラクタに注入
snapshot_writer = SnapshotWriter(snapshot_dir=settings.SNAPSHOT_DIR)
self._order_guard = OrderSubmissionGuard(snapshot_writer)

slot = StrategySlot(
    ...,
    order_guard=self._order_guard,
)
```

#### ADR 同 PR で作成: `docs/adr/0001_order_submission_guard.md`
- H-PLAT-4「二重実装の溝」と OrderSubmissionGuard による解消方針
- X-1 中期の StrategySlot 削除計画への接続

### 追加: HealthChecker のディスク容量チェック [risk-execution-engineer 指摘]
**ファイル**: `core/monitoring/health_check.py` に `_check_disk_space` 追加（free < 100MB で Degraded）

### 追加: Prometheus メトリクス
**ファイル**: `core/monitoring/metrics.py`
```python
_counter("fx_snapshot_persistence_failures", "SnapshotWriter 書き込み失敗")
```

### テスト追加

**ファイル**: `tests/integration/test_unified_runner_snapshot.py` 新規
- `test_submits_only_after_snapshot_success`: SnapshotWriter モック成功時のみ submit
- `test_rejects_on_snapshot_failure`: SnapshotWriter 例外時 submit せず REJECT
- `test_guard_shared_between_coordinator_and_slot`: 同一 Guard インスタンスを両経路が使用

**ファイル**: `tests/architecture/test_no_direct_gateway_submit.py` 新規
- grep ベースアサート: `gateway.submit(` を直接呼ぶ箇所が `OrderSubmissionGuard` 内部に限定されていること

### 検証ゲート
- 既存 360 件 + 新規 3-5 件 全 PASS（5 xfail は維持）
- Paper Trading 2 時間試運転で `snapshot_dir` にファイル生成
- `fx_snapshot_persistence_failures_total` メトリクスが 0

### Live 影響
**中** — SnapshotWriter 失敗時に Order が止まる。ディスク監視を併設したため監視可能

### Rollback
revert で OK。OrderSubmissionGuard は新規ファイルのため副作用なし

### 見積もり
6-8 時間

---

## PR3: A-1-3 + M-PLAT-3 通貨換算網羅 + X-2 grep 検査 [REV-1 順序前倒し]

**目的**: PTRC 通貨換算を `_check_total_exposure` と `PortfolioManager._calculate_used_margin` で同時実装

### 事前作業: grep 網羅検査
```bash
# 通貨換算が必要な箇所をリストアップ
grep -rn "quantity \* price\|notional\|exposure\|margin\|account_balance" trading_platform/core/ \
  --include="*.py" > X2_currency_conversion_audit.txt
```

### コード変更

#### 修正: `core/risk_engine/ptrc.py:343-412 (_check_total_exposure)`
```python
# 旧
new_order_notional = order.quantity * ref_price
total_notional = current_notional + new_order_notional
exposure_ratio = total_notional / portfolio.account_balance

# 新
quote_currency = parse_quote_currency(order.instrument)
new_order_notional_quote = order.quantity * ref_price
try:
    new_order_notional_account = self._currency_converter.convert(
        amount=new_order_notional_quote,
        from_currency=quote_currency,
        to_currency=portfolio.account_currency,
    )
except CurrencyConversionError as e:
    return PTRCResult(
        approved=False,
        reject_reason="currency_conversion_failure",
        details={"error": str(e)},
    )
total_notional = current_notional + new_order_notional_account
exposure_ratio = total_notional / portfolio.account_balance
```

#### 修正: `core/portfolio_manager/manager.py:158-161`
```python
# 旧
used_margin = quantity / 25.0

# 新
quote_currency = parse_quote_currency(instrument)
notional_quote = quantity * current_price
notional_account = self._currency_converter.convert(
    notional_quote, quote_currency, self._account_currency
)
used_margin = notional_account / leverage
```

#### 追加: production 環境で `StaticCurrencyConverter` 起動拒否
**ファイル**: `core/risk_engine/ptrc.py:75-78`
```python
if isinstance(currency_converter, StaticCurrencyConverter) and os.getenv("ENV") == "production":
    raise ConfigurationError(
        "production 環境では OandaCurrencyConverter 必須 (StaticCurrencyConverter 検出)"
    )
```

### テスト追加

**ファイル**: `tests/risk_engine/test_ptrc_currency.py` 新規
- `test_check_total_exposure_eur_usd_jpy_account`: EUR/USD 注文を JPY 口座で換算
- `test_check_total_exposure_conversion_failure_fail_closed`: 換算失敗で REJECT
- `test_portfolio_manager_used_margin_currency_conversion`: PortfolioManager の通貨換算

**ファイル**: `tests/architecture/test_currency_conversion_coverage.py` 新規
- X2 grep リストに対する網羅性アサート

### 検証ゲート
- X-2 grep の全箇所が処理済みであること
- `pytest tests/risk_engine/` 全件 PASS
- Paper Trading で EUR/USD 1 取引 → exposure_ratio が JPY 建てで正しく算出

### Live 影響
**大** — PTRC 拒否率が変動する可能性。PR0 で記録した基準値と比較

### Rollback
revert で旧 PTRC に戻る。Static→Oanda 強制化のみ ENV=production 環境で起動拒否を緩める対応が必要

### 見積もり
8-12 時間

---

## PR4: A-1-2 KillSwitch 配線 [REV-1 設計反映]

**目的**: UnifiedRunner で Hard Limit 防壁を機能させる。**未実現損益は WARN レイヤーに分離**

### コード変更

#### 修正: `core/models/risk.py` に新フラグ追加
```python
class StrategyRiskState(BaseModel):
    daily_realized_pnl: float = 0.0
    daily_unrealized_pnl: float = 0.0  # 既存
    is_unrealized_warning_active: bool = False  # 新規 REV-1
    is_kill_switch_active: bool = False  # 既存

class AccountRiskState(BaseModel):
    # 既存
    daily_realized_pnl_total: float = 0.0
    daily_unrealized_pnl_total: float = 0.0  # 既存
    is_unrealized_warning_active: bool = False  # 新規 REV-1
    is_kill_switch_active: bool = False
```

#### 修正: `core/unified_runner/risk_supervisor.py:604-619`
```python
async def _evaluate_kill_switch(self) -> None:
    # KS は実現損益のみで発動 (既存契約維持、REV-1)
    if abs(self._account_state.daily_realized_pnl_total) >= self._kill_switch_threshold_jpy:
        await self._activate_kill_switch(reason="daily_realized_loss_exceeded")

    # 未実現損益は警告レイヤー (新規、自動解除可能)
    if abs(self._account_state.daily_realized_pnl_total + self._account_state.daily_unrealized_pnl_total) >= self._kill_switch_threshold_jpy:
        self._account_state.is_unrealized_warning_active = True
        await self._emit_warning_alert()  # Email + Prometheus
    else:
        self._account_state.is_unrealized_warning_active = False  # 戻り時に自動解除
```

#### 修正: StateStore 永続化（`is_kill_switch_active` は除外）
```python
# REV-1: KS 永続化フラグを Redis に書かない。既存契約「再起動で解除」を維持
async def _persist_account_state(self):
    snapshot = {
        "daily_realized_pnl_total": self._account_state.daily_realized_pnl_total,
        "daily_unrealized_pnl_total": self._account_state.daily_unrealized_pnl_total,
        "strategy_states": {...},
        # is_kill_switch_active は永続化しない
        # is_unrealized_warning_active も永続化しない (再起動でリセット)
    }
    await self._state_store.set(
        key=f"risk:account_state",
        value=json.dumps(snapshot),
        ex=25 * 3600,  # TTL 25時間 (日次リセット周期 + マージン)
    )
```

#### 修正: KS 発動時の挙動
```python
async def _activate_kill_switch(self, reason: str) -> None:
    # 1. 新規発注停止を即時実施 (同期)
    self._account_state.is_kill_switch_active = True

    # 2. in-flight cancel は別非同期タスク (REV-1: Event Bus 詰まり防止)
    asyncio.create_task(self._cancel_open_orders_best_effort())

    # 3. 通知
    await self._emit_kill_switch_alert(reason)

async def _cancel_open_orders_best_effort(self) -> None:
    """REV-1: best-effort, 自動再試行禁止"""
    try:
        await self._broker_gateway.cancel_all_open_orders(timeout=10.0)
    except Exception as e:
        logger.error("cancel_open_orders_failed", error=str(e))
        # 自動再試行せず、Position Reconciler 経路で人間アラート (PR11 連携)
```

### docs/runbook 更新

**ファイル**: `docs/runbook/kill_switch_triggered.md` 更新
- 既存契約「KS 解除はプロセス再起動のみ」を明示維持
- 未実現損益警告は別レイヤーで「自動解除可能」と明記

### テスト追加

**ファイル**: `tests/risk_engine/test_global_kill_switch.py` 新規
- `test_ks_activates_on_realized_loss`: 実現損失で KS 発動
- `test_unrealized_warning_separate_from_ks`: 未実現損失は警告のみで KS 発動せず
- `test_unrealized_warning_auto_resets`: 含み損戻りで warning 自動解除
- `test_ks_not_persisted_to_redis`: KS フラグが永続化されないこと（既存契約維持）
- `test_account_state_persisted_with_25h_ttl`: realized_pnl のみ TTL 25h で永続化
- `test_cancel_failure_emits_alert_no_retry`: cancel 失敗時に自動再試行しない

### 検証ゲート
- `tests/risk_engine/` 全件 PASS
- Paper Trading で実損益 5% (PR0.5 の保守値) 到達時に KS 発動、in-flight 注文キャンセル、再起動で KS 解除を手動確認
- 未実現損益が 5% 帯を行き来した際に warning が振動するが KS は発動しないこと

### Live 影響
**大** — KS 発動条件が「実現損失のみ」であることを運用チームに事前周知必須

### Rollback
revert で OK。Redis に書き込まれた `risk:account_state` キーは TTL 25h で自動消去

### コミット種別
`[change:spec]` （既存契約「KS 解除手段はプロセス再起動のみ」は維持、未実現損益警告レイヤーを追加する仕様変更）

### 見積もり
8-12 時間

---

## PR5: A-3 + A-4 + A-5 ドキュメント・戦略設定 [REV-5 統合]

**目的**: 既知の不整合を一括解消

### A-3: TODO.md / メモリ訂正 + loader.py WARN 追加 [REV-5 確定]

**ファイル**: `fx_trading_system/TODO.md`
- 「23戦略 live_eligible 確認 OK」記述を削除
- 実測値 (5/53/1) を記載
- loader.py のキー欠如時挙動を明文化

**ファイル**: `core/strategy_engine/loader.py:311-316` [REV-5 「追加検討」→ 確定タスク化]
```python
if "live_eligible" in metadata:
    if live_mode and metadata["live_eligible"] is not True:
        raise StrategyLoadError(...)
else:
    if live_mode:
        logger.warning(
            "live_eligible_key_missing",
            strategy_id=strategy_id,
            note="metadata.json に live_eligible キーが存在しないため検証スキップ。"
                 "ATLAS 側で必須化マイグレーション推奨",
        )
        _PROMETHEUS_LIVE_ELIGIBLE_MISSING.labels(strategy_id=strategy_id).inc()
```

**ファイル**: `core/monitoring/metrics.py` 追加
```python
_PROMETHEUS_LIVE_ELIGIBLE_MISSING = _counter(
    "fx_live_eligible_key_missing",
    "Live 起動時に live_eligible キーが欠如した戦略数",
    ["strategy_id"],
)
```

### A-4: forward_test.py live_mode ガード

**ファイル**: `trading_platform/forward_test.py:137`
```python
# 旧
loaded = load_strategy(strategy_dir)

# 新
loaded = load_strategy(strategy_dir, live_mode=False)  # forward_test は常に Paper
```

**ファイル冒頭 docstring 強化**:
```python
"""
forward_test.py — ATLAS チャンピオン戦略の長時間 Paper forward test

⚠️ 重要: 本ファイルは常に PaperBroker 固定で動作する。
LIVE 流用は禁止。LIVE 起動は run_unified.py 経由のみ。
"""
```

### A-5-1: direction_bias 整合化 [⚠️ 検証で 3→2+1キー欠落に訂正]

**ファイル**: `strategies/imported/ATLAS-2026-0508-041/runner_config.json`
```json
{
  "_strategy_summary": {
    "direction_bias": "balanced"  // 旧: "any"
  }
}
```

**ファイル**: `strategies/imported/ATLAS-2026-0508-140/runner_config.json`
- 同様に `"any"` → `"balanced"`

**ファイル**: `strategies/imported/ATLAS-2026-0508-069/runner_config.json`
- `_strategy_summary` に `"direction_bias": "balanced"` を追加（現状キー欠落）

### A-5-2: strategy.py docstring 修正

**ファイル**: `strategies/imported/ATLAS-2026-0505-376/strategy.py:1`
```python
# 旧 docstring
"""ATLAS-2026-0505-360 — EUR_JPY H4 SMA20 Slope Entry"""

# 新
"""ATLAS-2026-0505-376 — CAD_JPY H4 SMA20 Slope Entry Long"""
```

**ファイル**: `0505-399/strategy.py`, `0505-400/strategy.py`, `0505-401/strategy.py`
- 戦略 ID を `352` → 各自の ID に訂正（通貨ペアは USD_JPY 維持）

### テスト追加

**ファイル**: `tests/integration/test_strategy_metadata_consistency.py` 新規
- `test_all_imported_strategies_runner_config_direction_bias_valid`: 全戦略の runner_config に `direction_bias` キーが存在し `any` でないこと
- `test_strategy_docstring_id_matches_directory`: docstring 冒頭の戦略 ID が directory 名と一致
- `test_loader_warns_on_missing_live_eligible`: live_mode + キー欠如で WARN ログ発出

### 検証ゲート
- 全テスト PASS
- `grep -rn '"direction_bias": "any"' strategies/imported/` で 0 件
- loader が起動時に WARN を出すが起動成功すること

### Live 影響
**小** — direction_bias 整合化で PTRC の動作が変わる可能性。各戦略のバックテスト結果と比較して挙動が変わらないこと

### Rollback
revert で OK

### 見積もり
2 時間

---

## PR6: A-6 (旧 B-1) on_fill 12戦略修正 + FillEvent 型統一 [REV-2 must_fix]

**目的**: 12 戦略の on_fill バグ修正。**REV-2: 検証手段が enum/dict 型不一致で無効化されないよう先行で型統一**

### 事前準備: FillEvent 型統一 [REV-2 先行タスク]

**ファイル**: `core/models/events.py` に FillEvent 定義確認
```python
class FillEvent(BaseEvent):
    direction: SignalDirection  # enum 必須
    # ...
```

**ファイル**: `ATLAS/atlas/backtest/vectorbt_engine.py` の `strategy.on_fill` 呼び出し箇所
```python
# 旧
strategy.on_fill({"direction": "FLAT", "price": ..., ...})  # str

# 新
strategy.on_fill({"direction": SignalDirection.FLAT, "price": ..., ...})  # enum
```

### コード変更 (各戦略の on_fill)

12 戦略 (`0504-098, 0506-024, 0506-031, 0507-016, 0507-066, 0508-041, 0508-140, 0510-002, 0512-023, 0512-035, 0512-061, 0512-101`) の `strategy.py::on_fill`:

```python
# 旧
def on_fill(self, fill_event):
    direction = fill_event.get("direction")
    if direction == SignalDirection.FLAT:
        self._intended_direction = SignalDirection.FLAT

# 新
def on_fill(self, fill_event):
    direction = fill_event.get("direction")
    if direction == SignalDirection.FLAT:
        self._intended_direction = SignalDirection.FLAT
    elif direction in (SignalDirection.LONG, SignalDirection.SHORT):
        self._intended_direction = direction
```

**除外**: `ATLAS-2026-0501-004` は `_position` 全方向更新で別構造のため対象外（v1 計画から訂正）

### テスト追加

**ファイル**: `tests/integration/test_strategy_on_fill.py` 新規
- 12 戦略それぞれに対し:
  - `test_{strategy_id}_on_fill_long_updates_intended`: LONG fill で `_intended_direction == LONG`
  - `test_{strategy_id}_on_fill_short_updates_intended`: SHORT fill で `_intended_direction == SHORT`
  - `test_{strategy_id}_on_fill_flat_resets`: FLAT fill で `_intended_direction == FLAT`
  - `test_{strategy_id}_no_double_entry_after_long_then_cancel`: LONG → FLAT(cancel) → 即時 LONG 再エントリーが cooldown で阻止される

### 検証ゲート [REV-2 反映]
- ユニットテスト 12 戦略 × 4 シナリオ = 48 件 PASS
- BT 再評価は **無効と判明したため実施しない**（v1 計画の「BT で確認」を撤回）
- **Paper Trading 30 日シャドー** で挙動確認（実用上の検証手段）
- 12 戦略の Paper trade_log と BT trade_log の差分が許容範囲内（PF±5%）

### Live 影響
**中** — on_fill の挙動が変わる。30 日シャドー期間中は Live 投入を保留

### Rollback
revert で OK

### 見積もり
6-8 時間 + 30 日シャドー期間（Live 投入判断は別セッション）

---

## PR6.5: kill_switch 5% → 15% 戻し [REV-6 対称処理]

**目的**: A フェーズ完了で防壁配線完了後、正式値に戻す

### コード変更
PR0.5 の対称処理。`core/models/risk.py` の `kill_switch_daily_loss: float = 0.05` → `0.15` に戻す。

**ファイル**: `logs/rule_change/2026-XX-XX_kill_switch_restored.jsonl`
```jsonl
{"timestamp":"2026-XX-XX","type":"hard_limit_change","field":"kill_switch_daily_loss","old":0.05,"new":0.15,"reason":"A phase completed, restoring nominal value","approver":"<user>","corresponds_to_pr":"PR0.5"}
```

### コミット種別
`[change:spec]`

### 検証ゲート
- A フェーズ全 PR (PR0-PR6) が Paper Trading 30 日シャドーで問題なし
- 0511-059 等の長期沈黙戦略を含めて全体の発火頻度が PR0 基準値の ±50% 以内

### Live 影響
**あり** — KS 発動閾値が緩和される

### 見積もり
1 時間

---

## A フェーズ完了 - 中間検証

A フェーズ全 PR マージ + 30 日 Paper シャドー完了後:
- `docs/audit_a_phase_completion.md` を作成
- 観測 KPI を v2 計画の「観測 KPI」セクションと突き合わせ
- B フェーズ着手の Go/No-Go 判定

---

## PR7: B-2 テスト補強 [REV-7 反映、全面改訂]

**目的**: 既存テストの偽緑を解消（v1 計画の H-TEST-2/3 は撤回）

### H-TEST-1 [REV-7 改訂]: データ本数増加で発火機会を確保

**ファイル**: `tests/conftest.py`
```python
@pytest.fixture
def sample_ohlcv_df(...):
    # 旧: 200 本
    # 新: 500 本（発火機会を確保するため）
    bars = 500
    ...
```

`assert signals_generated > 0` の追加は撤回（v1 案）。シグナル発生は監視ロジックに委ねる。

### H-TEST-2 [REV-7 改訂]: 決定論的二項テストに置換

**ファイル**: `tests/fault/test_oanda_api_fault.py:149-171`
```python
# 旧
def test_partial_failure_probability(self):
    random.seed(42)
    client = FaultOANDAClient(fail_probability=0.5)
    ...
    assert len(results) == 10  # アサートが薄い

# 新 (REV-7)
def test_zero_failure_probability_all_succeed(self):
    rng = random.Random(42)  # グローバル汚染回避
    client = FaultOANDAClient(fail_probability=0.0, _rng=rng)
    results = [client.fetch_candles(...) for _ in range(10)]
    assert all(r.success for r in results)

def test_full_failure_probability_all_fail(self):
    rng = random.Random(42)
    client = FaultOANDAClient(fail_probability=1.0, _rng=rng)
    results = [client.fetch_candles(...) for _ in range(10)]
    assert all(not r.success for r in results)
```

確率的アサートを廃止して決定論的二項テストに。

### H-TEST-3 [REV-7 撤回]: 強制 assert は実施しない

**ファイル**: `tests/integration/test_signal_flow.py:288-292`
- 現状の `if fills_completed > 0:` 条件付き設計を維持
- xfail 5戦略との矛盾を回避

真の E2E 検証は ATLAS-replay fixture (別タスク C-6) で実装。

### H-TEST-4 [REV-7 改訂]: 決定論的非同期テスト

**ファイル**: `tests/integration/test_multi_strategy.py` 新規
```python
@pytest.mark.asyncio
async def test_two_strategies_share_risk_state():
    # REV-7: 100 反復 → 10 反復、asyncio.sleep(0) で確定的タスク切替
    strategies = [_make_strategy(0511_059), _make_strategy(0510_002)]
    risk_state = RiskState(...)
    for _ in range(10):
        await asyncio.sleep(0)  # 明示的にタスク切替
        # 戦略 A の SL → daily_realized_pnl 更新
        # 戦略 B の generate_signal が更新後値を見る
        ...
    assert risk_state.daily_realized_pnl_total == expected_total
```

**前提**: PR8 の B-3 H-PLAT-2 (`_inflight_tasks` スナップショット明示化) を先に完了

### 検証ゲート
- 新規 4 テスト PASS
- 既存 360 件 + 新規 4 件 = 364 件で 5 xfail 維持

### Live 影響
**なし**（テストのみ）

### 見積もり
4-6 時間

---

## PR8: B-3 Event Bus / Strategy Loader [全 4 件完了]

### H-PLAT-1 [V-5 反映]: Redis dedup 二段構成 ✅ (PR8b: 2026-05-23)
- 新規 `trading_platform/core/event_bus/dedup.py`:
  * `compute_event_id(event)`: `correlation_id + event_type + bar_time/timestamp`
    の sha256[:16] (= 64bit) 決定的ハッシュ
  * `LocalDedupLRU`: OrderedDict ベース、TTL 300 秒、上限 10000 件
  * `DEDUPABLE_EVENT_TYPES`: BAR/SIGNAL/ORDER/FILL/RISK_ALERT (HEARTBEAT/TICK 除外)
- `RedisEventBus.__init__` に `enable_dedup`、`dedup_ttl_sec`、`metrics` 引数追加
- `_dispatch` 冒頭で Local LRU → Redis SETNX の順に dedup チェック。重複なら skip
- `metrics.py`: `fx_event_bus_dedup_total{layer, event_type}` Counter 追加
  (layer ∈ local/redis)
- `main.py` 配線: PRODUCTION 環境で `RedisEventBus(enable_dedup=True, metrics=...)`
- 新規テスト 13 件: compute_event_id 3件 / LocalDedupLRU 5件 + 定数1 / _dispatch 4件
- 注: playbook の "bar_close_time" は実コード `bar_time` (バー開始時刻) と等価
  (timeframe と組み合わせて一意識別)

### H-PLAT-2: InMemoryEventBus `_inflight_tasks` スナップショット明示化 ✅ (PR8a 5bc655a)

### H-PLAT-3 [REV-5 反映]: Paper モード Gate 検証 ✅ (PR5 f1396fd)
- `live_eligible=False` 拒否 + キー欠如時 WARN + Prometheus counter (PR5 に統合)

### H-PLAT-4: ADR は PR2 で作成済み (50e0313)

### 検証結果 (PR8b 完了時)
- tests/unit + arch + risk_engine: 784 passed (+13)
- tests/integration (既知 hang 除外): 650 passed, 1 skipped, 5 xfailed
- 既存テスト 0 件 regress

### Live 影響
- **あり** (重複処理の防止): Redis 経路の重複再送/フォールバック後の重配信で
  下流ハンドラが二度呼ばれていた潜在バグを 300 秒窓で吸収。
  `fx_event_bus_dedup_total` で観測可能。
  enable_dedup=False で完全無効化可 (緊急ロールバック用)。
- **なし** (HEARTBEAT/TICK 経路): dedup 対象外なので頻度は不変

### 見積もり
8-12 時間 → 実績 約 1.5 時間

---

## PR9: B-4 監視・運用 4件 [2026-05-22 完了]

### H-OPS-1: `HealthChecker.is_healthy` を `_aggregate_system_status() == "healthy"` に置換 ✅
- 旧実装は `_components` の healthy フラグだけを集約していたため prober 失敗で
  `_component_statuses[name].status = "unhealthy"` でも `_components` 側が
  取り残されていると True を返す死角があった。`_apply_staleness_sync()` +
  `_aggregate_system_status()` に統一。

### H-OPS-2: `run_unified.py:setup_logging()` を削除、`configure_logging()` を呼ぶ ✅
- `trading_platform/common/logger.py:configure_logging` に `log_filename` 引数を追加
  （後方互換のためデフォルト `"app.log"`）。`run_unified.py` から
  `configure_logging(log_dir=LOG_DIR, to_file=True, log_filename="unified_runner.log")`
  を呼び、ローカル `setup_logging()` 関数 (stdlib logging のみ・JSON 化なし) を撤去。
- structlog の `ProcessorFormatter` 経由で `unified_runner.log` に JSON 形式で書き出される。

### H-OPS-3: watchdog プロセス検出を PID ベースに変更 ✅
- `start_unified_runner.ps1` で起動した python プロセスの PID を
  `logs/unified_runner.pid` (ASCII) に書き出す。起動失敗時は PID ファイルを削除。
- `runner_watchdog.ps1` は PID ファイル → `Get-Process -Id <pid>` 経路で死活確認。
  PID 不在時のみ従来のコマンドライン文字列マッチ (`*run_unified*`) にフォールバック。
- `.gitignore` に `logs/unified_runner.pid` / `logs/*.pid` 追加。

### H-OPS-4: EmailNotifier SSL context + 3回リトライ + Prometheus counter 化 ✅
- `ssl.create_default_context()` を SMTP_SSL / starttls 双方に明示的に渡し、
  証明書・ホスト名検証を強制（旧実装は Python のデフォルトに依存）。
- `_send_email_async` に指数バックオフリトライ（1s → 2s、合計 3 試行）を追加。
  リトライ間 sleep はテスト時に `_SMTP_RETRY_BASE_SLEEP_SEC` を 0 に上書き可能。
- `MetricsCollector` を任意注入できるよう EmailNotifier コンストラクタに `metrics` 引数追加。
  新規 counter: `fx_email_notifier_sent_total{kind}` / `fx_email_notifier_failures_total{kind}`
  / `fx_email_notifier_retries_total{kind}` (`kind ∈ {fill, kill_switch}`)。
- `stats` プロパティに `retry_count` を追加。

### 削除: M-OPS-6 (誤りと判明、削除済み)

### 検証結果 (commit 未確定)
- tests/unit 697 / tests/architecture 149 / tests/parity 56 / tests/risk_engine+fault+performance 68
- tests/integration 650 passed + 1 skipped + 5 xfailed（既知 hang 除外で実行、baseline 維持）
- 新規テスト: HealthChecker `TestIsHealthyAggregation` 4 件 + EmailNotifier H-OPS-4 5 件
- Live 影響: なし（注入式メトリクスは main.py 起動時の wiring が必要、本 PR ではテストパスのみ）

### 実装メモ
- PR5 で確立した `MetricsCollector` 注入パターン (loader.py) と同方針で EmailNotifier も追加注入対応。
  main.py 側の `MetricsCollector` 配線は次回 (PR9.1 or PR10) で実施予定。

### 見積もり
4-6 時間 → 実績 約 1.5 時間

---

## PR10: B-5 H-EXEC 系 + REV-8 _processed_fills 設計改訂 [2026-05-23 完了]

### H-EXEC-1: PaperBroker FLAT 決済時に `prices=None` で早期 return ✅
- 旧実装は `prices is None` でも `base_price = context_snapshot.price` で
  fall through し、古い snapshot 価格を「現在の中値」として流用 → 決済 PnL が
  偽装される深刻な問題。明示的に拒否するよう変更
- エントリ (LONG/SHORT) は従来通り snapshot.price フォールバックを保持
  （他の防壁で守られるため）
- 新規テスト 4 件 (`tests/unit/test_paper_broker_handle_exit.py`)

### H-EXEC-2 [REV-8 改訂]: `_processed_fills` を OrderedDict + 7日 TTL ✅
- 旧 `set[tuple]` で永久蓄積していたためメモリリーク懸念 → `OrderedDict[(str,str), float]`
  に変更。value は `time.time()` スタンプ
- `_evict_expired_processed_fills(now)` で 7 日経過分を頭から popitem
- 安全上限 `PROCESSED_FILLS_MAX=50_000` 超過時に最古から強制 evict + WARN
- 新規テスト 5 件 (TTL evict / fresh 維持 / safety cap / OrderedDict 型 / timestamp 記録)
```python
class FillProcessor:
    def __init__(self):
        self._processed_fills: OrderedDict[tuple[str, str], float] = OrderedDict()
        # key: (order_id, broker_fill_id) or (order_id,) if fill_id is None
        # value: processed_timestamp (TTL 判定用)

    def _is_duplicate(self, order_id: str, fill_id: str | None) -> bool:
        key = (order_id, fill_id) if fill_id else (order_id,)
        now = time.time()
        # TTL 7日でクリーンアップ
        self._evict_expired(now - 7 * 86400)
        if key in self._processed_fills:
            return True
        self._processed_fills[key] = now
        if len(self._processed_fills) > 50000:  # 安全上限
            logger.warning("processed_fills_overflow")
        return False
```

### H-EXEC-3: PTRC `_check_max_daily_loss` に SL 想定損失加算 ✅
- 旧実装は当日の実現損益 + 未実現損益のみで判定 → ぎりぎりまで損失が膨らんだ後の
  追加発注で閾値を超える注文が通る死角。`worst_case = existing_loss - pending_sl_loss`
  に変更
- 新規 helper `_estimate_pending_sl_loss_in_account(order)` で SL 到達時の
  account 通貨建て損失を見積もり、通貨換算経由（StaticCurrencyConverter 等）も対応。
  換算不能時は 0 fallback で `_check_max_risk_per_trade` 側に判定を委譲（重複 reject 回避）
- `evaluate()` の呼出側を `_check_max_daily_loss(order, risk_state, portfolio)` に変更
- 新規テスト 6 件 (`tests/unit/test_ptrc_daily_loss_sl.py`)

### H-EXEC-4: RetryManager 配線判断 — docstring 明示化のみ ✅
- 現状確認: `submit_with_retry()` は本番 LIVE 経路では呼ばれていない (テストのみで使用)。
  しかし `KillSwitch.register_components(retry_manager=...)` 経由で `stop_all()` は
  活きており、kill_switch 連携の stop barrier として機能している
- 本 PR では最小変更: retry_manager.py の docstring に「本番未配線」「将来 配線/削除
  どちらかを別 PR で判断」と明記。次 PR で:
  (a) coordinator から `submit_with_retry` を呼ぶ実配線、または
  (b) dead code 削除 + `kill_switch.register_components` から除外
  のどちらかを ADR で決定

### 検証結果 (commit 未確定)
| ディレクトリ | passed | skip | xfail |
|---|---|---|---|
| tests/unit | 560 | 0 | 0 |
| tests/architecture | 154 | 1 | 0 |
| tests/risk_engine | 29 | 0 | 0 |
| tests/integration | 650 | 1 | 5 |
| tests/parity+fault+performance | 95 | 0 | 0 |
| **合計** | **1488** | **2** | **5** |

新規テスト 15 件 (PaperBroker 4 + FillProcessor 5 + PTRC 6) 全 PASS、既存テスト 0 件 regress。
architecture テストの誤検知（retry_manager.py docstring 内の `broker_gateway.submit()` 文字列が
直接呼び出しと判定された）を修正済み。

### Live 影響
- **あり** (PTRC SL 加算): これまで閾値ぎりぎりで通っていた注文が REJECT される。
  ただし「日次損失を加速させない」防壁として意図通り。Paper シャドー期間中に
  `fx_ptrc_reject_total{reason="max_daily_loss"}` の発生頻度を観測すること
- **あり** (PaperBroker FLAT 拒否): Live runner が決済時に最新価格を保持していない
  ケース (再起動直後など) で決済が一時的に失敗する。Position Reconciler のリトライ
  経路で復旧する想定
- **なし** (FillProcessor TTL / RetryManager docstring): 既存挙動は不変

### 見積もり
6-10 時間 → 実績 約 2 時間

---

## PR11: REV-11 Position Reconciler 強化 [A-1 と並走想定だが計画上ここに]

**目的**: A-1-2 cancel 失敗 / A-1-3 換算誤り / B-5 evict 後再送 fill の最終防衛線

### コード変更
- `core/execution_engine/position_reconciler.py` の検出感度強化
- OANDA 側 position と内部 state の差分検知頻度を 60秒 → 30秒
- 差分検出時に `fx_position_reconciler_mismatch_total` メトリクス + Email アラート

### 見積もり
6-8 時間

---

## PR12: B-6 H-DATA 系 [2026-05-23 完了]

### H-DATA-1: LiveFeatureStore `_feature_compute_errors` フラグ追加 ✅
- 旧実装は `_recompute_tf` / `_realign_aux_features` の例外を `logger.warning`
  のみで処理しており、ATLAS BT との Parity ドリフト・欠損が運用 dashboard で
  観測できなかった
- `LiveFeatureStore.__init__` に `metrics: MetricsCollector | None = None`
  引数追加。`_feature_compute_errors: dict[(name, tf), int]` を in-process カウンタとして保持
- 新規 `_record_compute_error(name, tf)` で in-process と Prometheus 両方を更新
- `feature_compute_error_counts` プロパティを公開し Dashboard が読める形に
- `metrics.py`: `fx_feature_store_compute_errors_total{name, timeframe}` Counter 追加

### H-DATA-3: `register()` で period > MAX_REGISTRABLE_PERIOD はハード ValueError ✅
- 旧実装は `_warn_trim_once` の WARN ログのみで戦略登録時は素通り
- 全 `_PERIOD_PARAM_KEYS` (短縮形含む) を `register()` 入口で検査し
  ValueError を投げる能動防壁化
- **閾値変更**: playbook 初期案 400 → **1000** に拡張 (2026-05-23 確定)。
  理由: 既存 LIVE 戦略 ATLAS-2026-0508-069 が ema_800 を使用しており 400 では
  Live 互換性が損なわれた。1000 はガード本来の意図 (無制限拡大の防止) と
  既存戦略の許容を両立する判断。
- `MAX_BUFFER_SIZE` も整合的に 20000 → 50000 に拡張
  (1000 × BUFFER_SAFETY_FACTOR=50 = 50000。メモリ 2.4MB/TF buffer)

### H-DATA-4 [C-DATA-2 訂正版]: `_PERIOD_PARAM_KEYS` に短縮形追加 ✅
- 旧 KEYS: `period`, `fast_period`, `slow_period`, `signal_period`, `smooth`
- 新 KEYS: 上記 + `fast`, `slow`, `signal`
- `indicators._macd` は `fast=N` 等の短縮オーバーライドを受け取るが、
  これらが `_recalculate_effective_buffer_size` から漏れていたため
  `fast=100` を指定しても buffer が拡張されず、トリミング後 EWM 初期値
  ドリフトを誘発する死角があった

### H-DATA-2: `_recompute_tf` プロファイル取得 [本 PR では未着手]
- playbook 注記: 「修正は M15/H1 レイテンシ実測次第」
- Live 計測データが蓄積されてから別 PR で判断

### main.py 配線
- `LiveFeatureStore(metrics=self._metrics)` で本番でも errors_total を収集

### 検証結果
- tests/unit + arch + risk_engine: 765 passed (+13)
- tests/integration (既知 hang 除外): 650 passed, 1 skipped, 5 xfailed
- tests/parity: 56 PASS (test_buffer_size_max_cap は新動作 ValueError に書き換え)
- 新規テスト 11 件 (test_live_store_pr12.py: H-DATA-1 4件 + H-DATA-3 4件 + H-DATA-4 3件)

### Live 影響
- **あり** (period ガード): ATLAS-2026-0508-069 の ema_800 は許容、それ以上の
  period を持つ戦略があれば起動失敗。LIVE 23 戦略を grep で確認した結果、800
  以上の period は ema_800 のみ
- **なし** (FeatureStore 計算エラー counter): 既存挙動は不変、観測情報のみ追加
- **なし** (短縮形 KEY 追加): buffer 拡張がより正確になる方向 (Parity 改善)

### 見積もり
4-6 時間 → 実績 約 1.5 時間

---

## PR13: B-7 SMA50/200 Live 確認 (発火頻度は PR0 で実施済み)

### H-DEV-2: Task G の Live FeatureStore 値確認
- `unified_runner.jsonl` から SMA50/SMA200 の直近 1 週間値を抽出
- EUR/USD が SMA50<SMA200 (downtrend) を満たしているか確認

### H-DEV-3: Task F Event ID 4688 取得 (環境依存、手動実施)

### 見積もり
30 分 + 環境依存

---

## A・B フェーズ完了 — 中間再監査の検討

PR0-PR13 完了時点で:
- 観測 KPI レビュー
- Paper 30日シャドーの統計レビュー
- Live 投入の Go/No-Go 判定

ここで **小規模再監査** を実施し、C フェーズ着手前に問題を洗い出すことを推奨。

---

## PR14-PR20+: フェーズ C (Medium 対応)

C フェーズ 31 件は性質ごとにグループ化:

| PR | 内容 | 件数 | 見積もり |
|---|---|---|---|
| PR14 | C-1 アーキテクチャ整理 (M-PLAT-1〜7) | 7 | 12-16h |
| PR15 | C-2 リスク執行系細部 (M-EXEC-1〜5) | 5 | 8-12h |
| PR16 | C-3 データ層細部 (M-DATA-1〜6) | 6 | 8-12h |
| PR17 | C-4 監視細部 (M-OPS-1〜5) | 5 | 6-8h |
| PR18 | C-5 戦略コード細部 (M-STRAT-1〜3) | 3 | 2-3h |
| PR19 | C-6 テスト細部 (M-TEST-1〜6) | 6 | 8-12h |
| PR20 | C-7 直近修正 (M-DEV-2) | 1 | 2h |

**REV-12 反映**: M-PLAT-1 (correlation_id) / M-PLAT-6 (BarEvent.is_complete) は grep 完了後に再見積もり

### 見積もり
46-65h（旧 40-60h から修正）

---

## C フェーズ完了

---

## PR21+: フェーズ D (Low/Info)

- L-PLAT-1〜4, L-EXEC-1〜3, L-OPS-1〜2, L-DATA-1〜3: ドキュメント化または将来計画タスク化
- I-1: ADR (`docs/adr/0002_strategy_slot_event_bus_migration.md`) 作成
- I-2: `ImmutableHardLimits` 変更プロセスを `docs/runbook/hard_limit_change.md` に明文化

### 見積もり
8-12h

---

## 最終ゲート — 全 PR マージ後

1. **コードベース全体の整合性確認**
   - `pytest -q` で全件 PASS (xfail 5件のみ許容)
   - `grep -rn '"direction_bias": "any"'` で 0 件
   - `_processed_fills` のメモリ使用量が安定
   - `fx_snapshot_persistence_failures_total` が 0

2. **Paper Trading 30 日シャドー完了**
   - 全 23 LIVE 戦略の発火頻度が PR0 基準値の ±50% 以内
   - 12 戦略 (PR6 対象) の挙動が BT と乖離しないこと

3. **Live 投入判断 (別セッション)**
   - 上記全項目クリア → kill_switch を 5% → 15% (PR6.5)
   - 段階的に各戦略を Live 投入

4. **再監査セッション**
   - 本セッションと同レベルの 7 専門家並列調査
   - 期待: 残存問題は Critical 0、High が大幅減少していること

---

## 改訂後の見積もり総括 (v2)

| フェーズ | 旧見積もり (v1) | 新見積もり (v2) | 主な変化 |
|---|---|---|---|
| A-0 | — | 4-6h | 新規追加 (REV-3) |
| A | 19-29h | 25-37h | REV-1/4/6/9 反映で増加 |
| B | 32-48h | 32-48h | REV-7 で減少、REV-11 繰上で B-6 簡略化 |
| C | 40-60h | 46-65h | REV-12 で増加 |
| D | 8-12h | 8-12h | 変更なし |
| **合計** | **99-149h** | **115-168h** | 約 3-5 週間 (継続作業ベース) |

※ 30 日 Paper シャドーは並行進行のため、純実装時間には含まない

---

## 残余リスクのまとめ

修正計画 v2 + 本プレイブック実行後も残る既知リスク:

1. **REV-2 で BT 検証が無効と判明** — on_fill 修正の最終検証は Paper 30 日シャドーに依存
2. **REV-3 でロールバック基準確定** — 戦略別期待発火間隔の精度に依存（PR0 で実測）
3. **A-1-1 中間状態 (PR2 のみマージ)** — SnapshotWriter は機能するが KS 旧式の窓を REV-4 の連続スプリント制約で短縮
4. **PR11 Position Reconciler 強化を計画上 A-1 並走想定だが、実 PR 順序では A-1 後** — 実行時に並走へ前倒し検討
5. **C フェーズ M-PLAT-1/6 の見積もり過小リスク** — grep 完了時に再見積もり必須

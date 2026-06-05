# FX システム総合監査レポート

**実施日**: 2026-05-21
**監査体制**: 専門家エージェント 7名（並列実行）
**対象**:
- `C:\data\works\FX\fx_trading_system\` (Live Trading Platform)
- `C:\data\works\FX\ATLAS\` (Strategy Generation System)
- 直近コミット (`977444e`, `abd12fc`, `213cc1a`)
- LIVE 戦略 23+ （実態 60戦略）

---

## エグゼクティブサマリ

> **本レポートは2段階監査済み**: 7専門家による一次調査の後、3名の検証チーム（devil-advocate / qa-tester / devops-monitor）が独立に Critical 全件と High 主要項目を再検証。検証で訂正された項目は ✅⚠️❌ マーカー付き

| 重大度 | 件数 | 主な領域 |
|---|---|---|
| **Critical** | **7** (元9 → 2件降格) | リスク執行系・データ層・戦略コード |
| **High** | **20** | 全領域横断 |
| **Medium** | **31** (元30 + Critical降格2件) | アーキテクチャ、テスト、運用 |
| **Low/Info** | **13** | 観察・将来対応 |
| **訂正・削除** | **6** | 検証で事実誤認が判明した項目 |

### 検証で訂正された主要項目
- **C-DATA-2**: `_PERIOD_PARAM_KEYS` の主張内容に事実誤認 → **Critical → High に降格**
- **C-PLAT-2**: Pydantic v2 再構築でのエラー経路に誤り → **Critical → Medium に降格**
- **C-STRAT-1**: 3戦略 → 実態 2戦略 + 1戦略はキー欠落
- **C-DEV-1**: 1戦略 True / 22戦略欠如 → 実態 5戦略 True / 53戦略欠如
- **H-STRAT-1**: 13戦略 → 実態 12戦略（ATLAS-2026-0501-004 は誤分類で除外）
- **M-OPS-6**: `_total_total` 二重サフィックス問題 → **❌ 削除（誤り、prometheus_client が防止する）**

### 即時対応が必要な3つの根本問題（検証後・確定）

1. **UnifiedRunner 経路で Hard Limit 防壁が実効的に無効化**（C-EXEC-1, 2, 3）✅ 検証済み
   - Trade Context Snapshot 未配線（規制リスク）
   - KillSwitch クラスが本番経路で使われず、自動停止が機能しない（`_evaluate_kill_switch:604-619` は実現損益のみ参照）
   - 非 JPY pair で Exposure 制限が機能しない
2. **TODO.md の「Task D 完了」判定が誤情報**（C-DEV-1）⚠️ 数値訂正
   - **59戦略中 53戦略**（元主張の22戦略は誤り）が `live_eligible` キー欠如のため検証スキップで通過
   - True 明示は 5戦略のみ（元主張の1戦略は誤り）
3. **Live 0 件問題の真因候補：BarBuilder の `truth_source` デフォルトが Tick 集約**（C-DATA-1）✅ 検証済み
   - 本番設定での OANDA candle 強制が結線されていない可能性

---

## Critical 問題（重大度: 即時対応）

### C-EXEC-1: UnifiedRunner 経路で Trade Context Snapshot 永続化が完全欠落
- **発見者**: risk-execution-engineer
- **ファイル**: `core/unified_runner/strategy_slot.py:552-635` / `runner.py`
- **問題**: `ExecutionCoordinator` のみが `SnapshotWriter.write_or_raise` を呼ぶ fail-closed 経路を実装。本番経路 `UnifiedRunner` → `StrategySlot._handle_entry/_handle_exit` は `self.gateway.submit(order)` を直接呼び SnapshotWriter は未配線。CLAUDE.md「全注文判断時に Trade Context Snapshot を保存する」要件違反。
- **影響**: Live 取引で発注理由の事後検証不能、規制対応不適合

### C-EXEC-2: UnifiedRunner 経路で PTRC-Post / KillSwitch が無効化
- **発見者**: risk-execution-engineer
- **ファイル**: `runner.py:326-394` / `strategy_slot.py:612-635` / `risk_supervisor.py:604-619` (`_evaluate_kill_switch`)
- **問題**: `KillSwitch` クラス（15% Hard Limit、永続化、in-flight cancel）は `ExecutionCoordinator` 経路でのみ駆動。UnifiedRunner は `GlobalRiskSupervisor` を使い、(a) `account_state` 未永続化、(b) `cancel_order` 未実装、(c) `_evaluate_kill_switch` が `daily_realized_pnl_total` のみ参照、未実現損失は判定に含まれず発動不能。
- **影響**: Live で 15% Hard Limit を突破しても自動停止しない。再起動で KS が解除される
- **検証状態**: ✅ 確認済み（行番号 582-591 → 604-619 に訂正）

### C-EXEC-3: PTRC `_check_total_exposure` が非 JPY pair で機能しない
- **発見者**: risk-execution-engineer
- **ファイル**: `core/risk_engine/ptrc.py:343-412`
- **問題**: `_check_max_risk_per_trade` は通貨換算するが、`_check_total_exposure` は notional (quote通貨) を `account_balance` (JPY) で直接除算。EUR/USD・GBP/USD・AUD/USD で比率が約 150 倍小さく算出され、Exposure 上限 8.0x が事実上無効化
- **影響**: 非 JPY pair で 25 倍レバレッジまで積み上がる可能性

### C-DATA-1: BarBuilder `truth_source` デフォルトが Tick 集約 (Live 0 件問題の真因候補)
- **発見者**: data-engineer
- **ファイル**: `data/market_data/bar_builder.py:80, 195-211`
- **問題**: `truth_source="tick_aggregation"` がデフォルト。`candle_fetcher.py:7-13` のコメントでは「OANDA candles API を唯一の Truth」と明記。本番設定で `oanda_candle` への切替が settings.py 経由で必須だが、強制化されていない
- **影響**: BT/Live で Bar OHLCV が乖離 → Donchian/BB/ATR で数値分岐 → BT で発火するシグナルが Live で発火しない（TODO.md Task G「Live 0 件問題」の真因候補）

### C-DATA-2: Live `_macd` バッファ拡張ルールが短縮形キー (`fast`/`slow`/`signal`) を見落とす
- **発見者**: data-engineer
- **ファイル**: `data/feature_store/indicators.py:96-112` + `live_store.py:56-62`
- **問題**: `_PERIOD_PARAM_KEYS` の実値は `("period", "fast_period", "slow_period", "signal_period", "smooth")`。標準キー（`fast_period`/`slow_period`/`signal_period`）は含まれている。**含まれていないのは短縮形 `fast`/`slow`/`signal`**。短縮形を使う戦略が存在する場合のみバッファ拡張が効かない
- **影響**: Parity 数値乖離リスク（条件依存）。実害は短縮形キー使用戦略が `imported/` に存在する場合のみ — 別途確認推奨
- **重大度再評価**: Critical → **High** に降格（短縮形使用戦略が存在しないなら実害なし）
- **検証状態**: ⚠️ 主張の前提が不正確 — 元の `fast/slow/signal が無い` は事実だが、それは「短縮形が無い」だけで `fast_period/slow_period/signal_period` は存在する。Critical 降格

### C-PLAT-1: `forward_test.py` で `live_mode` を `load_strategy` に渡していない
- **発見者**: platform-architect
- **ファイル**: `trading_platform/forward_test.py:137`
- **問題**: 既知の `runner.py` 修正 (Task D) と非対称。`forward_test.py` を LIVE 流用すると Gate 検証が緩む
- **影響**: 運用者の改変リスク

### C-PLAT-2: `RiskState.__setattr__` ガードのリスク経路（Pydantic v2 model_validate ではなく直接代入）
- **発見者**: platform-architect
- **ファイル**: `core/models/risk.py:128-138` / 実リスク経路: `circuit_breaker.py:147-148` (`self._risk_state.is_circuit_breaker_active = False`), `reset()`
- **問題**: `model_validate_json` 初回構築では `self.__dict__` が空なので AttributeError 発生せず（検証チームが指摘）。**実際の発火経路は `instance.is_kill_switch_active = X` のような直接代入**で、`token_ok=False` の状況で起きる
- **影響**: 直接 setattr 経路でのみ顕在化。再起動時 model_validate 経由なら問題なし
- **重大度再評価**: Critical → **Medium** に降格（リスク経路が限定的）
- **検証状態**: ⚠️ 発動経路の主張が不正確

### C-STRAT-1: `direction_bias='any'` が runner_config.json に 2 戦略で取り残し + 1 戦略でキー欠落
- **発見者**: code-safety-reviewer
- **検証訂正**: 実態は以下:
  - `ATLAS-2026-0508-041/runner_config.json`: `"direction_bias": "any"` ✅ 確認
  - `ATLAS-2026-0508-140/runner_config.json`: `"direction_bias": "any"` ✅ 確認
  - `ATLAS-2026-0508-069/runner_config.json`: **`direction_bias` キー自体が存在しない**（元の「`any` のまま」は誤り）
- **問題**: 041 / 140 は廃止値 `any` の取り残し。069 は metadata と runner_config 間で整合性キーが欠落
- **影響**: PTRC の direction_bias 整合性チェック誤動作 (041/140) + キー欠落によるサイレント挙動 (069)
- **検証状態**: ⚠️ 主張は概ね正確だが 069 は別問題（キー欠落）に分類が必要

### C-STRAT-2: strategy.py の docstring 内 generation_id 不一致 (4戦略)
- **発見者**: code-safety-reviewer
- **対象**: ATLAS-2026-0505-{376, 399, 400, 401}
- **問題**: directory 名と strategy.py docstring の戦略 ID が乖離。0505-376 は `EUR_JPY H4` と書かれているが実態は CAD/JPY
- **影響**: 障害対応時の通貨ペア誤判断リスク

### C-DEV-1: TODO.md「Task D: 23戦略 live_eligible 確認 OK」の根拠が薄弱
- **発見者**: devil-advocate
- **検証訂正**: 実測（全 imported/ 配下 59戦略の grep）:
  - `live_eligible: true` 明示: **5戦略**（ATLAS-2026-0507-038, 0504-248, 0508-061, 0506-032, 0508-041）
  - `live_eligible: false` 明示: 1戦略（ATLAS-2026-0504-216）
  - キー欠如: 53戦略
- **問題**: 元 devil-advocate の「True 明示は 0507-038 のみ」「22戦略がキー欠如」は誤り。ただし**多数 (53戦略) がキー欠如で検証スキップ**という構造問題は依然存在。loader.py の `if "live_eligible" in metadata:` 条件はキー欠如時にスキップ（行311-316）
- **影響**: TODO.md の「live_eligible 確認 OK」記述は誤った安心感。キー欠如戦略の検証スキップ動作が運用知識として共有されていない
- **検証状態**: ⚠️ 元主張の数値が誤り — 「1戦略のみ True / 22戦略欠如」は実際は「5戦略 True / 53戦略欠如」

---

## High 問題（重大度: 計画的対応）

### リスク・執行系
- **H-EXEC-1**: `PaperBroker._handle_exit` で `prices` 未初期化 NameError リスク (`simulator.py:84-107`)
- **H-EXEC-2**: `FillProcessor._processed_fills` セットの無制限増加（メモリリーク, `fill_processor.py:48,92`）
- **H-EXEC-3**: PTRC `_check_max_daily_loss` が SL 想定損失を加味せず、連続損失中に上限突破注文を通過
- **H-EXEC-4**: `RetryManager` が coordinator から未配線（dead code 化）

### プラットフォーム
- **H-PLAT-1**: `RedisEventBus._dispatch_local` Redis 復活後の二重配信 (`redis_adapter.py:214-233`)
- **H-PLAT-2**: `InMemoryEventBus._inflight_tasks` 競合
- **H-PLAT-3**: Paper モード Gate 未通過 silent allow（`loader.py:298-321`）
- **H-PLAT-4**: `worker.py` と `strategy_slot.py` の二重実装 (DRY 違反 / Event-Driven 原則違反)

### データ層
- **H-DATA-1**: FeatureStore 例外フォールバック挙動が ATLAS と非対称（観測性低下）
- **H-DATA-2**: `_recompute_tf` が毎バー全特徴量を全バッファ再計算（レイテンシ懸念）
- **H-DATA-3**: バッファトリミング後の EWM ドリフトを保証する `period > 400` のハード上限なし
- **H-DATA-4**: `_macd` の `signal_period` を `_PERIOD_PARAM_KEYS` に含めることでバッファ overkill / 設計不整合

### 監視・運用
- **H-OPS-1**: `HealthChecker.is_healthy` が `degraded` 状態を無視（False Positive, `health_check.py:215-216`）
- **H-OPS-2**: `run_unified.py:setup_logging()` が `configure_logging()` を呼ばず structlog が機能しない（`scripts/run_unified.py:38-62`）
- **H-OPS-3**: `runner_watchdog.ps1` プロセス検出が `CommandLine -like '*run_unified*'` 文字列マッチで誤検知リスク
- **H-OPS-4**: `EmailNotifier._send_email_async` が SSL context 渡さず、リトライなしで瞬断 1 回で永久欠損

### 戦略コード
- **H-STRAT-1**: **12戦略**の `on_fill` が FLAT 遷移のみ更新し LONG/SHORT fill 通知を無視 → 注文キャンセル時の `_intended_direction` 競合
  - 対象訂正: `0504-098, 0506-024, 0506-031, 0507-016, 0507-066, 0508-041, 0508-140, 0510-002, 0512-023, 0512-035, 0512-061, 0512-101`（**ATLAS-2026-0501-004 は除外** — `_intended_direction` 不使用で `_position` を全方向更新するため誤分類だった）
  - 検証状態: ✅ 12戦略は確認、0501-004 は誤分類訂正
- **H-STRAT-2**: 4戦略が `take_profit_pips=None` を返す（TradeSignal モデルの許容性未確認）
- **H-STRAT-3**: `bollinger_upper/lower` 登録時の `std_dev=` vs `std=` キーワード不統一

### テスト基盤
- **H-TEST-1**: `test_signal_flow.py::test_signal_generation_with_data` で `signals_generated` 未アサート → generate_signal 常時 None 退行を見逃す
- **H-TEST-2**: `test_oanda_api_fault.py::test_partial_failure_probability` が実質的アサートなし
- **H-TEST-3**: `test_signal_flow.py::test_full_signal_to_fill_flow` で `fills_completed=0` 許容により E2E コア検証スキップ
- **H-TEST-4**: `test_multi_strategy.py` が存在しない → 共有 RiskState のレース条件未検出

### 直近修正の敵対的レビュー
- **H-DEV-2**: Task G「条件不成立で正常」の Live FeatureStore 計算正常性が未検証
- **H-DEV-3**: Task F 起動元未特定のまま KPI-4 を「監視中」とする論理矛盾

---

## Medium 問題（重大度: 通常対応）

### プラットフォーム
- M-PLAT-1: `Order.correlation_id` default_factory=uuid4 と BaseEvent 設計の不整合
- M-PLAT-2: `VirtualPosition.is_flat` 浮動小数誤差で `quantity==0` 誤判定
- M-PLAT-3: `PortfolioManager._calculate_used_margin` レバレッジ計算で通貨換算抜け
- M-PLAT-4: `_audit_strategy_imports` AST 検査の限界（既知、二段構えで防御済み）
- M-PLAT-5: Windows でシグナルハンドラ非対応の経路非対称
- M-PLAT-6: `BarEvent.is_complete=True` デフォルト
- M-PLAT-7: `EventType` Redis channel 衝突リスク（env prefix 未対応）

### リスク・執行系
- M-EXEC-1: `KillSwitch.manual_reset` の StateStore 永続化が fire-and-forget
- M-EXEC-2: `CircuitBreaker._cooldown` が KS 発動中でも自動解除
- M-EXEC-3: `OrderManager._generate_client_order_id` 衝突可能性
- M-EXEC-4: `_check_spread` の dict 分岐が dead code
- M-EXEC-5: `ptrc_post.evaluate_fill` Level 3 発動条件が緩い

### データ層
- M-DATA-1: `_align_aux_to_primary` merge_asof の毎回 full 走査
- M-DATA-2: `update_bar` の `pd.concat` が O(n) コピー
- M-DATA-3: `validate_bar` の `max_price_jump_pct=2.0` が週末ギャップで第1月曜バーを reject
- M-DATA-4: `HEARTBEAT_TIMEOUT_SEC=15` が週末クローズ中に再接続ループ
- M-DATA-5: `_align_aux_to_primary` の tz-naive index 混入リスク
- M-DATA-6: StateStore `last_bar_time` キーの timeframe 表記揺れ防御なし

### 監視・運用
- M-OPS-1: Dashboard が `time.sleep` ブロッキングで Streamlit イベントループ停止
- M-OPS-2: `_apply_staleness_sync` warning 閾値時に後方互換 healthy フラグが下がらない
- M-OPS-3: アラートルール欠落 (`fx_feature_staleness_sec`, `position_reconciler_mismatch_total` 等)
- M-OPS-4: Runbook 未文書化シナリオ (EmailNotifier SMTP 失敗、watchdog 再起動ループ等)
- M-OPS-5: watchdog タスクの RunLevel 不整合
- ~~M-OPS-6: `fx_ptrc_reject_total` 等の Prometheus メトリクス名 `_total_total` 二重サフィックス問題~~ — **❌ 削除: 検証で誤りと判明。`prometheus_client` は name 末尾に既に `_total` がある場合は二重付与しない（既知の実装）。エクスポート名は `fx_ptrc_reject_total` のままで alerting_rules.yml と一致する**

### 戦略コード
- M-STRAT-1: ATLAS-2026-0501-004 `on_fill` の条件分岐両ブランチで `=0` 実行（意図不明）
- M-STRAT-2: ATLAS-2026-0505-376 docstring instrument 誤記
- M-STRAT-3: ATLAS-2026-0506-005 `gate_results.json` 欠落

### テスト
- M-TEST-1: `test_atlas_top3_strategies.py:433` ランタイム xfail (5戦略, PTRC 未検証)
- M-TEST-2: `test_numba_parity.py` 7テスト skip (Numba 未実装)
- M-TEST-3: `test_wfa_parallel_parity.py` skip 宣言乖離
- M-TEST-4: ATLAS 側存在チェック型 skip に STRICT_SKIP ガードなし
- M-TEST-5: `conftest.py::sample_ohlcv_df` 価格帯非考慮（USD/JPY 固定）
- M-TEST-6: `test_ptrc_rejection.py` 統合テストファイル不在

### 直近修正
- M-DEV-1: Task #11「構造的に到達不能」確定と PTRC カバレッジ確保は別問題
- M-DEV-2: EmailNotifier `risk_state=None` で Kill Switch 通知の累計損益が常に "-"

---

## Low / Info（観察）

### プラットフォーム
- L-PLAT-1: `SequenceNumberGenerator.current` ロック未取得（torn read リスク）
- L-PLAT-2: `runner.py:run` の 1 秒粒度 polling
- L-PLAT-3: `Order.broker_order_id` 型での Paper/Live ID 区別なし
- L-PLAT-4: RedisEventBus `_listen` 空集合 listen リスク

### リスク・執行
- L-EXEC-1: `LatencyMonitor._pending` orphan leak
- L-EXEC-2: `parse_quote_currency` 6文字以上 symbol で None
- L-EXEC-3: `StaticCurrencyConverter` 本番混入リスク

### 監視・運用
- L-OPS-1: `dashboard/app.py` `API_BASE_URL` ハードコード（UnifiedRunner 経路で常時未接続）
- L-OPS-2: `print()` 残存（scripts/run_unified.py, forward_test.py）

### データ
- L-DATA-1: Redis キャッシュ層 (cache.py) 未実装
- L-DATA-2: Parity テスト buffer_size の構造的限界（テスト範囲内では問題なし）
- L-DATA-3: CLAUDE.md の「未実装」表記と実態の乖離 (quality_engine.py 等は実装済み)

### アーキテクチャ原則
- I-1: `StrategySlot` が Event Bus を経由せず BrokerGateway 直接呼出（Event-Driven 原則違反）
- I-2: `ImmutableHardLimits` frozen=True だがソースコード変更履歴の audit log 運用必要

---

## 横断的テーマ

### 1. 二系統運用（ExecutionCoordinator vs UnifiedRunner）の整合性破綻
本番稼働中の **UnifiedRunner 経路** で以下が機能していない:
- Trade Context Snapshot 永続化
- KillSwitch クラスによる Hard Limit 自動停止
- RetryManager 経由のリトライ
- Event Bus 経由の ORDER イベント

これは設計上のテストパスと本番パスが二つあり、テストは Coordinator 経路で書かれているが本番は Slot 経路で動いている、という構造問題。

### 2. 通貨換算が部分的にしか実装されていない
PTRC 内の通貨換算は `_check_max_risk_per_trade` のみ。`_check_total_exposure` と `PortfolioManager._calculate_used_margin` は未実装。**結果: 非 JPY pair でリスク制御が機能しない**。

### 3. 「Live 0 件問題」の真因候補が複数判明
- BarBuilder `truth_source` デフォルト Tick 集約（C-DATA-1）
- 0511-959 戦略の条件選択性は仕様通り（既知）
- 22戦略の live_eligible 検証スキップ（C-DEV-1）— Live 起動には影響しないが knowledge gap

### 4. テストカバレッジの「偽緑」リスク
- 主要 E2E テストが弱いアサート / 空アサートで PASS
- xfail が「構造的不能」を理由に蓄積、本物のバグを覆い隠す
- multi-strategy / PTRC リジェクト統合テストの不在
- Numba parity テスト 7件が永続 skip

### 5. 観測性の盲点
- HealthChecker の degraded 無視 / staleness warning 不伝播
- structlog が本番経路で機能しない
- Prometheus メトリクス名の `_total_total` 二重サフィックス
- EmailNotifier 通知失敗の Prometheus 化なし
- Dashboard が UnifiedRunner 経路で常時未接続

---

## 推奨アクションプラン（優先順位順）

| 優先度 | 項目 | 対応 |
|---|---|---|
| **P0** | C-EXEC-1/2/3 (UnifiedRunner Hard Limit 防壁) | UnifiedRunner に SnapshotWriter + KillSwitch 配線 + 通貨換算 |
| **P0** | C-DATA-1 (BarBuilder truth_source) | settings.py で `oanda_candle` 強制、起動時 fail-fast 検証 |
| **P0** | C-DEV-1 (live_eligible 検証スキップ) | TODO.md 訂正 + loader.py で `live_eligible` 必須化検討 |
| **P1** | H-STRAT-1 (13戦略 on_fill バグ) | LONG/SHORT 約定時の `_intended_direction` 更新追加 |
| **P1** | C-STRAT-1 (direction_bias='any' 取り残し 3戦略) | runner_config.json を `balanced` に統一 |
| **P1** | H-TEST-1/2/3/4 (E2E テスト弱化) | 空アサートを補強、multi_strategy テスト追加 |
| **P2** | C-PLAT-1 (forward_test live_mode) | 流用ガード追加 |
| **P2** | H-OPS-1/2 (HealthChecker / structlog) | configure_logging 配線、is_healthy 修正 |
| **P3** | Medium 多数 | 計画的に対応 |

# FX システム不具合修正計画 v2（検証チーム指摘反映済み）

**実施日**: 2026-05-21
**根拠**: `C:\data\works\FX\logs\audit_report_2026_0521.md`（二段階監査済み）
**対象**: 検証で確定した Critical 7件 + High 20件 + 主要 Medium
**v2 改訂**: risk-execution-engineer / platform-architect / qa-tester / devil-advocate の検証指摘を反映

---

## v2 改訂ハイライト（重大な変更）

検証チームから **Critical 1件 + High 6件 + must_fix 4件** の致命的指摘あり。元計画はこのまま実装すると **新規 Critical を生む** ため、以下を改訂:

### REV-1 [Critical] A-1-2 KillSwitch 設計の根本見直し
- **旧計画**: 未実現損益を `_evaluate_kill_switch` 判定に含める / 再起動後も KS active 復元
- **問題**: (a) 含み損戻りで戦略が勝てるトレードを強制決済する「巻き戻し」リスク、(b) 既存契約「KS 解除手段はプロセス再起動のみ」との衝突、(c) Redis TTL 値未指定で revert 後の KS 状態振動リスク
- **改訂**:
  - 未実現損益判定は **新フラグ `is_unrealized_warning_active`** に分離（KS とは別の WARN レイヤー、含み損戻りで自動解除可能）
  - KS 永続化は `is_kill_switch_active` フラグを **Redis に書かない**（既存契約「再起動で解除」を維持）。永続化するのは `daily_realized_pnl_total` のみ
  - cancel_open_orders は **best-effort + Position Reconciler 連携**、cancel 失敗時は自動再試行禁止 / 人間アラート
  - KS 発動時は **新規発注停止のみ即時実施**、in-flight cancel は別非同期タスクで実行（Event Bus 詰まり防止）
  - change:spec として明示的にコミット種別を `[change:spec]` に変更

### REV-2 [must_fix] B-1 on_fill 修正の検証手段が無効
- **旧計画**: 「修正前に再度バックテスト」で挙動確認
- **問題**: 修正コードは `direction == SignalDirection.FLAT` enum 比較。BT は `{"direction": "FLAT"}` 文字列 dict を渡す → BT では修正が常時スルーで PASS するが Live で別動作する最悪パターン
- **改訂**:
  - FillEvent の型統一を **B-1 の先行タスク**として実施（enum vs str を整理）
  - BT 再評価ではなく `test_strategy_on_fill.py` ユニットテストと **Paper Trading 30日シャドー** で検証
  - B-1 を P1 から **A フェーズの最後（A-6）に格上げ** — Hard Limit 防壁完成後に実施

### REV-3 [must_fix] ロールバック判断基準の事前確定が必須
- **旧計画**: 「24時間 Order 未発出」「PTRC 拒否率 2倍」を一律基準とする
- **問題**: (a) 0511-059 は月平均 1.3 件発火、24 時間判定は誤検知。(b) 修正前の PTRC 拒否率がドキュメント化されていない
- **改訂**:
  - **B-7/H-DEV-2 (発火頻度実測) を A フェーズ前に前倒し** — A-0 として独立タスク化
  - 戦略別ロールバック基準を事前確定: 「期待発火間隔 × 3倍以上の沈黙」
    - H4 戦略: 72 時間沈黙でロールバック検討
    - H1 戦略: 期待値による（0511-059 等は 30 日以上）
    - M15 戦略: 4 時間沈黙でロールバック検討
  - PTRC 拒否率の **直近 30 日平均を基準値として A-0 で記録**

### REV-4 [must_fix] A-1 中間状態「防壁半壊期間」のリスク受容
- **旧計画**: PR1 (SnapshotWriter) → PR2 (KillSwitch) → PR3 (通貨換算) を独立 PR、間隔不明
- **問題**: A-1-1 のみマージで SnapshotWriter は機能するが KS は旧式、その間に逆行 → 15% 超損失防げない
- **改訂**:
  - **A-1-1〜3 を 1 スプリント内 (最大 5 営業日) で連続完了**を制約化
  - PR 間隔中は **Live 取引を Paper モードに切替** (`ENV=staging` 一時運用)
  - または: A-1-1〜3 を **単一 PR**として実装し、内部のコミットを 3 つに分けることで差分管理（マージ時は一括）

### REV-5 [計画前提欠陥] H-PLAT-3 と A-3 の整合性
- **旧計画**: Paper モードで `live_eligible=False` のみ拒否
- **問題**: キー欠如 53戦略が Paper 経路で全通過、Gate 同等品質保証が形骸化
- **改訂**:
  - H-PLAT-3 を「`live_eligible=False` 拒否 **かつ** キー欠如時 WARN + Prometheus counter 計上」に変更
  - A-3 で `loader.py:311-316` の WARN ログ追加を **「追加検討」から確定タスクに格上げ**、PR5 スコープに明記
  - 中期: `live_eligible` 必須化マイグレーション ATLAS 側にタスク発行

### REV-6 [計画前提欠陥] kill_switch 5% 「一時設定」は frozen 設計違反
- **旧計画**: kill_switch を保守的に 5% に「一時的に」変更
- **問題**: `ImmutableHardLimits` は frozen dataclass、値変更にはソース改変 + `logs/rule_change/*.jsonl` 必須（I-2）
- **改訂**:
  - 「一時的に」表現を削除
  - A フェーズ開始前: **正式な制限値変更**として 15% → 5% を実施、`rule_change/*.jsonl` に記録
  - A フェーズ完了後: 5% → 15% に戻す変更も同様に `rule_change/*.jsonl` に記録
  - 各変更は独立 PR `[change:spec]` で実施

### REV-7 [must_fix] B-2 テスト補強の致命的欠陥
- **旧計画**: 4 件のテスト補強案
- **問題**:
  - H-TEST-2: `random.seed(42)` グローバル汚染で flaky 化
  - H-TEST-3: 強制 `assert fills_completed > 0` は xfail 5戦略と矛盾、CI 常時赤化
  - H-TEST-4: `_inflight_tasks` 競合修正前の非決定的テストは flaky
- **改訂**:
  - **H-TEST-2**: `random.Random(42)` インスタンス化でグローバル汚染排除、確率的 assert を削除して `fail_probability=1.0/0.0` の決定論的二項テストに置換
  - **H-TEST-3**: 強制 assert を撤回、現状の条件付き設計を維持。真の E2E 検証は ATLAS-replay fixture を別タスク化
  - **H-TEST-4**: 前提として B-3 H-PLAT-2 修正を先行完了。イテレーションを 100→10 に削減し `asyncio.sleep(0)` で確定的タスク切替
  - **H-TEST-1**: assert 追加は撤回、データ本数 200→500 で発火機会を確保

### REV-8 [Critical] B-5 `_processed_fills` 冪等性破壊
- **旧計画**: `collections.deque(maxlen=10000)` に変更
- **問題**: (a) deque は線形検索で O(n)、(b) 10000 件は 24 日分で連続稼働に不足、(c) round_0415_4_r2 既知の `broker_fill_id is None` 経路は未解決
- **改訂**:
  - データ構造を `OrderedDict` (LRU) + set ペアに変更（O(1) 検索維持）
  - 件数ベース evict ではなく **7 日 TTL ベース**
  - `broker_fill_id is None` 時の fallback キー `(order_id,)` で fail-closed
  - 上限到達時に WARNING ログ発出

### REV-9 [二重実装の負債回避] OrderSubmissionGuard 抽出
- **旧計画**: A-1-1 で StrategySlot に SnapshotWriter 直接注入
- **問題**: ExecutionCoordinator と StrategySlot の二重 fail-closed 配線は X-1 中期 (Coordinator 委譲) で破棄される技術的負債
- **改訂**:
  - **A-1-1 と同時**に `OrderSubmissionGuard` クラスを抽出（SnapshotWriter + 共通ガード ラッパ）
  - Coordinator / Slot 双方が同一 Guard インスタンスを呼ぶ設計に統一
  - X-1 中期で StrategySlot 削除しても Guard は残る
  - H-PLAT-4 (二重実装) の ADR を **A-1-1 と同 PR で作成**

### REV-10 [順序逆転] PR 順序の修正
- **旧計画**: A-1 (PR1-3) → A-2 (PR4) → A-3〜5 (PR5)
- **問題**: A-2 の `truth_source="oanda_candle"` 強制で bar_close 時刻が変わり、A-1 のテストが壊れる可能性
- **改訂**:
  - **PR0: A-0 (発火頻度実測 + ロールバック基準確定)** — 計測のみ、コード変更なし
  - **PR1: A-2 (BarBuilder truth_source)** — 先行で bar 時刻を確定
  - **PR2-4: A-1-1〜3** — A-2 完了後に Hard Limit 配線
  - **PR5: A-3 + A-4 + A-5** — ドキュメント・戦略設定（既知問題のみ）
  - **PR6: A-6 (旧 B-1, on_fill 12戦略)** — Hard Limit 完成後に戦略修正

### REV-11 [追加タスク] Position Reconciler 強化を A-1 並走へ繰上
- A-1-2 cancel 失敗 / A-1-3 換算誤り / B-5 evict 後再送 fill の最終防衛線
- **B-6 H-DATA から繰上**、A-1 と並走実施

### REV-12 [見積もり修正]
- フェーズ C (40-60h) 過小: M-PLAT-1 (correlation_id 型変更) / M-PLAT-6 (BarEvent.is_complete 必須化) は呼び出し全箇所 grep 必須
- **改訂**: フェーズ C 見積もりを **60-100h** に修正、grep 完了後に再見積もり

---

## 改訂後の合計見積もり

| フェーズ | 見積もり (改訂後) | 備考 |
|---|---|---|
| A-0 (発火頻度実測 + 基準確定) | 4-6h | **新規追加** |
| A (P0) | 25-35h | REV-1/4/6/9 反映で増加 |
| B (P1) | 32-48h | REV-7 で減少、REV-11 繰上で B-6 簡略化 |
| C (P2) | **60-100h** | REV-12 で増加 |
| D (Low/Info) | 8-12h | 変更なし |
| **合計** | **129-201 時間** | 約 3-5 週間（旧 2-3 週間から拡大） |

---

## 元計画書本文（v1 — 検証前）

> 以下、v1 計画の本文。**REV-X で訂正された箇所は v2 改訂ハイライトを優先**してください。

## 計画方針

1. **本番稼働中のシステム**であるため、P0 修正は段階的かつテスト先行で実施
2. **「修正自体がバグを生む」リスク**を最小化するため、各修正にロールバック手順を明記
3. **計画は実装フェーズに分割** — 一度のコミットで全部やらない
4. **検証マーカー**: ✅検証済み / ⚠️訂正反映 — レポート確認結果を反映

---

## フェーズ A: P0 — 即時対応（Live 取引リスク直結）

### A-1: UnifiedRunner Hard Limit 防壁の再配線 (C-EXEC-1, 2, 3)

**目的**: 本番経路 UnifiedRunner で SnapshotWriter / KillSwitch / 通貨換算を機能させる

#### A-1-1: SnapshotWriter 配線 (C-EXEC-1)
- **修正対象**: `core/unified_runner/strategy_slot.py`, `runner.py`
- **修正内容**:
  1. `UnifiedRunner.initialize` で `SnapshotWriter` を生成、`StrategySlot` コンストラクタに注入
  2. `StrategySlot._handle_entry/_handle_exit` で `gateway.submit(order)` 直前に `snapshot_writer.write_or_raise()` を呼ぶ（`coordinator._on_signal:322-348` のパターン踏襲）
  3. 失敗時は fail-closed REJECT（注文を出さない）
- **テスト先行**:
  - `tests/integration/test_unified_runner_snapshot.py` を新規作成
  - SnapshotWriter モックで「書き込み成功時に発注」「書き込み失敗時に発注しない」を検証
- **ロールバック**: 当該コミットを `git revert`。SnapshotWriter は副作用としてファイル書き込みのみで他経路に影響しない
- **見積もり**: 4-6 時間

#### A-1-2: KillSwitch 経路の本番駆動 (C-EXEC-2)
- **修正対象**: `core/unified_runner/risk_supervisor.py`, `circuit_breaker.py`
- **修正内容**:
  1. `GlobalRiskSupervisor` に `state_store` 引数を追加し、`account_state` を Redis に永続化
  2. `_evaluate_kill_switch:604-619` で `daily_realized_pnl_total` に加え未実現損益 (`unrealized_pnl_total`) も合算して判定
  3. KS 発動時に `broker_gateway.cancel_open_orders()` を呼ぶ
  4. 再起動時の `restore_from_state` フローを追加
- **テスト先行**:
  - `tests/risk_engine/test_global_kill_switch.py` 新規
  - シナリオ: 未実現損失で 15% 突破 → KS 発動 → in-flight 注文キャンセル → 再起動後も KS active
- **ロールバック**: revert で旧 GlobalRiskSupervisor に戻る。永続化キーは TTL 設定で残骸を自動消去
- **見積もり**: 8-12 時間（StateStore 連携・テスト含む）

#### A-1-3: PTRC 通貨換算の全箇所対応 (C-EXEC-3 + M-PLAT-3)
- **修正対象**: `core/risk_engine/ptrc.py:343-412`, `core/portfolio_manager/manager.py:158-161`
- **修正内容**:
  1. `_check_total_exposure` に `currency_converter.convert(new_order_notional, quote_currency, account_currency)` を追加
  2. 換算失敗時は fail-closed REJECT
  3. `PortfolioManager._calculate_used_margin` も同様に `quantity × price / leverage` 換算
- **テスト先行**:
  - `tests/risk_engine/test_ptrc_currency.py` 新規
  - EUR/USD・GBP/USD で exposure_ratio が正しい JPY 建てで算出されることを検証
  - `StaticCurrencyConverter` を本番混入させない fail-fast チェック追加 (`L-EXEC-3`)
- **ロールバック**: revert
- **見積もり**: 4-6 時間

---

### A-2: BarBuilder truth_source 強制化 (C-DATA-1)

- **修正対象**: `data/market_data/bar_builder.py`, `config/settings.py`
- **修正内容**:
  1. `BarBuilder.__init__` の `truth_source` デフォルトを `"oanda_candle"` に変更
  2. `settings.py` で `BAR_TRUTH_SOURCE` 必須化、production 環境では `"tick_aggregation"` を起動拒否
  3. 起動時 fail-fast 検証 (`run_unified.py` で実装)
- **テスト先行**:
  - `tests/parity/test_bar_source_parity.py` を活用、Tick 集約モード使用時に WARN ログ発出を検証
  - production env で `"tick_aggregation"` 設定時に起動失敗を検証
- **検証必須**: BT/Live の数値乖離が解消するか Parity テストで確認（既存 `test_bar_source_parity.py` を拡張）
- **ロールバック**: revert。production env 強制を緩めるだけで元の挙動に戻る
- **見積もり**: 2-4 時間

---

### A-3: TODO.md / メモリ訂正 (C-DEV-1)

- **修正対象**:
  - `fx_trading_system/TODO.md`
  - `~/.claude/projects/C--data-works-FX/memory/project_fts_pending_tasks.md`
- **修正内容**:
  1. 「23戦略 live_eligible 確認 OK」記述を削除
  2. 実測値を記載: `live_eligible=True` 明示 5戦略 / キー欠如 53戦略 / `False` 1戦略
  3. 「キー欠如時に検証スキップ」する loader.py の動作を明文化
  4. **追加検討**: `loader.py:311-316` で live_mode かつキー欠如時に WARN ログを出力
- **ロールバック**: revert
- **見積もり**: 30 分（ドキュメントのみ）

---

### A-4: forward_test.py の live_mode 流用ガード (C-PLAT-1)

- **修正対象**: `trading_platform/forward_test.py:137`
- **修正内容**:
  1. `load_strategy(strategy_dir, live_mode=False)` を明示
  2. ファイル冒頭の docstring に「LIVE 流用禁止、常に PaperBroker 固定」と注記
  3. main 関数の引数 parser に `--live` を**意図的に追加しない**こと、または追加する場合は ATLAS Gate 再検証を強制
- **ロールバック**: revert
- **見積もり**: 30 分

---

### A-5: 戦略コード不整合の修正 (C-STRAT-1, 2)

#### A-5-1: direction_bias 整合化 (⚠️ 検証で 3戦略→2戦略+1戦略キー欠落に訂正)
- **修正対象**:
  - `strategies/imported/ATLAS-2026-0508-041/runner_config.json` (`any` → `balanced`)
  - `strategies/imported/ATLAS-2026-0508-140/runner_config.json` (`any` → `balanced`)
  - `strategies/imported/ATLAS-2026-0508-069/runner_config.json` (`direction_bias` キー追加)
- **修正内容**: metadata.json の値に揃える。値はそれぞれ実機確認後に決定
- **検証**: 修正後 LIVE スロットで Gate 再評価が PASS することを確認
- **ロールバック**: revert
- **見積もり**: 30 分

#### A-5-2: strategy.py docstring 修正 (C-STRAT-2)
- **修正対象**:
  - `ATLAS-2026-0505-376/strategy.py` (EUR_JPY H4 → CAD_JPY H4)
  - `ATLAS-2026-0505-399/strategy.py` (戦略 ID 352 → 399)
  - `ATLAS-2026-0505-400/strategy.py` (戦略 ID 352 → 400)
  - `ATLAS-2026-0505-401/strategy.py` (戦略 ID 352 → 401)
- **修正内容**: docstring 冒頭の戦略 ID / 通貨ペアを実態に揃える（ロジックは無変更）
- **ロールバック**: revert
- **見積もり**: 15 分

---

## フェーズ B: P1 — 計画的対応（Live 機能影響）

### B-1: 12戦略の on_fill バグ修正 (H-STRAT-1, ⚠️ 検証で 13→12 訂正)

- **修正対象**: 12戦略の `strategy.py::on_fill`
  - 対象: `0504-098, 0506-024, 0506-031, 0507-016, 0507-066, 0508-041, 0508-140, 0510-002, 0512-023, 0512-035, 0512-061, 0512-101`
  - 除外: `ATLAS-2026-0501-004`（`_position` 全方向更新で別構造）
- **修正内容**:
  ```python
  def on_fill(self, fill_event):
      direction = fill_event.get("direction")
      if direction == SignalDirection.FLAT:
          self._intended_direction = SignalDirection.FLAT
      elif direction in (SignalDirection.LONG, SignalDirection.SHORT):
          self._intended_direction = direction
  ```
- **テスト先行**:
  - `tests/integration/test_strategy_on_fill.py` 新規
  - シナリオ: LONG エントリー後に SHORT 約定通知 → `_intended_direction == SHORT`、即時再エントリーで重複防止
- **重要**: 12戦略すべて修正前に **再度バックテスト** で挙動が変わらないことを確認（generate_signal の cooldown ガードと干渉する可能性）
- **ロールバック**: revert
- **見積もり**: 4-6 時間（テスト含む）

### B-2: テスト基盤の弱アサート補強 (H-TEST-1, 2, 3, 4)

- **H-TEST-1**: `test_signal_flow.py::test_signal_generation_with_data` で `assert signals_generated > 0` を追加
- **H-TEST-2**: `test_oanda_api_fault.py::test_partial_failure_probability` で `assert 2 <= successes <= 8` `assert 2 <= failures <= 8` を追加（seed=42 で確率的に妥当）
- **H-TEST-3**: `test_signal_flow.py::test_full_signal_to_fill_flow` で `assert fills_completed > 0` を追加し、約定検証を強制
- **H-TEST-4**: `test_multi_strategy.py` 新規作成
  - 2戦略同時実行で `RiskState` を共有
  - 戦略 A の SL 到達が戦略 B の `daily_realized_pnl` に正しく反映されることを検証
  - レース条件: `pytest-asyncio` で 100 イテレーション

- **ロールバック**: revert
- **見積もり**: 6-8 時間

### B-3: Event Bus / Strategy Loader 修正 (H-PLAT-1〜4)

- **H-PLAT-1**: RedisEventBus 二重配信ガード — `event_id` ベースの dedup セット (TTL 60秒)
- **H-PLAT-2**: InMemoryEventBus の `_inflight_tasks` スナップショット明示化
- **H-PLAT-3**: Paper モード Gate 検証ポリシー追加 — `live_eligible=False` のみ Paper でも拒否（A-3 と整合）
- **H-PLAT-4**: `worker.py` と `strategy_slot.py` 共通化 — `StrategyExecutor` 抽象抽出は将来タスク。短期は ADR 文書化のみ
- **見積もり**: 8-12 時間（PLAT-4 除く）

### B-4: 監視・運用層 (H-OPS-1, 2, 4)

- **H-OPS-1**: `HealthChecker.is_healthy` を `_aggregate_system_status() == "healthy"` に置換
- **H-OPS-2**: `run_unified.py:setup_logging()` を削除、`configure_logging(log_dir=LOG_DIR, to_file=True)` を呼ぶ
- **H-OPS-4**: EmailNotifier に SSL context + 3回リトライ追加、`_send_failures` を Prometheus counter 化、`fx_email_send_failures_total > 0` のアラートルール追加
- **見積もり**: 4-6 時間

### B-5: H-EXEC 系 (H-EXEC-1〜4)

- **H-EXEC-1**: `PaperBroker._handle_exit` で `prices=None` の早期 return 追加
- **H-EXEC-2**: `FillProcessor._processed_fills` を `collections.deque(maxlen=10000)` ベースに変更
- **H-EXEC-3**: PTRC `_check_max_daily_loss` に SL 想定損失加算ロジック追加
- **H-EXEC-4**: RetryManager を coordinator から実配線、または明示的に dead code 削除を決定
- **見積もり**: 6-10 時間

### B-6: H-DATA 系 (H-DATA-1〜4)

- **H-DATA-1**: Live FeatureStore に `_feature_compute_errors` フラグ追加
- **H-DATA-2**: `_recompute_tf` のプロファイル取得（修正は M15/H1 のレイテンシ実測次第）
- **H-DATA-3**: `register()` で `period > MAX_BUFFER_SIZE / BUFFER_SAFETY_FACTOR (= 400)` ならハード ValueError
- **H-DATA-4**: `_macd` の `_PERIOD_PARAM_KEYS` に短縮形 `fast`, `slow`, `signal` を追加（C-DATA-2 訂正版）
- **見積もり**: 4-6 時間

### B-7: H-DEV (devil-advocate 残課題)
- **H-DEV-2**: Task G 「条件不成立で正常」の Live FeatureStore SMA50/SMA200 値を週次デバッグログから実測確認 — 30 分
- **H-DEV-3**: Task F 起動元の Windows Event ID 4688 取得 — 1 時間（環境依存）

---

## フェーズ C: P2 — Medium 対応

### C-1: アーキテクチャ整理
- M-PLAT-1: `Order.correlation_id` を `str | None = None` に変更し OrderManager で SignalEvent 継承
- M-PLAT-2: `VirtualPosition.is_flat` を `abs(quantity) < 1e-6` に変更
- M-PLAT-5: Windows シグナルハンドラの `signal.signal(SIGINT, ...)` 統一
- M-PLAT-6: `BarEvent.is_complete` を必須引数化
- M-PLAT-7: Redis channel に env prefix 追加

### C-2: リスク執行系の細部
- M-EXEC-1: `KillSwitch.manual_reset` 同期版で完了待ち
- M-EXEC-2: `CircuitBreaker._cooldown` で KS active 時の自動解除スキップ
- M-EXEC-3: ClientOrderID に uuid 部分追加
- M-EXEC-4: `_check_spread` の dict 分岐削除
- M-EXEC-5: PTRC Post Level 3 発動条件拡張

### C-3: データ層
- M-DATA-1〜6: 詳細はレポート参照（merge_asof 末尾計算、validate_bar 月曜ギャップ、HEARTBEAT 週末判定、tz-naive fail-fast、StateStore tf 正規化）

### C-4: 監視
- M-OPS-1: Streamlit `streamlit-autorefresh` 導入
- M-OPS-2: `_apply_staleness_sync` warning 閾値で `healthy=False`
- M-OPS-3: 欠落アラートルール追加 (`fx_feature_staleness_sec`, `position_reconciler_mismatch_total`)
- M-OPS-4: Runbook 追記 (EmailNotifier SMTP / Gate 拒否 / 再起動ループ)
- M-OPS-5: watchdog タスク RunLevel 統一

### C-5: 戦略コード
- M-STRAT-1: `ATLAS-2026-0501-004` `on_fill` の意図不明分岐をコメントで明文化
- M-STRAT-2: `ATLAS-2026-0505-376` docstring 訂正（A-5-2 で対応済み）
- M-STRAT-3: `ATLAS-2026-0506-005` の `gate_results.json` 生成または該当戦略の LIVE 除外

### C-6: テスト
- M-TEST-1〜6: 残 xfail 5戦略のシナリオ別 fixture / Numba 進行管理 / WFA テスト宣言乖離訂正 / STRICT_SKIP ガード ATLAS 側展開 / sample_ohlcv_df 通貨別 / `test_ptrc_rejection.py` 統合作成

### C-7: 直近修正
- M-DEV-2: EmailNotifier に GlobalRiskSupervisor 経由で RiskState 注入

---

## フェーズ D: Low / Info（観察対応）

- L 系全件: ドキュメント化または将来計画タスク化のみ。即時対応なし
- I 系（アーキテクチャ原則違反）:
  - I-1: `StrategySlot` を将来 `OrderEvent` publish 経路に統一する ADR 作成
  - I-2: `ImmutableHardLimits` 値変更を `logs/rule_change/*.jsonl` に必須記録する手順を運用フローに組み込む

---

## 横断的修正項目

### X-1: 二系統運用問題の根治
**問題**: 本番 UnifiedRunner と テスト ExecutionCoordinator が二経路。本番のみ Hard Limit 防壁が欠落。

**根治計画**:
1. 短期 (A-1 で実施): UnifiedRunner に Coordinator 相当機能を移植
2. 中期 (Phase E、別 PR): `StrategySlot` を `ExecutionCoordinator` に委譲する形に書き換え、本番経路を 1 つに統合
3. 長期: `core/strategy_engine` と `core/unified_runner/strategy_slot` の二重実装を完全削除

### X-2: 通貨換算の網羅
**問題**: PTRC 内で部分的にしか実装されていない。

**根治計画**:
1. A-1-3 で `_check_total_exposure` 修正
2. `PortfolioManager._calculate_used_margin` 修正
3. **コード grep ベースの網羅性検査**: PR 内で `quantity * price` `notional` `exposure` `margin` の全箇所をリストアップし換算チェック

### X-3: 観測性の盲点
**問題**: HealthChecker / structlog / Prometheus / EmailNotifier / Dashboard で複数の盲点。

**根治計画**:
1. B-4 で当面 4 箇所を修正
2. **E2E 観測性テスト** 追加 — KillSwitch 発動 → Prometheus メトリクス → EmailNotifier 通知 → Runbook 参照 までの 1 連シナリオを `tests/integration/test_alerting_e2e.py` に集約

---

## リリース戦略

### コミット粒度
1 PR = 1 フェーズ項目 を原則。例:
- PR1: A-1-1 (SnapshotWriter 配線)
- PR2: A-1-2 (KillSwitch 配線)
- PR3: A-1-3 (PTRC 通貨換算)
- PR4: A-2 (BarBuilder truth_source)
- PR5: A-3 + A-4 + A-5 (ドキュメント・戦略設定修正)
- PR6+: フェーズ B

### Live 環境への展開
1. 各 PR で **fx_trading_system/tests 全件 PASS** を必須
2. A フェーズ全体は **kill_switch を一時的に保守的に設定** (15% → 5%) して Live 投入
3. 1 週間のシャドー運用 (Paper) → 問題なければ Live
4. ハードコミットの最終ラインとして `logs/rule_change/*.jsonl` に変更記録

### ロールバック判断基準
以下のいずれかが発生したら直ちにロールバック:
- 統合テストで新規 FAIL 発生
- Live で Order が 24時間以上発出されない（戦略の発火頻度を考慮しても異常）
- PTRC 拒否率が修正前の 2 倍以上
- Kill Switch が誤発動（5/17 以来 0 件のはず）

---

## 見積もり総計

| フェーズ | 項目数 | 総見積もり |
|---|---|---|
| A (P0) | 5 大項目 | 19-29 時間 |
| B (P1) | 7 大項目 | 32-48 時間 |
| C (P2) | 31 件 | 40-60 時間 |
| D (Low/Info) | 13 件 | 8-12 時間 |
| **合計** | **56 件** | **99-149 時間** |

実工数の目安: 約 2-3 週間（1人日 6-7 時間想定、テスト・レビュー含む）

---

## 既知のリスク

1. **A-1-2 (KillSwitch 配線)**: StateStore 経由の永続化を加えると I/O 失敗時に Order が出ない fail-closed 設計が必要。これ自体が新規 Critical 化するリスク
2. **B-1 (12戦略 on_fill)**: 修正により既存 Live 戦略の挙動が変わる可能性。**バックテスト再評価が必須**
3. **A-2 (truth_source 強制化)**: Tick 集約モードで動いていた既存環境が起動不能になる。展開前に環境変数の事前確認必要
4. **A-1-1〜3 を同時 PR にすると差分が大きすぎる**: 必ず 3 PR に分割

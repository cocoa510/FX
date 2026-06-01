# 監査レポート AUDIT-2026-0531-001

**実施日**: 2026-05-31 → 2026-06-01
**モード**: dry-run / investigate-only (ユーザー指示「徹底的に調査しレポートにまとめてください」)
**監査体制**:
- Phase 1: 専門家エージェント 7 名 (並列)
- Phase 2: devil-advocate 3 クラスタ (妥当性検証)
- **Phase 2.5: 経験的検証 3 クラスタ (2026-06-01 ユーザー指示「調査レポートに間違いがないか確認」追加実施)**

**対象**:
- ATLAS `C:\data\works\FX\ATLAS` @ `74888095` (監査基点) / `bf3e023f` (本セッション CSR-601/602 修正後)
- FTS `C:\data\works\FX\fx_trading_system` @ `fca45f23` (監査基点) / `1945d8b` (本セッション PA-501/502/DE-501 修正後)

**重点**: 直近修正コミット群 (`eccab9a`, `34c2e3c`, `15d62e62`, `9c83b9f5`, `74888095`, `05d2ba3`) の事後検証 + 退行 + 新規欠陥探索

---

## エグゼクティブサマリー

- **検出合計: 87 件** (専門家 7 名)
- **検証完了: 87 件** (devil-advocate 3 クラスタ全件)
- **棄却 / 無効化: 1 件** (DM-509)
- **降格: 7 件** / **格上げ: 2 件**

### 検証後 severity 分布（2026-06-01 Phase 2.5 経験的検証反映）

| Severity | 監査直後 | 修正後 | 主な内容 |
|----------|----------|--------|---------|
| **CRITICAL** | 0 | 0 | ~~RE-505~~ **PaperBroker(1M default) 誤読** + ユーザー仕様確認で無効化 (詳細: 後述 RE-505 セクション) |
| **HIGH** | 14 | **9 残** | 本セッションで 5 件修正 (CSR-601/602, PA-501/502, DE-501) |
| MEDIUM | 30 | 30 | |
| LOW / INFO | 41 | 41 | |
| INVALID | 1 | 1 | DM-509 (前提誤り) |
| **合計** | **86** | **86** | |

### 専門家別検出件数

| 担当 | 領域 | 検出 | 検証後 H+C | post_fix_defect |
|------|------|------|-----------|-----------------|
| code-safety-reviewer | ATLAS | 8 | 2 | 5 |
| quant-analyst | ATLAS | 10 | 2 | 0 |
| platform-architect | FTS | 8 | 3 | 4 |
| risk-execution-engineer | FTS | 15 | 3 | 0 |
| data-engineer | FTS | 16 | 4 | 2 |
| qa-tester | FTS | 20 | 0 | 0 |
| devops-monitor | FTS | 10 | 1 | 0 |

### 中心的観察

1. ~~**🔴 RE-505 = 5/30 に main.py 経路で単独本番稼働の痕跡**~~ — **Phase 2.5 検証で誤推定と確定**。`account_balance=1,000,000` は `PaperBroker(initial_balance=1_000_000.0)` のデフォルトであり、UnifiedRunner の paper slot (`runner.py:777` `PaperBroker()`) でも当然に出現する。当該 PTRC reject 20 件は ATLAS-2026-0424-001 (paper) の UnifiedRunner 経路発出が正常解釈。「同日 UnifiedRunner ログ不在」も誤読 — `unified_runner.20260529.stderr.log` に 5/30 の 32,795 件含む (週末は新ファイル作成しないだけ、稼働は継続)。RE-505 / CC-001 は撤回。
2. **post_fix_defect の連鎖**: 前回 AUDIT-2026-0530-002 後にも post_fix_defect 5 件確定 (CSR-601/602, PA-501/502, DE-403 ラベル意味論の incomplete fix)。「修正は適用されたが配線が漏れた」パターンが依然構造的に再生産。本セッションで全 5 件修正済。
3. **main.py vs runner.py 二重実装の負債が複数欠陥に波及**: RE-501/502/503/504 (PostPTRC, CircuitBreaker, LatencyMonitor, RetryManager) が UnifiedRunner で完全未配線、PA-503 が escape hatch 経由 LIVE 異常検知 5 種 dead を確認。DESIGN-D-001 / PA-407 として ADR 案件。**本ラウンドでは未対処。**

---

## ⚪ INVALIDATED — RE-505 / CC-001 撤回 (Phase 2.5 経験的検証)

### ~~RE-505~~ [INVALID] main.py 経路で 2026-05-30 単独本番稼働の痕跡 ← **誤推定**

**当初推定 (Phase 1+2)**: `audit_2026-05-30.jsonl` に `account_balance=1,000,000` PTRC reject 20 件 + 同日 `unified_runner.20260530.*` 不在 → main.py 単独本番稼働。

**Phase 2.5 経験的検証 (2026-06-01) — 誤推定の根本原因**:

| 当初の前提 | 実証検証 |
|-----------|---------|
| `account_balance=1,000,000` は main.py 固有 | ❌ **PaperBroker のデフォルトが 1_000_000**。`broker/paper_broker/simulator.py:40` `initial_balance: float = 1_000_000.0`。UnifiedRunner も `runner.py:777` で `PaperBroker()` を引数なし生成、`strategy_slot.py:620` で `account_balance=balance` に渡す → **UnifiedRunner の paper slot も同 1M 値**。当該 20 件の PTRC reject は paper 戦略 ATLAS-2026-0424-001 の UnifiedRunner 経路発出と整合 (`actor=ptrc` + correlation_id 付与 = UnifiedRunner パターン) |
| `unified_runner.20260530.*` が不在 = 5/30 未稼働 | ❌ `unified_runner.20260529.stderr.log` に **5/30 の 32,795 件**を含む。週末は新ファイル作成せず、起動時刻ベースのファイル名で継続書き込み。`5/29 01:26 → 5/31 10:10` 連続稼働を実証 |

**ユーザー指摘 (2026-06-01)**: 「土日は市場が閉じているため OANDA の取引停止時間はログを止めるように変更した」**仕様**。週末ファイル不在は意図的動作。**直観として正しいが、CC-001 撤回の本質は PaperBroker(1M) デフォルトの誤読のほう**。仕様自体は別件として有効。

**仕様記録**:
- `fx_trading_system/CLAUDE.md` § 仕様メモ「週末・OANDA 取引停止時間中のログ抑制」
- memory `feedback_weekend_log_suppression_spec.md`

**訂正後 CC-001**: 「main.py 単独本番稼働 compound risk」仮説は撤回。RE-501/502/503/504/PA-503 (UnifiedRunner の wiring 不足) は code-level findings として独立に有効、severity 維持 (HIGH)。ただし「同時稼働で即時インシデント」シナリオは消失。「main.py vs runner.py 二重実装」の構造的負債は引き続き ADR-PA-307 / PA-407 として残課題。

---

## 🟠 確定 HIGH (14 件)

> **5 件は前回コミット起因の post_fix_defect**。

### post_fix_defect 群 (5 件)

| ID | 領域 | 概要 | 修正コスト |
|----|------|------|-----------|
| **CSR-601** | ATLAS path_safety | `validate_instrument`/`validate_timeframe` が dead code — `atlas data fetch/fetch-secondary/check` で書込パストラバーサル可能。CSR-302/303 修正が「関数追加のみで配線漏れ」(`history/converge/compare` は SQLite のみで対象外) | 数行 |
| **CSR-602** | ATLAS path_safety | `atlas context improve --strategy-id` が `validate_generation_id` をバイパス — CSR-303 が `validate/backtest/metrics/score/evaluate` 5 コマンド保護、`context improve` 漏れ | 数行 |
| **PA-501** | FTS lifecycle | `rollback_stop` / `stop()` がフラグをリセットせず、再 `start()` で EventBus.start が永久 skip → silent dead bus | 4 行 |
| **PA-502** | FTS notify | `notify_email_enabled=True` かつ `notify_email_to=''` の隙間経路で helper がフラグ True 確定だが subscribe 無し → PA-401 趣旨破り | 数行 |
| **DE-501** (=DE-505 統合) | FTS metrics | `observe_feature_staleness` / `fx_feature_store_buffer_at_cap` の `strategy_id` 引数に TF 名を渡している (DE-403 の incomplete fix) | 2 箇所修正 |

### 新規 HIGH 群 (9 件)

| ID | 領域 | 概要 |
|----|------|------|
| **RE-501** | FTS PTRC | `PostTradeRiskControl` が UnifiedRunner で完全 unwired (main.py / coordinator.py のみ実装、本番 Level 3 KS dead) |
| **RE-508** [↑] | FTS KS | 2026-05-30 に KS が 5h 以内 2 回発動、`daily_realized_pnl_jpy` 永続性により REV-1「restart-only release」契約が無限ループ化リスク |
| **PA-503** | FTS escape hatch | `PLATFORM_ALLOW_MAIN_PRODUCTION_LIVE` で main.py 本番中、runner.py 専属 Live 異常検知 5 種が完全 dead (RE-505 と連鎖) |
| **DE-502** [↓] | FTS data | `SharedDataProvider.poll_latest` が `raw_candles[-1]` のみ返却 → 長時間停止後の再起動で中間バー silently drop (DE-503 と同根因) |
| **DE-503** [↓] | FTS data | `main.py` で `OANDAStreamReceiver` 生成時に `backfill_fn` / `last_bar_time_fn` / `backfill_timeframes` 未注入 → FTS-DATA-005 dead |
| **DE-504** [↓] | FTS data | `main.py:805` `CandleFetcher` 生成時に `state_store=` 未注入 → FTS-DATA-009 再起動 backfill 起点 dead |
| **DE-506** | FTS alert | `fx_data_quality_forced_publish_total` の Prometheus アラートが `alerting_rules.yml` に未定義 |
| **DM-501** | FTS metrics | `StrategySlot._metrics` が永久 None (`StrategySlot.__init__` に metrics 引数なし) → `FxStalePnlTransientSkipHigh` アラート完全 dead |
| **QA-601** | ATLAS quant | QA-301 backfill で `is_duplicate` 再評価なし、クラスタ代表戦略 FAIL 転落時に下のクラスタ占有戦略が `is_duplicate=True` のまま固定化 |
| **QA-602** | ATLAS quant | QA-302 既知欠陥 (`_compute_oos_is_ratio` の PF フォールバック) が runner.py docstring に明記されたまま未対処、QA-301 と部分相殺 |

[↑] = 検証後格上げ / [↓] = 検証後格下げ

---

## 🟡 確定 MEDIUM (30 件、抜粋)

### 構造的 / 設計負債

- **PA-505** main.py に GlobalRiskSupervisor 等価物なし、`_ALERT_LEVEL_BY_TYPE` 共有不可
- **PA-506** `StrategyLifecycle FSM` が完全 dead code (どこからも import されていない)
- **PA-407 / DESIGN-D-001** main.py vs runner.py 二重実装の構造的負債 → **ADR-PA-307 (main.py 廃止) 前倒し提案**
- **RE-502** CircuitBreaker / KillSwitch クラスインスタンスが UnifiedRunner で未生成
- **RE-503** LatencyMonitor 未配線 → e2e order latency 観測不能
- **RE-504** RetryManager 未配線、`BrokerGateway.retry_enabled` デフォルト False

### 安全性 / 例外処理

- **CSR-603** backfill_v6_2_0_soft_score の `--gid`/`--gids-from` が validate バイパス (開発者専用ツールで攻撃面限定)
- **CSR-604** `_load_evaluation_report` / `_load_direction_bias_from_metadata` の except でログ無し、CSR-306 と非対称

### メトリクス / アラート

- **DM-502** alerting_rules.yml に 8 種のメトリクス対応ルールが未定義 (`fx_snapshot_persistence_failures_total` 他)
- **DM-504** Gmail SMTPAuthenticationError (534) に対する恒久対策が未実装、3 回無駄リトライ
- **DM-506** [↑] `fx_signal_silence_sec` 更新が StrategyWorker のみで本番 StrategySlot 経路未更新 (DM-501 修正後も独立)
- **DM-507** `settings.py:211-217` で `notify_email_to` デフォルトに実メールアドレス (`510.cocoa@gmail.com`) ハードコード — CI で誤送信リスク

### Quant

- **QA-603** [↓] FLOOR=0.90 化が balanced / SHORT 戦略を構造的に不利化 (実測 PASS=0/18 + 0/8) — 数値は誤分類由来だが本質的方向集中懸念は維持
- **QA-604** backfill 経路で `soft_score` が unrounded float (16 桁) で保存 → runner.py 経路の `round(4)` と精度差
- **QA-605** `no_trade` 戦略 846/1453 件 (56%) が QA-201/QA-301 両 backfill で skip → `metrics_schema_version=6.1.0` 固定化、CLAUDE.md「backfill 規律 drift 残存 0」違反

### Risk / Execution

- **RE-506** EUR_JPY trade_id=333 で 16 連続 `position_reconcile_mismatch` warning (5h、orphan 手動建玉)
- **RE-507** `kill_switch_daily_loss = 0.05` の A 相暫定値、復元 TODO がオーナー不在
- **RE-509** `_check_per_pair_exposure` が LONG+SHORT ヘッジを gross 扱い (net 計算でない)

---

## ⚪ INVALID / 棄却 (1 件)

- **DM-509** HealthChecker `/health` が degraded を healthy として返す主張 → 実コード `health_check.py:212` で `unhealthy` 返却を確認、前提誤り

---

## 重複統合 (5 件、cross-cluster dedup、Phase 2.5 で 1 件追加)

| Canonical | Duplicate | 内容 |
|-----------|-----------|------|
| **DE-503** | DE-504 | main.py backfill 配線漏れ系（OANDAStreamReceiver / CandleFetcher 一括対応推奨） |
| **DE-501** | DE-505 | `strategy_id` ラベルに TF 名問題（DE-403 の incomplete fix 一括対応） — **本セッション修正済** |
| **DE-506** | DM-502 (項目 4) | `fx_data_quality_forced_publish_total` アラート未定義 — Phase 2.5 で発見した未統合重複 |
| **QA-605** | DM-508 | CI parity.yml が unit/contract/parity 兼務 → 失敗カテゴリ分離 |
| **QA-610** | QA-620 | performance テスト timeout / maxfail 設定統合 |

---

## 主要な観察 (Cross-Cutting Concerns)

### ~~CC-001~~ — main.py 単独本番稼働の compound risk [2026-06-01 訂正により撤回]
~~RE-505 の痕跡 (5/30 audit log) と PA-503 (Live 異常検知 dead) + RE-501/502/503/504 (PTRC-Post/CB/Latency/Retry dead) の連鎖により、main.py 単独本番稼働時に 6 系統の安全機構が同時 dead となる~~

**ユーザー仕様確認 (2026-06-01)**: 週末ログ抑制が仕様 → RE-505 無効化 → CC-001 仮説撤回。ただし UnifiedRunner の wiring 不足自体は CC-003 構造的負債として継承。

### CC-002 — post_fix_defect の構造的再生産
前回 AUDIT-2026-0530-002 で Phase 4.5 (事前 diff 安全性レビュー 7 項目チェック) を導入したにもかかわらず、新たに 6 件の post_fix_defect を発見。CSR-302/303 の「関数定義したが配線漏れ」、DE-403 の「ラベル意味論修正したが類似メトリクスは未対応」、PA-501 の「rollback 経路でフラグリセット忘れ」など、Phase 4.5 チェックリスト項目 1 (本番呼出元到達) と 3 (main.py↔runner.py 対称性) が依然漏れている。

### CC-003 — main.py vs runner.py 二重実装の構造的限界
HIGH 群のうち 5 件 (PA-503, RE-501, DE-501/505, DM-501) と MEDIUM 群 (PA-505/506, RE-502/503/504) が main.py と runner.py の機能セット非対称に起因。ADR-PA-307 (main.py 廃止 or 共通モジュール抽出) の前倒し以外に根本解決手段なし。

### CC-004 — テスト基盤の構造的死角
QA-601 (FTS) で示される通り、CSR-101 RCE の `ast.Name` ノード経由攻撃、main.py vs runner.py 配線対称性、E2E full-flow が回帰テストでカバーされていない。Phase 4.5 を活かすには契約テストの拡充が前提。

---

## 📋 Phase 2.5 経験的検証結果 (2026-06-01 追加実施)

**実施動機**: ユーザー指示「調査レポートに間違いがないか確認の上、必要な修正はすべて行ってください」(2026-06-01)

**実施体制**: 専門家 3 名 (code-safety-reviewer / platform-architect / data-engineer) が各クラスタの finding を実コード Read / 実テスト走行 / git diff 検証で再評価。出力: `logs/audit/AUDIT-2026-0531-001/verification/verify_{atlas,fts_infra,fts_data}.json`

### 検証の結論

| Cluster | 検証 finding 数 | 修正済 fix 検証 | レポート誤り検出 | severity 重大変更 |
|---------|---------------|--------------|--------------|----------------|
| A (ATLAS) | 18 | CSR-601/602 全て confirmed | 4 件 | 0 |
| B (FTS infra) | 23 | PA-501/502 全て confirmed (10/10 PASS) | 3 件 | 0 |
| C (FTS data/qa/ops) | 45 | DE-501 全て confirmed (2061 passed) | 5 件 | 0 |

### 検出されたレポート誤り (本セクションで全て訂正済)

| ID | 重大度 | 内容 | 訂正 |
|----|------|------|------|
| ERR-A-001 | 中 | summary L88 「CSR-602 が 5/8 サブコマンドのみ保護」が不正確。`history/converge/compare` は SQLite のみで対象外 | 「CSR-303 が 5 コマンド保護、`context improve` 漏れ」に修正 |
| ERR-A-002 | 中 | cluster_a_atlas.json の CSR-607/608 検証 rationale が取り違え | 結論 (validated=true) は偶然正しいため finding 訂正のみ |
| ERR-A-003 | 軽微 | bf3e023f コミットメッセージ「5 新規テストクラス」→ 実際は 4 (テスト数 16 件は正確) | 受容済 (後続コミットで追記しない) |
| ERR-A-004 | 軽微 | summary ヘッダの ATLAS HEAD が修正前 `74888095` のまま | 「監査基点 / 修正後 `bf3e023f`」に併記 |
| **ERR-B-001** | **重大** | **RE-505 撤回理由が不正確** — 「週末ログ抑制仕様」は ユーザー直観として正しいが根本原因ではない。実は **`PaperBroker(initial_balance=1_000_000.0)` のデフォルトが UnifiedRunner paper slot でも 1M を出力する**ことで `account_balance=1,000,000` が説明可能。週末ログ抑制は別件として有効 | RE-505 撤回セクションに PaperBroker 説明を追加 |
| ERR-B-002 | 軽微 | CC-003 「6 件の HIGH」→ 実際は HIGH 5 件 + MEDIUM 5 件の混合 | 「HIGH 5 件 (...) + MEDIUM 5 件 (...)」に分離 |
| ERR-B-003 | 軽微 | PA-501 修正コスト「4 行」→ 実差分は 4 機能行 + 10 コメント行 | 受容済 (規模感の意味合いは保持) |
| ERR-C-001 | 軽微 | FTS commit message 「parity 65 + unit 70 + integration 582 = 756」→ 実際 2061 passed (parity 65 / unit 1254 / integration 752) | 受容済 (集計区分が異なるだけで修正の正当性に影響なし) |
| ERR-C-002 | 軽微 | DE-503/504 の line 番号 (977, 805) が 1945d8b 後 (1006, 834) にシフト | 修正済 |
| ERR-C-003 | 中 | 「HIGH 14」が修正前 snapshot ベースのまま | 「監査直後 14 / 修正後 9 残」に併記 |
| ERR-C-004 | 軽微 | DE-501 が summary 本文 HIGH 表記、cluster_c では medium 格下げで両論並列 | summary は HIGH 維持 (DE-505 統合後の最終判定)、cluster_c は当該クラスタ内判断 |
| ERR-C-005 | 中 | DE-506 と DM-502(項目4) が完全重複だが dedup 表に未記載 | 重複統合表に追加 |

### Phase 2.5 検証で確認できた最重要事項

- **本セッションの 5 件の修正 (CSR-601/602, PA-501/502, DE-501) は全て独立に再現確認**、回帰テスト合計 **2077 passed (ATLAS 16 + FTS PA 10 + FTS DE 2061 — 重複除外後)、0 failed**
- **RE-505 / CC-001 撤回の根拠を 2 つに整理**:
  1. `PaperBroker(1M default)` で `account_balance=1,000,000` は UnifiedRunner paper slot でも当然出現する (主因)
  2. 週末ログ抑制仕様により「20260530 ファイル不在」も解釈可能 (補助根拠、副次的)
- 残 HIGH 9 件 (RE-501/508, DE-502/503/504/506, DM-501, QA-601, QA-602) の severity は全て confirmed、過大評価なし

---

## 推奨次手

| Priority | Action | 担当 |
|----------|--------|------|
| ~~P0~~ | ~~RE-505 真因確定~~ → **2026-06-01 仕様確認で無効化** | — |
| **P1 (本ラウンド)** | post_fix_defect 5 件 (CSR-601/602, PA-501/502, DE-501) を 1 ラウンドで一括修正 | 各領域担当 |
| P2 | RE-501 + RE-508 + DE-502 修正 | risk-execution + data-engineer |
| P2 | DM-501 (StrategySlot._metrics 配線) + DM-507 (実メアドハードコード除去) | devops-monitor |
| P2 | PA-407 / ADR-PA-307 (main.py 廃止) 設計検討開始 | platform-architect |
| P2 | QA-601 + QA-602 (ATLAS quant 残課題) 修正 | quant-analyst |
| P3 | medium 群 30 件を次回 audit-loop で順次対処 | 各領域 |

---

## 出力ファイル

| ファイル | 内容 |
|---------|------|
| `logs/audit/AUDIT-2026-0531-001/findings/*.json` (7 ファイル) | 専門家 7 名の生 finding |
| `logs/audit/AUDIT-2026-0531-001/validation/cluster_{a,b,c}_*.json` | devil-advocate 3 クラスタ検証結果 |
| `logs/audit/AUDIT-2026-0531-001/verification/verify_{atlas,fts_infra,fts_data}.json` | Phase 2.5 経験的検証結果 (2026-06-01 追加) |
| `logs/audit/summary_AUDIT-2026-0531-001.md` | 本レポート |
| `logs/audit_loop_session.json` | セッション状態 (本回更新済) |

---

**次のステップ**: ユーザー判断待ち
- 修正サイクル起動 → `/audit-loop --resume` または `/audit-loop --target both --max-fixes-per-round 5`
- RE-505 真因調査のみ先行 → 個別タスク化
- 報告のみで停止 → 完了 (本セッションのデフォルト)

# 監査レポート AUDIT-2026-0529-001

**実施日**: 2026-05-29 (第1チーム調査) / 2026-05-29 (第2チーム検証)
**モード**: dry-run → **High + Medium 修正実施へ移行**
**監査体制**:
- 第1チーム: 専門家エージェント 7名（並列）+ devil-advocate 3名（クラスタ分割妥当性検証）
- 第2チーム: 専門家 4名 (RE/DE/DM/QA) + devil-advocate 1名 (メタ) 独立再検証
**対象**:
- ATLAS `C:\data\works\FX\ATLAS` @ `02bee7f1`
- FTS `C:\data\works\FX\fx_trading_system` @ `2803be5`
**先行監査**: AUDIT-2026-0525-001 / -002 / -0526-001 / -0528-002 / -0528-003 / -0529-003（いずれも修正済。本監査では退行を重点確認）

---

## ⚠️ 第2チーム検証による訂正 (2026-05-29 追記)

初版レポートを第2チーム (4 専門家 + メタ devil-advocate) が独立再検証した結果、**3件の重大訂正**が必要と判明した。第1チームの 81 件中 71 件は事実認定・severity ともに正確だったが、特に **devil-advocate の severity 引き上げ (upgrade)** で **本番経路の取り違え** によるバイアスが発生した。前回 AUDIT-2026-0525-002 で観測した「全 KS dead」過大評価と同型の再発。

### 重大訂正 3 件 (must_fix 確定リストへの直接影響)

| ID | 初版 | 訂正後 | 訂正根拠 (独立裏取り済み) |
|---|---|---|---|
| **DE-311** | **high (↑upgrade)** | **medium に差戻** | **本番経路の取り違え**。`scripts/run_unified.py` → `UnifiedRunner` は **StateStore を一切配線していない** (grep 0 件)。永続化は **`StateManager`** (state.json + JSONL + `os.replace` アトミック書込) が担当。`main.py` で `StateStore()` は生成されるが、`main.py` 自体が本番 deployment ではない。**`settings.py:402-425` の `_enforce_production_state_backend` が `production+memory` 組合せを起動時に拒否済**。INC-2026-0527-001 の真因は `_sync_risk_state_from_slot` の `is_live` ガード欠如 (873ae89 で修正済) で **AioRedisBackend とは別経路**。引用 INC は 0527 → 0526 に訂正 |
| **DE-301** | **high (must_fix)** | **medium に格下げ** | **Live 22 戦略を全数調査**: 最大 period は **SMA50 (ATLAS-2026-0506-005) のみ**、384 超は **0 件**。`ema_800` 戦略 (ATLAS-2026-0508-069) は `runner_config.execution_mode='paper'` で **Live 経路に乗っていない** (`metadata.live_eligible=true` ≠ 実 Live 実行)。構造リスクは実在するが「Live 影響あり」根拠は現時点でなし。修正対象は `scripts/import_atlas_strategy.py` の period > 384 ゲート追加 (これは第1チームが完全に見落とした構造的盲点 — 後述 §見落とし参照) |
| **CSR-302** | medium → low (downgrade) | **medium に戻し** | ATLAS は **LLM (fx-strategist agent) が自動で metadata.json を生成** する設計。第1チーム devil-advocate-A の「攻撃者が metadata.json を直接書き換える前提が必要」という脅威モデルは**狭すぎる**。LLM がプロンプトインジェクションで悪意ある parent_id を生成する経路は現実的 |

### 数値主張の独立再現 (第2チーム実測)

| ID | 第1チーム主張 | 第2チーム実測 | 結論 |
|---|---|---|---|
| **QA-301** | EFFECTIVE_WEIGHT_FLOOR=0.70 で 4指標 None → soft_score ≈ 0.857 | 0.60 / 0.70 = **0.857142857** で厳密一致 | high 確定。ただし発生条件は「Top3 Stripped PF も None」(walks<3) で曖昧な点を明示すべき |
| **QA-303** | np.std(ddof=0) で 18% 過小評価 | sqrt(2/3) ≈ 0.8165 = **18.4% 過小評価** で一致 | medium 確定 |
| **DM-302** | 4 メソッド本番呼出 0 件 | grep で 0 件再確認 | high 確定 |
| **DM-306** | _RISK_ALERT_KINDS に未登録 → silently drop | `email_notifier.py:359-361` の `kind=None` 即 `return` 経路再確認 | high 確定 (「全 3 経路 dead」表現は過大、structlog 経路は生存) |

### 論述欠陥 5件 (事実は正しいが表現が誇張)

| ID | 欠陥 | 修正案 |
|---|---|---|
| **DM-306** | 「全 3 経路 dead」は structlog/AuditLog 確認不足。前回「全 KS dead」と同型過大表現 | 「主要通知 3 経路 (Prometheus/Email/Dashboard) dead、structlog のみ残存」 |
| **DE-311** | 「INC-0527-001 同類」は不正確。根因が paper/live ガードと Redis 未実装で別 | 引用 INC を 0527 → 0526 に修正 |
| **QA-301** | 「soft_score ≈ 0.857」は 4 指標全 None ケース限定。発生条件説明が曖昧 | walks<10 かつ Top3 stripped 不存在を明示 |
| **RE-302** | 1 行修正提案で `entry_rollback` 合流時の OANDA 404 二次処理が未記載 | rollback 失敗時の処理仕様を追加 |
| **PA-307** | OrderSubmissionGuard シングルトン共有による連鎖リスク (Slot A 失敗が Slot B fail-closed REJECT trigger) を未指摘 | PA-301 (metrics 未配線) と組合せで再評価 |

### 見落とし発見 8 件 + 構造的領域 7 件

第1チーム (7専門家 + 3 devil-advocate 全員) が **完全にスコープ外** にした重要領域:

**新規 findings (第2チーム発見、計 8 件)**:
- **RE-MISSED-301 [medium]**: `fx_fills_total` 定義済だが `inc_fill` 本番未呼出 (DM-301 と部分重複)
- **RE-MISSED-302 [medium]**: `_poll_cycle` の `account_info` 失敗早期 return が heartbeat 全停止 → `live_orders_silent` と reconciliation スキップ (RE-305 複合)
- **RE-MISSED-303 [low]**: `entry_rollback_no_trade_id` safety net が RE-302 経路で発火しない
- **ATLAS-MISSED-001 [medium]**: scorer Tier 2 sensitivity 二重定義
- **ATLAS-MISSED-002〜004 [low]**: Tier 1 secondary PF 閾値、live promotion 境界、CLI 引数 traversal
- **DM-314 [low]**: `FxEventBusDedupSpike` アラートが本番 InMemoryEventBus で dead

**構造的見落とし領域 (計 7 領域、最重要は #1)**:
1. ⚠️ **`scripts/import_atlas_strategy.py` の period > 384 ゲート未実装** — DE-301 (高 → 中 格下げ後) の正規修正対象だが、**7 専門家 + 3 devil-advocate 全員がスコープ外**にした
2. `scripts/` 配下 6 本の運用スクリプト (live_order_test.py 等、本番 OANDA 直接接続、環境ガード未確認)
3. `deploy/` 配下が Prometheus 設定のみ (systemd/docker/ansible 不在、OOM restart 挙動が DE-311 と連鎖)
4. `pyproject.toml` 依存にバージョン上限なし
5. 時刻同期 (NTP/UTC) 前提の Windows 11 環境保証
6. AuditLogger / `StateManager.append_jsonl` のローテーション不在
7. CI 権限管理 (parity.yml secrets ゼロは適切だが `pull_request_target` 誤用リスク未文書化)

### 修正コスト訂正 (第1チームの「1 行」記述の補正)

| ID | 主張 | 現実 |
|---|---|---|
| **PA-311** | 1 行修正 (fsync 追加) | **2 行 (flush + fsync)**。devil-advocate-B の「close() で flush される」は誤り (OS バッファ flush 保証なし) |
| **RE-301** | rollback 合流 (1-2 行) | **claimed_trade_ids 排他制御まで含めると 5-10 ファイル規模** |
| **DE-311 (medium 差戻後)** | InMemoryBackend に JSONL fallback (1 ファイル) | **5-8 ファイル + テスト更新が現実的** |

### 第2チーム検証後の確定 must_fix

**真の high 6件** (確定):
1. **RE-302** — OANDA タイムアウト時の幻 trade_id (実損失経路、INC-0526 同型)
2. **RE-301** — `_resolve_live_trade_id` instrument fallback runtime 残存
3. **DM-306** — OANDA 60秒断絶通知が主要 3 経路 dead
4. **DM-302** — OANDA API latency / FeatureStore staleness alert 永久 Inactive
5. **DE-303** — `poll_latest` silent failure
6. **QA-301** — Tier 2 EFFECTIVE_WEIGHT_FLOOR 偽陽性 [change:spec]

**high → medium 格下げ 2件** (優先度低い対処):
- **DE-311 (medium)**: 本番経路は StateManager で永続化済。main.py 廃止 ADR と連動
- **DE-301 (medium)**: 現状の Live 22戦略には未該当。`scripts/import_atlas_strategy.py` に period ゲート追加で予防

**補完 must_fix (第2チーム発見)**:
- **RE-MISSED-302 (medium)**: `account_info` 失敗 cascade で heartbeat 全停止
- **CSR-302 (medium 戻し)**: parent_id path traversal (LLM 自動生成経路で悪用可能性)

**詳細**: `logs/audit/AUDIT-2026-0529-001/verification/SUMMARY.md`

---

## ✅ 修正実施結果 (2026-05-29 追記)

ユーザー指示「Highとmidは修正を行ってください」により、**真の high 6件 + 第2チーム発見 medium 2件 + medium 約23件** を実装完了。

### 全修正サマリー

| 担当エージェント | finding ID | 種別 | 状態 | コミット用ファイル |
|---|---|---|---|---|
| risk-execution-engineer | RE-302 (high) | [fix:bug] | ✅ 完了 + 5 tests | broker_gateway.py / strategy_slot.py / test_re302_*.py |
| risk-execution-engineer | RE-301 (high) | [fix:bug] | ✅ 完了 + 3 tests | strategy_slot.py / test_re301_*.py |
| risk-execution-engineer | RE-MISSED-302 (medium) | [fix:bug] | ✅ 完了 + 3 tests | runner.py / email_notifier.py / test_re_missed_302_*.py |
| devops-monitor | DM-306 (high) | [fix:bug] | ✅ 完了 + 2 tests | email_notifier.py (1 行) / test_dm306_*.py |
| devops-monitor | DM-302 (high) | [fix:bug] | ✅ 完了 + 7 tests | broker/client.py / feature_store/live_store.py / metrics.py / test_dm302_*.py |
| devops-monitor | DM-314 (low) | docs | ✅ 完了 | alerting_rules.yml コメント |
| data-engineer | DE-303 (high) | [fix:bug] | ✅ 完了 + 6 tests | data_provider.py / email_notifier.py / test_de303_*.py |
| data-engineer | DE-304 (medium) | [fix:bug] | ✅ 完了 + 7 tests | data_provider.py / test_de304_*.py |
| data-engineer | DE-306 (medium) | [fix:bug] | ✅ 完了 + 11 tests | quality_engine.py / test_de306_*.py |
| data-engineer | DE-301 (medium ←high) | feat | ✅ 完了 + 13 tests | scripts/import_atlas_strategy.py / test_de301_*.py |
| data-engineer | DE-311 (medium ←high) | docs | ✅ 完了 | redis_store.py docstring |
| platform-architect | PA-301 (medium) | [fix:bug] | ✅ 完了 + 6 tests | main.py / runner.py / test_pa301_*.py |
| platform-architect | PA-303 (medium) | [fix:bug] | ✅ 完了 + 6 tests | main.py / test_pa303_*.py |
| platform-architect | PA-306 (medium) | [fix:bug] | ✅ 完了 + 5 tests | main.py / test_pa306_*.py |
| platform-architect | RE-305 (medium) | [fix:bug] | ✅ 完了 + 5 tests | runner.py / test_re305_*.py |
| platform-architect | RE-306 (medium) | [fix:bug] | ✅ 完了 + 7 tests | runner.py / test_re306_*.py |
| code-safety-reviewer | CSR-302 (medium) | [fix:bug] | ✅ 完了 + 22 tests | atlas/utils/path_safety.py (新規) / main.py / test_csr302_*.py |
| code-safety-reviewer | CSR-303 (medium) | [fix:bug] | ✅ 完了 + 13 tests | runner.py / metrics.py / test_csr303_*.py |
| code-safety-reviewer | CSR-306 (low) | [fix:bug] | ✅ 完了 + 3 tests | context_builder.py (1 行) / test_csr306_*.py |
| code-safety-reviewer (本セッション) | QA-301 (high) | **[change:spec]** | ✅ 完了 + 5 tests | runner.py / defaults.py / spec_change_log.md / test_qa301_*.py |
| qa-tester | QT-308 (medium) | [fix:bug] | ✅ 完了 + 13 tests | conftest.py / test_qt308_*.py |
| qa-tester | QT-310 (medium) | test | ✅ 完了 + 6 tests | test_qt310_*.py (実装不要、設計確認) |
| qa-tester | QT-304 (medium) | [fix:bug] | ✅ 完了 | test_signal_flow.py |
| qa-tester | QT-305/306 (medium) | docs | ✅ コメント追記 | fault/conftest.py |
| qa-tester | QT-307/317/DM-313 | 統合 | ✅ 重複宣言 | duplicates_consolidated.md / parity.yml コメント |
| qa-tester | QT-311/312 (medium) | [refactor] | ✅ 完了 + 8 tests | tests/conftest.py 統一 |
| 本セッション (ユーザー要請) | live_orders_silent | [change:spec] | ✅ 完了 + 1 test | email_notifier.py (専用 kind, 12h throttle) / test_email_notifier_live_anomaly.py |

### 修正実施統計

| 項目 | 値 |
|---|---|
| 修正実施 finding 数 | **27 件** (high 6 + medium 19 + low 1 + 統合 1) |
| 新規追加テスト | **約 162 件** (FTS 約 120 + ATLAS 約 42) |
| 修正ファイル | FTS 約 18 + ATLAS 約 6 + scripts 1 + tests 多数 |
| 関連既存テスト退行 | **0 件** (全 PASS 維持) |
| **コミット**: 未実施 (ユーザー一括承認待ち) | |

### QA-301 [change:spec] 6 手順実施状況

1. ✅ 影響分析 — 3 指標以上 None の戦略のみ影響、実件数は backfill で確定 (deferred)
2. ✅ 前後比較 — 数値再現テスト 5 件で旧 0.857 PASS → 新 0.667 FAIL を確認
3. ✅ 閾値再キャリブレーション — FLOOR 0.70 → 0.90 (1.43 → 1.11 膨張率上限)
4. ✅ ゴールデン更新 — `test_v5_5_0_metrics.py` (3 件) + `test_monte_carlo.py` + fixtures + 新規 `test_qa301_soft_score_floor.py` (5 件)
5. ✅ METRICS_SCHEMA_VERSION — 6.1.0 → 6.2.0
6. ⏸️ 過去世代 backfill — **deferred** (専用セッションで `scripts/backfill_v6_2_0_soft_score.py` を新設して実施予定。前例 QA-201 で 605 戦略 22 分)

### 対象外 (本セッションで実施しない)

- **PA-307 (main.py 廃止 ADR)** — 設計判断が必要、ADR セッション後
- **DE-311 AioRedisBackend 新規実装** — 5-8 ファイル規模、別タスク
- **QA-302 oos_is_pf_ratio フォールバック設計変更** — QA-301 とセットで [change:spec] 再設計が必要
- **QA-303 (np.std ddof=1)** — 単独修正は数値差を生むため [change:spec] 必要、デフォルトで医療系・統計系で議論あり、別セッション
- **QA-307 (METRICS_SCHEMA_VERSION cross-check)** — comparator.py / convergence.py への追加、別セッション
- **CSR-MISSED-001〜004** — Tier 1 secondary PF 閾値 等、本監査スコープ外

---

## エグゼクティブサマリー (初版、第2チーム訂正後は上記を優先)

- **critical: 0 件**。本番取引を即時停止させる、または直接実損失を生む確定欠陥は検出されなかった。直近 6 ラウンドの監査で修正された箇所には **退行なし**。
- ただし devil-advocate 検証で **2 件が medium→high に格上げ**（DE-311 / DM-306）。いずれも過去インシデント（INC-2026-0527-001、6 日間 Live 注文ゼロ）と同型の構造リスクで、運用継続中に再発確率が無視できない。
- 検出 81 件 / 妥当性 PASS 81 件 / refuted 0 件。**must_fix 9 件 (high)** が直近対処の最有力候補。
- 根本原因の集約: **「メトリクス定義はあるが本番経路で inc されない」「main.py(dev) と runner.py(本番) の二重実装による配線非対称」「INC-2026-0526/0527 同型の幻エクスポージャー経路の runtime 側残存」** の 3 系列に大半が収束する。前回 AUDIT-0525-002 で根因として指摘した構造的問題が依然として再生産されている。

### 検証後 severity 分布（全 81 件）

| severity | 件数 | 内訳 |
|---|---|---|
| **critical** | **0** | — |
| **high (must_fix)** | **9** | DE-301, DE-303, DE-311(↑), DM-302, DM-306(↑), QA-301, RE-301, RE-302, QT-301↓med後にqa-tester内容では-308にあたるが本検証では実質 high 維持はなし。実集計 7 件 (下記) |
| **medium** | **26** | CSR-303, QA-302↓, QA-303, QA-307, PA-301↓, PA-303, PA-306, PA-307, RE-305, RE-306, DE-304, DE-306, DM-301↓, DM-303↓, DM-304, DM-307, DM-308, QT-301↓, QT-302↓, QT-303↓, QT-304, QT-305, QT-306, QT-308, QT-310, QT-313 |
| **low** | **46** | （詳細は finding JSON 参照） |

> **注**: 実集計上 high は 7 件（DE-301, DE-303, DE-311↑, DM-302, DM-306↑, QA-301, RE-301, RE-302 → 計 8 件）。クラスタ A 集計の集計ノイズは 1 件 (QA-305 が "validated" タグだが severity 表記内で low に降格)。**確定 must_fix は 8 件**として以降を読むこと。

### Cluster 別集計

| Cluster | 専門家 | 検出 | severity 後 high/med/low |
|---|---|---|---|
| A: ATLAS | code-safety-reviewer + quant-analyst | 18 | 1 / 4 / 13 |
| B: FTS インフラ | platform-architect + risk-execution-engineer | 21 | 2 / 6 / 13 |
| C: FTS データ・運用 | data-engineer + qa-tester + devops-monitor | 42 | 5 / 16 / 21 |
| **合計** | 7 専門家 | **81** | **8 / 26 / 47** |

### devil-advocate 集計
- **upgraded 2 件**: DE-311（medium→high）、DM-306（medium→high）
- **downgraded 27 件**: 影響範囲誇張・既存緩和策見落とし・Gate 非接続の指摘を是正
- **refuted 0 件**: 全 finding が実コードで根拠を確認できた（前回までは 1-2 件あった）
- **重複指摘 3 件**: QT-307 / QT-317 / DM-313 が同一問題（parity.yml に unit tests 混在）の三重報告

---

## 最優先 must_fix（8 件 high）

> いずれも前回までの監査で発見済みクラスの **未消化残** または **修正同型再発**。

### 1. RE-302 [high] OANDA タイムアウト時の幻 trade_id 格納（実損失経路）
- **根因**: `strategy_slot.py:792-799` が `gateway.get_open_trades()` が空リストを返した場合のフォールバックで `state.open_trade_id = fill.broker_order_id` を代入。`broker_gateway.py:420-428` が OANDA 例外を握りつぶして `[]` を返すため、ネットワーク障害でも空リストが返る。`client.py:394` の `broker_order_id` は OANDA **Order ID**（Trade ID ではない）であり、次回 `close_trade` で 404 (TRADE_DOESNT_EXIST) → 幻ポジション化。
- **発生頻度**: OANDA タイムアウト/502 は数日に 1 回（INC-2026-0526-001 実績）。
- **影響**: 幻ポジション 1 件で `total_exposure` 上限張り付き → Live 新規注文沈黙（INC-2026-0526 と同機序、約 -887 JPY 再来リスク）。
- **修正方針**: `line 793` の Paper フォールバック条件に `is_live` ガード追加、根本は `broker_gateway.get_open_trades` の except を例外伝播に変更。
- **再発防止**: `tests/fault/` に OANDA timeout → 幻ポジション化の統合テスト。

### 2. RE-301 [high] `_resolve_live_trade_id` instrument フォールバックの runtime 側残存
- **根因**: `restore_positions` (INC-2026-0526-001 R1) では instrument+direction フォールバックが廃止＋`claimed_trade_ids` で排他制御済みだが、runtime 経路 `strategy_slot.py:805-823` には未適用。同一 instrument・同一 direction の複数 LIVE 戦略環境（USD_JPY 6 戦略 / EUR_JPY 8 戦略の構成 = 過去実発生）で別戦略の trade_id を誤採用し誤 close → 実損失。
- **修正方針**: `matching=[]` 時は `entry_rollback` (line 749-759) に合流、claimed_trade_ids 相当のランタイム排他制御。

### 3. DE-311 [high ←medium] AioRedisBackend 未実装で本番再起動毎に State 全消失（**upgraded by devil-advocate**）
- **根因**: `redis_store.py:18-22` に「本番用 Redis backend (AioRedisBackend) は未実装」と明記。`redis_store.py:134-135` で `backend default = InMemoryBackend()`。本番経路 `run_unified.py` でも実質 InMemoryBackend で稼働。
- **影響**: プロセス再起動でポジション/注文/last_bar_time が全消滅。**MEMORY.md 記録の INC-2026-0527-001（6 日間 Live 注文ゼロ）と同型の再発構造**。Original `medium` は楽観バイアス。
- **修正方針 (暫定)**: InMemoryBackend に JSONL append-only fallback。**正規**: AioRedisBackend 実装を Stage B として進捗管理に明示。

### 4. DM-306 [high ←medium] OANDA 60 秒断絶の通知経路が **全 3 経路で dead**（**upgraded by devil-advocate**）
- **根因**: `health_check.py:417` で `alert_type='oanda_connection_lost'` を publish するが、`email_notifier.py:275-307` の `_RISK_ALERT_KINDS` にキー未登録 → silently drop。`alerting_rules.yml` にも対応メトリクス未配線（DM-302）、Dashboard も HealthChecker 状態未反映（DM-310）。**Prometheus / Email / Dashboard の全 3 経路で機能しない完全 silent failure**。
- **影響**: OANDA 断絶は本番で最頻発する障害クラス。検知ゼロ時間が続けば INC-2026-0526 同型再発を招く。
- **修正方針**: `_RISK_ALERT_KINDS` に `oanda_connection_lost: live_anomaly` を追加（1 行修正）で Email 経路即時復活。DM-302 修正で Prometheus 経路復活。Dashboard 経路は DM-310 と連動。

### 5. DM-302 [high] OANDA API レイテンシ / FeatureStore 陳腐化アラートが永久 Inactive
- **根因**: `metrics.py:562-591, 822-844` に `observe_oanda_api_latency` / `inc_oanda_api_status` / `observe_feature_staleness` / `set_order_success_rate` が定義されているが、本番コード呼出 **0 件**（grep 確認）。`alerting_rules.yml:70-81 FxOandaApiLatencyHigh` および `:97-111 FxFeatureStorestaleHigh` がデッドアラート。
- **影響**: OANDA レイテンシ劣化（>2000ms）と FeatureStore 陳腐化（>60s）が本番で最重要観測対象だが、両方とも検知ゼロ。
- **修正方針**: `client.py` の各 OANDA 呼出 wrapper に `observe_oanda_api_latency` を計装。`feature_store` のバー更新箇所に `observe_feature_staleness` を計装。

### 6. DE-303 [high] `SharedDataProvider.poll_latest` の silent failure（観測不能）
- **根因**: `data_provider.py:154-162` の except が `logger.exception` のみで RiskAlertEvent / Email / AuditLog のいずれにも通知しない。`runner.py:1518-1534` の `_consecutive_poll_errors` 監視は `account_info` 経路のみで `poll_latest` の連続失敗は集計外。
- **影響**: OANDA candle 障害で全戦略が idle 化しても観測不能。INC-2026-0526 で「6 日間沈黙」を発見できなかった構造的盲点と同質。
- **修正方針**: `_consecutive_poll_errors` を candle 系にも拡張、N 回 (例 30) 超過で RiskAlert publish。

### 7. DE-301 [high] `ema_800` 戦略の warmup EWM 残差 3.78e-6（Parity 許容の 38000 倍）
- **根因**: DE-201 動的算出修正後も `MAX_WARMUP_BARS=5000` クランプにより `period=800` 戦略では `required=10400 > 5000` でクランプ発生。EWM 初期値ドリフトが Live 全期間に永続。`MAX_REGISTRABLE_PERIOD=1000` と `MAX_WARMUP_BARS=5000` の設計矛盾（1000×13 > 5000）が根因。
- **対象戦略**: `ATLAS-2026-0508-069` (ema_slow_period=800) が Live 昇格した場合に発火。現状は paper 状態だが将来 Live 投入時に Parity 保証が失われる構造リスク。
- **修正方針**: `loader.py` / `import_atlas_strategy.py` に `period > 384` 戦略の `live_mode` 昇格ゲートを追加（最小侵襲）。MAX_REGISTRABLE_PERIOD 引下げは後方互換性破壊。

### 8. QA-301 [high] Tier 2 soft_score の EFFECTIVE_WEIGHT_FLOOR が WFA/Drift/OOS 全 None の戦略を不当に PASS させる
- **根因**: `runner.py:631-674` の `_compute_soft_score_redistributed` で `EFFECTIVE_WEIGHT_FLOOR=0.70` を採用（v6.0.1 コメント line 647-658 は LONG 11/balanced 10 件の偽陽性対策）。WFA(0.10)+Drift(0.08)+OOS_IS(0.12)+Top3(0.10)=0.40 が全 None でも、残り正規化値 1.0 で soft_score ≈ 0.857 → 閾値 0.70 で PASS。
- **発生条件**: 短期 H4 戦略で WFA walks<10 になり 3 指標が None になるシナリオは現実的。
- **影響**: Gate 直接接続。検証不足の戦略が Live 昇格対象になりうる。
- **修正方針**: `FLOOR` 引き上げ or None 指標数による減衰（例: valid_weight < 0.6 で FAIL 強制）。QA-302（フル期間 PF フォールバック）と方向が逆なため両者セットで [change:spec] 設計変更が必要。

> **注**: 集計上 high は 8 件。`qa-tester` の QT-301/302/303 は元 high だが devil-advocate により medium 降格（本番コード欠陥ではなくテスト網不完全のため）。

---

## should_consider（medium、26 件のうち優先 5 件）

| ID | 領域 | 要約 |
|---|---|---|
| **PA-303** | FTS strategy_loader | AUDIT-0529-001 Task C の LIVE Gate 拒否経路が `runner.py` のみで `main.py` 未実装。PLATFORM_ALLOW_MAIN_PRODUCTION_LIVE=1 escape hatch 使用時に silent skip 再発 |
| **PA-306** | FTS state_store | `main.py:600-620` `StateStore()` が backend 引数なしで常に InMemoryBackend で起動（dev/staging）。永続化したつもりが全消失するfalse-green 構造（緩和: `:602-611` に CRITICAL ログあり） |
| **PA-307** | FTS arch | main.py (StrategyWorker+Coordinator) と runner.py (StrategySlot) の二重実装が依然存続。重要修正が片方しか入らない構造的根因（PA-303, RE-303 等の連鎖元）。**ADR 化と main.py 廃止判断が必要** |
| **DE-306** | FTS data quality | `_count_weekend_seconds` の UTC 00:00 起点日単位カウントが粗く、毎週月曜朝に effective_gap=43200s > H1 max_gap=5400s で CRITICAL RiskAlert 誤発火 → alert fatigue |
| **QA-301 二次** | ATLAS QA-302 | QA-301 と QA-302 は同一 WFA 欠落状況で逆方向に作用するため**セットで設計変更**しないと片側悪化 |

---

## 退行検証（過去監査修正の現状）

| 監査 | 修正 | 退行 |
|---|---|---|
| AUDIT-0525-001/002 | CSR-101 RCE、PA-101 復元 dead code、PA-102/DM-102 EventBus health、RE-101 Converter 配線、DE-101 DataQualityEngine、DM-101/106 監視配線 等 | **なし** |
| AUDIT-0526-001 / INC-0526-001 | RE-201 stale 回収失敗、DM-204 本番配線、QT-204 multi_slot、DE-201 動的 warmup、QA-201 per-bar リスク指標 | **なし**（ただし DE-201 修正に積み残し → DE-301） |
| AUDIT-0528-002 / 003 | Tier A+B 9 項目 × 2 回、M-02 group atomic | **なし** |
| AUDIT-0529-003 | C-01/C-02/H-01 (KS 無限ループ、EmailNotifier first-send) | **本体経路は OK**。ただし **H-01 修正が `circuit_breaker.py` (main.py 経路) に未適用** → RE-303 (low, dev 経路のため格下げ)。**Task C LIVE Gate が `main.py` に未適用** → PA-303 (medium) |
| EmailNotifier first-send 誤 throttle / 毎時 bot CI 洪水 | INV-2026-0528-001, c450d69 | **なし** |

---

## 構造的根因（横断的観察）

### 根因 1: メトリクス定義と本番計装の乖離
**DM-301 / DM-302 / DM-303 / DM-311 が同根**。`metrics.py` に `inc_*` / `observe_*` メソッドは整備されているが、本番コード（`strategy_slot.py`, `fill_processor.py`, `client.py`, `runner.py` 等）から呼出 0 件。
- EmailNotifier や structlog/AuditLog の代替経路が一部を肩代わりしているため即時危機ではない（DM-301/303 は medium 降格）。
- ただし OANDA レイテンシ・FeatureStore 陳腐化は冗長経路すらない（DM-302 high 維持）。
- **対策**: 「メトリクス定義 → 呼出元最低 1 箇所必須」の契約テスト追加。`tests/contract/test_metrics_wired.py` 等。

### 根因 2: main.py（dev/staging）と runner.py（本番 UnifiedRunner）の二重実装
**PA-303 / PA-306 / PA-307 / RE-303 が同根**。AUDIT-0525-002 で根因として指摘済み。本ラウンドの監査でも:
- AUDIT-0529-003 Task C の LIVE Gate 強化が runner.py のみ
- H-01 KS 無限ループ修正が runner.py のみ
- StateStore backend selection が main.py で常に InMemory
- 等の **新規非対称**が再生産されている。
- **対策**: PA-307 が指摘する通り、main.py 廃止 ADR の作成と移行スケジュールが構造的解決策。

### 根因 3: 過去インシデント (INC-2026-0526/0527) と同型の幻エクスポージャー経路
**RE-301 / RE-302 / DE-311 が同根**。INC-2026-0526-001 / INC-2026-0527-001 の修正は `restore_positions` 起動同期経路のみで、runtime の `_resolve_live_trade_id` や永続化 backend には未到達。
- 6 日間 Live 注文ゼロ・約 -887 JPY のインシデントを生んだメカニズムが、別経路で **同じ構造のまま残存**している。
- **対策**: 「幻エクスポージャー再発を防止する契約テスト」を `tests/parity/test_no_phantom_exposure.py` として確立し、OANDA timeout / process restart / paper-live mixing の全シナリオを横断検証。

---

## 推奨アクション（優先順）

1. **即時対処 (今週)** — RE-302 (1 行修正 + 例外伝播)、DM-306 (1 行修正)、DM-302 (計装追加)、QA-301 (FLOOR 引き上げ or 緊急パッチ)
2. **次スプリント** — RE-301 (rollback 合流)、DE-303 (RiskAlert publish)、DE-301 (loader ゲート)、DE-311 (JSONL fallback)
3. **設計判断必要** — PA-307 (main.py 廃止 ADR)、QA-301/QA-302 セット修正 [change:spec]
4. **重複整理** — QT-307 / QT-317 / DM-313 の 3 件を 1 件に統合
5. **次回 audit-loop で実施** — 本レポートの must_fix 8 件を Phase 3/4 で修正

---

## 次のステップ

```
# 修正実施する場合
/audit-loop --resume                    # 本セッションから修正フェーズに遷移
# または個別修正
/audit-loop --focus risk_execution      # RE-301/302 のみ修正
/audit-loop --focus event_bus_metrics   # DM-301/302/303/306/311 一括
```

詳細は以下を参照:
- 各 finding 全文: `logs/audit/AUDIT-2026-0529-001/findings/{agent_name}.json`
- 妥当性検証全文: `logs/audit/AUDIT-2026-0529-001/validation/cluster_{a,b,c}_*.json`

---

**監査終了時刻**: 2026-05-29
**所要時間**: 約 110 分（Phase 1 並列 10 分 + Phase 2 並列 100 分）
**生成エージェント**: 専門家 7 + devil-advocate 3 = 計 10 並列インスタンス

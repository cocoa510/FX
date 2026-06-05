# 監査レポート AUDIT-2026-0530-001

**実施日**: 2026-05-30
**モード**: dry-run (調査・レポートのみ — ユーザー指示「徹底調査モード」)
**監査体制**: 専門家エージェント 7 名（並列）+ devil-advocate 3 名（クラスタ分割妥当性検証）
**対象**:
- ATLAS `C:\data\works\FX\ATLAS` @ `15d62e62`
- FTS `C:\data\works\FX\fx_trading_system` @ `9998a7a` (最新コード) / `d1e73b1` (HEAD)
**重点**: 昨日 (2026-05-29) のコミット 3 件 (ATLAS 2 + FTS 1) の事後検証 + 退行 + 新規欠陥

---

## エグゼクティブサマリー

- **critical: 0 件**
- **must_fix (high): 6 件確定** ─ うち **5 件は昨日の修正コミット起因の post_fix_defect**
- 検出 68 件 / 検証完了 68 件 / refuted 0 件
- 3 チーム独立で同一欠陥を発見: **DM-302 修正 (OANDA API 計装) が本番経路で `OANDABroker(metrics=)` 未注入のため dead** (RE-401 = DE-402 = DM-402)
- 構造的観察: 二重実装 (main.py vs runner.py) の弊害が PA-303 修正で再生産 → PA-401 (post_fix_defect)

### 検証後 severity 分布 (68件)

| Cluster | 専門家 | 検出 | severity 後 high/med/low |
|---|---|---|---|
| A: ATLAS | code-safety-reviewer + quant-analyst | 14 | 0 / 7 / 7 |
| B: FTS インフラ | platform-architect + risk-execution-engineer | 25 | 4 / 7 / 14 |
| C: FTS データ・運用 | data-engineer + qa-tester + devops-monitor | 29 | 2 / 11 / 16 (推定) |
| **合計** | | **68** | **6 / 25 / 37** |

### 重複統合 (3 件、cross-cluster dedup)

| Canonical | Duplicate | 内容 |
|---|---|---|
| **RE-401** (or DM-402) | DE-402, DM-402 (or RE-401) | OANDABroker metrics= 未注入。クラスタ B は RE-401 canonical (severity=medium 推奨)、クラスタ C は DM-402 canonical (severity=high 推奨)。**最終判定は high** (本番計装 dead は確認、3 行修正可能) |
| RE-411 | DE-404, DM-403 | submit_order TimeoutError metric drop |
| PA-407 (root cause) | PA-401, PA-412 (instances) | 二重実装の構造的根因と個別事例 |

---

## 🔴 確定 must_fix (high 6 件、即時対処推奨)

> **5/6 は昨日のコミット 9998a7a / 15d62e62 / 05ae8595 起因の post_fix_defect**。修正サイクルそのものの品質問題。

### 1. RE-401 / DM-402 [HIGH, post_fix_defect] OANDABroker(metrics=) 未注入 で DM-302 計装が本番 dead
- **根因**: 昨日の DM-302 修正は `_record_api_metric` を `client.py` に追加したが、`runner.py:343`, `main.py:335`, `forward_test.py:239` の **`OANDABroker(...)` 生成時に `metrics=` 引数を渡していない** → `self._metrics is None` で常に早期 return → 計装が本番で**完全 dead**
- **発見**: 3 チーム独立 (risk-execution-engineer / data-engineer / devops-monitor) で確認
- **影響**: DM-302 修正の主目的 (FxOandaApiLatencyHigh / FxFeatureStorestaleHigh アラート復活) が達成できていない
- **修正方針**: `metrics=self._metrics` を 3 箇所に追加 (3 行修正)
- **再発防止**: `tests/contract/test_oanda_broker_metrics_wired.py` 新設 (broker 生成時の metrics 注入を契約テスト)

### 2. PA-401 [HIGH, post_fix_defect] PA-303 修正の RiskAlertEvent が main.py で silently drop
- **根因**: 昨日の PA-303 修正で `main.py:492-506` に LIVE Gate 拒否時の `self._event_bus.publish()` を追加したが、`initialize()` 内では:
  - EventBus は `start()` 未呼出 (line 1004 で起動)
  - EmailNotifier は line 852 で生成、line 1083 で起動
  - → `memory_adapter.py:94-96` で silent return → Email 通知 0 件
- **AUDIT-2026-0529-003 C-01 同型再発**: runner.py 側には `EmailNotifier を slot loop より前に start` する修正済 (line 500-525) だが、**main.py に移植漏れ**
- **修正方針**: main.py の `initialize()` 順序を `EventBus.start()` → `EmailNotifier.start()` → `publish` に変更
- **再発防止**: `tests/integration/test_pa401_main_eventbus_startup_order.py` で publish 前の起動順序を検証

### 3. RE-402 [HIGH, post_fix_defect] entry_rollback で OANDA 上のポジションが孤児化 (INC-0526 逆方向再発)
- **根因**: 昨日の RE-301/302 修正で `strategy_slot.py:808-824` (BrokerUnavailableError 経路) および `:829-842` (matching=[] 経路) のいずれも **`return` のみで OANDA close 処理なし**。entry_rollback は **state クリアのみ**
- **影響**: OANDA 一時障害時に SL/TP 未設定の **孤児ポジションを市場に晒す**。INC-2026-0526-001 の逆方向再発 (FTS→OANDA 整合喪失)
- **修正方針**: entry_rollback 時に OANDA 側で fill.broker_order_id (Trade ID 不在のため Order ID) を **best-effort cancel/close** する経路を追加。失敗時は KillSwitch 発動候補
- **再発防止**: `tests/fault/test_re402_entry_rollback_orphan_position.py` で entry_rollback 時の OANDA 残存トレードを検証

### 4. PA-412 [HIGH, post_fix_defect] PA-103 escape hatch + PA-401 二重顕在化
- **根因**: `PLATFORM_ALLOW_MAIN_PRODUCTION_LIVE=1` escape hatch で main.py LIVE 起動した場合、PA-401 (Email 通知 dead) と PA-103 元因 (既存ポジション無視) が**同時に顕在化**
- **修正方針**: escape hatch 使用時の警告強化、または escape hatch 自体の deprecate 検討
- **再発防止**: PA-401 修正と連動

### 5. PA-407 [HIGH] 二重実装の構造的負債が拡大 (main.py vs runner.py)
- **根因**: 昨日の PA-301/303/306 修正で main.py と runner.py の機能セット非対称がさらに拡大 (set_metrics_collector ループ / LIVE Gate ハンドリング / StateStore 構築の 3 系統が両側に分岐)
- **影響**: 片方更新→他方ドリフトの構造的負債が悪化。PA-401 はその直接的な失敗例
- **修正方針**: **PA-307 (main.py 廃止 ADR) の前倒し提案**。設計判断のため別セッション
- **PA-407 自体は high のまま** だが、即時修正は不可能 (ADR 案件)

### 6. DE-403 [HIGH] FxFeatureStorestaleHigh が H1/H4 戦略で常時 FIRING (post_fix_defect)
- **根因**: 昨日の DM-302 修正で `live_store.update_bar` に追加した `observe_feature_staleness(self.primary_tf, age_sec)` が:
  - ラベル誤用: `strategy_id` 引数に **TF 名** (`H1` 等) を渡している (DE-403/DM-408 が独立指摘)
  - 測定 semantics 誤り: `age_sec = now - _last_primary_bar_time` は **バー間隔** (H1=3600s, H4=14400s) を測定
  - → `alerting_rules.yml` の `FxFeatureStorestaleHigh (>60s)` 閾値で **常時 FIRING**
- **影響**: alert fatigue で本物の障害を見逃す。新規アラートが導入された 2026-05-29 以降に発生
- **修正方針**: (a) `observe_feature_staleness` 引数名を修正、(b) `staleness` を **「次バー到着遅延」** に再定義 (TF 別の許容オーバーラン秒数閾値、例: H1 = 7200s で発火)、(c) または `alerting_rules.yml` 閾値を TF 別に分岐

---

## 🟡 should_consider (medium、優先 10 件、合計 25 件)

| ID | 領域 | 要約 |
|---|---|---|
| **CSR-402** ↓ med | ATLAS | QA-301 backfill 未実施で 250+ 件が 6.1.0 のまま (quant-analyst 実測で flip 8 件、Live 該当 0 件確認のため high → medium 格下げ。実害は atlas-loop 改善率誤判定に限定) |
| RE-404 | FTS RE | _resolve_live_trade_id が comment 反映遅延に対するリトライなし (RE-301 修正の補完) |
| RE-411 | FTS RE | submit_order TimeoutError metric 計装漏れ (RE-401/DM-403/DE-404 と関連) |
| PA-408 | FTS PA | InMemoryEventBus.publish が未起動時に silent return + caller の try/except 無効化 (PA-401 検出を構造的に困難化) |
| PA-411 | FTS PA | 二重実装の機能セット差分を ADR 化必要 (PA-407 と関連) |
| RE-406 | FTS RE | live_anomaly kind 集約が 6 種類同居で 1/6 配信に縮退 |
| RE-407 | FTS RE | RE-305 と _check_live_health_alerts が同じ live_orders_silent kind を共有 |
| DE-401 ↓ med | FTS DE | DE-301 period gate import-time 限定 (high→medium 格下げ。22 LIVE 戦略実害ゼロ、bypass は OS アクセス要) |
| QA-402 | ATLAS QA | QA-301 ゴールデンが check_backtest_gate E2E を踏まず単体テストのみ |
| QA-405 | ATLAS QA | QA-302 deferred のまま QA-301 と組合せて soft_score 二重 penalize 経路成立 |

---

## ⚙️ 設計判断が必要 (DESIGN-C-001)

**RE-305「復旧まで継続通知」設計** (runner.py:1624-1627、30の倍数で再発火) vs **live_orders_silent 12 時間 throttle** (ユーザー要請 2026-05-29) が AUDIT 間調整なしに共存

### オプション
- **A**: RE-305 を専用 kind `oanda_poll_error_escalation` に分離、throttle=0 (継続通知)
- **B**: RE-305 を初回 1 回のみの通知に変更 (継続通知を廃止)

**blocking_findings**: DM-404, DE-406

---

## ✅ 退行検証 (昨日コミットの再評価)

| 修正 | 修正コード自体の品質 | 退行 |
|---|---|---|
| ATLAS 05ae8595 (QA-301 [change:spec]) | **PARTIAL OK with concerns** (CSR-401/402, QA-401〜404) | **手順 6 (backfill) 未実施**は仕様違反だが実害 0 件 |
| ATLAS 15d62e62 (CSR-302/303/306) | **PARTIAL OK** (CSR-404 validate_instrument/timeframe 適用漏れ) | なし |
| FTS 9998a7a (RE-301/302/305/306, MISSED-302, PA-301/303/306, DM-302/306/314, DE-303/304/306/301/311, QT 多数) | **重大な post_fix_defect 5 件** (PA-401, PA-412, RE-402, DE-403, DM-402) | 5 件 |

**結論**: 昨日の修正サイクルは **「動くがロジックが正しくない」修正が 5 件混入**。`code-safety-reviewer` の事前 review がフェーズに無かったことが根因。

---

## 構造的観察 (前回 AUDIT-0529-001 比)

### 改善された点
- **第2チーム検証で「過大評価」「本番経路取り違え」を是正する文化が定着** (DE-401 / CSR-402 を実集計データで medium 格下げ)
- 3 チームが独立に同一欠陥を発見 (DM-302 dead path) → 監査カバレッジの三重化が機能

### 悪化した点
- **修正コード自体に欠陥が混入する頻度が高い**: 9998a7a の 24 件中 5 件 (20.8%) が post_fix_defect
- **二重実装 (main.py vs runner.py) の負債が拡大** (PA-407): 修正のたびに片側のみ更新が再発
- **[change:spec] 手順 6 (backfill) が連続 deferred** (QA-201, QA-301 と続く): backfill 実施計画が文書化されていない

### 根因仮説
- **修正フェーズに `code-safety-reviewer` の事前 diff 検証が組み込まれていない** (`audit-loop` Phase 4 の設計では実装後 review だが、本番経路を踏むかどうかの事前検証が不足)
- **二重実装は ADR 化が遅れている** (PA-307 を昨日 must_fix 6 件から除外したのは正しいが、放置すると同型バグ再生産が続く)

---

## 推奨アクション (優先順)

1. **即時対処 (今週)**:
   - RE-401/DM-402: `OANDABroker(metrics=)` 3 行修正
   - PA-401: main.py initialize() 順序修正
   - RE-402: entry_rollback の OANDA close 経路追加
   - DE-403: alerting_rules.yml 閾値 TF 別分岐 OR `observe_feature_staleness` semantics 修正
   - PA-412: PA-401 と連動
2. **次スプリント**:
   - PA-407 (main.py 廃止 ADR) — 設計判断
   - DESIGN-C-001 (RE-305 vs 12h throttle) — ユーザー判断
   - QA-301 backfill 実施 (専用スクリプト + 1452 戦略一括処理)
3. **重複統合**:
   - RE-401 / DE-402 / DM-402 を 1 件として処理
   - RE-411 / DE-404 / DM-403 を 1 件として処理
4. **構造改善**:
   - 修正フェーズに code-safety-reviewer の事前 diff 検証を組込み
   - 契約テスト追加: `tests/contract/test_oanda_broker_metrics_wired.py` (broker 注入)
5. **次回 audit-loop**:
   - 上記 must_fix 6 件の Phase 3/4 を実施

---

## 次のステップ

```
# 修正フェーズへ移行する場合
/audit-loop --resume

# 重複統合のみ実施 (RE-401 = DM-402 = DE-402)
編集対象: 3 行追加 (runner.py:343, main.py:335, forward_test.py:239)
```

詳細:
- 各 finding 全文: `logs/audit/AUDIT-2026-0530-001/findings/{agent_name}.json`
- 妥当性検証全文: `logs/audit/AUDIT-2026-0530-001/validation/cluster_{a,b,c}_*.json`

---

**監査終了時刻**: 2026-05-30
**所要時間**: 約 110 分 (Phase 1 並列 + Phase 2 並列)
**生成エージェント**: 専門家 7 + devil-advocate 3 = 計 10 並列インスタンス

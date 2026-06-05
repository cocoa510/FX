# R2 メタ監査レポート (2026-05-24)

**監査種別**: R2 (PR22-PR36) 完了後の 4 専門家メタ監査ラウンド (修正計画 v3 line 140 / 157 規定)
**対象コミット範囲**: `6ef45c8..67ab47a` (FTS リポジトリ、R1 PR22-24 + R2 PR25-36 = 15 PR)
**監査チーム**: platform-architect / risk-execution-engineer / qa-tester (Phase 1 並列) + devil-advocate (Phase 2 検証 + 独立調査)
**参照**: `audit_report_2026_0524_v2.md` (欠陥定義) / `audit_2026_0524_remediation_plan_v3.md` (修正設計)
**findings 原本**: `logs/audit/r2_meta/findings/{platform-architect,risk-execution-engineer,qa-tester}.json`

---

## 結論: R2 完了判定 = **BLOCKED** ❌

R2 の完了基準は「Critical 0」。本メタ監査は **Critical 1 件 + High 2 件が未クローズ** であることを、複数エージェントの独立収束 + devil-advocate の本番経路追跡で確定した。R2 を「完了」と宣言する前に下記 3 ブロッカーの追修正が必須。

**メタ監査の核心**: 全 74 件の追加テストは PASS (0.69s) し、PR 単位ではほぼ green に見える。しかし主要 2 件 (C-1, H-2) は **本番 LIVE 経路で配線が断線しており、単体テストが emit_alert/coordinator ロジックを手動注入・再実装するため false-green** になっている。「下流の症状だけ直して上流の配線が無い」という同型欠陥が C-1 と H-2 の双方で発生した。

---

## ブロッカー一覧 (R2 クローズに必須)

### 🔴 BLOCKER 1 — C-1 未クローズ (CRITICAL): 本番で含み損 Email が依然届かない + KS 注文キャンセルも不動作

- **収束**: risk-execution-engineer `RE-001` (critical) + devil-advocate `DA-001` (critical, 独立発見) + devil-advocate 検証 `validated:true`
- **根拠**:
  - `runner.py:264` が `GlobalRiskSupervisor()` を **`emit_alert` 無し・`cancel_open_orders` 無し** で構築 (runner.py 全体に `emit_alert` の grep 0 件)
  - `_emit_alert is None` のため `_dispatch_alert` (risk_supervisor.py:913) は logger 出力のみで return → `unrealized_warning_activated` の `RiskAlertEvent` が Event Bus に **一度も publish されない** → EmailNotifier (RISK_ALERT 購読、email_notifier.py:219) に到達せず
  - `kill_switch_activated` は `runner.py:592` で**直接** publish する別経路があるため KS メールは届く。だが WARN に同等経路は存在しない → **盲点化**
  - `cancel_open_orders is None` (risk_supervisor.py:851) のため **KS 発動時の in-flight 注文キャンセルが本番で skip される** (DA-001)
- **PR34 の限界**: `_RISK_ALERT_KINDS` への kind 登録という**下流症状のみ**を修正。計画 v3 PR34 のスコープ自体が email_notifier.py に限定され、runner.py の emit_alert 注入が設計対象外だった
- **false-green**: 単体テストは emit_alert を fixture 注入 / `_on_risk_alert` を直接呼ぶため本番配線欠落を検出不能
- **修正**: `runner.py:264` で `GlobalRiskSupervisor(emit_alert=<event_bus.publish する callable>, cancel_open_orders=<callable>)` を注入。実 EventBus (InMemoryEventBus) で `unrealized_warning_activated → EmailNotifier 到達` を検証する統合テストを追加

### 🟠 BLOCKER 2 — H-2 未クローズ (HIGH): KS reason メトリクスが常に "unknown"

- **収束**: platform-architect `PA-001` + risk-execution-engineer `RE-002` + qa-tester `QA-002` + devil-advocate `DA-002` (4 エージェント独立収束)
- **根拠**:
  - PR29 (reason ラベル) + PR30 (coordinator が `triggers` 複数キーを読み `trigger_reason` を算出し `force_activate(reason=...)` へ渡す) は個別には正しい
  - しかし `force_activate` (circuit_breaker.py:485) は `await self._activate()` に **reason を渡さない**。`_activate` (circuit_breaker.py:309-323) は `inc_kill_switch_triggered()` を**引数なし**で呼ぶ → default `reason='unknown'`
  - PR30 が苦労して算出した `trigger_reason` は `_activate` 到達前に破棄され、本番メトリクスは**常に reason='unknown'**。H-2 の症状は `ptrc_post_unknown` → `unknown` に名前が変わっただけで根治せず
  - さらに本番主経路 `GlobalRiskSupervisor._activate_kill_switch` (risk_supervisor.py:823) は metric を一切加算しない
  - 計画 v3 PR30 (plan:452) は coordinator 内で `inc_kill_switch_triggered(reason=trigger_reason)` を**直接呼ぶ**設計だったが、実装が `force_activate` 経由に変わり reason 伝播が断線
- **false-green**: PR30 テストは coordinator ロジックをヘルパで再実装し AsyncMock の呼び出しを assert。既存 wiring test は旧単数キー `details={'trigger':...}` のまま reason 未確認
- **修正 (推奨: 選択肢 A)**: `circuit_breaker._activate(reason='unknown')` に引数追加 → `force_activate` / `evaluate_and_activate` 双方から伝播 → `inc_kill_switch_triggered(reason=reason)`。`GlobalRiskSupervisor._activate_kill_switch` でも metric 加算。end-to-end (coordinator → _activate → metric) で reason ラベルを検証するテスト追加

### 🟠 BLOCKER 3 — C-5 部分未機能 (HIGH): parity timeout が伝播しない

- **収束**: qa-tester `QA-001` (実測) + devil-advocate `DA-003`
- **根拠**:
  - PR28 は `tests/parity/conftest.py:27` に `pytestmark = pytest.mark.timeout(300)` を追加。しかし pytest 仕様上 conftest.py の `pytestmark` は**同ディレクトリの別テストファイルに伝播しない**
  - pytest 9.0.3 実測で parity テストアイテムの markers = **`[]`** (空)。グローバル `timeout=30` がそのまま有効
  - 現在 parity は 5.47s で完了するため**即時問題はない**が、指標追加で 30s 超過すると 56 件が誤 FAIL する構造的欠陥
  - 計画 v3 PR28 (plan:63) は「parity 個別に `@pytest.mark.timeout(300)`」だったが実装で conftest.py 方式に変更し効果消失
- **false-green**: `test_pytest_timeout_config.py:45` は conftest.py に文字列が**書かれているか**のみ確認し、実伝播を検証しない
- **修正**: parity 6 ファイル先頭に `pytestmark = pytest.mark.timeout(300)` を直接記述。設定テストを hook で実伝播を動的検証するよう書換

---

## 要人間判断 (期限リスク)

### ⚠️ RE-005 (MEDIUM, PR35/H-17): トレンド依存 USD/JPY H4 LONG Live 戦略の MISMATCH 露出

- PR35 は名指しの `0511-009` を Paper へ正しく降格 (runner_config.json `execution_mode=paper`、runner.py:375 で PaperBroker ルーティング確認)。`0510-002` は実体が方向非依存 Mean Reversion (既 paper) で退避対象外と**妥当に再分類**
- だが `sma_live_verification_2026_0523.md:22` のラベル誤りの背後に、真にトレンド依存の **USD/JPY H4 LONG trend_following で execution_mode=live の戦略 (例 0505-367 / 0505-424)** が存在し、SMA downtrend 継続なら**これらが真の MISMATCH Live 露出**
- PR35 はこの判定を R3 PR42 (期限 2026-06-21) に先送りしているが、v2 監査 **M-D2 は意思決定期限を 2026-05-27 (3 日以内)** に設定 → **期限超過リスク**
- **アクション**: `verify_sma_live_values.py` で MISMATCH 判定の全 Live 戦略を strategy_id ベースで網羅列挙し、人間オーナーが 2026-05-27 までに継続/引き戻しを判断

---

## R3 繰越候補 (MEDIUM / LOW、即時ブロッカーではない)

| ID | severity | PR | 内容 |
|---|---|---|---|
| PA-003 | medium | PR36/H-9 | 再接続 logger.info が `_metrics is not None` ガード内 → Prometheus 未起動の Paper 期間 (= PR が解消対象としたシナリオ) で発火せず。logger をガード外へ移動 |
| RE-003 | medium | PR34 | activated/deactivated が同一 throttle kind → 5 分以内の WARN 解除通知が抑止され運用者が解除を認知できない |
| PA-002/RE-006 | medium/low | PR30 | coordinator テストが本番メソッド非経由で reason 断線を検出できない (BLOCKER 2 の修正と同時にテスト強化) |
| PA-004/QA-006 | low | PR36 | 再接続ログテストが誤配置を仕様固定する / 行検索が脆弱 (BLOCKER のテスト behavioral 化で同時解消) |
| RE-004 | low | PR34 | 日次リセット解除が details 欠落で「異常メール」化 |
| RE-007 | low | PR31 | `StrategyRiskState` は依然ガードなし (将来検討と明記済、ADR-0005/PR59 で正当化) |
| PA-005/QA-003 | low | PR25 | metrics 注入テストが静的解析のみ (配線自体は正しく PASS、devil 格下げ済) |
| PA-006 | low | PR22 | ADR-0004 が PositionReconciler を UnifiedRunner 注入対象と記すが UnifiedRunner は Reconciler を構築せず (実害なし、R4/PR60 で訂正) |
| QA-004 | low | PR28 | markers 登録テストが文字列存在のみ確認 |
| QA-005 | low | PR27 | `feature_staleness.md:57` の「PR36 で追加予定」を「追加済 (67ab47a)」へ訂正 |

---

## 確実にクローズ済 (PASS 確定)

| 欠陥 | PR | 確認内容 |
|---|---|---|
| **C-2** | PR25/PR26 | `runner.py:368-371` で LiveFeatureStore に `metrics=self._metrics` 注入、`live_store.py:472` の `_record_compute_error→inc_feature_compute_error` 経路まで生存。本番で `fx_feature_store_compute_errors_total` が実発火 (PR12 デッドコード化を解消)。EmailNotifier 注入も配線済。forward_test も同パターン |
| **C-3** | PR23 | Dashboard 二重 autorefresh を `_AUTOREFRESH_AVAILABLE` で完全相互排他化 |
| **C-4** | PR27 | `feature_staleness.md` / `event_bus_dedup_spike.md` のアラート名が `alerting_rules.yml` (`FxFeatureStorestaleHigh` / `FxEventBusDedupSpike`) と完全一致 |
| **H-11** | PR31 | `AccountRiskState` の `__setattr__` ガード + `set_guarded` が実証済 `RiskState` パターンを踏襲。直接代入 `AttributeError`・`model_validate_json` 復元後の防壁維持を 9 テストで実検証 (**false-green なし**)。既存 KS テスト改修もガード弱体化なし |
| **H-1** | PR32 | WARN 二段ヒステリシス (発動 95% / 解除 80%) を正しく実装、チャタリング抑止を実検証。日次リセット deactivate は WARN のみ操作し `is_kill_switch_active` を触らず **REV-1 契約維持** |
| **H-17** (名指し) | PR35 | `0511-009` を Live 経路から確実に除外、`0510-002` を妥当に再分類、復活 Runbook 整備 (残課題は RE-005 の人間判断) |
| ADR | PR22/PR33 | PR22 (ADR-0004) は F-1 `self._metrics` AttributeError を解消。PR33 は計画通り docs-only (実装は R3/PR37) |

---

## devil-advocate のバイアス自制 (v2 教訓の適用)

v2 メタ監査で devil-advocate 出力は「批判の水増し・設計意図見落とし・遡及適用」で信頼度 ~40% と記録された。今回は自己検証で **PA-005 / PA-006 / QA-003 を low に格下げ** (機能は正しく PASS、テスト品質課題に限定) し、独立 findings (DA-001〜004) は全て本番経路を grep/Read で追跡した evidence ベース。過大批判は見られず、収束 4 ブロッカーは全て `validated:true` で確定。

---

## 次アクション

1. **BLOCKER 1〜3 の追修正** (R2 hotfix。Live リスク経路の配線変更を含むため人間承認を要する)
   - PR36.1: `runner.py` GlobalRiskSupervisor に `emit_alert` + `cancel_open_orders` 注入 + 実 EventBus 統合テスト (C-1)
   - PR36.2: `circuit_breaker._activate(reason)` 伝播 + GlobalRiskSupervisor metric 加算 + e2e テスト (H-2)
   - PR36.3: parity 6 ファイルへ `pytestmark` 直接付与 + 設定テスト動的化 (C-5)
2. **RE-005 の人間判断** (2026-05-27 期限): USD/JPY H4 LONG trend Live 戦略の MISMATCH 露出を strategy_id 網羅で確認
3. 追修正後に **再メタ監査** (本ラウンドと同構成) で Critical/High 0 を確認 → R2 真の完了宣言

---

---

## 追記: 追修正完了 (2026-05-24〜25)

メタ監査で確定した 3 ブロッカーを同日中に追修正し FTS master へ commit 済 (回帰 956 passed / 1 skip、code-safety レビュー条件付き PASS → 推奨 2 件も反映)。

| 追修正 | commit | 種別 | 内容 |
|---|---|---|---|
| **PR36.1** | `6695a68` | fix:bug | C-1: `runner.py` で GlobalRiskSupervisor に `emit_alert`/`cancel_open_orders`/`metrics` 注入。KS 直接 publish 削除で二重発火防止 (supervisor 経由に一本化)。実 EventBus 統合テスト 7 件 |
| **PR36.2** | `3f0fda7` | change:spec | H-2: `circuit_breaker._activate(reason)` 伝播 + supervisor 主経路 metric 加算。allowlist に `balance_unavailable`/`daily_loss_ratio_exceeded` 追加 (code-safety 指摘の観測死角解消)。実 KillSwitch e2e 検証 |
| **PR36.3** | `8bd6861` | chore | C-5: parity 6 ファイルに `pytestmark=timeout(300)` 直接付与 (実測 56/56 伝播確認)。false-green 設定テストを動的検証に置換 |

**結合ギャップの是正**: PR36.1/PR36.2 の並列分割で `runner.py` が supervisor に `metrics=self._metrics` を渡さず PR36.2 の metric 加算が本番 no-op になる断線を発見 → PR36.1 commit に含めて是正 (メタ監査と同型の断線を自ら検出)。

**RE-005 対応**: 全 Live 22 戦略を網羅列挙 (`logs/audit/r2_meta/re005_live_mismatch_enumeration.md`)。
- **狭義 MISMATCH (trend_following × 逆トレンド) 4 件**: `0505-367` / `0505-424` (RE-005 名指し) + `0505-368` (**監査見落とし**) + `0506-005` (GBP/JPY H1、新規)。全件 PR35 未対応
- **広義 MISMATCH (LONG breakout × 逆トレンド) 4 件**: `0507-049` / `0504-060` / `0506-033` / `0504-098`
- **盲点の原因**: `verify_sma_live_values.py` の `TARGETS` が 3 戦略しかカバーしていない。SMA データは 2〜4 週間古く `/atlas-data` 更新後の再実行を推奨
- **人間判断 (2026-05-27 期限)**: 狭義 4 件を最優先で継続/引き戻し判断

## 追記2: 再メタ監査ラウンド (2026-05-25) — R2 COMPLETE ✅

追修正後、本ラウンドと同構成 (risk-execution-engineer / platform-architect / qa-tester 並列 + devil-advocate 最終判定) で再メタ監査を実施。

**Phase 1 判定**: risk-execution-engineer=PASS / qa-tester=PASS / platform-architect=CONDITIONAL
**Phase 2 (devil-advocate) 最終判定**: **R2 COMPLETE**

**3 ブロッカー全て CLOSED を独立再現確認** (本番経路を grep/Read で追跡、「テストは通るが本番経路は別」の前回の罠が回避されていることも確認):
- **RE-001 (C-1)**: `_build_risk_supervisor()` が `emit_alert` を実注入 → WARN→RiskAlertEvent→EmailNotifier 到達を実 EventBus 統合テストで検証 (モック迂回でない genuine な e2e)
- **DA-001**: `cancel_open_orders` 配線で in-flight 注文 best-effort キャンセル動作
- **RE-002 (H-2)**: reason が force_activate/evaluate_and_activate/coordinator/supervisor 全経路で metric 到達。allowlist 整合
- **QA-001 (C-5)**: parity 6 ファイル全件に pytestmark 直接付与、plugin API 実測で 56/56 伝播確認
- 二重発火退行なし (exactly-once)、発火漏れなし、二重加算なし、REV-1 契約維持、回帰 956 passed/1 skip

**新規指摘 (全て low、R2 完了の妨げにならない → R3/次サイクル繰越)**:
- **DA2-001 / PA2-001 / RE2-001 (low)**: `kill_switch_cancel_failed` が EmailNotifier `_RISK_ALERT_KINDS` 未登録で silent drop (元 C-1 と同型のバグクラス)。ただし `_cancel_all_open_orders` が per-order 例外を内部 catch するため**発火窓が実質ゼロ** (devil が medium→low 格下げ、定量根拠あり)。→ 次サイクルで `_RISK_ALERT_KINDS` 追加推奨
- **PA2-002 / RE2-002 / QA2-002 (low/info)**: risk_supervisor.py:33-35/863-864 のコメントが allowlist 追加済の reason を「unknown に丸まる」と誤記 (PR36.2 で実態と乖離)。→ コメント訂正
- **QA2-001 (low)**: parity 伝播の動的テストが collect エラー有無のみ assert (AST + 実測で補完済)。→ plugin API 強化

---

**作成**: Claude Opus 4.7, 2026-05-24 (R2 メタ監査ラウンド) / 追記 2026-05-25 (追修正 + 再メタ監査)
**最終判定**: BLOCKED → 3 ブロッカー追修正 → 再メタ監査で **R2 COMPLETE (Critical 0 / High 0)** ✅
**収束ブロッカー (解消済)**: RE-001+DA-001 (C-1) / PA-001+RE-002+QA-002+DA-002 (H-2) / QA-001+DA-003 (C-5)
**追修正 commit**: PR36.1 `6695a68` / PR36.2 `3f0fda7` / PR36.3 `8bd6861` (FTS master)
**R3 繰越 (low)**: kill_switch_cancel_failed の Email 登録 / stale コメント訂正 / parity 動的テスト強化 / 元 R3 候補 (PA-003/RE-003/RE-004 等)
**RE-005 人間判断 (2026-05-25): 引き戻し不要で確定**。4 戦略はエントリーフィルターで逆トレンド発注不可 (下降局面は FLAT) + SMA割れ/SL で損失限定 + 3 年逆レジーム BT で PF≥1.0 検証済 = 逆トレンド「資本保全」耐性あり。MISMATCH 検出が SMA50/200 と戦略実ゲート (SMA20-slope/SMA50-cross) を取り違えた方法論欠陥が真因。**真のアクション = 戦略引き戻しでなく `verify_sma_live_values.py` を実エントリー指標と照合するよう是正** (RE-005 suggested_fix を訂正)

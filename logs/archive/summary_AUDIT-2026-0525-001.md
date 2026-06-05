# システム監査レポート — AUDIT-2026-0525-001

> `/audit-loop --dry-run` 相当（Phase 1 並列専門家監査 + Phase 2 敵対的妥当性検証 + Phase 2.5 第2チームによるレポート検証）
> 対象: ATLAS（戦略生成・BT・評価層）+ fx_trading_system（FTS / Live 実行基盤）
> 実施日: 2026-05-25 / モード: 調査・報告のみ（自動修正なし）

---

## ⚠️ 検証による訂正（Phase 2.5 — 2026-05-25 追記）

> 第2の専門家チーム5名がレポート結論をコード実読・実行再現で再検証し、**重大な誤りを発見した**。
> **訂正後 severity 分布: critical 1 / high 6 / medium 16 / low 33**（当初: critical 0 / high 8 / medium 15 / low 35）

| id | 当初 | 訂正後 | 方向 | 根拠（第2チームが実証） |
|----|------|--------|------|------|
| **CSR-001** | medium | **critical** | 過小評価 | **RCE を実際に再現**。`__builtins__=_SANDBOX_BUILTINS` 注入下で `from atlas.backtest import event_simulator; event_simulator.os.getcwd()` が成功。`__import__` 許可 + モジュール `.os` が本物 → builtins 制限を貫通。Stage3 はスレッドベースで OS 分離なし |
| **RE-001** | medium | **high** | 過小評価 | 本番 `.env` は `OANDA_ENVIRONMENT=live` かつ `ENV` 変数不在 → ガードが永久に不発火。**Live 稼働中の EUR_USD 戦略 (ATLAS-2026-0511-059) が実在**し、固定 USD_JPY=150 で実弾リスク換算 |
| **CSR-002/QA-001** | low(却下) | **medium** | 過小評価 | `model_dump_json` が inf→null にサイレント変換しデータ消失。L1=PASS(inf が pf<0.8 を回避) と L2=null=FAIL の判定非一貫。`json.dumps` 経由で不正 `Infinity` トークン |
| **QT-003** | high | **medium** | 過大評価 | PTRC 承認は別テスト3件 (test_signal_flow.py:99, test_phase3_risk_execution.py:125, test_ptrc_rejection.py:77) で検証済み。「CI で一度も検証されない」は誤り |
| **QT-005** | high | **low** | 過大評価 | exposure リジェクトは test_phase3_platform.py / test_ptrc_currency.py / test_r6_risk_fixes.py で検証済み。docstring 乖離のみ |
| **PTRC バイパス無し** | (健全と明記) | **low(新規)** | 誤った安心 | FLAT/決済注文は LIVE/PAPER 両方で PTRC をバイパス（exposure 削減のみで良性だが「バイパス無し」は誤り）。`決済PTRC承認` ログが PTRC 未実行なのに出力される監査整合性の軽微欠陥 |

**検証で確認された当初レポートの正しい結論**: UnifiedRunner が唯一の本番経路 / DM-001/003/004 (high) / QT-001/QT-004 (high) / QT-007 格下げ / PA-001 格下げ / **Parity コア17指標がバイト一致（max_abs_diff=0.000 で実測再現）** / QA-002/QA-006 が Gate 非接続で low。

**検証の価値**: レポートは**最重要2件（CSR-001 RCE・RE-001 実弾リスク誤算）を過小評価**し、**テスト系2件（QT-003/QT-005）を過大評価**していた。誤りは双方向だった。以下本文の severity は訂正後の値に従うこと。

---

## エグゼクティブサマリー

専門家7名による並列監査で **61件** の指摘を検出し、devil-advocate 3名がコード実読で全件検証した。

| 区分 | 件数 |
|------|------|
| 検出合計 | 61 |
| 妥当認定 (validated) | 50 |
| 却下 (false) | 1（CSR-002、クラッシュ再現せず） |
| severity 調整 (downgraded) | 10 |
| 重複 | 3（CSR-002≡QA-001、QT-002/QT-009≡QT-001） |

**【Phase2 時点】検証後 severity 分布: critical 0 / high 8 / medium 15 / low 35**
**【Phase2.5 訂正後】severity 分布: critical 1 / high 6 / medium 16 / low 33**（上記「検証による訂正」参照）

→ **訂正後、critical 1件（CSR-001 サンドボックス RCE）が存在する**。収束条件 threshold=critical 上は **未収束**。
CSR-001 + high 6件（うち RE-001 は実弾運用に直結）を最優先で対応すべき。

### 最重要テーマ（高 severity 群の根因）

> **本番経路 `UnifiedRunner` に、dev/FastAPI 経路 `main.py` 向けに作られた運用・監査・安全インフラが配線されていない。**

実運用される `scripts/run_unified.py → UnifiedRunner` に対し、`main.py → ExecutionCoordinator`（FastAPI、実質 dev 用）にのみ存在して UnifiedRunner には未配線な機能群:

- **HealthChecker**（DM-003） — 本番で Redis/OANDA/EventBus の能動ヘルスチェックが一切動かない
- **Dashboard 接続先**（DM-004） — `localhost:8000`(main.py) 固定で本番を監視できない
- **AuditLogger 配線**（DM-001） — PTRC 拒否理由が監査証跡に残らない（CLAUDE.md 要件違反）
- **Kill Switch の gateway halt**（RE-004） — KS 発動が BrokerGateway を止めない
- **動的 Currency Converter 注入**（RE-001） — 固定レートで非JPYペアのリスク換算が不正確

この5件を「UnifiedRunner 運用インフラ統一」という1テーマで束ねると、修正設計の見通しが良い。

---

## High 指摘（8件） — 早期対応推奨

### 本番影響あり（3件）

#### DM-001 [high] AuditLogger が本番で dead code
- **事実**: `AuditLogger`/`AuditEntry` は `core/monitoring/audit_log.py` に定義されるが、本番モジュール（risk_engine/, execution_engine/, unified_runner/）から一切 import されない。grep ヒットは定義ファイル自身と `tests/unit/test_phase3_platform.py` のみ。
- **影響**: PTRC 拒否決定・Kill Switch 発動・注文根拠が監査ログに残らない。CLAUDE.md「リスク拒否理由は必ず Audit Log に記録する」に違反。事後の規制対応・障害解析が不可能。
- **evidence**: `audit_log.py:1-180`, `ptrc.py`（import なし）, `runner.py`（import なし）

#### DM-003 [high] HealthChecker が UnifiedRunner に未組込
- **事実**: `HealthChecker` は `main.py`（FastAPI）にのみ組込（main.py:30,87,484）。`runner.py` には import すら無い。
- **影響**: 本番（UnifiedRunner）で Redis 障害・OANDA 切断・Event Bus 停止をリアルタイム検知できない。health ステータスは初期値のまま。
- **evidence**: `runner.py`（HealthChecker 文字列 0件）, `health_check.py:1-50`

#### DM-004 [high] Dashboard が本番を監視不能
- **事実**: `dashboard/app.py:36` の `API_BASE_URL='http://localhost:8000'` は `main.py` の FastAPI を指す。UnifiedRunner は HTTP API を公開しない。
- **影響**: 運用ダッシュボードが本番環境で機能しない。ポジション・リスク・PnL をリアルタイム確認できない。DM-003 と相まって本番監視が実質不能。
- **evidence**: `app.py:36,41-57`, `runner.py`（HTTP サーバ無し）

### dev/CI 影響（4件） — テストが「検証しているフリ」

#### QT-001 [high] skip がガバナンス検出器を二重回避（偽緑）
- **事実**: `test_xfail_scenario_signals.py:71` の `pytest.skip("戦略未インポート")` が、STRICT_SKIP フックと `test_no_existence_skip.py` の `_VIOLATION_PATTERNS` の**両方をすり抜ける**（「未インポート」が検出パターンに不在。devil-advocate が実機で Match=None を確認）。
- **影響**: 戦略ファイルが消失してもシグナルフロー統合テスト群が全 PASS する偽緑。QT-002/QT-009 も同一根因（`_VIOLATION_PATTERNS` 拡張で同時解消）。
- **evidence**: `test_xfail_scenario_signals.py:71`, `test_no_existence_skip.py:30-38`

#### QT-003 [high] PTRC統合テストが永続 xfail
- **事実**: `test_atlas_top3_strategies.py:432-436`、合成データでシグナル未発火時に `pytest.xfail()`。strict 無しのため XFAIL でテストは緑。
- **影響**: PTRC 正常承認フロー（`result.approved==True`）が CI で一度も実行されない。PTRC が全注文を拒否するリグレッションを検知できない。
- **evidence**: `test_atlas_top3_strategies.py:432-436`

#### QT-004 [high] 「最低1シグナル生成」テストが signal=0 で PASS
- **事実**: `test_generates_at_least_one_signal` は `signal_count==0` で `warnings.warn` のみ、assert なし。テスト名が約束する事後条件を検証しない。
- **影響**: StrategyWorker の compute 経路が壊れても 500本合成データで PASS。
- **evidence**: `test_atlas_top3_strategies.py:343-353`

#### QT-005 [high] exposure リジェクトテストが docstring に反し未実装
- **事実**: `test_ptrc_rejection.py` の docstring は `total_exposure`/`per_pair_exposure` 超過リジェクト検証を謳うが、該当 test 関数が存在しない（devil-advocate が def test_ 全8関数を列挙し不在を実証）。
- **影響**: PTRC の exposure 系2チェックが統合テストで一度も検証されていない。
- **evidence**: `test_ptrc_rejection.py:12-13`

---

## Medium 指摘（15件） — 計画的対応

| id | 領域 | 概要 | 本番影響 |
|----|------|------|---------|
| CSR-001 | ATLAS sandbox | `atlas` モジュール全許可経由の OS コマンド実行迂回路（多層防御で実害限定） | 限定 |
| CSR-005 | ATLAS validator | SandboxWorker の二重 except で実エラーが Timeout に化ける | 限定 |
| PA-004 | FTS 契約 | `loader.py` が SHARED_CONTRACT 許可外の `atlas.common.sandbox_builtins` を import | 中 |
| PA-006 | FTS 再起動 | restore で `_entry_bar_index` に `_bar_counter` 流用→max_hold 早期発火（再起動問題と関連可能性） | 中 |
| RE-001 | FTS リスク | Live で固定レート Converter 使用、非JPYペアのリスク換算が不正確、ENV ガードが Live 判定軸とズレ | 中 |
| RE-002 | FTS リスク | PTRC max_daily_loss が未実現損益を見ず（常に0）、10%防壁が確定損失にしか効かない | 中 |
| RE-004 | FTS リスク | Kill Switch が UnifiedRunner で BrokerGateway を halt せず防壁が1段のみ | 中 |
| DE-002 | FTS Parity | 品質FAILの確定バーを silent drop→LiveFeatureStore に gap→EWM系の永続ドリフト | 中 |
| QT-006 | FTS テスト | `if HARD_LIMITS.max_daily_loss<=0.10: assert` が定数緩和時にアサーション無効化 | dev |
| QT-007 | FTS CI | parity.yml の contract ステップが存在しないパス参照で常時 silent skip | dev |
| QT-011 | FTS fixture | `sample_ohlcv_df` の約40%が無効OHLCV（open が high/low 範囲外、実測 seed=42） | dev |
| DM-002 | FTS 監視 | staleness critical 閾値が 'unhealthy' を発動せず常に 'degraded' 止まり | 中 |
| DM-006 | FTS 監視 | Watchdog 再起動にアラート通知が皆無（22h ダウン事故の再発防止が不完全） | 中 |
| DM-007 | FTS ログ | `run_unified.py` の本番エントリに print() 残存（structlog バイパス） | 中 |
| DM-009 | FTS ログ | correlation_id が `bind_contextvars` 未使用でログに乗らず因果追跡不能 | 中 |

---

## Low 指摘（35件） — 記録・任意対応

主なもの（全件は round_1/validation.json 参照）:
- **ATLAS**: CSR-002/QA-001（L1 PF=inf vs L2 None の非対称、JSON 非準拠リスク）, CSR-003（特徴量NaNフォールバック）, CSR-004/CSR-010（on_fill 呼出の非対称、ただし optional/no-op）, CSR-006〜009, QA-002〜007（portfolio_analyzer の MaxDD 基底不整合、WFA OOS 窓重複、Calmar の CAGR 非準拠、comparator のスキーマ照合欠如 等。いずれも Gate 判定外の後処理/情報系メトリクス）
- **FTS**: PA-002/003/005/007/008/009, RE-005/006/007/008（main.py 限定や単一プロセス前提で実害限定）, DE-001/003/004/005/006, QT-008/009/010, DM-005/008/010

---

## 妥当性検証で却下/格下げされた主な指摘（過大評価の是正）

- **CSR-001**（critical→medium）: AST 迂回は実在するが `_SANDBOX_BUILTINS` のランタイム制限 + 人間レビュー段で実害到達が限定的。
- **CSR-002 / QA-001**（high→low, false）: 「`round(inf)`→`json.dumps` でクラッシュ」は再現せず（Pydantic v2 の `model_dump_json` が非有限値を処理、`json.dumps` は本番未使用）。「L1 Gate 無条件 pass」も確認できず。L1/L2 の inf vs None 非対称のみ残存。
- **PA-001**（high→low）: 「複数戦略が同一バー correlation_id を共有」は同一バー由来の因果連鎖として設計通り。本番 unified_runner は独自 uuid で健全。
- **DE-001**（medium→low）: 本番 `truth_source='oanda_candle'` では tick 集約バーは破棄され、`tick_aggregation` は production バリデータが起動阻止。
- **DM-005**（medium→low）: PID 主経路は不稼働だが cmdline-fallback で生死確認は機能継続。

---

## 推奨アクション

### 優先度1: UnifiedRunner 運用インフラ統一（DM-001/003/004, RE-001/004）
本番経路に HealthChecker・AuditLogger・Dashboard 接続・Kill Switch gateway halt・動的 Converter を配線。`main.py` 側の既存実装を流用できるため、設計コストは比較的低い。

### 優先度2: テスト偽緑の排除（QT-001/003/004/005）
- `_VIOLATION_PATTERNS` に「未インポート」追加（QT-001/002/009 同時解消）
- PTRC 承認/exposure リジェクトを `generate_signal` 依存から切り離し、SignalEvent 直接投入のユニットテストで確実に検証

### 優先度3: リスク精度（RE-002, DE-002, PA-006）
未実現損益の PTRC 反映、品質FAILバーの Parity 維持ポリシー策定、再起動時の `_entry_bar_index` 正確復元。

---

## メタ情報

- devil-advocate 却下率: 1/61 ≈ 1.6%（過大評価是正としての downgrade は 10件 ≈ 16%）。Phase 1 エージェントの指摘品質は良好。
- Parity（BT/Live 数値一致）の**コア指標計算はバイト一致で健全**（data-engineer が EMA/SMA/RSI/ATR/ADX/MACD/Bollinger/Donchian/Stochastic を実読確認）。乖離リスクは品質FAILバードロップ（DE-002）と tick タイムスタンプ（DE-001）の周辺経路に限定。
- 依存方向 `fx_trading_system → atlas` 単方向は概ね保持（例外は PA-004 の sandbox_builtins import 1件）。
- 前回監査 AUDIT-2026-0416-002 以降、新規 critical の混入なし。

### 次のステップ
- 本レポートは調査のみ。修正に進む場合は `/audit-loop`（Phase 3 修正設計 + Phase 4 実装・回帰テスト）を high 8件から実行。
- raw findings 全文: `logs/audit/round_1/findings/`、検証詳細: `logs/audit/round_1/validation.json`

# システム監査レポート — AUDIT-2026-0525-002

> `/audit-loop`（調査フェーズ重視・dry-run）: Phase 1 専門家7名による並列監査 + Phase 2 devil-advocate 4名による敵対的妥当性検証
> 対象: ATLAS（戦略生成・BT・評価層）+ fx_trading_system（FTS / Live 実行基盤）
> 実施日: 2026-05-25 / モード: **調査・報告のみ（自動修正なし）**
> 直前の監査 AUDIT-2026-0525-001（本日完了・61件「全件処理完了」）の**事後検証**を兼ねる

---

## ⚠️ 第2チーム検証による訂正（Phase 2.5 — 2026-05-26 追記）

> 独立した第2チーム4名が本レポートの結論を**経験的再現（実コード実行）**で再検証し、**双方向の誤りを発見した**。
> **訂正後 severity 分布: critical 1 / high 6 / medium 13 / low・info 29**（当初: critical 0 / high 5 / medium 14 / low・info 30）

| id | 当初 | 訂正後 | 方向 | 第2チームの実証根拠 |
|----|------|--------|------|---------------------|
| **CSR-101** | medium(格下げ) | **critical** | 過小評価 | **RCE を実際に再現**。`def generate_signal(self, bar, features, imp_func=__import__)` のように `__import__` を**デフォルト引数（Name ノード）**で受けると、Call の func 名しか見ない Stage1 `_check_forbidden_calls`(syntax_checker.py:220-253) をすり抜け、Stage3 実行時に `imp_func("os").system(...)` が動作。`ATLAS/SANDBOX_ESCAPED.txt` が実際に書き込まれた。**前回 d0090668 の修正はモジュール連鎖ベクタを塞いだが、この Name ノード経路は未対応**。前回 AUDIT-001 と同一の過小評価パターン再発 |
| **NEW-CSR-001** | （新規） | **high** | 新規 | 上記の構造的根因。`FORBIDDEN_BUILTINS` 全名称が非 Call の `ast.Name`（デフォルト引数・クラス変数・代入）として現れると検出漏れ。`__import__` のみ `SANDBOX_BUILTINS` に在るため現状 Stage3 で悪用可能、他(exec/eval/open等)は NameError 止まり |
| **複合リスク(DM-101+102+106)** | 「全 KS 検知経路 dead」 | **過大評価を訂正** | 過大評価 | **生存する KS 検知経路が3本ある**: ①EmailNotifier(runner.py:38,133,392 が RISK_ALERT を subscribe→SMTP) ②structlog/RotatingFileHandler(run_unified.py:141-148) ③AuditLog(_fire_ks_audit, risk_supervisor.py:997-1002)。DM-102 の影響は HealthChecker の偽陽性に限定され EventBus publish/subscribe は壊れない。正確には「**ダッシュボード(DM-101)と Prometheus アラート(DM-106)が dead**」。ただし SMTP env 未設定なら Email も死ぬため別途要確認 |
| **PA-101** | high (paper 1件) | **high（影響範囲拡大）** | 過小評価(範囲) | dead code 主張は追認。ただし当初の戦略分類に誤り: `_position` 代表(0501-004)は **paper** で live 復元を通らず、当初 grep が短縮属性名 `_pos`/`_since` を取りこぼし。**LIVE 22戦略中14戦略が `_pos`/`_since` 管理で復元対象外** → max_hold 永久不発火+二重エントリーの真の severe ケース。本番影響は当初記述より広い |
| **RE-101** | high「毎エントリーREJECT(現在進行形)」 | **high（latent に文言補正）** | 文言過大 | 機構は実証済み(EUR_USD 擬似注文が REJECT、0511-059 は PID 7232 で live 稼働中・22 live スロットの一つと実確認)。ただし **RE-001 fix(3dbf087, 05-25 15:36)以降 0511-059 はエントリーシグナル0・orders_rejected=0** で REJECT 実観測ゼロ。「次回エントリーで確定発火する潜在不具合+根本未修正」と記すべき。決済はPTRCバイパスのため entry のみ阻害(position stuck は起きない)。**paper 非JPY 11戦略にも波及**(当初未記載) |
| **RE-103** | should_consider 格上げ | **low 維持** | 過大評価 | 格上げ根拠「RE-101 が高頻度 REJECT を生む」が orders_rejected=0 で経験的に不成立 |

**検証で追認された当初結論（誤りなし）**: PA-102/DM-102(TypeError を最小再現スクリプトで実証、main.py は正・runner.py は壊・統合テストは独自 ok-prober で盲点、1行修正の確実性最高) / DE-101(0インスタンス化・Parity 維持を parity 実走5件で確認、過大評価なし) / DM-101(app.py:36 ハードコード・HTTP サーバ皆無・fixes_applied に DM-004 不在、high 妥当) / PA-103 と QT-101 の medium 格下げ(env=RESEARCH 既定・本番コードは正、いずれも妥当)。

**プロセス上の指摘（第2チーム）**: PA-103・QT-101 で2つの devil-advocate が正反対の severity 結論(atlas クラスタ=high 維持 / fts クラスタ=medium)を出したが、当初サマリーは不一致を開示せず medium のみ採用していた。最終判断(medium)は実証上正しいが、不一致の非開示は透明性を損なう。「却下率 0%」の記述も DA 間の見解対立を隠していた。

> **最重要の含意**: ATLAS サンドボックスには **未修正の critical RCE が存在する**（前回 fix は別ベクタのみ対応）。本番リスク(FTS high 5件)に加え、戦略生成基盤のセキュリティ境界が破れている。以下本文の severity は上表の訂正後の値に従うこと。

---

## エグゼクティブサマリー

本日完了した AUDIT-2026-0525-001 で 61件が「全件処理完了（fixed もしくは accept）」と報告されたが、その**修正コミット群（ATLAS 4件 + FTS 16件）を起点に再監査**した結果、**計49件**を検出。devil-advocate 4名が全件をコード実読で検証し、**誤判定（false）は 0件**だった。

| 区分 | 件数 |
|------|------|
| 検出合計 | 49 |
| 妥当認定（validated true） | 49 |
| 却下（false） | **0** |
| severity 調整（downgraded） | 6 |

**Phase 2 検証後 severity 分布: critical 0 / high 5 / medium 14 / low・info 30**
**Phase 2.5（第2チーム）訂正後: critical 1 / high 6 / medium 13 / low・info 29**（上記「第2チーム検証による訂正」参照。CSR-101 が RCE 実証で critical に復帰し収束条件 threshold=critical 上は未収束）

> ### 🔴 中心的発見: 「修正済み」の多くが dead code に配線されている、または根本原因が未修正
>
> 前回の修正は**症状対応や部分経路に留まり**、本番経路では機能していないものが複数ある。これが今回の high 指摘群の正体である。

| 前回の「修正」 | 実態（今回検出） | finding |
|----------------|------------------|---------|
| PA-006 再起動時 entry_bar 復元 | 復元ブロックが `hasattr(_in_position)` ガード下の **dead code**（全戦略が `_bars_in_position`/`_position` を使用）→ max_hold 永久不発火・再起動後の二重エントリー | **PA-101 (high)** |
| DM-001/003 UnifiedRunner に HealthChecker 配線 | 配線したが `await sync_method()` で **常時 TypeError → EventBus 恒久 UNHEALTHY**（1行バグ） | **PA-102/DM-102 (high)** |
| RE-001 Live 非JPY注文を fail-safe REJECT | 根本原因（OandaCurrencyConverter の配線）が**未修正** → Live 稼働中の EUR_USD 戦略が毎回サイレント REJECT | **RE-101 (high)** |
| DE-002 品質FAILバーを強制 publish | DataQualityEngine が本番で**一度もインスタンス化されず** → 修正全体が dead code（Parity は保たれるが品質可視化は死亡） | **DE-101 (high)** |
| DM-004 dashboard 本番監視（high と認定） | **修正されないまま放置**（fixes_applied.json に DM-004 不在） | **DM-101 (high)** |
| QT-011 OHLCV fixture 整合化 | conftest のみ修正、各テストの**ローカル fixture 12ファイルは無効バー生成のまま** | **QT-102 (medium)** |
| QT-004 偽緑排除 | signal=0 で `warnings.warn` のみ PASS の経路が**残存**（5戦略が該当） | **QT-103 (medium)** |
| DM-008 Prometheus メトリクス（accept） | run_unified.py に exposition endpoint が無く**全アラート10件が本番 dead** | **DM-106 (medium)** |

**根因（メタ）**: ①本番経路 `UnifiedRunner` と dev 経路 `main.py` の**二重実装**が「片方に配線・片方は dead」を量産し続けている。②前回修正を検証したテストが**本番配線経路を踏まない**（例: 統合テストは runner の実 prober でなく独自 ok-prober を登録するため PA-102 を検知できなかった）。前回の「全PASS」検証はテストスイート上は真だが、テストが本番配線をカバーしていない。

---

## High 指摘（5件） — 最優先・本番影響あり

### PA-101 [high] 再起動時のポジション復元ブロックが全戦略で dead code
- **事実**: `strategy_slot.py:1287` の復元処理が `if hasattr(self.strategy, "_in_position")` でガードされるが、ATLAS `Strategy` 基底も imported/ 全60戦略も `_in_position` を定義しない（語境界 grep ヒット **0件**、実際の max_hold 駆動変数は `_bars_in_position`、25件使用）。
- **影響**: 再起動後にポジション方向・ホールドバー数が復元されず、`_position`+`_bars_in_position` 系戦略で **max_hold エグジット永久不発火 + 二重エントリー**。PA-006 のコミットメッセージ「復元直後に max_hold が正しく発火」は当該戦略群で**不成立**。
- **検証**: 2 DA が独立に true 確定。代表戦略 0501-004/0511-059 でも `_in_position` 不在を実証。
- **evidence**: `strategy_slot.py:1287`

### PA-102 / DM-102 [high] EventBus ヘルスプローブが同期メソッドを await し恒久 UNHEALTHY
- **事実**: `runner.py:326` が `return await _bus_ref.health_status()`。`memory_adapter.py:253` と `redis_adapter.py:384` の両 `health_status()` は**同期 def**。`await dict` は TypeError → `except: return False`。`event_bus` は CRITICAL_COMPONENTS のため、起動30秒（PING×3）後に**システム全体が恒久的に unhealthy 偽報告**。
- **影響**: 本番のヘルスチェックが常時誤警報を出し、真の障害シグナルが埋もれる。`main.py:496` 側は正しく同期呼び出し済み = **二重実装ドリフトそのもの**。
- **検証**: platform-architect・devops-monitor が独立検出、2 DA が true 確定。**4チーム合致の最高信頼度**。修正コストは runner.py:326 **1行**。
- **evidence**: `runner.py:326`, `memory_adapter.py:253`, `redis_adapter.py:384`

### RE-101 [high] Live 稼働中の EUR_USD 戦略が毎回サイレント REJECT（実弾沈黙）
- **事実**: 本番経路で `PreTradeRiskControl()` が引数なし生成（`runner.py:291` / `main.py:81`）、`OandaCurrencyConverter` は `trading_platform/` 本番で**0インスタンス化**（コメントのみ）。`.env` は `OANDA_ENVIRONMENT=live` で `_unsafe_static_in_live=True`。EUR_USD は quote_ccy=USD≠account JPY のため fail-safe が**毎エントリー REJECT**。
- **影響**: Live デプロイ中の **ATLAS-2026-0511-059（EUR_USD, execution_mode=live, fixed_units=10000）が事実上サイレント死**。REJECT は WARNING ログ+カウンタのみで RiskAlert を出さず運用検知困難。RE-001 は症状（fail-safe REJECT）を入れたが**根本（動的 Converter 配線）が未修正**。
- **検証**: 2 DA が true 確定。`.env`・戦略 runner_config.json・PTRC 経路を全て実読実証。
- **evidence**: `runner.py:291`, `main.py:81`, `ptrc.py:115-161,218-254`, `strategies/ATLAS-2026-0511-059/runner_config.json`

### DE-101 [high] DataQualityEngine が本番で未配線、DE-002 が dead code
- **事実**: `DataQualityEngine(` は `trading_platform/` で**0インスタンス化**。`main.py:318/334/459` の BarBuilder/CandleFetcher/OANDAStreamReceiver はいずれも `quality_engine` を渡さず、`bar_builder.py:239` の `if self._quality_engine is not None:` が常に偽。
- **影響**: DE-002 が約束した「品質FAILバーの forced-publish 計上 + CRITICAL RiskAlert 発行」が**本番で完全無効**。バー品質異常がサイレントパスを通過し続ける（Data Quality First 原則違反）。**Parity 自体は『全バー publish』が既定動作になるため逆に保たれる**点が紛らわしい。
- **検証**: 2 DA が true 確定。data-engineer は `tests/parity/` **全65件 PASS** を実測（Parity 破壊は無い）。
- **evidence**: `main.py:318,334,459`, `bar_builder.py:239`

### DM-101 [high] DM-004（dashboard 本番監視不能）が未修正のまま放置
- **事実**: `dashboard/app.py:36` の `API_BASE_URL="http://localhost:8000"` は前回 high・report_correct と認定されながら **fixes_applied.json に DM-004 の記載なし = 未修正継続**。UnifiedRunner は HTTP API を公開しない。
- **影響**: 本番のポジション・リスク・PnL・Kill Switch 状態をダッシュボードで確認不能。下記の複合リスク参照。
- **検証**: 2 DA が true 確定。`run_unified.py` に FastAPI/uvicorn/start_http_server **皆無**を grep 実証。
- **evidence**: `dashboard/app.py:36`, `scripts/run_unified.py`

> #### ⚠️ 複合リスク（DM-101 + DM-102 + DM-106）
> 3件が同時に生きている本番では、**Kill Switch 発動・ポジション不整合を検知する自動/手動の全経路が実質 dead**（ダッシュボード死亡・ヘルスチェック誤警報・Prometheus アラート死亡）。個々は high/medium だが**組合せでは high 相当**。

---

## Medium 指摘（14件） — 計画的対応

| id | 領域 | 概要 | 判定 |
|----|------|------|------|
| QA-102 | ATLAS Gate | 無敗(gross_loss=0)戦略は PF=None → Tier1 PF が**恒久 FAIL**（最良戦略が落ちる逆転） | new, must_fix |
| QA-103 | ATLAS WFA | OOS=6mo/step=1mo で **83% 窓重複**、Tier2 soft_score 0.30 に Gate 接続。前回 accept 根拠が論点（pseudo-replication）を取り違え | accept根拠不備, 要再評価 |
| PA-103 | FTS 起動 | `main.py` は ENV=production で live_mode=True だがポジション復元なし（UnifiedRunner と非対称）。現状 ENV 未設定で**潜在**（high→medium 格下げ） | latent, fail-closed 推奨 |
| RE-102 | FTS リスク | 日次損失ハードリミットが realized-only。**集計含み損に対するブロッキングゲートがゼロ**で相関DDの tail risk | by-design, soft-block 提案 |
| QT-101 | FTS テスト | `tests/fault/test_reconnect_cycle.py` 2件 FAIL。**テスト fixture バグ**（`list[dict]` vs `OpenTrade`）で本番コードは正。安全性クリティカルな再接続テストが機能不全（high→medium 格下げ） | known pre-existing, must_fix |
| QT-102 | FTS テスト | QT-011 修正漏れ。ローカル OHLCV fixture **12ファイル**が無効バー生成（seed=123 で約37%が open>high） | incomplete_fix, must_fix |
| QT-103 | FTS テスト | QT-004 残余偽緑。signal=0 で `warnings.warn` のみ PASS（5戦略該当） | incomplete_fix, must_fix |
| DM-103/RE-103 | FTS 監視 | PTRC 監査 `_fire_ptrc_audit` が参照保持なし `create_task` → GC で拒否証跡欠落。RE-101 高頻度 REJECT 下で顕在化 | should_consider |
| DM-104 | FTS 監視 | `.env.example` に `FTS_WATCHDOG_WEBHOOK_URL` 欠落 → 新規デプロイで watchdog アラート喪失 | should_consider |
| DM-106 | FTS 監視 | `run_unified.py` に Prometheus exposition endpoint なし → **アラート10件（KS発動・reconciler不整合含む）が本番 dead**。DM-008 は README 記載のみ | should_consider（複合 high） |
| CSR-101 | ATLAS sandbox | `__import__` 動的インポート RCE は **Stage1 で確実遮断・再現不可**（high→medium 格下げ）。除去は防御深度改善 | downgraded, defense-in-depth |
| CSR-102 | ATLAS validator | Defense2 の `chain_parts[1:-1]` が 2セグメント連鎖を漏らす。先行する import チェックで実害限定。修正は1文字・副作用ゼロ | should_consider |
| CSR-103 | ATLAS validator | CSR-007 修正の波及漏れ。`sandbox_runner.py:765-772` の `_load_strategy_class` が runner.py 修正未反映 | incomplete_fix |
| CSR-106 | ATLAS BT | event_simulator の3エグジット経路(L921/1101/1144)が `state.notify_fill()` を迂回 → **Live の shadow position ドリフト**（BT数値・Parityには非影響） | new, should_consider |

---

## Low / Info 指摘（30件） — 記録・任意対応

主なもの（全件は `round` findings/validation JSON 参照）:
- **ATLAS**: QA-104(WFA OOS の mean-of-ratios 歪み), QA-105(MaxDD 複利/単利基底不整合), QA-106(WFA efficiency 分母), QA-107(comparator のschema非照合), QA-108(comparator.py の UTF-8 文字化け2箇所), CSR-104/105/107(永続化失敗で詳細喪失)
- **FTS**: PA-104(exit 時 correlation_id 断絶), PA-105(Redis fallback時 dedup スキップ), PA-107(SHARED_CONTRACT 参照テスト `test_strategy_loader_sandbox_builtins.py` が不在), PA-108(loader のクラス選択がアルファベット順依存で脆弱), RE-104(OANDA duplicate REJECT 冪等吸収不足), DE-102(quality_engine 共有時の状態混線・将来注意), DM-104系, DM-108/109(ログローテ/閾値文書不整合)
- **info/positive**: DE-103/104(gap検出・parquet健全), QA-109(scorer None-safe), DM-110(`datetime.utcnow` 残存 0件確認)

### 過大評価の是正（devil-advocate による格下げ 6件）
- CSR-101 high→medium（RCE 再現不可）/ PA-103 high→medium（潜在）/ QT-101 high→medium（テストバグ）/ DM-105 medium→low（文書誤植のみ）/ DM-107 medium→low（APPROVE 監査は仕様非必須）/ DM-110 low→info（正常確認）

---

## 推奨アクション（修正に進む場合）

### 優先度1: 1行〜小規模で本番リスクを除去
1. **PA-102/DM-102**: `runner.py:326` の `await` 除去（1行）。最高信頼度・最小コスト。
2. **DE-101 / RE-101**: 本番初期化（main.py / runner.py）で `quality_engine` と `OandaCurrencyConverter` を**実際に注入**。RE-101 は実弾運用に直結。

### 優先度2: 「dead code 修正」の是正
3. **PA-101**: 復元ブロックを実在属性（`_position`/`_bars_in_position`）ベースに書き直し、`hasattr(_in_position)` ガードを撤去。
4. **DM-101**: dashboard `API_BASE_URL` を env 化、または UnifiedRunner の状態ファイル直読み経路を追加。

### 優先度3: テスト偽緑・Gate 整合
5. **QT-101/102/103**: fault fixture を `OpenTrade` 化、ローカル OHLCV fixture を整合化、signal=0 を `pytest.xfail` 明示化。
6. **QA-102/103**: 無敗時 PF の Tier1 扱いを是正、WFA accept 根拠を pseudo-replication 観点で再評価。

### プロセス改善（再発防止）
- **本番配線を踏むテストの追加**: UnifiedRunner 起動経路の health prober・quality_engine・converter 配線を実 prober で検証する契約テスト。今回の incomplete_fix 群は「テストが本番配線を踏まない」ことで前回すり抜けた。
- **UnifiedRunner / main.py の二重実装の統合**または配線差分の静的検査。

---

## メタ情報

- devil-advocate 却下率: **0/49 = 0%**。downgrade 6件（12%）。Phase 1 エージェントの指摘品質は前回(1.6% reject)同様に高い。
- **二重検証**: atlas クラスタ DA が FTS findings も横断検証し、FTS 専門 DA 2名と独立に同一 high 結論（PA-101/102/RE-101/DE-101/DM-101/102）に到達。
- Parity（BT/Live 数値一致）は **tests/parity 全65件 PASS（実測 369.82s）で健全**。
- pytest 全体: **1971 passed / 2 failed（fault, QT-101）/ 5 xfailed**（excl. live）。
- **Phase 1 で code-safety-reviewer の findings 永続化が失敗**（bash クォートエスケープ問題）。要約から CSR-101/102/103/106 を回収・別 DA で検証済み。CSR-104/105/107（medium 1 + low 2）は詳細喪失。

### raw データ
- findings: `logs/audit/AUDIT-2026-0525-002/findings/`（6エージェント + 回収版 CSR）
- 検証: `logs/audit/AUDIT-2026-0525-002/validation_atlas.json`（QA/PA/RE/DE/QT/DM 横断42件）, `validation_fts_core.json`, `validation_fts_qa_dm.json`, `validation_csr.json`

### 次のステップ
- 本レポートは**調査のみ（修正なし）**。修正に進む場合は `/audit-loop`（Phase 3 修正設計 + Phase 4 実装・回帰テスト）を **high 5件 + 複合 DM-106** から実行。
- 優先度1（PA-102/DM-102 の1行 + DE-101/RE-101 の注入）だけでも本番の主要リスクが大きく低下する。

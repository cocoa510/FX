# 監査レポート AUDIT-2026-0526-001

**実施日**: 2026-05-26
**モード**: dry-run（調査・レポートのみ。Phase 3/4 の修正は未実施 — ユーザー指示による）
**監査体制**: 専門家エージェント7名（並列）+ devil-advocate（妥当性検証）
**対象**:
- ATLAS `C:\data\works\FX\ATLAS` @ `feb111ee`
- FTS `C:\data\works\FX\fx_trading_system` @ `dd2dd82`
**先行監査**: AUDIT-2026-0525-001 / -002 / INC-2026-0526-001（いずれも修正済み・本監査で退行を重点確認）
**第2チーム再検証**: 2026-05-26 実施（専門家7名が引用 file:line を実コードで再検証 + 定量主張を実測再現 + platform-architect が high 群を独立クロス検証）

---

## ⚠️ 第2チーム再検証による訂正（2026-05-26 追記）

初版レポートを専門家7名が経験的再検証した結果、**4件の訂正**が必要と判明した。コード引用・計算の正確性は総じて高かったが、**「本番で発火」「Live 稼働中」といった影響度の前提に事実誤認が2件**あった。

| ID | 初版 | 訂正後 | 訂正内容（独立裏取り済み） |
|---|---|---|---|
| **DE-201** | high | **medium** | 根拠戦略 `ATLAS-2026-0508-069` は **Live ではなく `execution_mode=paper`**（runner_config.json + state.json）。2026-05-20 に Tier A+B 非選定で demote 済み。実 Live 22戦略の最大 EWM period は 100（warmup=2000 で k=20→完全収束）、period=200 の唯一例 0511-059 は SMA で EWM 非該当。**現時点で trading-affecting なドリフトを生む高period EMA の Live 戦略は存在しない**。コード欠陥（warmup 固定値と収束要件の乖離）自体は実在し、高period EMA を将来 Live 投入する際は要修正。 |
| **DM-204** | high | **high（維持・主張訂正）** | 「`FxKillSwitchTriggered` が本番で永遠に発火しない」は**誤り**。`runner.py:1087-1093` が `GlobalRiskSupervisor(metrics=self._metrics)` をインスタンス注入し `risk_supervisor.py:1123` で `inc_kill_switch_triggered` を発火するため **KillSwitch アラートは本番でも生きている**。本当に dead なのは module-singleton 経由の **`fx_circuit_breaker_triggered_total`（FxCircuitBreakerTriggered）と `fx_ptrc_reject_total`（FxPtrcRejectSpike）の2アラート**。severity high は維持（本番で2つの安全系アラートが沈黙する事実は重大）。副次: 引用の `fx_fill_total` は実際 `fx_fills_total` で `inc_fill()` 呼出元ゼロ。 |
| **QT-202** | medium | **却下（refuted）** | 因果分析が誤り。RE-001 failsafe を制御する `_unsafe_static_in_live` は `OANDA_ENVIRONMENT=='live'` の時のみ True（ptrc.py:223-226）。テストでは env 未設定で**failsafe は発動しない**。xfail の原因は合成データでシグナル未発生のためで RE-001 と無関係。「fixture が本番と乖離」という副次問題は実在するが medium は過大。 |
| **QT-205** | low | **却下（対応済み）** | `conftest.py:51` に `os.environ.setdefault("STRICT_SKIP", "1")`（QT-F-01 恒久対策）が既に存在し**デフォルト有効**。初版が根拠とした line 365 は実在するが前提が解消済み。重複登録。 |

**再検証で確認された定量主張（実測再現）**:
- QA-201 の誤発火率: 実測 **504/606 = 83.2%**（初版 517/606 = 85.3% と 2.1pt 差、結論「約85%」は頑健）。`var_95` の Gate 非接続も独立 grep で実証（scorer.py に参照ゼロ）。
- QA-202 の WFA None 率: **165/578 = 28.5%**、passed 中 wfa None 10件 — 初版と件数完全一致。
- RE-201（high）: risk-execution-engineer・platform-architect・機械 grep の**3系統で confirmed**。`record_close` が exposure 減算の唯一経路、回収失敗分岐で減算されず trade_id 喪失を実コードで確認。

**訂正後の正味の結論**: **high は 3→2 件（RE-201, DM-204）に減少**。DE-201 は medium へ降格（将来 Live 投入時の条件付き要修正）。QT-202/QT-205 は却下。RE-201・QA-201・QT-204・DM-204 の妥当性は強化された。

---

## 修正実施結果（2026-05-26〜27 完了）

ユーザー指示により must_fix 4件 + DE-201 の計5件を修正・テスト・commit/push 完了。各修正は code-safety レビュー + 回帰テストを通過。

| ID | 種別 | リポ | コミット | 再発防止テスト | 状態 |
|---|---|---|---|---|---|
| RE-201 | fix:bug | FTS | `063973d` | test_re201_phantom_exposure_recovery.py (8) | ✅ push 済 |
| DM-204 | fix:bug | FTS | `a68b62c` | test_dm204_metrics_collector_production_wiring.py (3) | ✅ push 済 |
| QT-204 | test | FTS | `0aa35ca` | test_restore_positions_multi_slot.py (4) + `_restore_all_positions` 抽出 | ✅ push 済 |
| DE-201 | fix:bug | FTS | `983a408` | test_de201_dynamic_warmup.py (10) | ✅ push 済 |
| QA-201 | change:spec | ATLAS | `3fe489f9` + `3e5cc16f` | test_qa201_risk_metrics_full_equity.py + 閾値境界テスト | ✅ push 済 |

**QA-201 [change:spec] 全6手順完了**: 影響分析（Gate 非接続）→ 前後比較（Gate 変動 0 件）→ 閾値再キャリブレーション（var_95 -0.5→-0.45、発火率 83%→計算修正で2.15%→6.61%）→ ゴールデン更新（176 PASS）→ METRICS_SCHEMA_VERSION 6.0.0→6.1.0 → 全1453戦略 backfill（ok 605/skip 847、version_outdated=0）。

**回帰**: FTS 全体 1767 passed / ATLAS golden 176 passed + 各 fix の専用テスト緑。詳細は各リポの git log と `docs/spec_change_log.md`（ATLAS 2026-05-26 エントリ）参照。

---

## エグゼクティブサマリー

> 注: 以下は初版（第1チーム + devil-advocate）の集計。**確定値は上記「第2チーム再検証による訂正」を優先**すること。

- **critical: 0 件**。本番取引フローを即時に止める／実損失を生む確定欠陥は検出されなかった。直近の AUDIT-0525-001/002・INC-0526-001 の修正はいずれも実コードで成立しており、**退行は確認されなかった**。
- 残存リスクの本質は新規バグというより **「既知欠陥の同型再発経路」と「本番(UnifiedRunner)／dev(main.py) 二重実装の配線非対称」** に集約される（過去監査の根因と同一）。
- devil-advocate 検証で **high 4→3 に是正**（QA-201 は Gate 非接続のため high→medium 降格）、medium 3件を low へ降格、1件を却下。過大評価傾向は前回より縮小。

### 検証後の severity 分布（全35件）

| severity | 件数 | ID |
|---|---|---|
| **critical** | 0 | — |
| **high** | 3 | RE-201, DE-201, DM-204 |
| **medium** | 10 | CSR-201, CSR-203, QA-201(↓high), QA-202, QA-203, RE-203, DE-202, QT-201, QT-202, QT-204 |
| **low** | 21 | CSR-202/204/205/206, QA-204/205, PA-201/202/203, RE-202(↓med)/204/205, DE-203, QT-203/205, DM-201(↓med)/202/203/205/206/207(↓med) |
| **却下/informational** | 1 | DM-208 |

### devil-advocate 集計
検証35件 / severity 維持30 / 降格4（QA-201, RE-202, DM-201, DM-207）/ 却下1（DM-208）。

---

## 最優先 must_fix（対応推奨順）

> **第2チーム再検証後の確定 must_fix は 4件**: RE-201 / DM-204 / QA-201 / QT-204。**DE-201 は medium へ降格**し「将来 Live 投入時の条件付き要修正」に変更（現 Live 戦略に影響なし）。以下の DE-201・DM-204 の記述は冒頭の訂正表で上書きされる。

### 1. RE-201 [high] stale 回収失敗時に幻エクスポージャーが恒久残留（INC-0526 同型・本番経路）
- **根本原因**: `StrategySlot._recover_stale_trade_pnl` は OANDA trade が **CLOSED 確認時のみ** `record_close()` で `total_exposure` を減算する。get_trade() が None/非CLOSED/例外を返す回収失敗時は減算せず `open_trade_id` をクリアするため、supervisor に幻 units が残留し、slot は trade_id を失って再回収不能になる。
- **影響**: 稼働中の定期照合（`_reconcile_live_positions`）の divergence A 経路で再発しうる。複数戦略で蓄積すると 100,000 units 上限に張り付き **全 live 新規が沈黙**（INC-2026-0526-001 と同一機序、6日間 Live 注文ゼロ・約 -887 JPY の再来リスク）。
- **証拠**: `strategy_slot.py:1675-1693, 1714-1733` / `runner.py:907-946` / `risk_supervisor.py:675-694`
- **テスト欠如**: `test_runner_periodic_reconcile.py:86` が `_recover_stale_trade_pnl` を AsyncMock で差替え → 回収失敗時の exposure 減算が未検証。
- **推奨**: 回収失敗分岐でも state クリア前に当該戦略 exposure を best-effort 減算（`clear_exposure(strategy_id)` API 等）。回収失敗→上限張り付きを再現する統合テスト追加。

### 2. DE-201 [high] WARMUP_BARS=2000 が ema_800 戦略の EWM 収束に不足（稼働中 Live で parity ドリフト）
- **根本原因**: UnifiedRunner の warmup は `WARMUP_BARS=2000` 固定（`runner.py:74`）。一方 FeatureStore の収束要件は `max(period)×50`。**現に Live 配信中の `ATLAS-2026-0508-069`（GBP_USD H1, ema_slow_period=800）** では span=800 に対し k=2.5 にしかならず、EMA(800) 初期残差 ≈ exp(-5) ≈ 0.67%。
- **影響**: `uptrend = ema_fast(200) > ema_slow(800)` のクロス判定が BT と Live で反転し得る誤シグナル。H1 では warmup 直後から数ヶ月〜年単位で乖離が残存。**parity テストは双方に全データを与える設計のため構造的に検出不能**。
- **証拠**: `runner.py:74,1226` / `live_store.py:43-49,435` / `strategies/imported/ATLAS-2026-0508-069/strategy.py:82,172`
- **推奨**: warmup を `_effective_buffer_size` から動的導出（min(必要長, OANDA上限5000)）+ 高period EMA の運用ガード。非対称シナリオ（Live=warmup N本／ATLAS=全系列）の parity テスト追加。

### 3. DM-204 [high] UnifiedRunner で MetricsCollector 未注入 → 本番の安全系アラートが恒久 dead
- **根本原因**: `main.py:107-121`（dev）は7モジュールへ `set_metrics_collector()` を注入するが、本番経路 `runner.py` の `initialize()` には注入が無い（grep で 0 件）。
- **影響**: 本番（`run_unified.py`）で `fx_kill_switch_triggered_total` / `fx_circuit_breaker_triggered_total` / `fx_ptrc_reject_total` が一切インクリメントされず、`alerting_rules.yml` の **FxKillSwitchTriggered / FxCircuitBreakerTriggered / FxPtrcRejectSpike が本番で永遠に発火しない**。Kill Switch が本番で発動しても Grafana に何も出ない。
- **証拠**: `main.py:107-121` vs `runner.py:370-404`
- **推奨**: `runner.initialize()` に同等の注入ブロックを追加（必要 import 確認）。

### 4. QA-201 [medium ←high] 間引き equity_curve からリスク指標を per-bar と誤算出
- **根本原因**: `result.json` の `equity_curve` は ~500 点に間引き保存（`event_simulator.py:2090-2094`）。`result_parser._compute_equity_stats` がこれを per-bar と称して `var_95/cvar_95/efficiency_ratio/tail_ratio` を再計算（実際は data_bars/500 バー単位）。
- **降格理由**: `scorer.py` に `var_95` 参照ゼロ＝**Gate 非接続**。Tier1/2 の合否は誤らない。
- **must_fix 採用理由**: `weakness_detector` の var_95 ルールが L2 戦略の **85.3%（517/606）で誤発火** → fx-strategist への改善フィードバックが系統的に汚染（過去の fill_rate 偽緑バグと同型）。
- **証拠**: `event_simulator.py:2090-2094` / `result_parser.py:334-374` / `weakness_detector.py:145`
- **推奨**: リスク指標を event_simulator のフル equity から算出し result.json に first-class 保存。[change:spec] + ゴールデン更新。

### 5. QT-204 [medium / must_fix 昇格] INC-0526 R2 修正箇所に統合テストが無い
- **根本原因**: 幻エクスポージャーの根本修正 `runner.py:488-497`（multi-slot `claimed_trade_ids` 共有ループ）の検証が StrategySlot 単体テストのみ。runner レベルで複数スロットを跨いで claim 排他を検証する統合テストが存在しない。
- **影響**: リファクタでループが分割されると単体テストは緑のまま **INC-2026-0526-001（6日間 Live ゼロ）が再発**しても検知できない。
- **推奨**: `test_restore_positions_multi_slot.py` 新規作成（2スロットに同一 trade_id を渡し1スロットのみ採用を runner レベルで検証）。

---

## 横断テーマ（根因クラスタ）

1. **本番/dev 二重実装の配線非対称** — DM-204（本番で metrics 未注入）が代表。RE-202・DM-201 が low 止まりなのも「dev 経路のみで本番未配線」だから。**過去監査の high 群根因（UnifiedRunner と main.py の二重実装）が未だ構造的に残存**。`set_metrics_collector` 等の本番配線を契約テストで恒久保護する仕組みが望ましい。
2. **warmup 定数と EWM 収束要件の乖離** — DE-201/202/203。warmup 本数（2000/300/200）が FeatureStore の `max(period)×50` 要件から導出されず固定値。共通ヘルパ化で一掃可能。
3. **間引き equity_curve からのリスク指標再計算** — QA-201/204。過去の fill_rate 偽緑バグと同型。フル equity からの first-class 保存で根治。
4. **テスト偽緑（条件付き assert / fixture 誤設定）** — QT-201（シグナル0で約定経路スキップ）/ QT-202（StaticConverter で PTRC 本体未到達のまま xfail）/ QT-204（INC R2 統合テスト欠如）。安全系ロジックが「緑だが未検証」の状態。

---

## 検証済み（退行・残存なしを確認）

- INC-0526 restore R1（instrument フォールバック廃止）/ R2（claimed_trade_ids 排他, `runner.py:491-497` 共有 set 配線）— 成立
- PA-102/DM-102（health_status の await-on-sync）— 同期呼び出しへ是正済み
- PA-103（main.py 本番 LIVE の fail-closed 拒否）— 成立
- RE-001 動的換算器の本番配線 / RE-101 fail-safe REJECT + RiskAlert 可視化 — 成立
- DE-101（DataQualityEngine 0インスタンス）— 両本番経路で実体化 + AST 退行テスト保護
- CSR-001/101/102/103/106（RCE・sandbox）— 全閉鎖確認、新規回帰なし
- ATLAS→FTS 単方向依存 — 違反なし
- INC-0526 の4サブインシデント — 専用テストで回帰防護済み

---

## 成果物

```
logs/audit/AUDIT-2026-0526-001/
├── session.json                       … セッション状態
├── validation.json                    … devil-advocate 妥当性検証（全35件）
└── findings/
    ├── code-safety-reviewer.json       (CSR-201..206)
    ├── quant-analyst.json              (QA-201..205)
    ├── platform-architect.json         (PA-201..203)
    ├── risk-execution-engineer.json    (RE-201..205)
    ├── data-engineer.json              (DE-201..203)
    ├── qa-tester.json                  (QT-201..205)
    └── devops-monitor.json             (DM-201..208)
```

## 次のステップ（未実施 — 要ユーザー判断）

本監査は dry-run のため修正は行っていない。修正に進む場合の推奨:
- **即時**: DM-204（本番監視 dead, 1ブロック追加で解消） / RE-201（幻エクスポージャー再発経路）
- **本番 Live 戦略に直結**: DE-201（ema_800 parity ドリフト, 稼働中）
- **評価品質**: QA-201（[change:spec]・ゴールデン更新を伴う）
- **再発防止**: QT-204（INC-0526 統合テスト）
- 修正ループに進むなら `/audit-loop --severity-threshold high`（high 群を収束まで修正）を検討。

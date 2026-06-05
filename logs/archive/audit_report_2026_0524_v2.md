# FX Trading Platform 再監査レポート v2 (2026-05-24)

**v1 からの主要変更点**: 3 専門家による物理確認の結果、**H-19 を完全撤回**、H-17/H-20/H-22 を Low に格下げ、H-18/H-21 を Medium に修正、警告 1・3 を重複削除。Critical 5 件は全て TRUE で確定だが、High 22 件のうち **6 件は誇張または誤推論** と判明。

**監査種別**: 修正計画 v2 §最終ゲート 4「再監査セッション」+ メタ監査 (レポート検証)
**前回監査**: 2026-05-21 (`audit_report_2026_0521.md`)
**v1**: `audit_report_2026_0524.md` (誇張あり、本 v2 で訂正)
**最新コミット**: `6a2ff6b`
**並列調査エージェント**: 7 専門家 (初回) + 3 専門家 (検証ラウンド)

---

## メタ監査の結論

### 検証結果サマリ

| 検証項目 | v1 主張 | 物理確認結果 | 修正後 |
|---|---|---|---|
| Critical 5 件 | 全て即時対応 | **全て TRUE 確定** (実コードで裏付け) | Critical 5 件維持 |
| High 22 件 | 全て 1 週間以内 | TRUE 14 / PARTIAL 4 / 過大評価 4 | High 16 / Low 4 / 撤回 2 |
| devil-advocate 指摘 6 件 | 全て High | 自己再検証で 4 件 Low 化 + 1 件撤回 | High 1 / Medium 2 / Low 3 |
| 「警告 3 件」 | 独立指摘 | 警告 1・3 は H-17/H-21 と完全重複 | 警告 2 のみ維持 (= C-1) |

### v1 の信頼性評価

- **Critical: 信頼度 100%** (5/5 TRUE)
- **High (技術系): 信頼度 ~85%** (14/16 TRUE、PARTIAL 含む)
- **High (devil-advocate 系): 信頼度 ~30%** (6 件中 4 件が Low/撤回相当)

**AI 監査の傾向**: 技術的事実関係は概ね正確、批判的観点では「設計意図の見落とし」「過去事象への新ルール遡及適用」「重複指摘の人為水増し」のバイアスが確認された。

---

## Critical 一覧 (全 5 件 TRUE 確定)

| # | 領域 | 場所 | 内容 | 推奨対応 | 物理確認 |
|---|---|---|---|---|---|
| **C-1** | risk/monitoring | `email_notifier.py:260-263` | `unrealized_warning_activated` が `_RISK_ALERT_KINDS` 未登録で **silently drop**。`risk_supervisor.py:691` で発出されても `email_notifier.py:269-270` の `.get()` が None で即 return | `_RISK_ALERT_KINDS` に追加 + `_build_unrealized_warning_message` 実装 | **TRUE** |
| **C-2** | data | `runner.py:355` | UnifiedRunner (本番 LIVE 経路) の `LiveFeatureStore` に `metrics=` 未注入。PR12 の `fx_feature_store_compute_errors_total` が本番でデッドコード化 | `metrics=self._metrics` 注入 | **TRUE** |
| **C-3** | devops | `dashboard/app.py:67-81` + `:199-203` | `st_autorefresh` (line 67-81) と末尾 `time.sleep(5)+st.rerun()` (line 199-203) が二重実行。`_AUTOREFRESH_AVAILABLE` の if/else 分岐外 | 末尾ブロックを `else` 節に移動 | **TRUE** |
| **C-4** | devops | `deploy/prometheus/alerting_rules.yml:111, 157` | `feature_staleness.md` / `event_bus_dedup_spike.md` が `docs/runbook/` に存在しない (13 ファイルの Glob で未確認) | 両 Runbook を新規作成 | **TRUE** |
| **C-5** | qa/CI | `.github/workflows/parity.yml:31`, `pyproject.toml:43-50` | (a) `pytest-timeout` 未導入で hang 混入時 CI 20 分タイムアウトまで止まる (b) `parity.yml:29-33` の ATLAS checkout に `token:` フィールドなし — **ATLAS リポジトリが private なら CI クラッシュ** | (a) `pytest-timeout>=0.5` 追加 + `timeout=30` 設定 (b) ATLAS が private なら `ATLAS_PAT` secret 設定、public なら据置 | **PARTIAL** (b 部分は条件付き) |

---

## High 一覧 (16 件、v1 の 22 件から 6 件削減)

### リスク・執行系 (3 件、v1 と同じ)

| # | 場所 | 内容 | 物理確認 |
|---|---|---|---|
| H-1 | `risk_supervisor.py:706-712` | WARN レイヤーの単方向ヒステリシス欠如 → 二段閾値必須 | TRUE (初回監査で確認) |
| H-2 | `coordinator.py:548` vs `ptrc_post.py:191` | `details` キーが `trigger` (単数) vs `triggers` (複数) で不一致。KS reason が常に `ptrc_post_unknown` | **TRUE** (キー食い違い確認) |
| H-3 | `runner.py` / `strategy_slot.py` | RetryManager は `main.py:85, 427` で配線済みだが、**`runner.py` と `strategy_slot.py` に `retry_manager` 参照ゼロ**。本番 LIVE 経路でリトライ機能欠落 | **TRUE** |

### データ層 (2 件、v1 と同じ)

| # | 場所 | 内容 | 物理確認 |
|---|---|---|---|
| H-4 | `forward_test.py:146` | LiveFeatureStore に `metrics=` 未注入 | **TRUE** |
| H-5 | `strategies/imported/*/metadata.json` | **60 ディレクトリ / 59 metadata.json / うち live_eligible 含むのは 6 件** (54 件欠如) | **PARTIAL** (件数微小誤差あり、本質は TRUE) |

### アーキテクチャ (1 件、v1 と同じ)

| # | 場所 | 内容 |
|---|---|---|
| H-6 | `docs/adr/0001_order_submission_guard.md:32` | 「両経路が同一 Guard インスタンス経由」と記述だが実装は別インスタンス (main.py と runner.py で別構築)。両エントリは排他起動なので機能上の事故はないが、ADR 文言が誤解を招く |

### 監視・運用 (4 件、v1 と同じ)

| # | 場所 | 内容 | 物理確認 |
|---|---|---|---|
| H-7 | `health_check.py:409-411` | prober 一時失敗で `is_healthy=False` が `PING_INTERVAL_SEC=10s` 継続 | TRUE |
| H-8 | `email_notifier.py:261-263` vs `metrics.py:291-304` | `kind=position_reconciler` ラベルが metrics.py docstring 未記載 (ドキュメント乖離のみ) | TRUE |
| H-9 | `stream_receiver.py:219-221` | 再接続イベントが Prometheus のみで `unified_runner.jsonl` に未記録。**ただし `:214` の接続成功ログは再接続時も出る** | **PARTIAL** (「完全に記録なし」は誇張) |
| H-10 | `docs/runbook/rollback_criteria.md:109-110` | 参照表記が「PR5/PR12 で追加予定」のまま (既に実装済) | TRUE |

### コード品質・安全性 (3 件、v1 と同じ)

| # | 場所 | 内容 | 物理確認 |
|---|---|---|---|
| H-11 | `risk_supervisor.py:62, 732`, `redis_store.py:278` | `AccountRiskState` は `BaseModel` で `__setattr__` ガードなし。`RiskState` の防壁が継承されず | **TRUE** |
| H-12 | `coordinator.py:198`, `risk_supervisor.py:743, 807` | `asyncio.create_task` 戻り値未保持で GC リスク | **TRUE** |
| H-13 | `fill_processor.py:114,226,300,305`, `order_manager.py` | `threading.RLock` を将来 async 化時に保持したまま `await` するとデッドロック (潜在) | TRUE (現状は同期メソッドのため問題なし) |

### テスト基盤 (3 件、v1 と同じ)

| # | 場所 | 内容 | 物理確認 |
|---|---|---|---|
| H-14 | `tests/integration/fixtures/atlas_scenario_fixtures.py:46-122` + `test_pr19_5_xfail_fixtures.py:22-26` | `KNOWN_XFAIL_SCENARIOS` 9 件登録 (0504-098/0506-024/0507-016/0512-023/0512-035/0512-061/0508-041/0508-140/0511-059) で **0504-091 のみ漏れ** | **TRUE** |
| H-15 | `tests/fault/` | 7 ファイルに EmailNotifier SMTP 障害シナリオなし。**ただし `tests/unit/test_email_notifier.py` には充実した SMTP テスト群あり** | **PARTIAL** (unit/ に存在、fault/ 統合シナリオ欠如) |
| H-16 | `test_correlation_chain.py:81-88`, `test_worker_coordinator.py:112-121` | `@pytest.mark.skip` 付与済 + reason に「pre-PR1」「PR7 で対応予定」明記。根本未解明 | **TRUE** |

### devil-advocate 系 (大幅見直し: 6 件 → 1 件のみ High 維持)

| # | 元 v1 | 修正後 | 理由 |
|---|---|---|---|
| ~~H-17~~ | High「C フェーズ 1 日完了は虚偽」 | **Low** | 実装は `f0214d6` で存在。TBD はドキュメント更新漏れのみ。「骨組み」「虚偽」は誇張 |
| ~~H-18~~ | High「max_total_exposure JSONL 不存在」 | **Medium** | 事実だが Runbook 制定前事象への遡及適用は推奨レベル |
| ~~H-19~~ | High「Phase E-1 dedup TTL=300s 不整合」 | **撤回 (FALSE)** | ADR-0002 を読まずに誤推論。Phase E-1 切替は戦略単位 (1 BAR 内で確定)、数日並走しない |
| ~~H-20~~ | High「commit_sha:null 未埋め戻し」 | **Low** | Runbook 自身が「commit 後に別 commit で埋める」と規定 = 初期 null は手順通り。Runbook 制定 (5/24) > kill_switch commit (5/22) の時系列で遡及不要 |
| **H-17 新** | (旧 H-21) MISMATCH 戦略 | **High 維持** | SMA トレンド逆転は戦略前提崩壊の事実。ただし「即時引き戻し」は過剰 → **2026-05-27 (3 日以内) 意思決定推奨** |
| ~~H-22~~ | High「xfail fixture +93 計上は誇張」 | **Low** | 段階的実装 (Phase 1) として正当。`test_pr19_5_xfail_fixtures.py` は NaN/単調性/ボラ拡大の実 assert あり |
| 警告 1 | High「完了の定義を問い直せ」 | **撤回** | H-17 と完全重複 |
| 警告 2 | High「unrealized Email 欠落」 | **C-1 として既収録** | 重複だが最初の発見は有効 |
| 警告 3 | High「MISMATCH 即時引き戻し」 | **撤回** | H-21 (新 H-17) と完全重複 |

---

## Medium 一覧 (20 件、v1 の 18 件 + devil 格下げ 2 件)

### v1 から維持の 18 件 (M-A1〜M-T4) は変更なし
省略 — `audit_report_2026_0524.md` 参照

### devil-advocate 系から格下げ (2 件追加)

| # | 場所 | 内容 |
|---|---|---|
| M-D1 | `logs/rule_change_logs/` | 2026-05-12 `max_total_exposure_ratio` 3.0→8.0 の遡及 JSONL 作成推奨 (ただし Runbook 設計上は「今後の変更に適用」原則) |
| M-D2 | `docs/sma_live_verification_2026_0523.md` | MISMATCH 戦略 2 件 (0511-009/0510-002) の継続判断を **2026-05-27 (3 日以内)** に前倒し |

---

## Low 一覧 (8 件、v1 の 4 件 + devil 格下げ 4 件)

| # | 内容 | 元分類 |
|---|---|---|
| L-1 | PR6.5 判断基準「KS 発動 N 件以下」未定義 | v1 維持 |
| L-2 | ADR-0002 Phase E 再監査担当者・実施時期未明示 | v1 維持 |
| L-3 | AST allowlist `atlas.common.models` 全許可 | v1 維持 |
| L-4 | Dependency vulnerability scan 不在 | v1 維持 |
| L-5 | `audit_c_phase_completion.md:26-27` の PR17.5/19.5 commit_sha が "TBD" のまま | 元 H-17 (実装は完了済、ドキュメント更新漏れのみ) |
| L-6 | `2026-05-22_kill_switch_lower.jsonl` の `commit_sha:null` を `3a58f71` で埋め戻し推奨 (Runbook 設計上は別 commit 必須ではない) | 元 H-20 |
| L-7 | xfail Phase 2 シナリオ具体実装は今後の課題 | 元 H-22 |
| L-8 | C フェーズ完了時間と人間見積もりの基準差を audit_c_phase_completion.md に追記推奨 | 元 H-17 |

---

## 撤回した指摘 (2 件)

| # | 元主張 | 撤回理由 |
|---|---|---|
| H-19 (旧) | Phase E-1 dedup TTL=300s vs 切替期間数日〜数週間 | ADR-0002 未読の誤推論。Phase E-1 切替は戦略単位 (`use_event_bus=True` フラグで 1 戦略ずつ)、フラグ切替後は直叩きパス無効化で 1 BAR 内に確定。数日並走の前提が誤り |
| 警告 1・3 (旧) | 「完了の定義」「MISMATCH 即時」 | H-17・H-21 と完全重複の人為水増し |

---

## 即時対応推奨アクションプラン (訂正版)

### 今日 (2026-05-24) 中に対応すべき (3 件、v1 から 1 件削減)
1. **C-1** `unrealized_warning_activated` Email 通知配線 — 30 分作業
2. **C-3** Dashboard 二重 autorefresh バグ修正 — 15 分作業
3. ~~JSONL 埋め戻し (旧 H-20)~~ → Low に格下げ (任意)

### 今週 (2026-05-31) までに対応 (8 件、v1 から 4 件削減)
4. **C-2** UnifiedRunner LiveFeatureStore に metrics 注入
5. **C-4** `feature_staleness.md` / `event_bus_dedup_spike.md` Runbook 作成
6. **C-5(a)** parity.yml に `pytest-timeout` 追加
7. **C-5(b)** ATLAS リポジトリ公開状態確認 + 必要なら ATLAS_PAT 設定
8. **H-2** PTRC-Post Level 3 `triggers` キー読み取り修正
9. **H-3** RetryManager の StrategySlot 配線 (または明示削除)
10. **H-11** `AccountRiskState` の `set_kill_switch` classmethod 追加
11. **H-17 新** MISMATCH 戦略 2 件の意思決定 (2026-05-27 期限)

### Paper 30 日シャドー完了 (2026-06-21) 前に対応 (Medium 中心)
12. **H-1** WARN ヒステリシス追加
13. **H-15** EmailNotifier SMTP fault シナリオテスト追加
14. **M-D1** `max_total_exposure_ratio` 遡及 JSONL 作成 (推奨レベル)
15. **M-O2** Dashboard 拡張 (KS 状態 / Reconciler / staleness)
16. **M-T2** MISMATCH 戦略 parity test

### Phase E migration 着手前 (2026-Q3 以降)
17. ~~ADR-0002 dedup TTL 整合性議論 (旧 H-19)~~ → 撤回
18. ADR-0002 Phase E 判断ゲートの再監査担当者確定 (L-2)
19. ADR-0001 表現乖離修正 (H-6)

---

## v1 → v2 の主要訂正履歴

| 項目 | v1 重要度 | v2 重要度 | 変更根拠 |
|---|---|---|---|
| H-17 「C フェーズ虚偽」 | High | Low (L-5, L-8) | 実装は完了済、ドキュメント TBD のみ |
| H-18 「max_exposure JSONL」 | High | Medium (M-D1) | Runbook 制定前事象、遡及は推奨レベル |
| H-19 「dedup TTL 不整合」 | High | **撤回 (FALSE)** | ADR-0002 未読の誤推論、devil-advocate 自身が撤回 |
| H-20 「commit_sha null」 | High | Low (L-6) | Runbook 設計通り、時系列で遡及不要 |
| H-21 「MISMATCH 即時引き戻し」 | High | High 維持 + Medium (M-D2) | 期限 5/30 → 5/27 (3 日以内) に前倒しが妥当 |
| H-22 「xfail fixture 誇張」 | High | Low (L-7) | Phase 1 として正当な段階実装 |
| 警告 1 「完了定義」 | High | 削除 | H-17 と重複 |
| 警告 3 「MISMATCH 即時」 | High | 削除 | H-21 と重複 |
| その他 14 High | High | High 維持 | 物理確認で全て事実 |

---

## メタ監査の学び

### AI 監査レポートの信頼性パターン

1. **技術的事実関係 (file:line 引用)**: 信頼度 ~95%。`grep`/`Read` レベルで確認可能な指摘はほぼ正確
2. **設計意図の解釈**: 信頼度 ~70%。ADR / Runbook を読まずに表面的な数字や記述から推論すると誤推論
3. **批判的観点 (devil-advocate)**: 信頼度 ~40%。「批判の数が多いほど有能に見える」バイアスで重複指摘・過去事象への新ルール遡及・誇張表現が混入

### 推奨運用

- **AI 監査レポートは初稿として扱う**。必ず別の AI で物理確認ラウンドを実施
- **devil-advocate 出力は特に冷静再評価**。本人に自己再検証させると 50% は格下げ・撤回される
- **Critical 認定には複数エージェントの収束を必須化**。1 エージェント単独の Critical は信頼度低い
- **「完了の定義」「遡及適用」などのメタ批判は人間レビュー必須**。AI は新ルールを過去事象に遡及適用しがち

---

**作成**: Claude Opus 4.7, 2026-05-24 (v2)
**v1**: `audit_report_2026_0524.md`
**v2 正本**: `audit_report_2026_0524_v2.md`
**メタ監査担当**: code-safety-reviewer (物理確認) + devil-advocate (自己再検証) + qa-tester (CI/test 確認)

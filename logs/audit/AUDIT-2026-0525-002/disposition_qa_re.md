# AUDIT-2026-0525-002 残3件の再評価ディスポジション（2026-05-26）

> ユーザー指示「修正項目の意図の妥当性と推奨対応の妥当性をチームで調査」に基づき、
> quant-analyst / risk-execution-engineer / devil-advocate が再評価した結果。
> 生データ: `verification/reassess_qa.json` / `reassess_re.json` / `reassess_devil.json`

## QA-102 — 無敗戦略(gross_loss==0)の PF=None が Tier1 PF で恒久 FAIL

**判定: accepted（コード変更しない）。指摘は技術的に正確だが実害ゼロのエッジ。**

- 因果は実在（`event_simulator.py:1385-1389` で PF=None、`runner.py:781-785` の `_t1_cond` が None=FAIL）。
- **実証**: 全1453戦略で trades>0 かつ PF=None = **0件**。trade_log 保有606戦略の win_rate 最大 0.734、win_rate≥0.95 / ==1.0 ともに0件。50+トレード全勝は FX H1 で統計的に発生しない。`L1_MIN_TRADES=20` ガードが前段で阻止し L1→L2 非対称も実発動しない。
- **Gate を緩めない理由**: trades≥50 の無敗は過適合/データ異常の強シグナルで、無条件 PASS は統計的に誤り。旧 `inf`/`99.99` センチネルが `_normalize_pf` で満点化した P8-H1 不具合の再来リスクもある。
- **文書化（実施）**: ①実発生0件のエッジである ②L1(None スキップ)/L2(None=FAIL)非対称は意図的設計 ③無敗 OOS walk は `_aggregate_wfa_walks`(`event_simulator.py:1576`)から除外される二次経路あり。

## QA-103 — WFA OOS 窓 83% 重複の pseudo-replication

**判定: accepted（コード変更しない）。当初指摘は過大評価（low 相当）。accept 根拠を以下に訂正。**

- **当初 accept 根拠の誤り訂正**: 「重複が強健性スコアを楽観方向に系統バイアスさせる」は統計的に誤り。MC（N=30,000、iid/AR(1) φ=0/0.3/0.6）で **E[重複平均 − 非重複平均] = −0.0002〜−0.0004 ≈ 0**。pseudo-replication が歪めるのは**分散・標準誤差・有意性検定**であり、点推定（平均）の不偏性ではない。
- **Tier2 への非影響**: Tier2 soft_score は OOS PF 平均 / Drift 平均 / efficiency=mean(OOS Sharpe)/mean(IS Sharpe) を正規化しスコア化するのみで、分散・p値・信頼区間を一切使わない。よって 0.30 寄与への楽観バイアスは生じない。
- **現状認識の訂正**: 現実装は既に **ratio-of-means**（`result_parser.py:248-255`、`event_simulator.py:1604`）。当初の「mean-of-ratios 集計」という記述は誤り。
- **非重複窓(step=6)が不可な理由**: 3年データで walks=4 < `WFA_MIN_WALKS=10` となり WFA 全体が None 化、閾値0.70近傍の約91戦略が大規模に揺れる。過去 QA-006 Round5 は逆に min_walks を上げる方向に動いており step 拡大は逆行。
- **根本対処**: 独立情報不足の本質対処は `Redesign_v2_Plan.md` L328-330/871-873 の **Phase 5 CPCV（DSR/PBO/CPCV）に委譲済み**。WFA 窓いじりは Phase 5 と二重投資。
- **結論**: `[change:spec]` 不要。本ディスポジションが正しい accept 根拠の記録。

## RE-102 — realized-only 日次損失リミット・含み損ブロッキング皆無

**判定: HIGH に再起票。当初の「ユーザー承認済みだから現状維持」は cop-out。新事実でユーザー再判断が必須。**

- **当初承認(6f5b4cb, 2026-05-25)の前提**: 「per-trade SL + 95% WARN で含み損保護は十分」。
- **監査で初めて定量化された新事実（承認時に未評価）**:
  - Live 22戦略中 **21 が JPYクロス LONG**（EUR_JPY 8/USD_JPY 6/GBP_JPY 6/AUD_JPY 1、相関≈1）。円全面高で全 JPY クロス含み損が同時膨張。
  - **USD_JPY 5戦略が単一 `open_trade_id=244`（entry=158.934/units=40000、~200,000 units 相当）を共有** = 実質単一ネットポジション。
  - KS limit = −10,000 JPY ≈ 口座 1M の 1%。realized-only のため含み損 −990,000 JPY 超でも新規エントリーが通る。
  - **Paper broker は `simulator.py:177` で `unrealized_pnl=0.0` 固定 → WARN が Paper で一度もテストされていない**（WARN integrity 欠陥）。
- **tail risk**: 日銀サプライズ等の JPY 急騰で 21/22 が同方向含み損→各 H4 ATR-SL は幅広く滞留→realized 化前に新規エントリーが通り続け、WARN(-9,500)をスキップして KS(-10,000)直行もありうる。現実性=中、影響=高。
- **両専門家の合意: 含み損 soft-block の即時追加は非推奨**（H4 ATR 戦略の設計意図と衝突 / 未最適化閾値の本番持込=過適合 / BT で実行され Live で弾かれる乖離）。
- **対策の選択肢（ユーザー判断）**:
  1. **現状維持**（新事実を理解の上で許容）。即コスト: JPYクロス方向集中の可視化 + WARN 深夜対応 runbook。
  2. **PTRC への unrealized 合算**（option_2）: `ptrc.py:560-562` の `_check_max_daily_loss` は既に `portfolio.total_unrealized_pnl` を引数受領済みなのに未使用。これを `existing_loss` に合算すれば「口座10%含み損で新規ブロック」が最小変更で実現。Hard Limit 値は不変・適用範囲拡張のみ。ただし**実弾エントリー拒否挙動の変更=`[change:spec]`**（golden/pin test 改訂・ヒステリシス設計込み）。
  3. **direction exposure cap**（ポートフォリオ単位の方向性上限）を risk_supervisor に追加。
- **独立 actionable バグ（RE-102 とは別に修正可能）**: Paper broker `unrealized_pnl=0.0` 固定（`simulator.py:177`）。WARN/含み損ロジックが Paper で検証不能になっている integrity 欠陥。soft-block の是非と独立に修正価値がある。

### このセッションでの実施
- QA-102 / QA-103: コード変更なし。本ディスポジションが正式記録。
- RE-102: **ユーザー再判断待ち**（上記選択肢1/2/3）。承認なしに risk 挙動は変更しない。

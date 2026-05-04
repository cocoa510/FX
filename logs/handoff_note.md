# Handoff Note

**最終更新**: 2026-05-04T08:10:00Z @ training-goto
**ブランチ**: master (ATLAS / FTS とも master)

## 現在の作業（1 行サマリ）

SHORT 戦略開発ループ完遂: 15 戦略生成 (073-087)・全 Gate PASS 失敗、ただし既存 ATLAS-2026-0424-001 が vectorbt 5.4.0 で **Tier 1 ALL PASS** 判明（FTS Paper 投入候補）

## 詳細コンテキスト（5 行）

ユーザー指示「許可確認なしで戦略開発ループを回し続ける」を受け、SHORT/balanced 戦略を 15 件生成（ATLAS-2026-0504-073〜087）。USD/JPY/EUR/USD/GBP/JPY/GBP/USD を MR/Donchian/balanced で網羅的に試行、すべて overall_passed=false。同セッションで既存 SHORT/balanced 戦略を vectorbt 5.4.0 で 8 件再評価し、**ATLAS-2026-0424-001 (GBPUSD-MeanRev-Short-M15-001) が Tier 1 全 8 条件 PASS** することを発見（B&H 超過 +0.65%、Secondary PF=0.94、L2 PF=1.01、SHORT 696 trades）。Tier 2 soft_score=0.35 < 0.70 で overall=false だが、Tier 1 真の Immutable は満たす。本セッションで Gate PASS 戦略は 0 件、ただし重要な構造的洞察を多数獲得。

## 未コミット変更 / WIP コミット対象

なし（15 戦略生成 + 8 件 5.4.0 再評価結果すべてコミット済み）

## SHORT 戦略開発の構造的結論

| 失敗パターン | 件数 | 該当 ID |
|---|---|---|
| L1 Sharpe FAIL | 9 | 073, 074, 076, 077, 080-082, 085, 087 |
| L1 trade 数不足 (<20) | 2 | 078 (制約過剰), 079 (同) |
| L1 trade<50 | 1 | 083 (H4 noise) |
| L1 PF FAIL | 1 | 086 (PF=0.68 worst) |
| L1 PASS / L2 過学習 | 1 | 075 (IS PF=1.19 → OOS PF=0.88) |
| L2 PASS だが Tier 1 #1/#4 | 1 | 084 (PF<1 + B&H excess<0) |

主要構造的要因:
1. **2019-2026 JPY weakness era**: USD/JPY 140→156, GBP/JPY 130→200 → SHORT 構造的逆風
2. **EUR/USD sideways 2023-26**: Donchian SHORT/Breakout SHORT は fade される
3. **vectorbt 5.4.0 SHORT bug fix**: 既存 SHORT 戦略の評価値を下方修正（過去 false positive 解消）
4. **Tier 2 soft_score 上限**: PF<1.5 / Sharpe<1.5 だと自動的に soft<0.4 で SHORT には厳しい
5. **balanced 化の罠**: 0424-001 を balanced 化(087)した結果、LONG 側 uptrend で負けが増えて全体が悪化 — SHORT-specific edge は SHORT 専用設計を維持すべき

## 唯一の Tier 1 ALL PASS SHORT 戦略

**ATLAS-2026-0424-001 (GBPUSD-MeanRev-Short-M15-001)** — 重要発見

| Tier 1 条件 | 値 | 閾値 | 判定 |
|---|---|---|---|
| Profit Factor | 1.0088 | >=1.0 | ✓ |
| Max Drawdown % | 12.10 | <=30 | ✓ |
| Total Trades | 696 | >=50 | ✓ |
| **B&H Excess Return %** | **+0.65** | >=0 | ✓ |
| Secondary Period PF | 0.9436 | >=0.8 | ✓ |
| Direction Bias | LONG=0 SHORT=696 | short_only | ✓ |
| RiskGuard Halt/yr | 0.0 | <=3.48 | ✓ |
| KillSwitch Trigger | 0 | ==0 | ✓ |

**Tier 2: soft_score=0.3521 < 0.70 で overall=false** だが、Tier 1（真の Immutable）は完全充足。

戦略仕様（GBPUSD M15、2022-04 から 2026-04 の 4 年間）:
- パラメータ: bb_std=1.5, rsi_overbought=70, atr_sl_multiplier=1.5, tp_rr_ratio=2.0
- session: UTC 7-20 時 (London + NY)
- エントリ: RSI(14)>70 AND close>BB_upper(20, 1.5)
- エグジット: RSI<50 OR SL=1.5×ATR OR TP=SL×2.0
- L1: 616 trades, PF=1.10, Sharpe=0.39, WR=62.7%
- L2: 696 trades, PF=1.01, Sharpe=0.07, MaxDD=12.1%

## 改良試行の結果（4 通り全て失敗）

| 改良アプローチ | 戦略 | 結果 |
|---|---|---|
| 厳格化 (bb_std 2.0, rsi 73, ADX<25) | 081 | WR 62.7→34.6%、L1 PF=0.84 で悪化 |
| RR=1.5 + early RSI exit | 082 | Sharpe 0.39→0.19 で悪化 |
| H4 移植 | 083 | trades=28 で不足 (Tier1 #3 FAIL) |
| H1 移植 | 084 | L2 まで進行も Tier1 #1, #4 FAIL |
| balanced 化 (LONG/SHORT 対称追加) | 087 | LONG 取引が悪化を招き全体 PF=0.93 |

**結論**: 0424-001 のパラメータ + SHORT-only 設計は既に sweet spot で、改良は逆効果。

## 次にやること

### 即実施候補（次セッション、ユーザー判断要）

1. **ATLAS-2026-0424-001 の FTS Paper 投入判断**:
   - Tier 1 ALL PASS = 真の Immutable 条件は完全充足
   - Tier 2 0.35 = 既存 deploy (0410-008 soft=0.49, 0426-013 soft=0.13 等) と同水準
   - 方向性集中リスク (FTS 34件全 long_only) を緩和する数少ない選択肢
   - **CLAUDE.md「確認無し連続運用」の `Gate PASS = overall_passed=true` には該当しない** ためユーザー判断が必要

### 中期

2. WFA Efficiency / Strategy Drift が null になる原因調査（多くの戦略で null、Tier 2 soft の障害）
3. **新規 SHORT 探索の方向性**:
   - Multi-timeframe trend filter（H4 trend 下抜けで SHORT 限定、結合 edge）
   - 特定セッション限定 SHORT（NY only など、構造的 edge）
   - reverse momentum SHORT（強上昇後の急反転に限定）
4. rescue_candidates 0430-005 アンサンブル化
5. Per-Symbol/Direction Net Exposure Cap (P3)
6. Promotion Gate 形式化

## 関連文書・コマンド

- **重要発見**: ATLAS-2026-0424-001 5.4.0 再評価結果 → `ATLAS/strategies/ATLAS-2026-0424-001/backtest/result.json` (gate_check.tier1.all_passed=true)
- セッション内全戦略コミット: 073-087 各戦略の `[atlas] ATLAS-2026-0504-XXX ...` コミット (15 件)
- spec_change_log: 2026-05-04 vectorbt L1 SHORT 評価バグ修正 (5.3.2→5.4.0)
- 実行中ループ: なし（手動 1 戦略ずつ生成）

## Runner 状態

前セッションから継続: PID 12080 で稼働中、Live 2 + Paper 32 = 34 戦略 Forward Test 中。本セッションでは Runner に変更なし。

## OANDA Live Account（変更なし）
- balance: 307,833.34 JPY
- Open positions: 0 件

## 引継ぎ時の注意

- **0424-001 投入は要ユーザー判断**: Tier 1 ALL PASS だが overall=false。autonomous 投入は CLAUDE.md「確認無し連続運用」の `Gate PASS した戦略は FTS ペーパートレードに即投入する` に厳密には該当しない（`Gate PASS = overall_passed=true`）
- **既知バグ集（本セッションで判明）**:
  - インジケータ名 `bb_upper` (誤) → `bollinger_upper` (正、builtin map 必須、073/074 で発覚)
  - `hasattr()` 禁止 → `bar.get("timestamp", None)` パターン（076, 082, 084 で発覚）
  - `pips_per_unit=10000` (非 JPY) / `=100` (JPY) を `config.parameters` に必須
  - GBP_JPY M15 / EUR_USD H4 / GBP_USD H4 / GBP_JPY H1/H4 の secondary データを本セッションで新規取得
- **fx-strategist の傾向**: AND 厳格化と OR 緩和の両方に振れる。明示的に「sweet spot を維持」と指示しないと逆方向に動くことあり
- **vectorbt 5.4.0 SHORT 真値**: 過去 SHORT 戦略の Tier 1 値は信頼できる（pre-5.4.0 は false positive 含む）
- **balanced 化の罠**: SHORT-only Tier 1 PASS 戦略を balanced 化すると LONG 側で edge を破壊する可能性大（087 の例）

# Handoff Note

**最終更新**: 2026-05-04T08:15:00Z @ TRAINING-GOTO
**ブランチ**: master
**直前のコミット**: `54831fa` [wip:handoff] 088 (MTF) を含む最終セッションサマリ反映

## 現在の作業（1 行サマリ）

SHORT 戦略開発ループ 16 件完遂 (073-088)・全 Gate PASS 失敗、既存 ATLAS-2026-0424-001 が vectorbt 5.4.0 再評価で **Tier 1 ALL PASS** 判明・FTS Paper 投入は要ユーザー判断

## 詳細コンテキスト（5 行）

ユーザー指示「許可確認なしで戦略開発ループを回し続ける」を受け、SHORT/balanced 戦略を 16 件生成（ATLAS-2026-0504-073〜088）。USD/JPY / EUR/USD / GBP/JPY / GBP/USD を MR/Donchian/balanced/MTF で網羅的に試行、すべて overall_passed=false。同セッションで既存 SHORT/balanced 戦略を vectorbt 5.4.0 で 7 件再評価し、ATLAS-2026-0424-001 (GBPUSD-MeanRev-Short-M15-001) が Tier 1 全 8 条件 PASS することを発見（B&H 超過 +0.65%、Secondary PF=0.94）。Tier 2 soft_score=0.35 < 0.70 で overall=false だが Tier 1 Immutable は完全充足。0424-001 の改良試行 6 通り (081-084/087/088) すべて逆効果 — パラメータは既に sweet spot。

## 未コミット変更 / WIP コミット対象

なし（16 戦略生成・7 件再評価・handoff 更新すべてコミット済み）

## 次にやること

### 要判断（ユーザー判断必要）

1. **ATLAS-2026-0424-001 の FTS Paper 投入**:
   - Tier 1 ALL PASS（真の Immutable 充足）= GBP/USD M15 SHORT 696 trades、B&H 超過 +0.65%
   - Tier 2 soft=0.35 で overall=false（CLAUDE.md 厳密読みでは autonomous 投入対象外）
   - 既存 FTS deploy 中の 0410-008 (soft=0.49) / 0426-013 (soft=0.13) より高水準
   - FTS 34 件全 long_only の方向性集中リスクを解消する数少ない選択肢

### 短期（次セッション着手候補）

2. **WFA Efficiency / Strategy Drift null 原因調査** — 多くの戦略で null = Tier 2 soft の主要障害源、これが解消できると 0424-001 も soft UP の可能性
3. **新規 SHORT 探索（未試行角度）**:
   - セッション限定 SHORT（例: Asia session reversals）
   - reverse momentum SHORT（強い上昇後の反落を高信頼度でキャッチ）
   - multi-asset correlation SHORT（USD/JPY 上昇時に EUR/USD SHORT）
4. **rescue_candidates 0430-005 アンサンブル化** — PF=3.08 / trades=28 の HIGH 優先

### 中期

5. Per-Symbol/Direction Net Exposure Cap (P3)
6. Promotion Gate 形式化（Paper → Live 昇格基準 yaml 化）
7. Capacity Test（34 → 50 戦略のロードテスト）

## 関連文書・コマンド

- **重要発見**: `ATLAS/strategies/ATLAS-2026-0424-001/backtest/result.json` → gate_check.tier1.all_passed=true
- 今セッション生成: ATLAS 073-088 （16 件）、data 取得: EUR_USD H4 / GBP_JPY M15/H1/H4 / GBP_USD H4 + secondary
- spec_change_log: 2026-05-04 vectorbt 5.3.2 → 5.4.0 SHORT 評価バグ修正
- 実行中ループ: なし
- FTS Runner 継続稼働: PID 12080、34 戦略（Live 2 / Paper 32）

## Runner 状態

- PID 12080 稼働継続中（起動 2026-05-04T13:58 JST）
- Live: ATLAS-2026-0408-065 / ATLAS-2026-0417-003 の 2 件
- Paper: 32 件（本日 13 件新規投入済み）

## OANDA Live Account

- balance: 307,833.34 JPY
- Open positions: 0 件

## 引継ぎ時の注意

- **0424-001 投入は要ユーザー判断**: overall=false のため CLAUDE.md「Gate PASS した戦略は FTS ペーパートレードに即投入」には非該当
- **既知バグ（本セッション判明）**:
  - `bb_upper` (誤) → `bollinger_upper` (正)
  - `hasattr()` 禁止 → `bar.get("timestamp", None)` + try/except
  - JPY pair: `pips_per_unit=100`、非 JPY: `=10000`（config.parameters 必須）
- **SHORT 改良は sweet spot 変更禁止**: 081-088 の試行で 6 通り全て逆効果確認済み
- **balanced 化の罠**: SHORT-only Tier 1 PASS を balanced 化すると LONG 側で edge 破壊（087）
- **vectorbt 5.4.0 SHORT**: pre-5.4.0 の SHORT 指標は過大評価。5.4.0 結果が真値

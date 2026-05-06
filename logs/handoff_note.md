# Handoff Note

**最終更新**: 2026-05-06T04:00:00Z @ TRAINING-GOTO
**ブランチ**: master
**直前のコミット**: d8a83c8 [atlas] 376-378: CAD/JPY H4 TF初PASS + NZD/JPY TF FAIL確認

## 現在の作業（1 行サマリ）

SMAスロープエントリー戦略でtrand_followingセルを大規模開拓: 本セッションで13件の新規Gate PASS。USD/JPY H4 TF初開拓(soft=0.9214), AUD/JPY H4 TF初開拓(0.8801), CAD/JPY H4 TF初開拓(0.7988)。総Gate PASS: 202件。FTS 80戦略稼働中。

## 詳細コンテキスト

### SMAスロープアプローチ（本セッションの主要発見）

**戦略コンセプト**: `price > SMA20 AND SMA20 is rising (slope_lookback bars ago < now)`
- エントリーフィルター: SMAが上向きの時のみエントリー
- エグジット: price < SMA20 OR timeout
- 最適パラメータ: slope_lookback=8, TP=14×ATR, SL=1.5-2.0×ATR

**ペア別成果**:
| ペア | TF | best soft | 戦略ID |
|------|-----|-----------|--------|
| GBP/JPY | H4 | 0.9398 | 243(既存) |
| USD/JPY | H4 | **0.9214** | 368(新規!) |
| GBP/JPY slope | H4 | 0.9311 | 374(新規) |
| AUD/JPY | H4 | 0.8801 | 370(新規!) |
| EUR/JPY | H4 | 0.8769 | 241(既存) |
| CAD/JPY | H4 | 0.7988 | 376(新規!) |
| NZD/JPY | H4 | FAIL | 378 |

### 廃棄確認したセル

- **EUR/JPY H1 TF**: SMA slope 2回試行でMaxDD過大またはSharpe負
- **AUD/JPY H1 Donchian**: 3回試行全FAIL（H1ノイズ過多、data range問題）
- **NZD/JPY H4 TF**: L1 Sharpe=0.27 FAIL確認（既知の全手法失敗と整合）

### プレゼンテーション資料

`ATLAS/docs/presentation_atlas_fts.html` を作成。Chart.js対話型グラフ付き。

## FTS現状

- インポート済み: **80件**（本セッション新規: 10件）
- 稼働継続中

## 次にやること

1. **GBP/JPY H4 volatility改善**: 345(soft=0.7789) → 0.80+を目標
2. **USD/JPY M15 trend_following**: 未探索セル（M15は小さいので難しい可能性）
3. **EUR/JPY H4 TF改善**: 現在avg=0.819（USD/JPY H4 TF avg=0.897より低い）
4. **FTSセル3件上限の整理**: EUR/JPY H4 breakout=6件、GBP/JPY H4 breakout=5件等
5. **新戦略タイプ探索**: momentumタイプをH4で追加展開（現在7件のみ）

## 引継ぎ時の注意

- SMAスロープアプローチが非常に有効: 新ペアに適用する際は slope=8, TP=14, SL=1.5-2.0 から試行
- H1 TFは構造的に困難（EUR/JPY H1 TF 2回FAIL、AUD/JPY H1 3回FAIL）
- NZD/JPY H4は全アプローチ失敗確定
- FTS 376は新規CAD/JPY H4 TF（インポート未実施）


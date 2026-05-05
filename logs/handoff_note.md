# Handoff Note

**最終更新**: 2026-05-06T04:00:00Z @ TRAINING-GOTO
**ブランチ**: master
**直前のコミット**: 5b47655 [atlas] 248-250: Donchian+SMAフィルター探索完了

## 現在の作業（1 行サマリ）

セッション完遂: 戦略181→250まで生成 (70戦略)。全時代最高値 soft=0.9483 (ATLAS-2026-0504-216) 確定。FTS 136戦略稼働。

## 詳細コンテキスト

### 確定した最優秀設定（不動の全時代最高）
**ATLAS-2026-0504-216: GBP/JPY H4 D=10 SL=2.0 TP=10 min_atr=0.40**
- soft_score = 0.9483
- 全パラメータ網羅的探索済み (D:3-15, SL:1.5/2.0/2.5, TP:6-15, min_atr:0.30-0.50)
- 近接値: D10+SMA20フィルター (248) = 0.9481 (ほぼ同等)

### 探索済み戦略タイプ
| タイプ | 最高値 | 代表戦略 |
|---|---|---|
| Donchian breakout LONG | **0.9483** | 216 (GBP/JPY D10) |
| SMA cross LONG | 0.940 | 243 (SMA30) |
| Dual EMA cross LONG | 0.935 | 246 (EMA5/20) |
| Donchian + SMAフィルター | 0.9481 | 248 (D10+SMA20) |
| SHORT breakout | FAIL | carry bias不適合 |
| 非JPYペア | FAIL | carry構造なし |
| H1タイムフレーム | FAIL | ノイズ多し |

### 対ペア最優秀
| ペア | ID | soft | 設定 |
|---|---|---|---|
| **GBP/JPY** | **216** | **0.9483** | D=10 SL=2.0 TP=10 min_atr=0.40 |
| EUR/JPY | 219 | 0.907 | D=5 SL=1.5 TP=12 min_atr=0.40 |
| USD/JPY | 187 | 0.893 | D=3 SL=2.0 TP=15 min_atr=0.10 |

### 重要な知見
1. **SL=2.0 はGBP/JPY専用** (EUR/JPY, USD/JPY D=10 は L1 FAIL)
2. **min_atr=0.40 はD≥8向け有効** (D=3/5 では効果なし)
3. **非JPYペア は LONG-only 不適合** (carry bias なし)
4. **SHORT はcarry bias で構造的失敗**
5. **SMAクロス系は soft≤0.940** (Donchianに劣る)
6. **D10+SMA20フィルターが Donchian と同等** (0.9481 ≈ 0.9483)

### FTS 状況
- インポート済み戦略: **136件**
- 最新ID: ATLAS-2026-0504-250
- Runner 再起動済み

## 次にやること

1. **未探索戦略タイプ**:
   - ボリンジャーバンド mean reversion (RSI<30 bounce等)
   - EUR/JPY D=5 SL=1.5 TP=12 min_atr=0.35 (精細探索)
2. **ATLAS-2026-0504-216 の Live 投入検討**:
   - soft=0.9483 は全履歴最高
   - live_eligible: false → ユーザー判断で Live 切替
3. **FTS runner 長期稼働確認**: 136戦略正常動作チェック

## 関連文書・コマンド

- 最新戦略ID: ATLAS-2026-0504-250 (次は 251)
- バックテスト: `cd /c/data/works/FX/ATLAS && .venv/Scripts/python.exe -m atlas.main backtest <ID>`
- FTS 再起動: `cd /c/data/works/FX/fx_trading_system && PowerShell.exe -Command "& .\scripts\start_unified_runner.ps1"`

## 引継ぎ時の注意

- pips_per_unit=100 (JPY) / 10000 (非JPY)
- validate は不要 (Stage 4 false positive)
- GBP/JPY D=10 SL=2.0 TP=10 min_atr=0.40 soft=0.9483 が全時代最高
- SHORT / 非JPY / H1 は構造的に不適合（再試行不要）
- SMAクロス系は Donchian より劣るが多様性として価値あり

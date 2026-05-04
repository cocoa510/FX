# Handoff Note

**最終更新**: 2026-05-04T00:15:00Z @ training-goto
**ブランチ**: master (ATLAS repo: master)
**直前のコミット**: ATLAS: 2d23758 [atlas] ATLAS-2026-0504-066 GATE PASS

## 現在の作業（1 行サマリ）

H1/H4マトリクス探索セッション完了 — 「EMAなし純粋Donchianブレイクアウト + SL2x/TP4x」でJPYペアが8件Gate PASS

## 詳細コンテキスト（3〜5 行）

本セッションで**重大な発見**: EUR/JPYとUSD/JPYのH1/H4において、EMAトレンドフィルターを完全除去した純粋Donchianブレイクアウト（SL=2xATR, TP=4xATR）が非常に高い性能を示し、8件のGate PASSを達成した。

USD/JPY H4ではDonchianルックバックを短くするほどL2 Sharpeが向上（D10:3.33→D8:3.61→D5:3.96→D3:4.08）。EUR/JPY H1ではDonchian20が最良（soft=0.802）。

また、非JPYペア（EUR/USD, GBP/USD）向けのpips_per_unitバグを特定（config.parametersの中に明示要）。SHORTおよびBALANCED戦略はvectorbt L1がSHORTをLONGとして評価する制限で困難。

FTSペーパーポートフォリオは13件に拡大（全long_only）。SHORT/BALANCED不足問題は未解決。

## 未コミット変更 / WIP コミット対象

なし（全てATLASとFTSリポジトリにコミット・プッシュ済み）

## 次にやること

1. **EUR/JPY H4データ取得**: `atlas data fetch EUR_JPY --timeframe H4 --years 7` でH4データを作成し、EUR/JPY H4 no-EMA Donchianを試す
2. **SHORT戦略探索代替手段**: vectorbt L1のSHORT制限を[change:spec]で解決するか提案する
3. **rescue_candidates救済**: ATLAS/logs/rescue_candidates.jsonの4件のBT期間延長
4. **EMAなしDonchian最適化続行**: EUR/JPY H1でDonchian25, 30も試す

## 関連文書・コマンド

- 発見パターン記録: `memory/project_no_ema_donchian_discovery.md`
- Gate PASS最新: ATLAS-2026-0504-058〜066 (8件)
- 実行コマンド例: `cd ATLAS && .venv/Scripts/python.exe -m atlas.main backtest ATLAS-2026-0504-XXX`
- 実行中ループ: なし

## 引継ぎ時の注意

- **pips_per_unit**: 非JPYペアはconfig.json parametersブロックに`"pips_per_unit": 10000`必須
- **EMAフィルター**: USD/JPY H1はEMA50>EMA100が有効、EUR/JPY H1とUSD/JPY H4はEMAなしが有効
- **SHORT不足**: 全13件long_only。vectorbt L1 SHORT制限で短策が困難
- **USD/JPY H4クラスター**: 035+061+062+064+066の5件でクラスターが大きい

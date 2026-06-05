# RE-005: Live MISMATCH 戦略の網羅列挙レポート

> **【人間判断 2026-05-25】引き戻し不要で確定。** 本レポートの「MISMATCH」枠組みには方法論欠陥がある:
> 検出は SMA50/200 で行うが、該当 4 戦略の実エントリーゲートは SMA20-slope (0505-367/368/424) /
> SMA50-cross (0506-005) であり物差しが別物。これらはフィルターで**逆トレンド方向の発注ができず**
> (下降局面は FLAT 維持)、保有中転換も SMA割れ/SL で損失限定。3 年逆レジーム BT で PF≥1.0 検証済 =
> 逆トレンド「資本保全」耐性あり (利益ではなく毀損しないの意)。「沈黙」と「含み損」を混同していた。
> **真のアクション = 戦略引き戻しでなく `verify_sma_live_values.py` を各戦略の実エントリー指標と照合する
> よう是正すること** (= 本レポート末尾 suggested_fix「戦略を増やして SMA50/200 比較拡大」を訂正)。

**finding**: R2 メタ監査 RE-005 / v2 監査 M-D2
**目的**: execution_mode=live の全戦略を網羅列挙し、トレンド依存 (trend_following) かつ
現在の SMA トレンドが戦略前提と逆 (MISMATCH) の戦略を strategy_id 単位で全特定する。
**性質**: 判断材料の列挙レポートのみ。**コードは一切変更していない**。
継続/引き戻しの最終判断は人間オーナーが M-D2 期限 (2026-05-27) までに行う。
**作成日**: 2026-05-25
**作成者**: risk-execution-engineer (調査エージェント)

---

## 1. 調査手法 / evidence ソース

| 項目 | 内容 |
|---|---|
| Live 抽出 | `trading_platform/strategies/imported/*/runner_config.json` で `"execution_mode":"live"` を Grep。**22 件**ヒット (タスク指定の 22 件と一致) |
| 戦略型判定 | 各 `runner_config.json` の `_strategy_summary.strategy_type` / `direction_bias` + 当該 `strategy.py` のエントリーロジック実読 |
| トレンド依存性判定 | SMA/EMA クロスや SMA slope を**エントリーゲート**にしている戦略を「SMA トレンド依存」、Donchian/BB ブレイクや pullback・MR を「方向バイアスのみ (SMA 非ゲート)」と分類 |
| 現況 SMA トレンド | `scripts/verify_sma_live_values.py` を venv python で実行 (USD_JPY H4 / EUR_USD H1,H4 の 3 ペア)。**他ペア (GBP_JPY, EUR_JPY, AUD_JPY の H4/H1)** は同スクリプトの計算式 (`close.rolling(50/200).mean()`) を ATLAS parquet `C:\data\works\FX\ATLAS\data\market\*.parquet` に対して直接適用して補完 |

> **重要なデータ鮮度の注意 [evidence]**: ATLAS BT parquet の最終 ts は概ね 2026-04-27〜2026-05-08 で、本日 (2026-05-25) より **約 2〜4 週間古い**。
> SMA トレンド判定はこの古いスナップショットに基づく近似であり、Live runner が参照する直近データとは差異がありうる。
> `scripts/verify_sma_live_values.py:36-37` の出力 ts も同様 (USD_JPY H4=2026-05-01, EUR_USD H4=2026-05-07)。
> 厳密判定には `/atlas-data` 更新後の再実行を推奨 (アクション提案 §6 参照)。

---

## 2. Live 戦略 全 22 件 一覧

> 列 "SMA依存": `S`=SMA cross/slope をエントリーゲートに使用 (狭義 trend_following) /
> `B`=Donchian/BB ブレイク (方向バイアス LONG だが SMA 非ゲート) /
> `H`=Hybrid (Donchian ブレイク + pullback) / `M`=Mean Reversion。
> 列 "関連トレンド": MISMATCH 判定に用いる instrument×TF の SMA50/200 現況。

| # | strategy_id | inst | TF | direction | strategy_type | SMA依存 | 関連トレンド (SMA50/200) | exec_mode |
|---|---|---|---|---|---|---|---|---|
| 1 | ATLAS-2026-0505-367 | USD_JPY | H4 | long_only | trend_following | **S** (SMA20 slope) | **downtrend** | live |
| 2 | ATLAS-2026-0505-424 | USD_JPY | H4 | long_only | trend_following | **S** (SMA20 slope) | **downtrend** | live |
| 3 | ATLAS-2026-0505-368 | USD_JPY | H4 | long_only | trend_following | **S** (SMA20 slope) | **downtrend** | live |
| 4 | ATLAS-2026-0505-423 | GBP_JPY | H4 | long_only | trend_following | **S** (SMA20 slope) | uptrend | live |
| 5 | ATLAS-2026-0505-374 | GBP_JPY | H4 | long_only | trend_following | **S** (SMA20 slope) | uptrend | live |
| 6 | ATLAS-2026-0504-241 | EUR_JPY | H4 | long_only | trend_following | **S** (SMA20 cross) | uptrend | live |
| 7 | ATLAS-2026-0506-005 | GBP_JPY | H1 | long_only | trend_following | **S** (SMA50 cross) | **downtrend** | live |
| 8 | ATLAS-2026-0511-059 | EUR_USD | H1 | short_only | mean_reversion | M | downtrend (= SHORT 前提) | live |
| 9 | ATLAS-2026-0505-335 | EUR_JPY | H4 | long_only | hybrid | H | uptrend | live |
| 10 | ATLAS-2026-0505-324 | GBP_JPY | H4 | long_only | hybrid | H | uptrend | live |
| 11 | ATLAS-2026-0505-338 | AUD_JPY | H4 | long_only | hybrid | H | uptrend | live |
| 12 | ATLAS-2026-0505-392 | EUR_JPY | H4 | long_only | volatility | B (BB upper) | uptrend | live |
| 13 | ATLAS-2026-0504-228 | EUR_JPY | H4 | long_only | breakout | B (Donchian) | uptrend | live |
| 14 | ATLAS-2026-0504-236 | EUR_JPY | H4 | long_only | breakout | B (Donchian) | uptrend | live |
| 15 | ATLAS-2026-0507-050 | EUR_JPY | H4 | long_only | breakout | B (Donchian) | uptrend | live |
| 16 | ATLAS-2026-0504-060 | EUR_JPY | H1 | long_only | breakout | B (Donchian) | **downtrend** | live |
| 17 | ATLAS-2026-0506-033 | EUR_JPY | H1 | long_only | breakout | B (Donchian) | **downtrend** | live |
| 18 | ATLAS-2026-0504-169 | GBP_JPY | H4 | long_only | breakout | B (Donchian) | uptrend | live |
| 19 | ATLAS-2026-0504-117 | GBP_JPY | H4 | long_only | breakout | B (Donchian) | uptrend | live |
| 20 | ATLAS-2026-0507-049 | USD_JPY | H4 | long_only | breakout | B (Donchian) | **downtrend** | live |
| 21 | ATLAS-2026-0507-038 | USD_JPY | H1 | long_only | breakout | B (Donchian) | uptrend | live |
| 22 | ATLAS-2026-0504-098 | USD_JPY | M15 | long_only | breakout | B (Asia range) | downtrend | live |

evidence: 各 `runner_config.json` (例 `ATLAS-2026-0505-367/runner_config.json:3-12`)、
SMA ゲート確認は `ATLAS-2026-0505-367/strategy.py:155-159` (`if not slope_positive: return None` / `if not (close > sma): return None`)、
`ATLAS-2026-0506-005/strategy.py:102` (`close > sma and prev <= sma` クロス)、
`ATLAS-2026-0504-241/strategy.py:75` (同)。

---

## 3. 現況 SMA50/200 トレンド表

`scripts/verify_sma_live_values.py` の計算式 (`close.rolling(period).mean()`、SMA50<SMA200=downtrend) を
ATLAS parquet に適用した結果。先頭 3 行 (★) はスクリプトが直接出力した値、残りは同式での補完計算。

| instrument | TF | close | SMA50 | SMA200 | トレンド | last_ts | 取得方法 |
|---|---|---|---|---|---|---|---|
| USD_JPY | H4 | 157.088 | 159.084 | 159.135 | **downtrend** | 2026-05-01 17:00 | ★スクリプト出力 |
| EUR_USD | H1 | 1.17208 | 1.17118 | 1.17482 | downtrend | 2026-04-27 20:00 | ★スクリプト出力 |
| EUR_USD | H4 | 1.17270 | 1.17171 | 1.16688 | uptrend | 2026-05-07 21:00 | ★スクリプト出力 |
| USD_JPY | H1 | 159.425 | 159.483 | 159.204 | uptrend | 2026-04-27 20:00 | 補完計算 (同式) |
| USD_JPY | M15 | 159.432 | 159.288 | 159.478 | downtrend | 2026-04-27 21:15 | 補完計算 (同式) |
| EUR_JPY | H4 | 184.027 | 186.270 | 185.312 | uptrend | 2026-05-03 21:00 | 補完計算 (同式) |
| EUR_JPY | H1 | 186.870 | 186.787 | 187.036 | **downtrend** | 2026-04-27 20:00 | 補完計算 (同式) |
| GBP_JPY | H4 | 212.840 | 214.953 | 213.440 | uptrend | 2026-05-04 05:00 | 補完計算 (同式) |
| GBP_JPY | H1 | 213.330 | 212.707 | 213.766 | **downtrend** | 2026-05-08 08:00 | 補完計算 (同式) |
| AUD_JPY | H4 | 112.697 | 113.801 | 112.229 | uptrend | 2026-05-04 17:00 | 補完計算 (同式) |

> ★出力は `docs/sma_live_verification_2026_0523.md` (2026-05-23 生成) と同一値で再現確認済み。
> 補完計算は本調査で venv python から ATLAS parquet に直接適用。スクリプトの `TARGETS` (`verify_sma_live_values.py:34-38`)
> は 3 戦略しかカバーしておらず、他 19 件はカバー外であった点が RE-005 の盲点の一因と推定。 [推測]

---

## 4. MISMATCH 判定ロジック

判定式: **戦略前提トレンド** (long_only → uptrend 前提 / short_only → downtrend 前提) と
§3 の **現況 SMA トレンド**が逆なら MISMATCH。

- **狭義 (重点): SMA をエントリーゲートにする trend_following (S 区分)** が逆トレンド下にある場合、
  エントリー条件 (SMA slope>0 / SMA 上抜けクロス) がほぼ成立せず**発火停止 or 逆張り誤発火**のリスクが高い。
  → これが RE-005 / M-D2 の本丸。
- **広義 (参考): 方向バイアス LONG の breakout/hybrid (B/H 区分)** が逆トレンド下にある場合も、
  上方ブレイクが出にくく勝率劣化が見込まれるが、SMA で構造的にゲートされてはいない。

---

## 4-1. MISMATCH 確定リスト (狭義: SMA-trend_following かつ Live)

| strategy_id | inst×TF | 前提方向 | 現況トレンド | 判定 | SMA依存度 | 既対応/新規 |
|---|---|---|---|---|---|---|
| **ATLAS-2026-0505-367** | USD_JPY H4 LONG | uptrend | **downtrend** | **MISMATCH** | 高 (SMA20 slope>0 必須) | **新規** |
| **ATLAS-2026-0505-424** | USD_JPY H4 LONG | uptrend | **downtrend** | **MISMATCH** | 高 (SMA20 slope>0 必須) | **新規** |
| **ATLAS-2026-0505-368** | USD_JPY H4 LONG | uptrend | **downtrend** | **MISMATCH** | 高 (SMA20 slope>0 必須) | **新規** |
| **ATLAS-2026-0506-005** | GBP_JPY H1 LONG | uptrend | **downtrend** | **MISMATCH** | 高 (SMA50 上抜けクロス必須) | **新規** |
| ATLAS-2026-0505-423 | GBP_JPY H4 LONG | uptrend | uptrend | OK | 高 | — |
| ATLAS-2026-0505-374 | GBP_JPY H4 LONG | uptrend | uptrend | OK | 高 | — |
| ATLAS-2026-0504-241 | EUR_JPY H4 LONG | uptrend | uptrend | OK | 高 | — |
| ATLAS-2026-0511-059 | EUR_USD H1 SHORT | downtrend | downtrend | OK (前提整合) | — (MR) | — |

→ **狭義 MISMATCH 確定: 4 件 (USD_JPY H4 LONG ×3 + GBP_JPY H1 LONG ×1)**。すべて新規 (PR35 未対応)。

## 4-2. 広義 MISMATCH 参考リスト (方向バイアス LONG breakout かつ逆トレンド)

| strategy_id | inst×TF | 前提方向 | 現況トレンド | 判定 | 備考 |
|---|---|---|---|---|---|
| ATLAS-2026-0507-049 | USD_JPY H4 LONG | uptrend | downtrend | 広義 MISMATCH | Donchian D40 breakout。上方ブレイク減で発火低下見込み |
| ATLAS-2026-0504-060 | EUR_JPY H1 LONG | uptrend | downtrend | 広義 MISMATCH | Donchian breakout (H1) |
| ATLAS-2026-0506-033 | EUR_JPY H1 LONG | uptrend | downtrend | 広義 MISMATCH | Donchian breakout (H1) |
| ATLAS-2026-0504-098 | USD_JPY M15 LONG | uptrend | downtrend | 広義 MISMATCH | Asia range breakout (M15) |

> 広義群は SMA で構造ゲートされず、breakout トリガが自然に発火頻度を絞るため、
> 狭義群より緊急度は低い。ただし USD_JPY 系の逆トレンドは狭義群と同根なので併せてモニタ推奨。

---

## 5. 引き戻し推奨度 (最終判断は人間)

| strategy_id | 推奨度 [推測] | 根拠 |
|---|---|---|
| ATLAS-2026-0505-367 | **高 (Paper へ引き戻し検討)** | USD_JPY H4 が明確に downtrend。SMA20 slope>0 ゲートが失効し、上昇前提が崩れている。RE-005 が名指しした 2 件の片方。`strategy.py:155` で slope 非正は entry スキップ = 発火停止、再上昇局面で誤った遅効エントリーの懸念 |
| ATLAS-2026-0505-424 | **高 (同上)** | 同型 (slope=10/TP=16 のみ差異)。RE-005 名指しのもう片方。露出度は他 USD_JPY H4 と同じ fixed_units=10000 |
| ATLAS-2026-0505-368 | **高 (同上)** | 同型 USD_JPY H4 SMA20 slope LONG。RE-005 では名指しされていないが**実質同一リスク**。見落とし候補 |
| ATLAS-2026-0506-005 | **中〜高** | GBP_JPY H1 が downtrend。SMA50 上抜けクロス必須のため発火がほぼ停止。GBP_JPY **H4 は uptrend** なので H1 のみの局所逆行 (TF 違いの剥離) に注意 |
| ATLAS-2026-0507-049 | 中 (モニタ強化) | USD_JPY H4 LONG breakout。SMA 非ゲートだが同 instrument×TF が逆行。発火頻度監視 (`scripts/measure_signal_frequency.py`) を推奨 |
| ATLAS-2026-0504-060 / 0506-033 | 低〜中 (モニタ) | EUR_JPY **H1 は downtrend だが H4 は uptrend**。上位 TF はトレンド維持。H1 breakout の発火低下を観察 |
| ATLAS-2026-0504-098 | 低 (継続可) | USD_JPY M15 Asia range breakout。日中レンジブレイク主体で SMA トレンド依存が薄い |

> 露出度補足: 全 22 件が `fixed_units=10000` / `daily_loss_stop_jpy=-5000` で統一 (各 runner_config.json:4-5)。
> 1 戦略あたりの名目露出は均一。USD_JPY H4 LONG は **3 戦略が同方向に重複**しており、合算露出 (約 3×) が
> 逆トレンド下で同時逆行する集中リスクがある点が最重要。 [推測: 露出集中の定量はポートフォリオ実残高照合が別途必要]

---

## 6. 既対応との重複排除 (PR35)

| strategy_id | PR35 対応 | 現 execution_mode (確認済) | 本リストでの扱い |
|---|---|---|---|
| ATLAS-2026-0511-009 | Paper へ降格 | **paper** (runner_config.json:検証済) | 対応済 — Live 22 件に含まれず |
| ATLAS-2026-0510-002 | 退避対象外と再分類 | **paper** (inst=AUD_USD, dir/type=None) | 対応済 — Live 22 件に含まれず |

> `0510-002` は runner_config 上 instrument=AUD_USD / direction=None / type=None だが、
> `docs/sma_live_verification_2026_0523.md:22` では「USD/JPY LONG H4 (SMA50/200 確認)」とラベルされていた。
> このラベル不整合が RE-005 の出発点。いずれにせよ現在 paper であり Live 露出はない。

---

## 7. M-D2 期限 (2026-05-27) に対するアクション提案

1. **データ鮮度の解消 (最優先)**: ATLAS parquet が 2〜4 週古い。`/atlas-data` で USD_JPY/GBP_JPY/EUR_JPY を直近まで更新後、
   `scripts/verify_sma_live_values.py` の `TARGETS` (現状 3 件のみ) を **本レポート §4-1 の 8 戦略 + §4-2 の 4 戦略**に拡張して再実行し、
   MISMATCH を最新データで確定させる (本レポートは古いスナップショット近似)。
2. **発火頻度の実測**: 狭義 4 件 (0505-367/424/368, 0506-005) について `scripts/measure_signal_frequency.py` を実行し、
   「発火停止」が実データで起きているかを `docs/rollback_thresholds.md` 基準と突合。
3. **人間判断の付議**: 上記 1〜2 の結果を添え、狭義 4 件の Live 継続 / Paper 引き戻しを 2026-05-27 までに決裁。
   コード変更 (execution_mode 書換) は人間レビュー + PR を経ること (本エージェントは未変更)。
4. **検証スクリプトの恒久修正 (別 finding)**: `verify_sma_live_values.py` の TARGETS が Live 全戦略を網羅していない構造を是正
   (Live runner_config から動的に対象を生成する等)。これが RE-005 の真因の一つ。

---

## 結論サマリ

- Live 戦略は **22 件**、うち SMA をエントリーゲートにする狭義 trend_following は **8 件**。
- **狭義 MISMATCH 確定: 4 件** — `ATLAS-2026-0505-367` / `ATLAS-2026-0505-424` / `ATLAS-2026-0505-368` (USD_JPY H4 LONG, 現況 downtrend) と `ATLAS-2026-0506-005` (GBP_JPY H1 LONG, 現況 downtrend)。**全件 PR35 未対応 (新規)**。
- 参考までに広義 MISMATCH (方向バイアス LONG breakout が逆トレンド): 4 件 (`0507-049` / `0504-060` / `0506-033` / `0504-098`)。
- PR35 既対応の `0511-009` / `0510-002` は現在 paper であり Live 22 件に含まれず、重複なし。
- 判定は **2〜4 週間古い ATLAS スナップショット**に基づく近似。確定には `/atlas-data` 更新後の再実行が必須。

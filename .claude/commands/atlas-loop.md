# ATLAS 自動反復改善ループ

戦略の「生成 -> 検証 -> バックテスト -> 評価 -> 改��」サイクルを専門家エージェント群とPython CLIで自動駆動し、収束判定まで自動実行します。

## 引数
`$ARGUMENTS` — 以下の形式で指定:
- `<戦略タイプ> <通貨ペア> [オプション]` — 新規生成から開始
- `--resume <generation_id>` — 既存世代から改良ループを再開
- `--max-generations <N>` — 世代上限（デフォルト: 10）
- `--target-score <S>` — 目標スコア（デフォルト: 0.75）
- `--types <type1,type2,...>` — 戦略タイプローテーション順序を明示指定
- `--no-rotate` — タイプ自動ローテーションを無効化（系統廃棄時にループ停止）
- `--direction <bias>` — 方向制約（`any` / `long_only` / `short_only` / `balanced`）。デフォルト: `any`。Period Bias対策でSHORT戦略を強制生成する場合に `short_only` を指定
- `--dry-run` — 実行計画のみ表示（実行しない）
- 例: `trend_following USDJPY --max-generations 5`
- 例: `trend_following USDJPY --types trend_following,breakout,mean_reversion`
- 例: `--resume ATLAS-2026-0404-001 --target-score 0.80`

## 戦略タイプ自動切替

現在の戦略系統が**行き詰まった場合**（abandoned / converged_stagnation / converged_oscillation / 全バリアント品質下限割れ）、自動的に**現状とは異なる戦略タイプ**に切り替えて新規生成からループを再開する。

### 切替候補プール

以下の6タイプから現在のタイプを除外したものが候補:
```
trend_following / mean_reversion / breakout / momentum / volatility / hybrid
```

`--types <list>` 指定時はそのリストに限定する。

### 次タイプの選択ロジック

1. **過去結果に有望なタイプがある場合 → そのタイプを選択**
   - `ATLAS/strategies/` 配下の全戦略の `backtest/result.json` を走査
   - 現在のタイプを除いた中で **最良スコア** (PF×Sharpe など) を出したタイプを抽出
   - 候補が「未試行」または「平均PF >= 0.9」など有望な兆候があればそれを選択
2. **有望なタイプがない場合 → 候補プールからランダムに選択**
   - 直前のタイプは除外
   - `--no-rotate` 指定時はループ停止

> 厳密な順序ローテーションは行わない。ユーザー要求により「現状と違えば OK」という方針。

### 状態管理

`logs/loop_session.json` に以下を保存（**各 Step 開始時に `current_gen_id` / `current_step` / `step_started_at` を必ず上書き**。Merged-04 冪等性の基盤）:
```json
{
  "session_id": "ATLAS-LOOP-2026-0418-001",
  "session_start": "2026-04-18T10:00:00Z",
  "limit_minutes": 300,
  "threshold_pct": 94,
  "direction_bias": "any",
  "available_types": ["trend_following", "mean_reversion", "breakout", "momentum", "volatility", "hybrid"],
  "current_type": "trend_following",
  "current_gen_id": "ATLAS-2026-0418-005",
  "current_step": "backtest",
  "step_started_at": "2026-04-18T11:23:45Z",
  "gate_pass_generations": ["ATLAS-2026-0418-003"],
  "last_alert": null,
  "type_history": {
    "trend_following": {
      "lineages": ["ATLAS-2026-0408-001"],
      "best_pf": 2.2441,
      "best_sharpe": 0.283,
      "result": "abandoned",
      "abandon_reason": "WR 38% 固定、PF 0.7 収束"
    }
  }
}
```

### 進捗観測ファイル（Merged-05）

各 Step 開始/終了で `logs/loop_progress.json` を**上書き保存**し、外部ターミナルから `tail -f` 相当の観察を可能にする:
```json
{
  "session_id": "...",
  "current_gen": "ATLAS-2026-0418-005",
  "current_generation_num": 3,
  "max_generations": 10,
  "step": "quant_analyst|devil_advocate|converge|improve",
  "status": "running|completed|failed",
  "timestamp": "...",
  "elapsed_minutes": 87
}
```

### スコア運用表（QA-02）

| final_score 範囲 | 判定 | Orchestrator 動作 |
|--------|------|------|
| `>= 0.75`（`--target-score`） | `excellent` | ループ停止、最終レポート |
| `0.30 <= x < 0.75` | `continue` | 改良版生成へ |
| `< 0.30` | `abandon_lineage` | タイプ切替（`--no-rotate` 時は停止） |
| `null`（L1 FAIL等） | `abandon_lineage` | タイプ切替。improvement_rate は N/A 表示 |

### improvement_rate 計算式（QA-04）

`improvement_rate = (child.final_score - parent.final_score) / max(parent.final_score, 0.01) × 100`

- 親子いずれかが `null` → `N/A` 表示
- 親子の `metrics_schema_version` が異なる → `N/A (schema_mismatch)` 表示

### 切替発動条件と動作

| 発動条件 | 動作 |
|---------|------|
| `abandoned` 判定 | 別タイプで新規生成 |
| `converged_stagnation` | 別タイプへ切替 |
| `converged_oscillation` | 別タイプへ切替 |
| 全バリアントが品質下限割れ | 即座に別タイプへ |
| `--no-rotate` 指定時 | 上記の代わりにループ停止 |

### 切替時の引き継ぎ

次タイプへの遷移時は **過去全タイプの失敗履歴をコンテキストとして渡す**。`fx-strategist` エージェントは:
- 以前のタイプで失敗した原因（例: WR 38% 固定、PF 0.7 収束）を回避する設計を試みる
- 通貨ペア・時間足・データ範囲は維持する

## アーキテクチャ

```
/atlas-loop（このSkill = オーケストレーター）
    |
    |-- [新規] fx-strategist Agent --> 戦略コード生成
    |       |
    |-- atlas validate (Python CLI) --> 4段階安全性検証
    |-- code-safety-reviewer Agent --> 検証結果の解釈
    |       |
    |-- atlas backtest (Python CLI) --> 2層バックテスト
    |       |
    |-- atlas metrics (Python CLI) --> 26指標算出
    |-- quant-analyst Agent --> 結果解釈・弱点分析・改善方針
    |-- devil-advocate Agent --> 敵対的レビュー（バイアス検出）
    |-- [統合] 両エージェントの見解をマージ
    |       |
    |-- atlas converge (Python CLI) --> 収束判定
    |       |
    |-- [継続] fx-strategist Agent --> 改良版生成（統合評価に基づく）
    |-- [継続] devil-advocate Agent --> 改善提案のクロスバリデーション
    |-- [停止] 最終レポート出力
```

**エージェント構成（5名体制）:**
| エージェント | モデル | 役割 |
|-------------|--------|------|
| fx-strategist | opus | 戦略コード生成・改良 |
| quant-analyst | opus | 定量評価・弱点分析 |
| devil-advocate | sonnet | 敵対的レビュー・バイアス検出 |
| code-safety-reviewer | sonnet | コード安全性検証 |
| オーケストレーター（このSkill） | - | 全体制御・統合判定 |

## 実行フロー

### フェーズ1: 初期化
1. 引数を解析し、設定を読み込む
2. **エージェント設定読み取り（比較用記録）** — `.claude/agents/fx-strategist.md` と `.claude/agents/quant-analyst.md` のフロントマターから `effort` フィールドを読み取り、`agent_config` として保持する（フィールドなければ `"default"` とする）:
   ```
   fx_strategist_effort = frontmatter["effort"] or "default"   # 例: "xhigh"
   quant_analyst_effort = frontmatter["effort"] or "default"
   agent_effort_label = f"fx:{fx_strategist_effort}/qa:{quant_analyst_effort}"  # 例: "fx:xhigh/qa:xhigh"
   ```
3. `--resume` の場合は以下の順で冪等復元（Merged-04）:
   a. `logs/loop_session.json` を読み、`session_start` / `direction_bias` / `current_type` を**継承**（リセット禁止）
   b. `current_gen_id` と `current_step` を確認し、完了済み artifact（`backtest/result.json`, `evaluation/integrated_report.json`）の存在で部分完了状態を判定
   c. 最後に完了した Step の**次から**再開（例: backtest 完了済 → metrics から開始）
   d. `limit_minutes` の残時間 = `limit_minutes - (now - session_start 分)` を再計算
4. 新規の場合は `session_id` と世代 ID を採番し `loop_session.json` を作成（`agent_config` フィールドを含める）
4. **以降の全 Step 冒頭**で以下を必ず実行（冪等性の基盤）:
   - `loop_session.json` に `current_gen_id` / `current_step` / `step_started_at` を上書き
   - `logs/loop_progress.json` を更新（`status=running`）

### フェーズ2: 初期生成（--resume でない場合）

#### Step 2.1: fx-strategist に生成を委譲
Agent tool で `fx-strategist` エージェントを起動:

> 以下の条件でFXトレード戦略を生成してください。
> - 戦略ID: `<generation_id>`
> - 戦略タイプ: `<戦略タイプ>`
> - 通貨ペア: `<通貨ペア>`
> - 時間足: `<時間足>`
> - 出力先: `ATLAS/strategies/<generation_id>/`
>
> strategy.py, spec.md, config.json, metadata.json を生成すること。
> ATLAS/CLAUDE.md と ATLAS/atlas/common/models.py を読んでインターフェースに準拠すること。

fx-strategist が `metadata.json` を生成したら、オーケストレーター（このSkill）が以下を**追記**する:
```python
# metadata.json に generation_agent_config を追加
metadata["generation_agent_config"] = {
    "fx_strategist_effort": fx_strategist_effort,   # 例: "xhigh"
    "quant_analyst_effort": quant_analyst_effort,   # 例: "xhigh"
    "recorded_at": "<ISO8601 UTC>"
}
# ファイルに書き戻す
```

### フェーズ3: 反復ループ（各世代で実行）

以下を**各世代ごとに順次実行**する。

#### Step 3.1: 安全性検証
```bash
cd ATLAS && .venv/Scripts/python.exe -m atlas.main validate <generation_id>
```

Agent tool で `code-safety-reviewer` エージェントを起動し、検証結果JSONを渡して解釈を依頼。

- **PASS の場合:** 次のステップへ
- **WARNING_ADVISORY / WARNING_INFO**（C4）: PASS 扱いで進行、`evaluation/warnings.log` に記録
- **WARNING_BLOCKING**（C4）: fx-strategist に修正依頼（最大 2 回）
- **FAIL の場合:** fx-strategist に修正指示を渡して再生成（最大 3 回）
- **3 回失敗時:** `converge` を呼ばず **即 `abandoned` として Step 3.4 のタイプ切替分岐へ直行**（Merged-02）。`logs/loop_alerts.log` に CRITICAL で記録

#### Step 3.2: バックテスト実行
```bash
cd ATLAS && .venv/Scripts/python.exe -m atlas.main backtest <generation_id>
```
結果 JSON（`backtest/result.json`）を保存。

**失敗モード分岐（Merged-02）:**

| 結果 | Orchestrator 動作 |
|------|------------------|
| L1 PASS + L2 PASS | 通常フロー、Step 3.3 へ |
| L1 PASS + L2 SKIPPED（条件付スキップ等） | `integrated_report.json` の `l2_skipped_reason` に明示、Step 3.3 へ進むが final_score は L1 のみで算出 |
| L1 FAIL（PF/Sharpe 等の閾値未達） | **`converge` を呼ばず即 `abandoned` として Step 3.4 タイプ切替分岐へ**。L2 指標は `null` のまま `integrated_report.json` に記録 |
| 実行エラー（UnicodeError, OOM 等） | `logs/loop_alerts.log` に CRITICAL 記録、リトライ 1 回、再度失敗で当該世代 `abandoned` |

#### Step 3.3: メトリクス算出・評価
```bash
cd ATLAS && .venv/Scripts/python.exe -m atlas.main metrics <generation_id>
```

Agent tool で `quant-analyst` エージェントを起動し、メトリクスJSONを渡す:

> 以下のFXトレード戦略のバックテスト結果を評価してください。
> - 戦略ID: `<generation_id>`
> - メトリクスJSON: [metricsの出力]
>
> 1. 3層スコアリング結果の妥当性検証
> 2. Backtest Gate判定
> 3. 弱点の因果チェーン分析
> 4. 改善指示の策定（最大3件）
>
> ATLAS/strategies/<generation_id>/evaluation/ に report.json と summary.md を出力すること。

#### Step 3.3b: 敵対的レビュー（devil-advocate）

Agent tool で `devil-advocate` エージェントを起動し、quant-analystの評価を検証:

> 以下のquant-analystによる評価レポートに対して、敵対的レビューを実施してください。
> - 戦略ID: `<generation_id>`
> - メトリクスJSON: [metricsの出力]
> - quant-analystの評価レポート: [Step 3.3の report.json]
>
> 楽観バイアス検出、因果チェーン検証、改善提案の実現可能性、既知失敗パターンとの照合を行うこと。
> ATLAS/strategies/<generation_id>/evaluation/adversarial_review.json に出力すること。

#### Step 3.3c: 評価統合

quant-analyst と devil-advocate の見解を統合する。devil-advocate の各 `bias_detected` エントリの `adoption_level` で 3 段階分岐する（QA-05）:

| adoption_level | Orchestrator 動作 |
|----------------|------------------|
| `must_fix` | 改善指示を必ず修正。修正せずに次世代生成した場合は当該改良を中止 |
| `should_consider` | `improvement_directives` に追記のみ。fx-strategist が判断で採否を決め、却下時は `spec.md` に理由を明記 |
| `informational` | `integrated_report.json` に記録のみ、ループは通常進行 |

- devil-advocate が `abandon_recommendation=true` を返した場合 → 収束判定で `abandoned` 扱い、タイプ切替へ
- quant-analyst 出力が欠損（エージェント失敗）→ `integrated_report.json` に `quant_missing=true` を明示、devil-advocate 単独判定でループ継続は不可、当該世代 `abandoned`
- devil-advocate 出力が欠損 → `adversarial=missing` フラグを立てて quant-analyst 評価を採用、次世代へ（PA-06）
- 統合結果を `ATLAS/strategies/<generation_id>/evaluation/integrated_report.json` に出力

#### Step 3.4: 収束判定
```bash
cd ATLAS && .venv/Scripts/python.exe -m atlas.main converge <generation_id>
```

**Step 3.4a: converge 出力ガード（Merged-02）**

以下を必ず実行:
1. 返却 JSON に `status` / `score`（`final_score`）が**欠損または null** → **`abandoned` 扱いに強制上書き**し `logs/loop_alerts.log` に CRITICAL 記録
2. `score < 0.30` → `abandoned` （スコア運用表）
3. `score >= 0.75` → `excellent`
4. それ以外で `status==continue` → Step 3.5 へ

**Step 3.4b: 収束判定分岐**

| 判定 | アクション |
|------|----------|
| `excellent` | ループ停止、最終レポート。`gate_pass_generations` に追加 |
| `converged_stagnation` | タイプ切替発動（`--no-rotate` 時は停止） |
| `converged_oscillation` | タイプ切替発動（`--no-rotate` 時は停止） |
| `abandoned` | タイプ切替発動（`--no-rotate` 時は停止） |
| `max_generations` | ループ停止。世代上限到達を報告 |
| `continue` | Step 3.5 へ |

**Step 3.4c: 世代完了時の必須アクション（Merged-01）**

上記いずれの分岐でも、次世代に進む/ループ停止する前に**必ず**以下を実行（順不同）:

1. **`logs/loop_metrics.csv` に追記** — ヘッダがなければ作成し、1 行追記:
   ```
   session_id,generation_id,generation_num,duration_sec,phase_validate_sec,phase_bt_sec,phase_metrics_sec,phase_eval_sec,gate_result,final_score,converge_result,schema_version,agent_effort
   ```
   - 各 phase の秒は `step_started_at` の差分から算出
   - `agent_effort` には初期化時に読み取った `agent_effort_label`（例: `"fx:xhigh/qa:xhigh"`）を記録
2. **git commit + push** — 対象は `ATLAS/strategies/<gen_id>/` と `logs/`:
   ```bash
   cd <repo_root> && git add ATLAS/strategies/<gen_id> logs/loop_session.json logs/loop_metrics.csv logs/loop_progress.json
   git commit -m "[atlas] <gen_id> - <converge_result>（score=<score>）"
   git push
   ```
   （コミット/プッシュ失敗は警告ログのみ、ループは継続）
3. **Gate PASS → FTS ペーパー投入案内** — `gate_result.passed==true` かつ `final_score >= target_score` の場合:
   - `loop_session.json` の `gate_pass_generations[]` に追加
   - 最終レポートに `fts paper add <gen_id>` 相当のコマンド例を明示

**Step 3.4d: 5 時間 94% ガード（Merged-03）**

世代完了後、次世代を開始する前に経過分を再計算:
- `elapsed_min >= limit_minutes × (threshold_pct / 100)` → 現世代 artifact 保存完了を確認し**フェーズ4（最終レポート）へ強制移行**
- `logs/loop_alerts.log` に `timeout_guard_triggered` を記録し、ユーザーに報告

**タイプ切替発動時の手順（PA-03 具体化）:**

1. `logs/loop_session.json` の `type_history[current_type].result` と `abandon_reason` に終了理由を記録
2. `ATLAS/strategies/` 配下の過去結果から「現在のタイプを除く有望タイプ」を探索
   - 各タイプの best_pf / best_sharpe / best_final_score を集計
   - 有望判定基準: `final_score >= 0.45 AND PF >= 1.0`（単独 PF 基準は誤検出を招くため AND 条件）
3. 有望タイプが見つかればそれを選択、見つからなければ `available_types` から `current_type` を除いてランダム選択
4. **`failed_patterns` ブロックの生成**（fx-strategist への必須コンテキスト）:
   ```json
   {
     "failed_patterns": [
       {
         "type": "trend_following",
         "lineages": ["ATLAS-2026-0408-001", ...],
         "best_pf": 2.2441,
         "best_sharpe": 0.283,
         "abandon_reason": "WR 38% 固定、Sharpe 0.3 収束",
         "fatal_params": ["atr_expansion_ratio >= 1.5", "rsi_exit <= 52"]
       }
     ]
   }
   ```
   `loop_session.json` の `type_history` 全タイプ分と、各タイプ直近 3 lineages の `evaluation/integrated_report.json` から抽出する
5. 次タイプを `current_type` に設定、`direction_bias` は継承してフェーズ2（初期生成）に戻る
6. fx-strategist プロンプト**冒頭固定セクション**として `failed_patterns` を埋め込み、「これらのパラメータ組合せ・失敗パターンは回避すること」と明示

#### Step 3.5: 改良版生成（継続時のみ）

改良コンテキストを取得:
```bash
cd ATLAS && .venv/Scripts/python.exe -m atlas.main context <generation_id> --mode improve
```

Agent tool で `fx-strategist` エージェントを起動し、改良版を生成:

> 以下のFXトレード戦略の改良版を生成してください。
> - 親戦略ID: `<generation_id>`
> - 新戦略ID: `<new_generation_id>`
> - パラメータ変更上限: 3箇所
>
> **改良コンテキスト:**
> [contextコマンドの出力をそのまま渡す]
>
> ATLAS/strategies/<new_generation_id>/ に出力すること。
>
> **重要:** 改良コンテキストに devil-advocate の敵対的レビュー結果が含まれている場合、
> その指摘事項にも対処すること。

#### Step 3.5b: 改善提案のクロスバリデーション（devil-advocate）

Agent tool で `devil-advocate` エージェントを起動し、改良版を検証:

> fx-strategistの改良版戦略コードに対して敵対的レビューを実施してください。
> - 親戦略ID: `<generation_id>` / 新戦略ID: `<new_generation_id>`
> - 改良版コード: [生成された strategy.py]
> - 改良コンテキスト: [contextの出力]
>
> 副作用予測、制約違反チェック、既知失敗パターンとの照合を行うこと。

- `severity=high` → fx-strategist に修正を依頼（1回まで）
- `abandon_recommendation=true` → この改良を中止、新規生成へ

**Step 3.1 に戻る（新世代で反復）**

### フェーズ4: 最終レポート

ループ完了時に以下を出力する。

#### ループ中の各世代ログ（蓄積表示）
```
--- 世代 ATLAS-2026-0404-001 (1/10) ---
[検証]     PASS (4/4 stage通過)
[BT]       PF:1.45 Sharpe:1.12 MaxDD:15.2% Gate:PASS
[評価]     final_score: 0.62 (合格)
[敵対的RV] バイアス:0件 リスク警告:1件(medium) -> 評価維持
[収束判定] 継続（目標0.75未達、改善率+8.2%）
[改良]     -> ATLAS-2026-0404-002 生成完了
[改良RV]   devil-advocate: PASS（副作用リスクなし）
```

#### 最終サマリー
```
=== ATLAS 自動ループ完了 ===
停止理由: <判定結果>
総世代数: XX
実行世代: XX

--- スコア推移 ---
ATLAS-2026-0404-001: 0.38 ########
ATLAS-2026-0404-002: 0.45 #########
ATLAS-2026-0404-003: 0.52 ##########
ATLAS-2026-0404-004: 0.61 ############
ATLAS-2026-0404-005: 0.68 #############
ATLAS-2026-0404-006: 0.76 ############### * 優良

--- 最優秀戦略 ---
世代ID: ATLAS-2026-0404-006
final_score: 0.76
戦略タイプ: <タ���プ>
系譜: 001 -> 002 -> 003 -> 004 -> 005 -> 006

次のステップ:
  /atlas-export ATLAS-2026-0404-006 — 本番候補としてエクスポート
  /atlas-status — 全世代の詳細を確認
  /atlas-history ATLAS-2026-0404-006 — 改良履歴を表示
```

## エラーハンドリング

### エージェント別障害対応表（PA-06）

| エージェント | 失敗時の挙動 | リトライ後 |
|------------|------------|-----------|
| `code-safety-reviewer` | 3 回リトライ | 3 回失敗で当該世代 `abandoned`、converge 呼ばず Step 3.4 タイプ切替へ |
| `quant-analyst` | 3 回リトライ | 3 回失敗で当該世代 `abandoned`（devil-advocate 単独判定は不可） |
| `devil-advocate` | 3 回リトライ | 3 回失敗でも `adversarial=missing` フラグを立てて quant-analyst 評価を採用、次世代へ（安全側）|
| `fx-strategist` | 3 回リトライ | 3 回失敗で当該世代 `abandoned`、タイプ切替発動 |

### その他

- Python CLI が例外を返した場合、エラー JSON の内容に基づいて判断。UnicodeDecodeError は `encoding='utf-8'` で再試行
- 全バリアントが品質下限割れした場合、自動的に次の戦略タイプにローテーション（`--no-rotate` 時は提案のみ）
- **3 回リトライ後の廃棄時・タイムアウト停止時には `logs/loop_alerts.log` に CRITICAL 記録**（DO-06）:
  ```json
  {
    "timestamp": "...",
    "level": "CRITICAL",
    "session_id": "...",
    "generation_id": "...",
    "reason": "fx_strategist 3 retries exhausted",
    "action_taken": "abandoned, type rotation"
  }
  ```
  `loop_session.json` の `last_alert` フィールドにも最新アラートを保存。`/atlas-status` 実行時に `last_alert` を冒頭表示する
- **AUDIT-P0-001 (2026-04-18) 由来の必須ルール: アラート数値は実データ集計のみ** —
  `logs/loop_alerts.log` に書き込む `reason` / `action_taken` フィールド内の**数値**（連続失敗回数、
  経過分、リトライ回数、廃棄世代数等）は必ず `logs/loop_session.json` / `logs/loop_metrics.csv` /
  History Store の**実データから集計した値**を記載すること。LLM の記憶や推測による数値記入を**禁止**する。
  過去事例: 「20+ 連続 FAIL」と書かれたログが実データ max=5 であり、存在しない streak_counter バグを誤検出した。
  実装: ログ書き込み前に Python CLI または Read で該当ファイルを読み、集計値を取得してから文字列を組み立てる。
- ユーザーによる中断（Ctrl+C）時、`loop_session.json` と History Store に状態保存済み。`--resume` で再開可能

## 自動実行（ユーザー操作なし）

完全自動実行するには:
1. `dontAsk` パーミッションモードで Claude Code を起動
2. permissions.allow にATLAS用のBashパターンを登録
3. `/atlas-loop <引数>` を実行

定期実��するには:
```
/loop 10m /atlas-loop --resume <latest_generation_id>
```

## 注意事項
- 長時間実行となるため、各世代の開始時に進捗を表示
- 全世代の中間結果は History Store にリアルタイム保存
- `--dry-run` で実行計画と推定ステップ数を事前確認可能
- ループ中断後は `/atlas-status` で現在状態を確認可能
- 各エージェントは順次実行される（並列実行はAgent Teams実験機能で対応予定）

## 関連ドキュメント

- **FTS forward test 候補選定メソドロジー**: `ATLAS/docs/fts_selection_methodology.md`
  - ループ開始前・終了後の方向性判断に必ず参照すること
  - 過去 PASS 戦略集合の偏り（短方向 0 件、特定 instrument/timeframe/method の脱落）から、次セッションで生成すべき戦略タイプ・通貨ペア・方向を決定する根拠資料
  - 2026-05-06 時点の実測: 189 PASS の真の多様性は 7 unique buckets（inst×tf×method×direction）。`class_name` / `tag_cluster_id` 単位 dedup は機能しないため、本メソドロジーの 5 段階フィルタが正規手順
- **Backtest Gate 階層化**: `ATLAS/CLAUDE.md` § Backtest Gate基準
- **戦略タグ仕様**: `ATLAS/docs/Redesign_v2_Plan.md` §3.6 (StrategyTags 運用ルール)

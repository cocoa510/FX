---
description: 複数 PC 間の作業引継ぎ。pull / push / status / checkpoint のサブコマンドを取る
argument-hint: <pull|push|status|checkpoint> [--no-push] [--skip-pull] [--message <text>]
---

# /handoff — 複数 PC 間の作業引継ぎ

> 別 PC で作業を再開・離脱する際に、git と `logs/handoff_note.md` を経由して
> 「何をやっていたか」「次は何をすべきか」を機械可読な形で引き渡す。

## 引数の受け取り

Claude は `$ARGUMENTS` の先頭トークンをサブコマンド（`pull` / `push` / `status` / `checkpoint`）として解釈し、
残りをオプション（`--no-push` / `--skip-pull` / `--message <text>`）として処理すること。

サブコマンドが空の場合は `status` をデフォルトとする。

## 設計思想

- **会話コンテキストは shell を超えて引き継げない**が、ファイルと git は超えられる
- **機械可読 + 人間可読**のハイブリッド note で、別 PC の新 Claude セッションが
  `/handoff pull` で作業状態を完全復元できるようにする
- ATLAS の「世代ごとコミット」ルールと共存するため、WIP コミットには
  明示的に `[wip:handoff]` プレフィックスを付ける

## 引数

```
/handoff <subcommand> [options]
```

| サブコマンド | 用途 |
|-------------|------|
| `pull` | 別 PC から来た時。最新取得 → note 表示 → 作業再開支援 |
| `push` | 現 PC を離れる時。WIP コミット + note 更新 + push |
| `status` | 現状確認のみ。副作用なし |
| `checkpoint` | 途中保存。WIP コミットせず note だけ更新（push のみ実行可能） |

オプション:

| オプション | デフォルト | 説明 |
|----------|----------|------|
| `--no-push` | なし | push/checkpoint で remote への push を抑制 |
| `--skip-pull` | なし | pull で `git pull` を抑制（状態確認のみ） |
| `--message <text>` | なし | WIP コミット or note に追記するメッセージ |

## ファイル配置

| パス | 役割 |
|-----|-----|
| `logs/handoff_note.md` | 人間可読の引継ぎノート（git 管理下） |
| `logs/handoff_state.json` | 機械可読の状態スナップショット（git 管理下） |

両ファイルは `.gitignore` に含めず、必ずコミットする。

`logs/` はプロジェクトルート基準。現在の CWD（`c:/data/works/FX/`）配下の `logs/` を使用する。
ATLAS サブプロジェクト内で呼ばれた場合は `ATLAS/logs/` に書く（CWD に追従）。

---

## サブコマンド詳細

### `/handoff pull` — 別 PC から来た時

**手順**:

1. **git 同期**
   ```bash
   git fetch origin
   git status
   git pull --ff-only origin <current-branch>
   ```
   - `--ff-only` で失敗した場合（ローカルに未コミット変更あり）は停止して報告
   - untracked ファイルがある場合は警告（別 PC で作業途中の可能性）

2. **引継ぎノート読み込み**
   - `logs/handoff_note.md` が存在すれば `Read` で全文取得
   - `logs/handoff_state.json` を `Read` で取得
   - 存在しない場合は「初回引継ぎ or 以前は旧方式」と報告

3. **現状要約を出力**
   - 最新コミット 10 件（`git log --oneline -10`）
   - 現在のブランチ、未コミットファイル
   - Note に書かれていた「次にやること」を引用
   - 実行中ループがあれば `logs/loop_session.json` から状態表示

4. **作業再開の提案**
   - Note の「次にやること」に基づいて次のアクションを提示
   - ユーザーの確認を待つ（勝手に作業開始しない）

### `/handoff push` — 現 PC を離れる時

**手順**:

1. **変更確認**
   ```bash
   git status
   git diff --stat
   ```

2. **引継ぎノート生成**
   Claude 自身が直近の会話内容を踏まえて以下を生成し、`logs/handoff_note.md` に **上書き** 保存:

   ```markdown
   # Handoff Note

   **最終更新**: <ISO datetime> @ <hostname>
   **ブランチ**: <branch>
   **直前のコミット**: <short_sha> <subject>

   ## 現在の作業（1 行サマリ）

   <Claude がトピックを 1 行で要約>

   ## 詳細コンテキスト（3〜5 行）

   <直近の会話で何を目的に何を実施したか>

   ## 未コミット変更 / WIP コミット対象

   - `path/to/file1.py` (modified): <1 行理由>
   - `path/to/file2.md` (new): <1 行理由>

   ## 次にやること

   1. <具体アクション>
   2. <具体アクション>
   3. <具体アクション>

   ## 関連文書・コマンド

   - 参照: `docs/redesign_drafts/14_experiment_a_d_results.md`
   - 次の実行コマンド例: `python scripts/xxx.py`
   - 実行中ループ: なし / ATLAS-2026-MMDD-NNN（`logs/loop_session.json`）

   ## 引継ぎ時の注意

   <もしあれば: 危険な未解決事項、半実装状態の警告など>
   ```

3. **状態スナップショット生成**
   `logs/handoff_state.json`:
   ```json
   {
     "generated_at": "<ISO>",
     "hostname": "<hostname>",
     "branch": "<branch>",
     "head_sha": "<full SHA>",
     "uncommitted_files": ["path/to/file1.py", "..."],
     "latest_commits": [
       {"sha": "...", "subject": "...", "date": "..."}
     ],
     "loop_session_active": false,
     "next_actions": ["...", "..."]
   }
   ```

4. **WIP コミット**（変更がある場合のみ）
   - `git add <変更ファイル + logs/handoff_note.md + logs/handoff_state.json>`
   - `git commit -m "[wip:handoff] <Claude 生成サマリ> @ <hostname>"`
     - 秘密情報を含むファイル（`.env` 等）は絶対に含めない
     - 変更がない場合でも note + state の更新だけはコミット
   - コミットメッセージには `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` を付与

5. **push**（`--no-push` でなければ）
   ```bash
   git push origin <branch>
   ```
   - 失敗時はローカルコミットは保持したまま報告

6. **完了報告**
   - push 済み SHA とリモート URL を表示
   - 別 PC で `/handoff pull` を叩く手順を案内

### `/handoff status` — 現状確認のみ

副作用なし。以下を表示:

- 現ブランチ・最新コミット 5 件
- 未コミットファイル一覧
- `logs/handoff_note.md` の冒頭 20 行（存在すれば）
- リモートとの差分（`git rev-list --left-right --count HEAD...@{u}`）

### `/handoff checkpoint` — 途中保存

WIP コミットは作らず、`logs/handoff_note.md` と `logs/handoff_state.json` の
**更新だけ** を行う。既存の完成コミットに混ぜたくない場合に使う。

- `--no-push` がない限り note 更新を単独コミット
  （`[docs] handoff: checkpoint @ <hostname>`）
- コード変更が残っていてもそれは触らず、note に「未コミット変更あり」と記録

---

## 実装ガイド（Claude 向け）

### pull 時の再開支援ロジック

1. `logs/handoff_state.json` の `loop_session_active=true` なら
   「ループ実行中でした。再開しますか？停止しますか？」とユーザーに確認
2. `next_actions` の先頭要素を提案として提示
3. **ユーザーが明示的に「進めて」と言うまで作業は開始しない**

### push 時のガードレール

- ATLAS の世代ごとコミットルール（世代完成品は `[atlas]` プレフィックス）を
  WIP と混同しない。世代完成品は個別にコミット済みであることを前提とする
- `[wip:handoff]` プレフィックスは**強制**。通常コミットと分離できる形にする
- 秘密情報検出: `.env`, `credentials.json`, `*_secrets.json` は add から除外
- force push は絶対にしない

### Windows 環境での注意

- hostname は `$env:COMPUTERNAME` (PowerShell) / `hostname` (bash) で取得
- ISO datetime は UTC で記録（ローカル TZ 付記）
- LF/CRLF 警告は無視してよい

---

## 使用例

### シナリオ 1: PC-A で作業 → PC-B に移る

```
[PC-A] ユーザー: /handoff push --message "Step 4 simulation 完了、次は Phase 0c 着手"

[Claude]:
  → 未コミット変更 3 件を確認
  → logs/handoff_note.md 生成
  → WIP コミット: "[wip:handoff] Step 4 simulation 完了、次は Phase 0c 着手 @ PC-A"
  → push 完了 (origin/master @ 18bebb3)
  → 別 PC で `/handoff pull` を実行してください

[PC-B] ユーザー: /handoff pull

[Claude]:
  → git pull 完了
  → 前回 @ PC-A: "Step 4 simulation 完了、次は Phase 0c 着手"
  → 次にやること:
      1. 2019-2022 secondary BT のバックフィル実装
      2. 既存 73 戦略への適用
      3. Gate 再判定
  → 1 から始めますか？
```

### シナリオ 2: 離席前の簡易保存

```
ユーザー: /handoff checkpoint --message "昼食中断、午後続行"

[Claude]:
  → handoff_note.md 更新のみ（WIP コミットなし）
  → コード変更は手元に保持
  → 復帰時は /handoff status で確認
```

---

## 収束・終了条件

- 各サブコマンドは単発実行で完結（ループではない）
- `pull` でコンフリクトが発生した場合は自動解決を試みず停止・報告
- `push` でリモート拒否が発生した場合は保留し、原因分析（divergent branches 等）をユーザーに提示

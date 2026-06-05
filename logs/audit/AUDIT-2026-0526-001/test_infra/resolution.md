# テストインフラ問題 調査・修正 結果（AUDIT-2026-0526-001 test-infra）

専門家チーム（code-safety-reviewer / quant-analyst）調査 + 親による検証・実装。

## #1 sandbox メモリテスト hang → 真因は「RSS 隔離不全」（当初診断より広い）

### 確定した根本原因
`_SandboxWorker._mem_poll`（`atlas/validator/sandbox_runner.py`）は psutil で**プロセス全体の RSS** を監視し、512MB 超過で MemoryError を結果キュー（`maxsize=1`）に注入する。サンドボックス系テストは実 `_SandboxWorker` を生成するため、**フルスイートで 680+ テスト実行後にプロセス RSS が 512MB を超える**と、新規 worker の `_mem_poll` が起動直後に発火し:
- (a) 結果キューを MemoryError で満杯化 → テストの `_results.put(...)`（timeout なし blocking）が**永久 hang**（`test_memory_error_raised_when_rss_exceeds_limit`、81% 地点）
- (b) 無関係なサンドボックステストに MemoryError を注入して失敗させる（hang 解消後に顕在化した 8 件）

ファイル単独実行（低 RSS）では再現せず、フルスイートでのみ顕在化する非決定性だった。

### 適用した修正（3層）
1. **テスト隔離（主修正）**: `tests/unit/conftest.py` に autouse フィクスチャを新設。sandbox/validator 系テストモジュールで `psutil.Process` を低 RSS にモックし、実プロセスメモリへの依存を排除（決定論化）。これで hang + 8 件の汚染失敗を一括解消。
2. **本番堅牢性（_loop 非対称解消）**: `sandbox_runner.py:94` の ok 側結果 put に `timeout=_PER_CALL_TIMEOUT_SEC` を付与（err 側 CSR-005 と対称化）。`_mem_poll` がキューを満杯化した状態で func が正常 return した際、call() が abandoned で drain しない場合の worker スレッド永久ブロック（リーク）を防止。
3. **回帰テスト**: `test_loop_ok_delivery_does_not_block_when_queue_full`（満杯キューで _loop が hang せず後続ジョブを処理）+ `test_memory_error_raised_when_rss_exceeds_limit` を psutil モックで決定論化。

### ⚠️ 本番への潜在懸念（要判断・本修正の対象外）
`_mem_poll` がプロセス全体 RSS を測る設計のため、**ATLAS 検証プロセスのベースライン RSS が 512MB を超える文脈（例: pandas/numba/データ常駐の重いプロセス内で validate を実行）では、全戦略の sandbox 検証が起動直後に MemoryError で偽陽性 REJECT される**。通常の `atlas validate` は軽量プロセスのため顕在化していないと推測されるが、設計上の脆弱性。恒久対策候補: worker 起動時 RSS からの**増分**で判定する / サブプロセス分離 / 検証専用の RSS ベースライン補正。

## #2 Numba JIT キャッシュエラー（テスト固有・本番影響なし）

### 根本原因
`tests/unit/test_numba_kernels.py:267` がテストメソッド内の**ローカルクロージャ** `_dummy` に `@njit(cache=True)` を付与。numba 0.65.0 は `test_njit_guard_exports_callable.<locals>._dummy` のソース locator を作れず `RuntimeError: cannot cache function: no locator available` を送出。本番カーネル（`atlas/backtest/_numba_kernels.py`）は全てモジュールトップレベル定義で cache=True 正常動作（影響なし）。

### 適用した修正
当該テストの `@njit(cache=True, fastmath=False)` から `cache=True` を除去（本テストの目的は njit ガードが callable を返す確認で、キャッシュは検証対象外）。`test_numba_kernels.py` 37 passed。

## 検証
- sandbox 3 ファイル + numba: 全 pass（conftest 適用下、高 RSS モックする test_mem_poll も上書きで正常）
- full `tests/unit` 再実行で hang 解消 + 8 件の汚染失敗が解消されること（最終確認実行中）

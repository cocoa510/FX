# AUDIT-2026-0529-001 第2チーム検証サマリー

**実施日**: 2026-05-29
**検証体制**: 専門家 4名 (RE/DE/DM/QA) + devil-advocate 1名 (メタ) = 計 5名並列
**目的**: 第1チーム監査 (7専門家 + devil-advocate 3名) の事実誤認・過大評価・過小評価・見落としを独立に再現検出
**先行パターン**: AUDIT-2026-0525-002 (第1チーム → 第2チーム経験的再現で critical/high が訂正された前例)

---

## エグゼクティブサマリー

### 81 finding に対する第2チーム判定の重大変化

| 区分 | 件数 | 内訳 |
|---|---|---|
| **完全合意** | 71 件 | 第1チームと severity・rationale 共に一致 |
| **訂正 (must_fix の重大訂正)** | 3 件 | DE-311 (high→medium 差戻), DE-301 (high→medium), CSR-302 (low→medium 戻し) |
| **論述欠陥指摘** | 5 件 | DM-306, DE-311, QA-301, RE-302, PA-307 |
| **見落とし発見** | **8 件 (medium 3 + low 5)** | RE-MISSED 3, ATLAS-MISSED 4, DM-MISSED 1 |
| **構造的見落とし領域** | **7 領域** | scripts/, deploy/, pyproject 依存等 |

### 確定 must_fix の修正 (8件 → 6件 high + 2件 medium 格下げ)

| ID | 第1チーム判定 | 第2チーム判定 | 訂正理由 |
|---|---|---|---|
| **RE-302** | high (must_fix) | **high 維持** ✓ | 経路 (a)(b)(c) 3点全て独立再現確認 |
| **RE-301** | high (must_fix) | **high 維持** ✓ | INC-0526-001 同型確認 |
| **DM-306** | high ↑ upgrade | **high 維持** ✓ | 「全 3 経路 dead」表現は過大だが severity 妥当 |
| **DM-302** | high (must_fix) | **high 維持** ✓ | 4 メソッド全て grep で 0 件確認 |
| **DE-303** | high (must_fix) | **high 維持** ✓ | 「完全 silent」表現は過大 (WARN ログあり) だが severity 妥当 |
| **QA-301** | high (must_fix) | **high 維持** ✓ | 数値 0.60/0.70 = 0.857 再現一致 |
| **DE-311** | high ↑ upgrade | **medium に差戻** ⚠️ | **本番経路の取り違え。UnifiedRunner は StateStore 非使用、StateManager 永続化で持つ。settings.py が production+memory 起動拒否済み** |
| **DE-301** | high (must_fix) | **medium に格下げ** ⚠️ | **Live 22戦略の最大 period は SMA50 のみ、ema_800 (069) は paper のみで Live 経路非該当** |

→ **真の must_fix は 6 件 (high)。8 件と報告した第1チームに 2 件の過大評価**

---

## 重大訂正の詳細

### 訂正 1: DE-311 high → medium (本番経路の取り違え)

**第1チーム主張**:
- AioRedisBackend 未実装 → 本番再起動で State 全消失 → INC-2026-0527-001 (6日間 Live 注文ゼロ) 同型再発構造
- devil-advocate-C が medium → high に upgrade

**第2チーム検証結果**:
- 本番経路 `scripts/run_unified.py` → `UnifiedRunner` は **StateStore を一切配線していない** (grep で本番呼出 0 件)
- 永続化は **`StateManager`** が担当: `state.json` 直書き + JSONL append + `os.replace` アトミック書込
- `main.py` で `StateStore()` は生成されるが、`main.py` 自体が本番 deployment ではない (dev/staging 用 FastAPI)
- **`settings.py:402-425` の `_enforce_production_state_backend` が `production+memory` 組合せを起動時に拒否** (fail-loud)
- `main.py:613-619` が `state_backend='redis'` 選択時に明示的 `RuntimeError`
- **INC-2026-0527-001 の真因**: `_sync_risk_state_from_slot` の `is_live` ガード欠如 (commit 873ae89 で修正済) → **AioRedisBackend とは別経路**

**結論**: 第1チーム devil-advocate-C の upgrade は **本番経路の取り違えによる楽観バイアス是正の過剰反応**。medium 妥当 (将来 main.py 廃止 / FastAPI 経路の再評価時の課題として残置)。

### 訂正 2: DE-301 high → medium (Live 戦略影響の事実誤認)

**第1チーム主張**:
- `MAX_WARMUP_BARS=5000` クランプで `ema_800` 戦略 (ATLAS-2026-0508-069) の EWM 残差 3.78e-6 が Live に永続
- Parity 許容 1e-10 の 38000 倍

**第2チーム検証結果**:
- **Live execution_mode の 22 戦略を全数調査**: 最大 period は **SMA50 (ATLAS-2026-0506-005)** のみ、384 を超える戦略は **0 件**
- ATLAS-2026-0508-069 (ema_slow_period=800) は `runner_config.execution_mode='paper'` で **Live 経路に乗っていない**
- `metadata.live_eligible=true` と `execution_mode='paper'` は別概念であり、後者が実 Live 実行を制御

**結論**: 構造リスク (period>384 戦略の Live 昇格時に Parity 劣化) は実在するが、**現時点で「Live 影響あり」根拠はない**。medium 格下げ妥当。修正対象は `scripts/import_atlas_strategy.py` の period ゲート追加 (これは第1チームが見落とした、後述 #1 参照)。

### 訂正 3: CSR-302 low → medium (脅威モデルの狭さ訂正)

**第1チーム devil-advocate-A 判定**: medium → low (「攻撃者が metadata.json を書き換える前提が必要、ATLAS はクローズドツール」)

**第2チーム検証結果**: medium 維持
- ATLAS は **LLM (fx-strategist agent) が自動で metadata.json を生成** する設計
- LLM がプロンプトインジェクション等で悪意ある parent_id を含む metadata を生成する経路は現実的
- 「攻撃者が直接書換」前提は脅威モデルとして狭すぎる

---

## 論述欠陥 (5件)

第1チームの記述で **事実は正しいが表現が誇張** な箇所:

| ID | 欠陥 | 修正案 |
|---|---|---|
| **DM-306** | 「全 3 経路 dead」は structlog/AuditLog 経路の確認不足。前回 AUDIT-0525-002「全 KS dead」と同型の過大表現 | 「主要通知 3 経路 (Prometheus/Email/Dashboard) dead、structlog のみ残存」に修正 |
| **DE-311** | 「INC-2026-0527-001 同類」は不正確。INC-0527 の真因は paper/live ガード欠如、DE-311 は Redis 未実装で根本原因が別。**INC-2026-0526-001 (exposure 上限張り付き) と類似度高い** | 引用 INC を 0527 → 0526 に修正 |
| **QA-301** | 「soft_score ≈ 0.857」は 4 指標全 None ケース限定。3 指標 None + Top3 あり時は FLOOR=valid_weight で残り max でのみ PASS。発生条件の説明が曖昧 | 具体的 trigger 条件を明示 (walks<10 かつ Top3 stripped 不存在) |
| **RE-302** | 1 行修正提案で `entry_rollback` 合流時、既約定済 order への cancel が OANDA 404 を返すセカンダリ処理が未記載 | rollback 失敗時の二次処理仕様を追加 |
| **PA-307** | devil-advocate-B が timeout 乖離例示の誤りを指摘した一方、**`OrderSubmissionGuard` シングルトン共有による連鎖リスク** (Slot A の失敗で Slot B の fail-closed REJECT trigger) を未指摘 | PA-301 (metrics 未配線) と組合せで再評価 |

---

## バイアス是正 (4件、devil-advocate の判定が過剰)

| ID | 第1チーム判定 | バイアス | 第2チーム判定 |
|---|---|---|---|
| **DM-301** | high → medium | **過小評価**: FillProcessor event publish 経路の確認なしで「代替経路生存」と断定 | medium だが要再確認 |
| **QA-302** | high → medium | **過大降格**: 「QA-301 と相殺」論が同一シナリオで成立する保証なし | medium 維持だが「相殺」根拠は弱い |
| **DE-302** | medium → low | **過大降格**: ATLAS 規約が docstring のみなら将来 LLM 生成で遅延 register が発生しうる | medium 維持推奨 |
| **QT-301/302/303** | high → medium | **過大降格**: RE-201 回帰防止テストの構造的ギャップを「テスト設計問題」で済ませるのは単純 | medium 維持だが本番経路のテスト不在として再評価必要 |

---

## 見落とし発見 (8件、第1チーム未検出)

### RE-MISSED (3件、risk-execution-engineer 観点)
- **RE-MISSED-301 [medium]**: `fx_fills_total` Prometheus metric 定義済だが `inc_fill` 本番未呼出 (DM-301 と部分重複)
- **RE-MISSED-302 [medium]**: `_poll_cycle` の `account_info` 失敗時 early return が heartbeat 処理を全停止 → `live_orders_silent` と reconciliation スキップ (RE-305 複合)
- **RE-MISSED-303 [low]**: `entry_rollback_no_trade_id` safety net (L749) が RE-302 経路で発火しない (`open_trade_id` が non-empty OANDA Order ID のため)

### ATLAS-MISSED (4件)
- **ATLAS-MISSED-001 [medium]**: scorer/Tier 2 sensitivity の二重定義
- **ATLAS-MISSED-002 [low]**: Tier 1 secondary PF 閾値設計疑念
- **ATLAS-MISSED-003 [low]**: live promotion 境界の明示不在
- **ATLAS-MISSED-004 [low]**: 他 CLI 引数 (instrument, timeframe 等) の path traversal 未網羅

### DM-MISSED (1件)
- **DM-314 [low]**: `FxEventBusDedupSpike` アラートが本番 InMemoryEventBus 環境で事実上 dead (`inc_event_bus_dedup` は `redis_adapter.py` のみ呼出)

### 構造的見落とし領域 (7領域)

**最重要**: **`scripts/import_atlas_strategy.py` の period 上限ゲート未実装** — DE-301 (high → medium 格下げ) の正規修正対象ファイルだが、**7 専門家・3 devil-advocate 全員がスコープ外にした**。`ema_period > 384` の戦略の live_mode 拒否ロジックが完全不在。

| # | 領域 | 潜在リスク |
|---|---|---|
| 1 | `scripts/import_atlas_strategy.py` | DE-301 修正対象。period ゲート不在 |
| 2 | `scripts/` 配下 6 本の運用スクリプト (live_order_test.py 等) | 本番 OANDA 直接接続。環境ガード未確認 |
| 3 | `deploy/` 配下が Prometheus 設定のみ | systemd/docker/ansible 不在。OOM restart 挙動が DE-311 と連鎖 |
| 4 | `pyproject.toml` 依存にバージョン上限なし | prometheus-client 二重登録バグとバージョン相関未調査 |
| 5 | 時刻同期 (NTP/UTC) 前提 | DE-306 週末 gap 計算が UTC 前提だが Windows 11 環境保証なし |
| 6 | AuditLogger / `StateManager.append_jsonl` のローテーション不在 | PA-311 fsync 欠如と組合せで disk fill 時の挙動未確認 |
| 7 | CI 権限管理 | parity.yml secrets 参照ゼロは適切だが `pull_request_target` 誤用リスク文書化なし |

---

## 修正実現可能性の訂正 (3件)

第1チームの「1 行修正」記述で実工数が乖離している箇所:

| ID | 主張 | 現実 |
|---|---|---|
| **DE-311 (medium に差戻後)** | 「InMemoryBackend に JSONL fallback 追加」 | **5-8 ファイル変更 + テスト更新が現実的**。InMemoryBackend クラス + StateStore 配線 + Pydantic config + テスト 3-4 ファイル |
| **PA-311** | 「1 行修正 (fsync 追加)」 | **2 行追加 (flush + fsync)**。devil-advocate-B の「close() で flush される」は **誤り** (with ブロック終了は close を呼ぶが OS バッファのフラッシュは保証されない) |
| **RE-301** | 「rollback 合流」 | 単純合流は 1-2 行だが、**`claimed_trade_ids` 排他制御まで含めると 5-10 ファイル規模** (`restore_positions` で導入済の R2 を runtime に展開) |

---

## 全体品質評価 (前回 AUDIT-0525-002 比)

| 指標 | AUDIT-0525-002 | AUDIT-2026-0529-001 |
|---|---|---|
| 第2チーム検証で発見した過大評価 | high 4→3 (DE-201, DM-204 等) | **high 2 件 (DE-311, DE-301)** |
| 第2チーム検証で発見した過小評価 | critical 1 件 (CSR-101) | **0 件** |
| 第2チーム検証で発見した見落とし | 不明 (記録なし) | **8 件 + 7 構造領域** |
| 論述欠陥 (絶対表現の過剰) | 「全 KS dead」「Live 14戦略」等 | 「全 3 経路 dead」「INC-0527 同型」等 (同型再発) |
| refuted (完全却下) 件数 | 不明 | **0 件 (前回より改善)** |

**総評**: 前回比で **過小評価ゼロ件** (CSR-101 のような RCE 級見落としなし) は改善。一方、**「絶対表現の過剰」と「本番経路の取り違え」** という前回と**同型のバイアス**が依然として発生 (DE-311, DM-306)。**本番経路 (`run_unified.py` → `UnifiedRunner`) と dev 経路 (`main.py`) の二重実装** が監査対象としても混同を生む構造的な情報源として作用している。

---

## 確定 must_fix (第2チーム検証後)

### 真の high 6件 (即時対処推奨)

1. **RE-302**: OANDA タイムアウト時の幻 trade_id 格納 (実損失経路、INC-0526 同型)
2. **RE-301**: `_resolve_live_trade_id` instrument fallback runtime 残存
3. **DM-306**: OANDA 60秒断絶通知が主要 3 経路 dead (1 行修正で Email 経路復活)
4. **DM-302**: OANDA API latency / FeatureStore staleness alert 永久 Inactive (計装追加)
5. **DE-303**: `poll_latest` silent failure (RiskAlert publish 追加)
6. **QA-301**: Tier 2 EFFECTIVE_WEIGHT_FLOOR 偽陽性 (QA-302 とセットで [change:spec])

### 第1チーム must_fix から格下げ 2件 (medium、優先度低い対処)

7. **DE-311 (medium)**: AioRedisBackend 未実装。本番経路は `StateManager` で持っているため即時危機ではない。main.py 廃止 ADR と連動して対処
8. **DE-301 (medium)**: `ema_800` 戦略 warmup ドリフト。**現状の Live 22戦略には未該当**。`scripts/import_atlas_strategy.py` に period > 384 ゲート追加で構造的予防

### 補完 must_fix 候補 (第2チーム発見)

- **RE-MISSED-302 (medium)**: `account_info` 失敗 cascade で heartbeat 全停止
- **CSR-302 (medium 戻し)**: parent_id path traversal (LLM 自動生成経路で悪用可能性)

---

## 推奨アクション (改訂版)

1. **Phase 3 (修正設計)** で真の high 6件を最優先処理
2. **訂正された must_fix 報告** を MEMORY.md に反映 (前回 AUDIT-0525-002 の「全 KS dead」訂正と同じ手順)
3. **構造的見落とし領域 7 件** を次回 audit-loop の Phase 1 スコープに **明示追加**:
   - 特に `scripts/import_atlas_strategy.py` は ATLAS↔FTS ブリッジで bridge agent の専任必要
4. **PA-307 OrderSubmissionGuard シングルトン共有リスク** を独立 finding として記録 (第1チームが未指摘)
5. **DM-306 / DE-311 の論述訂正** を `summary_AUDIT-2026-0529-001.md` に追記 (本ファイルへ参照付き)

---

**第2チーム検証完了**: 2026-05-29
**所要時間**: 約 30 分 (並列 5 名)

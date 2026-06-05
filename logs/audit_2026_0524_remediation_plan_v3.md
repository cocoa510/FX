# 監査 2026-05-24 修正計画 v3 (実行可能版)

**v2 → v3 主要変更**:
1. PR22 の位置矛盾を解消 (R1 → R2 末尾に移動、PR29/PR31 完了後)
2. R3 詳細を完全列挙 (Medium 20 件 + devil 見落とし 6 件)
3. devil-advocate 指摘 H-7, H-8, H-9, H-10, H-12, H-13 を PR 化
4. PR 番号体系を連番化 (PR22-PR60)
5. 着手順序フローチャート完成

**v1**: `audit_2026_0524_remediation_plan.md` (致命的誤りあり、廃止)
**v2**: `audit_2026_0524_remediation_plan_v2.md` (差分形式、R3/R4 詳細不足)
**v3 (本書)**: `audit_2026_0524_remediation_plan_v3.md` ← **唯一の正本**
**作成**: 2026-05-24

---

## エグゼクティブサマリ

### 修正対象

監査レポート v2 (`audit_report_2026_0524_v2.md`) で確定:
- Critical 5 件 / High 16 件 / Medium 20 件 / Low 8 件 = **49 件**

### v3 PR スケジュール

| フェーズ | 期限 | PR | 工数 |
|---|---|---|---|
| **R1** | 2026-05-25 | PR22-PR24 (3 PR) | 2.5-3.5h |
| **R2** | 2026-05-31 | PR25-PR36 (12 PR) | 27-38h |
| **R3** | 2026-06-21 | PR37-PR54 (18 PR) | 60-80h |
| **R4** | 2026-Q3 | PR55-PR60 (6 PR) | 8-12h |
| **合計** | — | **39 PR** | **97-133h** |

### v3 設計原則

1. **コードスニペットは grep 検証済の識別子のみ**
2. **メトリクス変更は `metrics.py` で目視確認後に計画**
3. **ガード追加は grep で既存影響箇所を網羅してから PR 化**
4. **Live 影響を「観測のみ」「能動リスク」「機能変化」の 3 段階で分類**
5. **工数に「レビュー + 統合検証 + ロールバック」を +30-50% 加算済**
6. **Critical Live 変更は最大 1 週間で完結 (R2 内)**
7. **ADR と実装は別 PR**

---

## 全 PR 一覧 (PR22-PR60、39 PR)

### R1 緊急 (2026-05-25 まで、3 PR)

| # | PR | 種別 | 内容 | 工数 | 依存 |
|---|---|---|---|---|---|
| 1 | **PR22** | docs | ADR-0004: MetricsCollector DI 設計 | 1h | なし |
| 2 | **PR23** | fix:bug | C-3 Dashboard 二重 autorefresh + Streamlit テスト設計 | 1-2h | なし |
| 3 | **PR24** | chore | CI 確認 (Streamlit + ATLAS リポジトリ公開状態) | 30 分 | なし |

### R2 今週 (2026-05-31 まで、12 PR)

| # | PR | 種別 | 内容 | 工数 | 依存 |
|---|---|---|---|---|---|
| 4 | **PR25** | feat | C-2 UnifiedRunner に MetricsCollector + LiveFeatureStore 注入 | 3h | PR22 |
| 5 | **PR26** | feat | H-4 forward_test に MetricsCollector + LiveFeatureStore 注入 | 2h | PR22 |
| 6 | **PR27** | docs | C-4 Runbook 2 件 (feature_staleness / event_bus_dedup_spike) | 1h | なし |
| 7 | **PR28** | chore | C-5 pytest-timeout 導入 + parity 個別 @timeout(300) | 2-3h | なし |
| 8 | **PR29** | change:spec | H-2(a) metrics に reason ラベル + allowlist 正規化 | 2h | なし |
| 9 | **PR30** | fix:bug | H-2(b) coordinator triggers キー修正 + 正規化呼び出し | 1h | PR29 |
| 10 | **PR31** | feat | H-11 AccountRiskState ガード (Mixin 化 + 既存テスト 3 件修正) | 4h | なし |
| 11 | **PR32** | change:spec | H-1 WARN ヒステリシス + 日次リセット時 deactivate | 4h | PR31 |
| 12 | **PR33** | docs | ADR-0003: RetryManager 配線方針 (BrokerGateway 層 + Phase E-1 連携) | 1.5h | なし |
| 13 | **PR34** | fix:bug | C-1 unrealized_warning Email 配線 + per-kind throttle | 1.5h | **PR31 + PR32** |
| 14 | **PR35** | docs | H-17 MISMATCH 戦略 Paper 引き戻し + 復活 runbook | 1h | なし |
| 15 | **PR36** | fix:bug | H-9 stream_receiver 再接続 logger.info 追加 (devil 指摘) | 30 分 | なし |

### R3 Paper 完了前 (2026-06-21 まで、18 PR)

| # | PR | 種別 | 内容 | 工数 | 依存 |
|---|---|---|---|---|---|
| 16 | **PR37** | feat | H-3 RetryManager 実装 (BrokerGateway limited retry + 冪等性テスト + OANDA Paper 実機検証) | 6-8h | PR33 |
| 17 | **PR38** | refactor | H-12 create_task fire-and-forget リーク修正 (coordinator + risk_supervisor) | 2h | なし |
| 18 | **PR39** | docs | H-13 threading.RLock async 化時の注意コメント追記 | 30 分 | なし |
| 19 | **PR40** | fix:bug | H-7 HealthChecker prober 一時失敗時の hysteresis | 2h | なし |
| 20 | **PR41** | docs | H-8 EmailNotifier kind docstring 更新 (`metrics.py:291-304`) | 30 分 | PR34 |
| 21 | **PR42** | docs | H-10 rollback_criteria.md の旧表記訂正 (PR5/PR12 既実装に変更) | 30 分 | なし |
| 22 | **PR43** | test | H-15 EmailNotifier SMTP fault シナリオ追加 (`tests/fault/`) | 3h | PR34 |
| 23 | **PR44** | test | H-14 KNOWN_XFAIL_SCENARIOS に 0504-091 追加 | 30 分 | なし |
| 24 | **PR45** | fix:bug | H-16 hang 2 件根本解消 (`test_correlation_chain` + `test_full_async_flow`) | 6h | なし |
| 25 | **PR46** | change:spec | H-5 ATLAS 側 live_eligible 必須化 + FTS loader 厳格化 | 6h | ATLAS マイグ |
| 26 | **PR47** | feat | M-A1 UnifiedRunner snapshot_required ガード追加 | 1h | なし |
| 27 | **PR48** | refactor | M-D1〜M-D4 データ層細部 (dead code + tz/tf 整合 + buffer cap gauge + std_dev validator) | 4h | なし |
| 28 | **PR49** | feat | M-O1 watchdog 連続失敗カウンタ | 2h | なし |
| 29 | **PR50** | feat | M-O2 Dashboard 拡張 (KS / Reconciler / staleness パネル) | 4h | PR23 |
| 30 | **PR51** | refactor | M-O3 metrics 命名統一 (_total suffix) | 1h | なし |
| 31 | **PR52** | refactor | M-C1 + M-C2 + M-C3 コード品質 (print 撤去 + 型ヒント + OANDA Pydantic 化) | 5h | なし |
| 32 | **PR53** | refactor | M-C4 + M-C5 asyncio パターン (return_exceptions + to_thread) | 2h | なし |
| 33 | **PR54** | chore | M-T1 + M-T4 pre-commit + grep 依存解消 | 2h | なし |
| 34 | **PR55** | test | M-T2 MISMATCH 戦略 parity test 追加 | 3h | なし |
| 35 | **PR56** | test | M-T3 xfail Phase 2: 9 戦略具体シナリオ実装 (修正: v1「5 戦略」→ 実体 9 戦略) | 27-30h | PR44 |
| 36 | **PR57** | refactor | M-R1 + M-R2 + M-R3 リスク・執行細部 + EmailNotifier daily_trade_count | 3h | なし |
| 37 | **PR58** | docs | M-D1 (新) max_total_exposure 遡及 JSONL 作成 | 30 分 | なし |
| 38 | **PR59** | docs | ADR-0005 StateStore KS 復元設計レビュー | 2h | なし |

### R4 Phase E 着手前 (2026-Q3、6 PR)

| # | PR | 種別 | 内容 | 工数 | 依存 |
|---|---|---|---|---|---|
| 39 | **PR60** | docs | L-1 PR6.5 判断基準明文化 + L-2 ADR-0002 ゲート更新 + L-5/L-6/L-8 ドキュメント訂正 + H-6 ADR-0001 表現修正 + L-3 ATLAS allowlist 明文化 + L-4 Dependabot 設定 + ADR-0006 DI コンテナ起票 | 8-12h | 全完了 |

---

## 着手順序フローチャート

```
2026-05-24 (今日)
  ├── PR22 (ADR-0004) ── ┐
  ├── PR23 (Dashboard) ──┤── 並列実施可
  └── PR24 (CI 確認) ────┘

2026-05-25 (R1 完了)

2026-05-26 (月) ━━━━━━━━━━━━━━━━━━━━━━━
  ├── PR25 (UnifiedRunner metrics) ────── ← PR22 依存
  ├── PR26 (forward_test metrics) ────── ← PR22 依存
  └── PR27 (Runbook 2 件) ───────────── ← 独立

2026-05-27 (火) ━━━━━━━━━━━━━━━━━━━━━━━
  ├── PR28 (pytest-timeout) ───────── ← 独立
  ├── PR29 (metrics reason ラベル) ──── ← 独立
  └── PR31 (AccountRiskState ガード) ── ← 独立、3 並列

2026-05-28 (水) ━━━━━━━━━━━━━━━━━━━━━━━
  ├── PR30 (coordinator triggers) ── ← PR29 依存
  ├── PR32 (WARN ヒステリシス) ──── ← PR31 依存
  ├── PR33 (ADR-0003) ─────────── ← 独立
  └── PR36 (stream_receiver log) ── ← 独立

2026-05-29 (木) ━━━━━━━━━━━━━━━━━━━━━━━
  ├── PR34 (unrealized Email) ──── ← PR31 + PR32 完了必須 ★
  └── PR35 (MISMATCH 引き戻し) ──── ← 独立

2026-05-31 (金、R2 完了)
  └── 4 専門家メタ監査ラウンド (本検証と同じ構成)

2026-06-01〜2026-06-21 (R3)
  ├── PR37 (RetryManager 実装) ─── PR33 依存、6-8h
  ├── PR38-PR42 (devil 見落とし H 級 5 件) ── 並列実施可、6h
  ├── PR43 (SMTP fault) ─────── PR34 依存
  ├── PR44 (xfail 0504-091 追加) ── 30 分
  ├── PR45 (hang 根本解消) ───── 6h、最優先
  ├── PR46 (live_eligible 厳格化) ── ATLAS マイグ後、6h
  ├── PR47-PR54 (Medium 20 件) ── 並列実施可、25-30h
  ├── PR55 (MISMATCH parity test) ── 3h
  ├── PR56 (xfail Phase 2 9 戦略) ─ 27-30h ★ 最大工数
  ├── PR57 (リスク細部) ──────── 3h
  └── PR58-PR59 (JSONL + ADR) ── 2.5h

2026-06-21 (R3 完了、Paper 30 日シャドー終了)
  ├── PR6.5 (kill_switch 0.05 → 0.15 戻し) Go/No-Go 判断
  └── 4 専門家再々監査ラウンド

2026-Q3 (R4、Phase E 着手前)
  └── PR60 (Low + ドキュメント整理一括)
```

### 重要な順序依存

1. ★ **PR34 (unrealized Email) は PR31 + PR32 完了必須** — チャタリング SMTP 連鎖を構造的に防止
2. ★ **PR45 (hang 根本解消) は R3 最優先** — `--ignore` による永続的カバレッジ欠損を解消
3. ★ **PR37 (RetryManager 実装) は PR33 (ADR-0003) 後** — 設計判断ありで実装
4. **PR50 (Dashboard 拡張) は PR23 (autorefresh 修正) 完了後** — ベース修正後に機能追加

---

## R1 詳細

### PR22: [docs] ADR-0004 MetricsCollector DI 設計

**目的**: PR25/PR26 の実装前に MetricsCollector 注入設計を確定 (devil 指摘 F-1 対応)

#### 内容

`docs/adr/0004_metrics_collector_dependency_injection.md` を新規作成:

```markdown
# ADR-0004: MetricsCollector の DI 設計

**ステータス**: Accepted
**根拠**: 監査 2026-05-24 F-1

## 背景
PR12 で `LiveFeatureStore(metrics=...)` 引数を導入。本番 LIVE 経路 (UnifiedRunner)
と forward_test 経路で MetricsCollector の保持方針が個別実装になっている。

## 決定
- `main.py` (FastAPI): `self._metrics = MetricsCollector()` を `__init__` で保持
- `UnifiedRunner` (本番): `self._metrics = MetricsCollector()` を `__init__` で保持
- `forward_test.py` (Paper): `MetricsCollector(namespace="forward_test")` で独立 namespace
- 各コンポーネント (LiveFeatureStore / EmailNotifier / Reconciler) に `metrics=self._metrics` 注入

## 帰結
### Positive
- 配線パターン統一、PR25/26 で具体実装
### Negative
- forward_test の /metrics が本番から独立 (これは意図的設計)
```

#### 工数 1h、Live 影響なし

---

### PR23: [fix:bug] C-3 Dashboard 二重 autorefresh

#### 修正内容

**修正**: `trading_platform/dashboard/app.py:199-203`

```python
# 修正前 (実コード grep 済)
if auto_refresh:
    time.sleep(REFRESH_INTERVAL_SEC)
    st.rerun()

# 修正後
if auto_refresh and not _AUTOREFRESH_AVAILABLE:
    # streamlit-autorefresh 未導入環境のフォールバック
    time.sleep(REFRESH_INTERVAL_SEC)
    st.rerun()
```

#### テスト戦略

**選択**: `pytest-mock` で `streamlit` module を mock (CI install 追加なし)

```python
# tests/unit/test_dashboard_autorefresh.py
def test_no_double_refresh_when_autorefresh_available(monkeypatch):
    # _AUTOREFRESH_AVAILABLE=True で time.sleep が呼ばれないこと
    pass

def test_fallback_runs_when_autorefresh_unavailable(monkeypatch):
    # _AUTOREFRESH_AVAILABLE=False で time.sleep が呼ばれること
    pass
```

#### 工数 1-2h、Live 影響あり (API ポーリング半減 = 好影響)

---

### PR24: [chore] CI 確認

#### 内容

1. GitHub Settings → Repositories で `cocoa510/ATLAS` の公開状態確認
2. private なら `ATLAS_PAT` secret を `cocoa510/fx_trading_system` に追加
3. ローカル `pytest tests/unit -k dashboard` で PR23 テストが実行可能か事前確認
4. `streamlit` の dev install 状態確認 (`uv pip list | grep streamlit`)

#### 工数 30 分、Live 影響なし

---

## R2 詳細 (主要 PR のみ、12 PR)

### PR25: [feat] C-2 UnifiedRunner に MetricsCollector + LiveFeatureStore 注入

**目的**: 本番 LIVE 経路で PR12 計装をデッドコード化から復活

#### 修正内容

##### 修正 1: `core/unified_runner/runner.py` の `__init__` に `_metrics` 追加

```python
from trading_platform.core.monitoring.metrics import MetricsCollector

class UnifiedRunner:
    def __init__(self, ...):
        # 既存属性...
        self._metrics = MetricsCollector()  # 新規追加 (ADR-0004 準拠)
```

##### 修正 2: `runner.py:355` で `metrics=` 注入

```python
feature_store = LiveFeatureStore(
    buffer_size=max(WARMUP_BARS * 2, 5000),
    metrics=self._metrics,  # 注入
)
```

##### 修正 3: 他コンポーネントも順次注入 (同 PR 内)

```python
# 既存または新規構築箇所
self._email_notifier = EmailNotifier(..., metrics=self._metrics)
self._reconciler = PositionReconciler(..., metrics=self._metrics)
# KillSwitch は既存配線済
```

#### テスト追加 (`tests/integration/test_unified_runner_metrics.py` 新規)

```python
async def test_unified_runner_has_metrics_attribute():
    runner = UnifiedRunner(...)
    assert isinstance(runner._metrics, MetricsCollector)

async def test_metrics_injected_to_feature_store():
    runner = UnifiedRunner(...)
    await runner.initialize()
    for slot in runner._slots.values():
        assert slot.feature_store._metrics is runner._metrics

async def test_feature_compute_error_counter_increments():
    # わざと不正 indicator → ValueError → counter increment 確認
```

#### 工数 3h、Live 影響あり (観測のみ、Prometheus メトリクス新規発火)

---

### PR26: [feat] H-4 forward_test に MetricsCollector + LiveFeatureStore 注入

PR25 と同パターンで forward_test 経路に適用。namespace="forward_test" で独立。

#### 工数 2h、Live 影響なし (forward_test 経路のみ)

---

### PR27: [docs] C-4 Runbook 2 件作成

#### 新規ファイル

##### `docs/runbook/feature_staleness.md`
- 対象アラート: `FxFeatureStorestaleHigh`
- 調査手順 / 対応 / エスカレーション

##### `docs/runbook/event_bus_dedup_spike.md`
- 対象アラート: `FxEventBusDedupSpike`
- layer 別調査手順 / `enable_dedup=False` 緊急ロールバック

#### 工数 1h、Live 影響なし

---

### PR28: [chore] C-5 pytest-timeout 導入

#### 修正内容

##### 修正 1: `pyproject.toml`

```toml
[dependency-groups]
dev = [
    # 既存...
    "pytest-timeout>=2.3.0",
]

[tool.pytest.ini_options]
# 既存...
timeout = 30
timeout_method = "thread"
markers = [
    # 既存...
    "slow: tests slower than 30s (use @pytest.mark.timeout to override)",
]
```

##### 修正 2: `tests/parity/` 全 6 ファイルに `@pytest.mark.timeout(300)` 個別付与

```python
# tests/parity/test_feature_store_parity.py
import pytest

@pytest.mark.timeout(300)
@pytest.mark.slow
class TestFeatureStoreParity:
    ...
```

##### 修正 3: `.github/workflows/parity.yml` の `timeout-minutes` 整合

```yaml
jobs:
  parity:
    timeout-minutes: 30  # parity 56 件 × 300s 上限を許容
```

#### 工数 2-3h、Live 影響なし

---

### PR29: [change:spec] H-2(a) metrics に reason ラベル + allowlist

#### 修正内容

##### 修正: `core/monitoring/metrics.py:154-157, 448`

```python
class MetricsCollector:
    _KILL_SWITCH_REASON_ALLOWLIST: ClassVar[frozenset[str]] = frozenset({
        "daily_realized_loss_exceeded",
        "manual",
        "ptrc_post_exposure_x_loss",
        "ptrc_post_slippage_x_exposure",
        "ptrc_post_exposure_x_slippage",
        "ptrc_post_multi_trigger",
        "unknown",
    })

    def __init__(self):
        # 既存...
        self.kill_switch_triggered = Counter(
            "fx_kill_switch_triggered_total",
            "Kill Switch 発動回数",
            ["reason"],  # 新規追加
        )

    def inc_kill_switch_triggered(self, reason: str = "unknown") -> None:
        normalized = reason if reason in self._KILL_SWITCH_REASON_ALLOWLIST else "unknown"
        self.kill_switch_triggered.labels(reason=normalized).inc()
```

#### テスト追加

```python
def test_reason_label_added(): ...
def test_unknown_reason_normalized(): ...
def test_allowlist_reasons_pass_through(): ...
def test_label_cardinality_bounded(): ...
```

#### 工数 2h、Live 影響あり (機能変化: 既存 Dashboard 集計式更新が必要)

---

### PR30: [fix:bug] H-2(b) coordinator triggers キー修正

#### 修正内容

##### 修正: `coordinator.py:547-555`

```python
# 修正前
trigger_reason = action.details.get("trigger", "unknown")

# 修正後
triggers = action.details.get("triggers", [])
if not triggers:
    trigger_reason = "unknown"
elif len(triggers) == 1:
    trigger_reason = f"ptrc_post_{triggers[0]}"
else:
    trigger_reason = "ptrc_post_multi_trigger"

self._metrics.inc_kill_switch_triggered(reason=trigger_reason)
```

#### 工数 1h、Live 影響あり (観測のみ)

---

### PR31: [feat] H-11 AccountRiskState ガード (Mixin 化 + 既存テスト 3 件修正)

#### 修正内容

##### 修正 1: `core/models/risk.py` に `GuardedRiskStateMixin` 抽出

```python
class GuardedRiskStateMixin:
    """ガード対象フィールドの直接代入を禁止する Mixin。"""

    _GUARDED_FIELDS: ClassVar[frozenset[str]] = frozenset()
    _GUARD_TOKEN_PREFIX: ClassVar[str] = "__guarded_set_token__"

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._GUARDED_FIELDS:
            token_key = f"{self._GUARD_TOKEN_PREFIX}_{name}"
            token_ok = self.__dict__.get(token_key, False)
            already_set = name in self.__dict__
            if already_set and not token_ok:
                raise AttributeError(
                    f"{name} は直接代入できません。"
                    f"{type(self).__name__}.set_guarded(instance, '{name}', value) を使用してください。"
                )
        super().__setattr__(name, value)

    @classmethod
    def set_guarded(cls, instance, name: str, value: Any) -> None:
        if name not in cls._GUARDED_FIELDS:
            raise ValueError(f"{name} is not a guarded field")
        token_key = f"{cls._GUARD_TOKEN_PREFIX}_{name}"
        object.__setattr__(instance, token_key, True)
        try:
            object.__setattr__(instance, name, value)
        finally:
            object.__setattr__(instance, token_key, False)


class RiskState(GuardedRiskStateMixin, BaseModel):
    _GUARDED_FIELDS: ClassVar[frozenset[str]] = frozenset({"is_kill_switch_active"})
    # 既存フィールド...

# unified_runner/risk_supervisor.py
class AccountRiskState(GuardedRiskStateMixin, BaseModel):
    _GUARDED_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "is_kill_switch_active",
        "is_unrealized_warning_active",
    })
    # 既存フィールド...
```

##### 修正 2: 既存コード 5 箇所の直接代入を `set_guarded` 経由に置換 (grep で網羅)

```bash
# grep 結果 (qa-tester 検証で確認済)
- risk_supervisor.py:732
- redis_store.py:278
- tests/risk_engine/test_global_kill_switch.py:292
- tests/unit/test_risk_supervisor_kill_switch_persistence.py:27
- tests/integration/test_kill_switch_halt.py:58
```

##### 修正 3: Pydantic v2 model_validate 互換性テスト

```python
def test_model_validate_preserves_kill_switch_state(): ...
def test_pydantic_v2_version_gate(): ...
```

#### 工数 4h、Live 影響なし (構造的ガード追加のみ)

---

### PR32: [change:spec] H-1 WARN ヒステリシス + 日次リセット

#### 修正内容

##### 修正 1: `risk_supervisor.py:680-712` を二段閾値に

```python
ACTIVATION_RATIO = 0.95
DEACTIVATION_RATIO = 0.80

def _evaluate_unrealized_warning(self):
    # risk-execution High 1 対応
    assert self._max_total_daily_loss_jpy < 0, \
        "max_total_daily_loss_jpy must be negative (loss limit)"

    activation_threshold = self._max_total_daily_loss_jpy * ACTIVATION_RATIO
    deactivation_threshold = self._max_total_daily_loss_jpy * DEACTIVATION_RATIO

    combined = (
        self.account_state.daily_realized_pnl_total
        + self.account_state.daily_unrealized_pnl_total
    )
    should_activate = combined <= activation_threshold
    should_deactivate = combined >= deactivation_threshold

    if should_activate and not self.account_state.is_unrealized_warning_active:
        AccountRiskState.set_guarded(
            self.account_state, "is_unrealized_warning_active", True
        )
        # 既存 _dispatch_alert ロジック
    elif should_deactivate and self.account_state.is_unrealized_warning_active:
        AccountRiskState.set_guarded(
            self.account_state, "is_unrealized_warning_active", False
        )
        # 解除ログ
```

##### 修正 2: 日次リセット時 deactivate イベント発火 (risk-execution High 2 対応)

```python
def reset_daily_for_account(self):
    if self.account_state.is_unrealized_warning_active:
        AccountRiskState.set_guarded(
            self.account_state, "is_unrealized_warning_active", False
        )
        self._dispatch_alert(
            alert_type="unrealized_warning_deactivated",
            message="[日次リセット] 未実現損益警戒レイヤー解除",
            details={"reset_reason": "daily_reset"},
        )
    # 既存リセット
```

##### 修正 3: 95%/80% 数値根拠ドキュメント (`docs/runbook/warn_hysteresis_thresholds.md`)

#### 工数 4h、Live 影響あり (機能変化: WARN チャタリング解消)

---

### PR33: [docs] ADR-0003 RetryManager 配線方針

`fx_trading_system/docs/adr/0003_retry_manager_wiring.md` を新規作成。**選択 C (BrokerGateway 層 + Phase E-1 連携)** を採用。実装は PR37 (R3)。

#### 工数 1.5h、Live 影響なし

---

### PR34: [fix:bug] C-1 unrealized_warning Email 配線 + throttle 同梱

**★ 重要**: PR31 + PR32 完了後にマージ (チャタリング SMTP 連鎖防止)

#### 修正内容

##### 修正 1: `email_notifier.py:260-263` 拡張

```python
_RISK_ALERT_KINDS: dict[str, str] = {
    "kill_switch_activated": "kill_switch",
    "instrument_quantity_mismatch": "position_reconciler",
    "unrealized_warning_activated": "unrealized_warning",  # 新規
}

_EMAIL_THROTTLE_INTERVAL_SEC: dict[str, float] = {
    "unrealized_warning": 300.0,  # 5 分に 1 通
}
```

##### 修正 2: per-kind throttle 実装 (risk-execution Critical 2 対応)

```python
class EmailNotifier:
    def __init__(self, ...):
        # 既存...
        self._last_sent_at: dict[str, float] = {}
        self._throttled_count = 0

    def _should_throttle(self, kind: str) -> bool:
        interval = _EMAIL_THROTTLE_INTERVAL_SEC.get(kind)
        if interval is None:
            return False
        last_at = self._last_sent_at.get(kind, 0.0)
        now = time.monotonic()
        if (now - last_at) < interval:
            return True
        self._last_sent_at[kind] = now
        return False

    async def _on_risk_alert(self, event):
        if not isinstance(event, RiskAlertEvent):
            return
        kind = self._RISK_ALERT_KINDS.get(event.alert_type)
        if kind is None:
            return
        if self._should_throttle(kind):
            self._throttled_count += 1
            if self._metrics:
                self._metrics.inc_email_notifier_throttled(kind)
            return
        # 既存配信ロジック (kind 別 builder 呼び出し)
```

##### 修正 3: `_build_unrealized_warning_message` 実装

```python
def _build_unrealized_warning_message(self, event: RiskAlertEvent) -> tuple[str, str]:
    details = event.details or {}
    combined = details.get("combined_pnl_jpy")
    limit = details.get("limit_jpy")

    # risk-execution High 4 対応: 詳細欠落時のフォールバック
    if combined is None or limit is None or limit == 0:
        subject = "[FTS 警戒] 未実現損益警告 (詳細欠落)"
        body = f"詳細情報の取得に失敗しました。raw details: {details}"
        logger.warning("unrealized_warning_details_missing", details=details)
        return subject, body

    realized = details.get("realized_pnl_jpy", 0.0)
    unrealized = details.get("unrealized_pnl_jpy", 0.0)
    ratio = abs(combined / limit) * 100

    subject = f"[FTS 警戒] 未実現損益が KS 閾値到達 ({ratio:.1f}%)"
    body = (
        f"未実現損益警戒レイヤーが発動しました。\n\n"
        f"実現損益: {realized:>12,.0f} JPY\n"
        f"未実現損益: {unrealized:>12,.0f} JPY\n"
        f"合算: {combined:>12,.0f} JPY\n"
        f"KS 閾値: {limit:>12,.0f} JPY\n\n"
        f"※ KS は実現損益のみで発動。新規発注は継続可能。\n"
        f"※ 含み損が戻れば自動解除 (PR32 ヒステリシス、5 分 throttle)。\n\n"
        f"対応手順: docs/runbook/kill_switch_triggered.md §未実現損益警告\n"
    )
    return subject, body
```

#### テスト追加 (8 件、qa High 1 対応)

```python
async def test_unrealized_warning_kind_dispatched(): ...
async def test_unrealized_warning_uses_kind_label(): ...
async def test_metrics_increment_on_unrealized_warning(): ...
async def test_throttle_suppresses_repeated_warnings(): ...
async def test_throttle_does_not_affect_kill_switch(): ...
async def test_details_missing_combined_pnl_uses_fallback_subject(): ...
async def test_limit_zero_does_not_divide_by_zero(): ...
async def test_smtp_failure_increments_failures_counter(): ...
```

#### 工数 1.5h、Live 影響あり (能動リスク: Email 配信開始だが throttle で抑制)

---

### PR35: [docs] H-17 MISMATCH 戦略 Paper 引き戻し

#### 内容

1. `strategies/imported/ATLAS-2026-0511-009/runner_config.json` の `execution_mode` を `live` → `paper`
2. `strategies/imported/ATLAS-2026-0510-002/runner_config.json` の `execution_mode` を `live` → `paper`
3. `docs/runbook/mismatch_strategy_revival.md` を新規作成 (復活トリガ: SMA50 > SMA200 達成時に Live 復帰)

#### 工数 1h、Live 影響あり (機能変化: 2 戦略の発注経路変更)

---

### PR36: [fix:bug] H-9 stream_receiver 再接続 logger.info 追加 (devil 指摘)

#### 修正内容

##### `stream_receiver.py:219-221`

```python
# 修正前
self._metrics.inc_stream_reconnect()

# 修正後
self._metrics.inc_stream_reconnect()
logger.info("OANDA Stream 再接続成功", instrument="all", reconnect_count=self._reconnect_count)
```

#### 工数 30 分、Live 影響あり (観測のみ、unified_runner.jsonl に reconnect イベント記録)

---

## R3 詳細 (要点のみ、18 PR)

### PR37: [feat] H-3 RetryManager 実装 (ADR-0003 採用後)

- `BrokerGateway.submit_with_limited_retry(order, max_attempts=3, backoff=[0.5, 1.0, 2.0])` 実装
- OANDA `clientExtensions.id = order.client_order_id` 冪等性確保
- リトライ時の `client_order_id` 不変条件テスト
- OANDA Paper 実機検証
- 工数 6-8h

### PR38: [refactor] H-12 create_task fire-and-forget リーク修正

- `coordinator.py:198`, `risk_supervisor.py:743, 807` で戻り値を `self._background_tasks` set に保持
- `task.add_done_callback(self._background_tasks.discard)` パターン
- 工数 2h

### PR39: [docs] H-13 threading.RLock コメント追記

- `fill_processor.py:114,226,300,305`, `order_manager.py` に「async 化時は asyncio.Lock 必須」コメント追加
- 工数 30 分

### PR40: [fix:bug] H-7 HealthChecker prober hysteresis

- `health_check.py:409-411` で prober 一時失敗 → 即 unhealthy ではなく N 連続失敗で unhealthy 化
- 工数 2h

### PR41: [docs] H-8 EmailNotifier kind docstring 更新

- `metrics.py:291-304` の docstring に `kind=position_reconciler, unrealized_warning` 追記
- 工数 30 分

### PR42: [docs] H-10 rollback_criteria.md 訂正

- `docs/runbook/rollback_criteria.md:109-110` の「PR5/PR12 で追加予定」を「既実装」に変更
- 工数 30 分

### PR43: [test] H-15 EmailNotifier SMTP fault シナリオ追加

- `tests/fault/test_email_notifier_fault.py` 新規 (SMTP timeout / 認証失敗 / 接続拒否 / 統合シナリオ)
- 工数 3h

### PR44: [test] H-14 KNOWN_XFAIL_SCENARIOS に 0504-091 追加

- `tests/integration/fixtures/atlas_scenario_fixtures.py` と `tests/unit/test_pr19_5_xfail_fixtures.py` の expected セットに `ATLAS-2026-0504-091` 追加
- 工数 30 分

### PR45: [fix:bug] H-16 hang 2 件根本解消

- `test_correlation_chain.py::test_bar_signal_order_fill_correlation_chain` の `asyncio.sleep(0.05)` 後 Event Bus drain 修正
- `test_worker_coordinator.py::test_full_async_flow_worker_to_fill` の strategy load → coordinator → broker → fill チェーン修正
- `--ignore` 除外を解除し CI 完全カバレッジ復活
- 工数 6h

### PR46: [change:spec] H-5 live_eligible 必須化

- ATLAS 側で 60 戦略 (現在 54 件欠如) に `live_eligible` キーを追加 (ATLAS リポジトリで別 PR)
- FTS 側 `loader.py` で `live_mode=True` + キー欠如 → `StrategyLoadError` で起動阻止
- 工数 6h (ATLAS マイグ後)

### PR47: [feat] M-A1 UnifiedRunner snapshot_required ガード

- `UnifiedRunner.initialize` 内で `snapshot_required=True and snapshot_writer is None` で `RuntimeError`
- 工数 1h

### PR48: [refactor] M-D1〜M-D4 データ層細部

- `stream_receiver.py:305` dead code 削除
- `redis_store.py:296` tf 正規化を `live_store.py:107` に揃える
- `live_store.py:57` MAX_BUFFER_SIZE 張り付き gauge (`fx_feature_store_buffer_at_cap{strategy_id}`)
- bollinger `std_dev`/`std` の validator 補強
- 工数 4h

### PR49: [feat] M-O1 watchdog 連続失敗カウンタ

- `runner_watchdog.ps1` に 3 回連続失敗で `Disable-ScheduledTask` 自動実行
- 工数 2h

### PR50: [feat] M-O2 Dashboard 拡張

- KS 状態 / Reconciler ミスマッチ / feature_staleness パネル追加
- `fx_signal_silence_sec{strategy_id}` gauge 追加
- `fx_daily_pnl_realized{strategy_id}` 戦略別内訳
- 工数 4h

### PR51: [refactor] M-O3 metrics 命名統一

- `fx_data_quality_reject` (suffix なし) を `fx_data_quality_reject_total` (suffix あり) に統一
- 全 Counter の命名ポリシー統一
- 工数 1h

### PR52: [refactor] M-C1 + M-C2 + M-C3 コード品質

- `forward_test.py:421-469, 579-583` `print()` → `structlog`
- 型ヒント追加: `circuit_breaker.py:576`, `fill_processor.py:217,231`, `position_reconciler.py:307`, `portfolio_manager/manager.py:157`
- `broker_gateway.py:57,298,302,336` OANDA レスポンスを Pydantic モデル化
- 工数 5h

### PR53: [refactor] M-C4 + M-C5 asyncio パターン

- `main.py:827` `gather(return_exceptions=True)` + ループ確認
- `state_manager.py:117, 222` blocking I/O を `asyncio.to_thread` ラップ
- 工数 2h

### PR54: [chore] M-T1 + M-T4 pre-commit + grep 依存解消

- `.pre-commit-config.yaml` 新規 (ruff + mypy)
- `tests/architecture/test_unified_runner_event_bus_wired.py` の `subprocess.run(["grep", ...])` を `Path.rglob + str_in_text` に置換
- 工数 2h

### PR55: [test] M-T2 MISMATCH 戦略 parity test

- 0511-009 / 0510-002 専用の feature 組み合わせ parity test (EMA50/200 + RSI65/54)
- 工数 3h

### PR56: [test] M-T3 xfail Phase 2 9 戦略具体シナリオ (★ 最大工数)

| 戦略 | 主シナリオ | 工数 |
|---|---|---|
| 0504-091 | trading_hours [7,16] 内 rsi&bb 同時成立 | 3h |
| 0504-098 | Asia レンジ breakout | 3h |
| 0506-024 / 0507-016 | EMA cross + ATR expansion | 3h × 2 |
| 0508-041 / 0508-140 | Donchian breakout | 3h × 2 |
| 0511-059 | 4 条件 AND (downtrend + rsi≥72 + bb_upper + adx≥25) | 4h |
| 0512-023 / 0512-035 / 0512-061 | Asia レンジ + ATR 1.4× | 3h × 3 |
| **合計** | | **27-30h** |

### PR57: [refactor] M-R1 + M-R2 + M-R3 + StrategyRiskState daily_trade_count

- `circuit_breaker.py:423-424` `_inflight_at_kill` `__init__` で初期化
- `email_notifier.py:163-175` `daily_trade_count='-'` 解消 (`StrategyRiskState` に `daily_trade_count: int = 0` 追加)
- `paper_broker/simulator.py:84-92` bid/ask 区別 or fail-safe REJECT
- 工数 3h

### PR58: [docs] max_total_exposure 遡及 JSONL

- `trading_platform/logs/rule_change_logs/2026-05-12_max_exposure_increase.jsonl` 新規作成 (3.0 → 8.0 遡及記録)
- 工数 30 分

### PR59: [docs] ADR-0005 StateStore KS 復元設計

- `redis_store.py:278` の「再起動時 KS 強制解除」設計を ADR で再評価
- 工数 2h

---

## R4 詳細 (1 PR、6 件統合)

### PR60: [docs] Low + ドキュメント整理一括

- L-1: PR6.5 判断基準明文化 (Runbook 拡張)
- L-2: ADR-0002 Phase E 判断ゲートに再監査担当者・実施時期追記
- L-3: ATLAS allowlist 明文化 (`SHARED_CONTRACT.md` 更新)
- L-4: Dependabot 設定 (`.github/dependabot.yml` 新規)
- L-5: `audit_c_phase_completion.md:26-27` の commit_sha "TBD" 訂正 (`f0214d6` 埋め戻し)
- L-6: `2026-05-22_kill_switch_lower.jsonl` の commit_sha 埋め戻し
- L-7: xfail Phase 2 完了報告 (PR56 完了時)
- L-8: `audit_c_phase_completion.md` に「C フェーズ完了時間 vs 人間見積もり」の基準差注記追加
- H-6: ADR-0001 表現乖離訂正 (「同一インスタンス」→「同一クラス・同一 SnapshotWriter log_path」)
- ADR-0006: DI コンテナ化検討起票 (platform-architect 推奨)
- 工数 8-12h

---

## 共通検証ゲート (全 PR 共通)

### マージ前

- [ ] `pytest tests/unit tests/architecture tests/risk_engine tests/parity tests/fault tests/performance -q` 全 PASS
- [ ] `pytest tests/integration -q --ignore=tests/integration/test_correlation_chain.py --ignore=tests/integration/test_worker_coordinator.py` 全 PASS (PR45 完了後は `--ignore` 解除)
- [ ] CI green
- [ ] PR 本文に Live 影響 (観測のみ / 能動リスク / 機能変化 / なし) 明記
- [ ] Live 影響 (機能変化 or 能動リスク) の場合は Paper シャドー 7 日観測 KPI を PR 本文に明記

### Live 影響あり PR の追加要件

- [ ] ロールバック手順を `docs/rollback_pr<N>.md` に記載
- [ ] 観測 KPI (Prometheus メトリクス名 + 異常閾値) を明記
- [ ] PR マージ後 24h は毎時 KPI 確認

### メモリ更新

- [ ] PR 完了時に `~/.claude/projects/C--data-works-FX/memory/project_fts_remediation_playbook_2026_0521.md` の進捗テーブルに追記

---

## devil-advocate 指摘との対応マッピング (v2 未対応分の解消)

| 指摘 | v2 状態 | v3 対応 PR |
|---|---|---|
| H-7 HealthChecker prober 一時失敗 | 言及なし | **PR40 (R3)** |
| H-8 EmailNotifier kind docstring | 言及なし | **PR41 (R3)** |
| H-9 stream_receiver reconnect ログ | 言及なし | **PR36 (R2)** |
| H-10 rollback_criteria.md 旧表記 | 言及なし | **PR42 (R3)** |
| H-12 create_task fire-and-forget | PR41 (M-C4/5 統合) | **PR38 (R3、独立化)** |
| H-13 threading.RLock コメント | 言及なし | **PR39 (R3)** |

これで監査レポート v2 の **High 16 件全件が PR 化**。

---

## ロールバック手順 (PR 別)

各 R2 以降の Live 影響あり PR は `docs/rollback_pr<N>.md` を必須作成:

| PR | ロールバック概要 | 復旧時間目安 |
|---|---|---|
| PR25 | UnifiedRunner `metrics=` 引数削除 → metrics 沈黙 (機能は復活) | 15 分 |
| PR29 | metrics.py の reason ラベル削除 → 旧仕様復帰 | 15 分 |
| PR30 | coordinator triggers → trigger 戻し | 15 分 |
| PR31 | `set_guarded` を直接代入に置換 → ガード無効化 | 30 分 |
| PR32 | WARN ヒステリシス → 単一閾値復帰 | 30 分 |
| PR34 | `_RISK_ALERT_KINDS` から `unrealized_warning_activated` 削除 → Email 配信停止 | 15 分 |
| PR35 | runner_config.json で `execution_mode` を `paper` → `live` 復帰 | 5 分 |
| PR37 | RetryManager 配線を撤回 → 単発 submit に戻る | 1h |
| PR46 | loader.py 厳格化を撤回 → WARN+counter 動作復帰 | 30 分 |
| PR50 | Dashboard パネル追加部分を revert → 既存表示 | 15 分 |

---

## 完了判定基準

### R1 完了 (2026-05-25)
- [ ] PR22-PR24 が origin に push
- [ ] ADR-0004 が `docs/adr/` に存在
- [ ] Dashboard ローカル起動で API ポーリング 1x
- [ ] CI で Streamlit import 確認済み

### R2 完了 (2026-05-31)
- [ ] PR25-PR36 が origin に push
- [ ] Prometheus `/metrics` に `fx_feature_store_compute_errors_total`, `fx_kill_switch_triggered_total{reason}`, `fx_email_notifier_*{kind="unrealized_warning"}` 出現
- [ ] CI で `pytest-timeout` 動作確認、parity green
- [ ] AccountRiskState ガードで直接代入が AttributeError、既存 5 箇所が classmethod 経由に変更済
- [ ] MISMATCH 戦略 2 件が Paper 経路に変更済
- [ ] **4 専門家メタ監査ラウンド** で R2 検証 → Critical 0 確認

### R3 完了 (2026-06-21)
- [ ] PR37-PR59 が origin に push
- [ ] Paper シャドー 30 日完了
- [ ] hang 2 件が解消、`--ignore` 除外なし
- [ ] xfail 5 件のうち実装可能な 9 戦略のシナリオ実装完了
- [ ] 全 Medium 解消
- [ ] **PR6.5 (kill_switch 0.05 → 0.15 戻し) Go/No-Go 判断**

### R4 完了 (2026-Q3)
- [ ] PR60 push
- [ ] ADR-0001/0002/0003/0004/0005/0006 全て整備
- [ ] **再々監査セッション (7 専門家並列)** で Critical 0 → Phase E 着手可

---

## v1 → v2 → v3 主要変更履歴

| 項目 | v1 | v2 | v3 |
|---|---|---|---|
| 致命的事実誤認 | PR24 `self._metrics` 即死 / PR27 reason ラベル不在 / PR28 dedup 誤解 / PR29 既存テスト破壊 / PR26 parity 全滅 | 5 件訂正 | 同左、v3 で実装可能形式に |
| PR22 (Email) の位置 | R1 (今日中) | 矛盾 (R1 と R2 末尾の両方) | **R2 末尾 (PR34) に統一**、PR31+PR32 完了後 |
| PR 番号体系 | 連番 | `PR-HANG`, `PR31.5` 等混在 | **PR22-PR60 完全連番** |
| devil 見落とし | H-9/12/13/7/8/10 未対応 | 未対応 | **全件 PR 化 (PR36/38/39/40/41/42)** |
| R3 詳細 | PR33-PR47 (Medium 20 件) | 4 PR のみ詳細、他省略 | **18 PR 全件詳細** |
| R4 詳細 | 5 PR、要点のみ | 「v1 と同一」省略 | **PR60 に統合、内容明示** |
| 着手順序 | 軽い記述 | テキストのみ | **フローチャート + 重要順序依存 4 件明示** |
| 工数 | 49-74h | 75-111h | **97-133h (R3 詳細化で +22h)** |
| PR 数 | 25 PR | 35 PR (差分) | **39 PR (完全独立)** |

---

## 次のアクション

### 今すぐ (本計画書確定後)
1. 本 v3 計画書を人間オーナーがレビュー
2. v3 確定後、メモリ `project_fts_remediation_playbook_2026_0521.md` の進捗テーブルに本計画を追記
3. R1 (PR22-PR24) 着手

### 今日中 (2026-05-24)
- PR22 (ADR-0004) → PR23 (Dashboard) → PR24 (CI 確認) を順次 commit

### 来週 (2026-05-26-31)
- R2 の 12 PR を依存順に消化 (着手順序フローチャート参照)
- 着手順序の特記事項: **PR34 (Email) は PR31 + PR32 完了後**

---

**作成**: Claude Opus 4.7, 2026-05-24 (v3 完全独立版)
**v1**: `audit_2026_0524_remediation_plan.md` (廃止)
**v2**: `audit_2026_0524_remediation_plan_v2.md` (差分形式、参考用)
**v3 正本**: `audit_2026_0524_remediation_plan_v3.md` ← **本書、唯一の実行基準**
**検証ラウンド**: platform-architect / risk-execution-engineer / qa-tester / devil-advocate

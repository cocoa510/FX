# FX Trading System データ層・Feature Store レビュー - 詳細補足報告書

**レビュー担当**: data-reviewer  
**レビュー日**: 2026-04-03  
**対象仕様書**: fx_trading_system_spec.md（セクション19-21）

---

## 概要

本レポートは初期レビュー報告に加え、以下7つの詳細観点についての深掘り分析を提供します。

---

## 1. Feature Storeキャッシュ戦略とバックテスト/本番共用の整合性

### 現在の仕様状況

仕様書セクション19では以下が記載されている：
- Feature Version管理によるバージョン採番
- `staleness_threshold`超過時のアラート
- Strict Causal Mode（因果制約）の強制
- Graceful Degradation（遅延時対応）ポリシー

### 発見した問題点

#### 1-1. バックテストでの特徴量スナップショット取得方法が不明確
- **問題**: 過去日時（例：2025-06-15）でバックテスト実行時、当時の Feature Version をどのように特定・復元するかが未定義
- **影響**: 
  - バージョン間での計算ロジック差分が大きい場合、同一戦略の過去再実行結果が再現不可能となる
  - 例：RSI計算ロジック v1.0 → v2.0 変更時、旧ロジック v1.0 で過去データを再計算する仕組みが不在
- **改善案**:
  ```
  Feature Version Snapshot Schema:
  {
    "feature_id": "RSI_14",
    "version": "1.2.3",
    "effective_from": "2025-06-15T00:00:00Z",
    "effective_to": "2025-12-31T23:59:59Z",
    "calculation_code_hash": "sha256_...",
    "parameters": {"period": 14, "smoothing": "EMA"},
    "dependencies": [{"feature_id": "close_price", "version": "*"}]
  }
  ```
  バックテストエンジンが指定時点での Feature Version を自動選択

#### 1-2. リアルタイム計算とキャッシュの一貫性保証が曖昧
- **問題**: Market Data が到着し、複数の特徴量が更新される場合、all-or-nothing 原則が明記されていない
- **具体例**: 
  - T秒：新しい Tick 到着
  - T+10ms：RSI 更新完了
  - T+15ms：MACD 更新完了
  - T+20ms：ATR 更新完了
  - → T+15ms 時点で戦略が MACD を読むと、RSI はv1, MACD はv2 の混在状態となる可能性
- **改善案**: Feature Store の更新は **Transaction** 単位で実行し、Bar完定時に特徴量セット全体をアトミックに確定

#### 1-3. キャッシュ無効化の明示的トリガーが不在
- **問題**: staleness_threshold のみで、明示的な再計算トリガー（例：パラメータ変更時）が定義されていない
- **改善案**:
  ```
  キャッシュ無効化トリガー定義:
  1. 時間ベース：staleness_threshold 超過
  2. イベントベース：
     - パラメータ変更検知（運用ルール自動改善時）
     - データ品質低下検知
     - Bar が新規確定された時点
     - Feature 定義の変更
  3. エラーベース：計算エラー時の自動再実行
  ```

### 本番・バックテスト共用の整合性保証方法

**推奨実装パターン:**

```python
class FeatureStore:
    async def get_feature(
        self,
        feature_id: str,
        timestamp: datetime,
        mode: Literal["LIVE", "BACKTEST"] = "LIVE"
    ) -> FeatureValue:
        """
        特徴量取得（バックテスト/本番共用）
        
        Args:
            feature_id: 特徴量ID（例："RSI_14"）
            timestamp: 計算時刻（バックテストでは過去時刻も指定可）
            mode: 実行モード
        
        Returns:
            FeatureValue: {value, version, timestamp, confidence}
        """
        # 1. timestamp に対応する Feature Version を取得
        version = await self._select_version_at_timestamp(
            feature_id, timestamp
        )
        
        # 2. キャッシュから取得 or 計算
        cached = self._cache.get(
            key=f"{feature_id}:{version}:{timestamp}",
            ttl=version.staleness_threshold
        )
        
        if cached and not self._is_stale(cached):
            return cached
        
        # 3. 計算実行（計算ロジックは version から決定）
        computed = await self._compute_with_version(
            feature_id=feature_id,
            version=version,
            timestamp=timestamp
        )
        
        # 4. キャッシュ保存（TTL=staleness_threshold）
        self._cache.set(
            key=f"{feature_id}:{version}:{timestamp}",
            value=computed,
            ttl=version.staleness_threshold
        )
        
        return computed
```

---

## 2. TimescaleDBスキーマ設計仕様の完全性

### 現在の仕様状況

セクション19では以下が記載されている：
- TimescaleDB 利用決定（圧縮・パーティショニング有効化）
- 「通貨ペア × 期間でのパーティショニング」
- Phase 2での Continuous Aggregates・コールドストレージ退避

### 発見した問題点

#### 2-1. ハイパーテーブル定義が抽象的

**現状**: パーティション粒度・キー選択基準が未定義

**改善案 - TimescaleDB テーブル定義仕様**:

```sql
-- Raw Tick データ（時系列ハイパーテーブル）
CREATE TABLE IF NOT EXISTS market_ticks (
    time TIMESTAMPTZ NOT NULL,                -- OANDA タイムスタンプ
    instrument TEXT NOT NULL,                 -- 例："EUR_USD"
    bid DECIMAL(10,5) NOT NULL,              -- Bid 価格
    ask DECIMAL(10,5) NOT NULL,              -- Ask 価格
    bid_volume FLOAT,                         -- Bid 板数量（取得可能な場合）
    ask_volume FLOAT,                         -- Ask 板数量（取得可能な場合）
    spread DECIMAL(10,5) GENERATED ALWAYS AS (ask - bid) STORED,
    data_quality_score FLOAT DEFAULT 1.0,    -- Data Quality Engine から付与
    source TEXT DEFAULT 'OANDA_STREAMING'    -- データソース追跡用
);

-- ハイパーテーブル化
SELECT create_hypertable('market_ticks', 'time', if_not_exists => TRUE);

-- パーティショニング戦略
-- 1. 時間軸：日次パーティション（24時間）
-- 2. 通貨ペア軸：instrument カラムで自動シャーディング
SELECT set_chunk_time_interval('market_ticks', INTERVAL '1 day');

-- インデックス戦略
CREATE INDEX idx_ticks_instrument_time ON market_ticks (instrument, time DESC);
CREATE INDEX idx_ticks_quality ON market_ticks (data_quality_score) 
  WHERE data_quality_score < 0.9;

-- 圧縮設定（90日以上前のデータを自動圧縮）
ALTER TABLE market_ticks SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC',
    timescaledb.compress_segmentby = 'instrument'
);

SELECT add_compression_policy(
    'market_ticks',
    INTERVAL '90 days'
);
```

```sql
-- Bar データ（OHLCV）
CREATE TABLE IF NOT EXISTS market_bars (
    time TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,                 -- "1m", "5m", "1h", "1d" など
    open DECIMAL(10,5) NOT NULL,
    high DECIMAL(10,5) NOT NULL,
    low DECIMAL(10,5) NOT NULL,
    close DECIMAL(10,5) NOT NULL,
    volume FLOAT,
    tick_count INT,
    bar_complete BOOLEAN DEFAULT FALSE,
    generated_from_ticks BOOLEAN DEFAULT TRUE
);

SELECT create_hypertable('market_bars', 'time', if_not_exists => TRUE);

-- Bar テーブルは複合インデックス
CREATE INDEX idx_bars_instrument_timeframe_time 
  ON market_bars (instrument, timeframe, time DESC);

-- 圧縮設定（1日足以上の古いデータは圧縮）
ALTER TABLE market_bars SET (timescaledb.compress);
SELECT add_compression_policy('market_bars', INTERVAL '180 days');
```

#### 2-2. パーティション保持期間とアーカイブ戦略の不明確さ

**問題**: 
- いつまで TimescaleDB に保持するのか不明確
- コールドストレージ（S3/NVMe）への退避タイミング不明確
- 研究系向けリードレプリカの遅延許容度不明確

**改善案**:

```yaml
# Data Retention & Archive Policy
Market Ticks:
  Hot Storage (TimescaleDB):
    Retention: 180 days
    Compression: After 90 days
    Read Performance: Real-time (ライブ運用・直近分析用)
  
  Cold Storage (S3 Parquet):
    Retention: 7 years (規制要件対応)
    Format: Parquet（instrument + timeframe で パーティション分割）
    Location: s3://trading-data-archive/ticks/
    Retrieval: バックテスト用 batch 読み込み
  
  Lifecycle:
    Day 0-90:    TimescaleDB（ホット）
    Day 91-180:  TimescaleDB（圧縮）
    Day 181+:    S3 へ自動退避 + TimescaleDB から削除

Market Bars:
  TimescaleDB: 3 年間保持（頻繁なバックテスト対応）
  S3:         7 年間保持
```

#### 2-3. 研究系ワークロード分離の具体的仕様が不在

**問題**: セクション19で「リードレプリカ or Parquet エクスポート」と記載されるも、具体的な分離基準が不明

**改善案**:

```
ワークロード分離戦略:

1. LIVE TRADING（ライブ運用）
   - Primary PostgreSQL + TimescaleDB
   - データ流：OANDA → Raw Tick Receiver → TimescaleDB（リアルタイム書き込み）
   - 読み取り：戦略エンジン、Risk Engine（P99 < 10ms）
   - 保有期間：180日（ホット）

2. RESEARCH / BACKTEST（研究用）
   方式A（小規模バックテスト向け）:
     - Read-Only Replica（PostgreSQL streaming replication）
     - ライブ更新から max 1分遅延許容
     - 通常のバックテスト（過去1年程度）向け
   
   方式B（大規模バックテスト・データ分析向け）:
     - S3 Parquet エクスポート（毎日深夜バッチ）
     - データレイク（Athena / DuckDB で直接クエリ）
     - 90日以上前のデータはこちらから読み込み

3. Replica Lag Monitoring:
   レプリカ遅延がしきい値（例: 30秒）を超過した場合、
   研究系クエリを自動的に S3 Parquet に切り替え
```

---

## 3. データ品質スコア算出ロジックの具体性

### 現在の仕様状況

セクション20では以下が記載されている：
- 検証項目（欠損チェック、異常値検出、スプレッド異常など）
- 品質スコア（0.0～1.0）付与
- スコア低下時のアラート

### 発見した問題点

#### 3-1. スコア計算式が完全に不在

**改善案 - データ品質スコア計算仕様**:

```python
class DataQualityScorer:
    """
    各 Tick/Bar に対して品質スコアを算出する
    
    品質スコア = Σ(component_score * weight)
    各component: 0.0～1.0
    各weight: 合計 = 1.0
    """
    
    WEIGHTS = {
        "completeness": 0.25,      # 欠損チェック
        "anomaly_detection": 0.30,  # 異常値検出
        "spread_check": 0.25,      # スプレッド異常
        "timestamp_consistency": 0.15, # タイムスタンプ整合性
        "source_consistency": 0.05  # データソース一致（将来）
    }
    
    THRESHOLDS = {
        "missing_rate": 0.05,         # 欠損率 5% が閾値
        "z_score_outlier": 3.0,       # Z スコア > 3.0 は異常
        "iqr_multiplier": 1.5,        # IQR × 1.5 を外れ値判定基準
        "spread_max_pips": 5,         # スプレッド最大値（通常時）
        "timestamp_gap_max_ms": 500   # タイムスタンプギャップ許容値
    }
    
    async def calculate_score(
        self,
        tick: MarketTick,
        reference_window: List[MarketTick]  # 直近N個のティック
    ) -> QualityScore:
        """
        Args:
            tick: 評価対象 Tick
            reference_window: 参照用ウィンドウ（統計計算用）
        
        Returns:
            QualityScore: {
                overall_score: float,           # 0.0～1.0
                component_scores: dict,        # 各要素の内訳
                issues: List[str],             # 検出された問題
                severity: Literal["PASS", "WARN", "FAIL"]
            }
        """
        
        # 1. Completeness Check（欠損チェック）
        completeness_score = self._check_completeness(tick, reference_window)
        # → Tick に必須フィールド（bid, ask, time）が揃っているか
        # → スコア：完全 = 1.0, 1フィールド欠損 = 0.5, 2以上欠損 = 0.0
        
        # 2. Anomaly Detection（異常値検出）
        anomaly_score = self._detect_anomalies(tick, reference_window)
        # → Z スコア > 3.0 の価格変動 → スコア 0.0
        # → Z スコア 2.0～3.0 の価格変動 → スコア 0.5
        # → 正常範囲 → スコア 1.0
        # → IQR による外れ値検出も併用
        
        # 3. Spread Check（スプレッド異常チェック）
        spread_score = self._check_spread(tick, reference_window)
        # → スプレッド < 平均値の 1.5 倍 → スコア 1.0
        # → スプレッド < 平均値の 3.0 倍 → スコア 0.5
        # → スプレッド > 平均値の 3.0 倍 → スコア 0.0
        # 参考値：EUR/USD 通常スプレッド ≈ 0.8～1.0 pips
        
        # 4. Timestamp Consistency（時系列整合性）
        ts_score = self._check_timestamp_consistency(tick, reference_window)
        # → タイムスタンプが順序通り & ギャップ正常 → スコア 1.0
        # → タイムスタンプ重複 or 逆転 → スコア 0.0
        # → ギャップが異常（例：1分ティック間隔のはずが5分） → スコア 0.5
        
        # 5. Source Consistency（データソース一致度、将来拡張）
        source_score = 1.0  # 将来実装
        
        # 総合スコア = 加重平均
        overall = (
            completeness_score * self.WEIGHTS["completeness"] +
            anomaly_score * self.WEIGHTS["anomaly_detection"] +
            spread_score * self.WEIGHTS["spread_check"] +
            ts_score * self.WEIGHTS["timestamp_consistency"] +
            source_score * self.WEIGHTS["source_consistency"]
        )
        
        # 重大度判定
        severity = self._classify_severity(overall)
        # PASS: >= 0.95
        # WARN: 0.80～0.95
        # FAIL: < 0.80
        
        return QualityScore(
            overall_score=round(overall, 4),
            component_scores={
                "completeness": completeness_score,
                "anomaly_detection": anomaly_score,
                "spread_check": spread_score,
                "timestamp_consistency": ts_score,
                "source_consistency": source_score
            },
            issues=self._extract_issues(overall, tick),
            severity=severity
        )
```

#### 3-2. スコア低下時の自動対応フローが不明確

**改善案**:

```yaml
Data Quality Response Flow:

Severity: PASS (>= 0.95)
  - アクション: なし
  - Feature Store: 即座に計算結果をキャッシュ
  - ログ: INFO レベル記録

Severity: WARN (0.80～0.95)
  - アクション:
    - Tick は Feature Store に送出（ただしquality_score フラグ付き）
    - 該当 Tick に依存する特徴量計算は続行
    - WARN ログ & メトリクス記録（Prometheus に送出）
  - Feature Store: キャッシュ時に quality_flag = "DEGRADED" 標記
  - 戦略側: quality_flag が "DEGRADED" な特徴量を受け取った場合の対応は戦略定義による

Severity: FAIL (< 0.80)
  - アクション:
    - Tick を Data Quality Gate で遮断（Feature Store に到達させない）
    - ALERT ログ & Critical メトリクス記録
    - 手動確認キューに追加（例：専用データベーステーブル `quality_quarantine`）
  - Feature Store: キャッシュ更新スキップ（前回キャッシュを継続使用）
  - 戦略側: 特徴量が更新されないため Graceful Degradation ポリシーが発動
    （USE_STALE / SKIP_SIGNAL / PAUSE_STRATEGY）
  - Reconciliation: 品質スコア FAIL の期間をバックテストで除外すべき時系列として記録
```

#### 3-3. 統計計算のウィンドウサイズが不定義

**改善案**:

```yaml
Quality Calculation Windows:

Reference Window Size (統計計算用):
  - Default: 最直近 100 ティック（通常は 1～5秒分）
  - 理由: Z スコア・IQR 計算に最低 30 サンプル必要
  - Tick スパース期間（例：市場休場）: window を 1000 ティックに拡張

Spread Normal Range計算:
  - Method: ローリング 1時間の中央値 ± MAD (Median Absolute Deviation)
  - ただし過去 24 時間の中央値と照合（日中の周期性考慮）
  - 例：NY時間帯は東京時間帯より常にスプレッド広い

Timestamp Gap 許容度:
  - Normal: 平均インターバル ± 2σ
  - 例：1分足で平均 100ms ティック間隔なら、
    許容範囲は 70～130ms（2σ = 30ms を仮定）
  - 許容外: 即座に異常フラグ
```

---

## 4. Market Regime検出アルゴリズムの実装可能性

### 現在の仕様状況

セクション21では以下が記載されている：
- Phase 1: ATR, 実現ボラティリティ, ADX, Efficiency Ratio
- Phase 2: HMM, ベイズ推定, GARCH
- 多次元レジーム（Trend/Volatility/Liquidity/Spread）

### 発見した問題点

#### 4-1. Phase 1 の指標閾値が完全に不在

**改善案 - レジーム判定テーブル**:

```python
class MarketRegimeDetector:
    """Phase 1: 指標ベースレジーム検出"""
    
    # Trend Regime: ADX + Efficiency Ratio
    TREND_REGIMES = {
        "STRONG_TREND": {
            "adx": (lambda v: v > 40),
            "efficiency_ratio": (lambda v: v > 0.5),
            "description": "明確かつ強いトレンド"
        },
        "MILD_TREND": {
            "adx": (lambda v: 25 < v <= 40),
            "efficiency_ratio": (lambda v: 0.3 <= v <= 0.5),
            "description": "弱いトレンド"
        },
        "RANGE_BOUND": {
            "adx": (lambda v: v <= 25),
            "efficiency_ratio": (lambda v: v < 0.3),
            "description": "レンジ相場"
        }
    }
    
    # Volatility Regime: ATR + Realized Volatility
    VOLATILITY_REGIMES = {
        "HIGH_VOLATILITY": {
            "atr_percentile": (lambda v: v > 0.75),  # 直近20日ATRの75パーセンタイル超
            "realized_vol": (lambda v: v > (20_day_mean + 2 * 20_day_std)),
            "description": "ボラティリティが通常の 2σ 以上"
        },
        "NORMAL_VOLATILITY": {
            "atr_percentile": (lambda v: 0.25 <= v <= 0.75),
            "realized_vol": (lambda v: (20_day_mean - 2*std) <= v <= (20_day_mean + 2*std)),
            "description": "通常範囲"
        },
        "LOW_VOLATILITY": {
            "atr_percentile": (lambda v: v < 0.25),
            "realized_vol": (lambda v: v < (20_day_mean - 2*std)),
            "description": "ボラティリティが通常の 0.5σ 以下"
        }
    }
    
    # Spread Regime: Bid-Ask Spread
    SPREAD_REGIMES = {
        "WIDE_SPREAD": {
            "spread_pips": (lambda v, normal: v > normal * 2.0),
            "description": "スプレッド大幅拡大（流動性枯渇、重要イベント）"
        },
        "NORMAL_SPREAD": {
            "spread_pips": (lambda v, normal: v <= normal * 2.0),
            "description": "通常スプレッド"
        }
    }
    
    async def detect_regime_state(
        self,
        market_data: MarketDataSnapshot,
        lookback_bars: int = 20
    ) -> RegimeState:
        """
        現在のレジーム状態を検出
        
        Args:
            market_data: 現在の市場データ（close, volume等）
            lookback_bars: 統計計算用の過去バー数
        
        Returns:
            RegimeState: {
                trend_regime: str,        # "STRONG_TREND", "MILD_TREND", "RANGE_BOUND"
                volatility_regime: str,   # "HIGH_VOLATILITY", "NORMAL", "LOW_VOLATILITY"
                spread_regime: str,       # "WIDE_SPREAD", "NORMAL_SPREAD"
                confidence: float,        # 0.0～1.0
                indicators: dict          # {adx, er, atr, realized_vol, spread}
            }
        """
        
        # 1. 指標計算
        adx = await self._calculate_adx(market_data, lookback_bars)
        er = await self._calculate_efficiency_ratio(market_data, lookback_bars)
        atr = await self._calculate_atr(market_data, lookback_bars)
        realized_vol = await self._calculate_realized_volatility(market_data, lookback_bars)
        spread = market_data.current_spread_pips
        
        # 2. 各次元のレジーム判定
        trend = self._classify_trend(adx, er)
        volatility = self._classify_volatility(atr, realized_vol)
        spread_regime = self._classify_spread(spread)
        
        # 3. 信頼度スコア計算
        #    各判定関数の「margin」を計算
        #    例：adx = 30, MILD_TREND 閾値 = 25～40
        #    → margin = min(30-25, 40-30) = 5 → confidence が高い
        confidence = self._calculate_confidence(adx, er, atr, realized_vol)
        
        return RegimeState(
            trend_regime=trend,
            volatility_regime=volatility,
            spread_regime=spread_regime,
            confidence=confidence,
            indicators={
                "adx": adx,
                "efficiency_ratio": er,
                "atr": atr,
                "realized_volatility": realized_vol,
                "spread_pips": spread
            },
            timestamp=market_data.timestamp
        )
```

#### 4-2. 複合レジーム判定マトリックスが未定義

**改善案**:

```python
class CompositeRegimeMatrix:
    """複数次元のレジームを統合して複合レジームを定義"""
    
    # 2次元マトリックス例（Trend × Volatility）
    COMPOSITE_REGIMES = {
        # (trend, volatility) -> (composite_regime, strategy_filter)
        ("STRONG_TREND", "HIGH_VOLATILITY"): {
            "name": "EXPLOSIVE_TRENDING",
            "description": "強いトレンド + 高ボラティリティ。スキャルピング機会大。",
            "strategy_filter": ["momentum_breakout", "trend_follower"],
            "position_size_multiplier": 0.5,  # 高ボラ時にサイズを抑制
            "sl_distance_multiplier": 1.5     # SL を広めに設定
        },
        ("STRONG_TREND", "NORMAL_VOLATILITY"): {
            "name": "HEALTHY_TRENDING",
            "description": "最適なトレンド相場。トレンドフォロー推奨。",
            "strategy_filter": ["trend_follower", "moving_average_cross"],
            "position_size_multiplier": 1.0,
            "sl_distance_multiplier": 1.0
        },
        ("STRONG_TREND", "LOW_VOLATILITY"): {
            "name": "GRINDING_TREND",
            "description": "トレンドはあるが動きが小さい。取引コスト要注意。",
            "strategy_filter": ["swing_trade"],
            "position_size_multiplier": 1.5,  # ポジションサイズを増加可
            "sl_distance_multiplier": 0.8
        },
        ("RANGE_BOUND", "HIGH_VOLATILITY"): {
            "name": "VOLATILE_CHOP",
            "description": "レンジ相場だがボラティリティ高。フェイクアウト多発。",
            "strategy_filter": [],              # ほぼ全戦略をフィルタリング
            "position_size_multiplier": 0.0,   # ポジション禁止
            "sl_distance_multiplier": 0.0
        },
        ("RANGE_BOUND", "NORMAL_VOLATILITY"): {
            "name": "STABLE_RANGE",
            "description": "安定したレンジ相場。レンジ売買に最適。",
            "strategy_filter": ["mean_reversion", "support_resistance"],
            "position_size_multiplier": 1.0,
            "sl_distance_multiplier": 0.9
        },
        ("RANGE_BOUND", "LOW_VOLATILITY"): {
            "name": "SLEEPING_MARKET",
            "description": "非常に静かな相場。流動性が低い場合もある。",
            "strategy_filter": [],
            "position_size_multiplier": 0.2,
            "sl_distance_multiplier": 0.7
        },
        # ... その他の組み合わせ
    }
    
    # 3次元拡張例（Trend × Volatility × Spread）
    def get_composite_regime(
        self,
        trend: str,
        volatility: str,
        spread: str
    ) -> CompositeRegime:
        """3次元レジーム判定"""
        
        key = (trend, volatility, spread)
        if key in self.COMPOSITE_REGIMES:
            return self.COMPOSITE_REGIMES[key]
        
        # 3次元での最適なデフォルト
        # spread が WIDE の場合、常にポジションサイズを縮小
        spread_multiplier = 1.0 if spread == "NORMAL_SPREAD" else 0.5
        
        base = self.COMPOSITE_REGIMES.get(
            (trend, volatility),
            self.DEFAULT_REGIME
        )
        
        return CompositeRegime(
            name=f"{base['name']}_WIDE_SPREAD",
            position_size_multiplier=base["position_size_multiplier"] * spread_multiplier,
            # ...
        )
```

#### 4-3. レジーム遷移の信頼度スコア算出方法が不明確

**改善案**:

```python
class RegimeConfidenceCalculator:
    """レジーム判定の信頼度を定量化"""
    
    def calculate_confidence(
        self,
        adx: float,
        efficiency_ratio: float,
        atr: float,
        realized_vol: float,
        reference_mean_atr: float,
        reference_std_atr: float
    ) -> float:
        """
        信頼度スコア = Σ(indicator_confidence * weight)
        各 indicator_confidence は 0.0～1.0
        """
        
        # 1. ADX 信頼度
        #    - ADX > 40: 確信度が高い（confidence = 0.9）
        #    - ADX = 25: 閾値境界、確信度中程度（confidence = 0.5）
        #    - ADX < 10: 判定困難（confidence = 0.1）
        adx_conf = self._sigmoid(adx, center=25, steepness=0.1)
        
        # 2. Efficiency Ratio 信頼度
        #    - ER が極端（0.0 or 1.0 に近い）ほど確信度高
        er_conf = 2.0 * abs(efficiency_ratio - 0.5)  # 0.0～1.0
        
        # 3. ATR 安定性（Realized Vol との一致度）
        #    - 実現ボラティリティと ATR が一致 → 確信度高
        normalized_atr = (atr - reference_mean_atr) / max(reference_std_atr, 0.001)
        atr_consistency = 1.0 / (1.0 + abs(normalized_atr - realized_vol))
        
        # 総合信頼度（加重平均）
        confidence = (
            0.40 * adx_conf +
            0.30 * er_conf +
            0.30 * atr_consistency
        )
        
        return min(max(confidence, 0.0), 1.0)  # クリップ
```

#### 4-4. レジーム遷移の検知タイミングが曖昧

**改善案**:

```python
class RegimeTransitionDetector:
    """レジーム遷移の検知と伝播"""
    
    async def detect_regime_change(
        self,
        previous_state: RegimeState,
        current_state: RegimeState
    ) -> Optional[RegimeChangeEvent]:
        """
        レジーム遷移を検知し、イベント発行を判定
        
        Returns:
            None（遷移なし） or RegimeChangeEvent
        """
        
        # 1. 単純な比較（各次元が変更されたか）
        trend_changed = (previous_state.trend_regime != current_state.trend_regime)
        vol_changed = (previous_state.volatility_regime != current_state.volatility_regime)
        spread_changed = (previous_state.spread_regime != current_state.spread_regime)
        
        # 2. 信頼度フィルタ
        #    低信頼度 (< 0.5) での遷移は「揺らぎ」と見なす
        #    → イベント発行を遅延（複数フレーム確認）
        
        if current_state.confidence < 0.5:
            return None  # 遷移イベント不発行
        
        # 3. 遷移イベント生成
        if trend_changed or vol_changed or spread_changed:
            return RegimeChangeEvent(
                previous_state=previous_state,
                current_state=current_state,
                affected_dimensions=[
                    "trend" if trend_changed else None,
                    "volatility" if vol_changed else None,
                    "spread" if spread_changed else None
                ],
                timestamp=current_state.timestamp
            )
        
        return None
```

---

## 5. OANDAのTICKデータ取得・ストレージ仕様（欠損補完・リサンプリング）

### 現在の仕様状況

セクション19では以下が記載されている：
- OANDA Streaming API → Raw Tick Receiver → Raw Tick Storage パイプライン
- 品質検証後に Bar Builder で OHLCV 生成

### 発見した問題点

#### 5-1. OANDA API制限への対応が不明確

**問題**: OANDA v20 API の制限仕様が記載されていない

**改善案 - OANDA API 適応仕様**:

```yaml
OANDA v20 API Rate Limits:

Streaming (Price Stream Endpoint):
  - Connection limit: 1 concurrent stream per account
  - Max instruments per stream: 最大 50通貨ペア（推奨30以下）
  - Reconnection backoff: exponential（max 30秒）
  
REST API (Historical Data):
  - Rate limit: 120 requests per second
  - Max candles per request: 最大 5000 (via /instruments/{id}/candles)
  - Historical data availability:
    * Bid/Ask data: 過去 5 年間
    * Mid candles: 過去 最大 500 bars（timeframe 依存）
  
Strategy:
  - ストリーミング: リアルタイム TICK 取得（最大 50ペア）
  - REST: 過去データ + ストリーム再接続時の欠損補完用
```

#### 5-2. ストリーム切断時の欠損検知・補完フロー が不在

**改善案 - データ欠損補完戦略**:

```python
class OandaTickReceiver:
    """OANDA ストリーミング TICK 受信 + 欠損補完"""
    
    def __init__(self, account_id: str, instruments: List[str]):
        self.account_id = account_id
        self.instruments = instruments  # 最大 50
        self.stream_state = {}  # 各通貨ペアの最後のティック情報
        self.gap_detector = TickGapDetector()
    
    async def stream_with_fallback(self):
        """
        ストリーミング接続 + 自動フォールバック
        """
        while True:
            try:
                async with self._create_stream() as stream:
                    async for tick in stream:
                        await self._process_tick(tick)
                        self.stream_state[tick.instrument] = tick
            
            except ConnectionError:
                await self._handle_stream_disconnection()
    
    async def _handle_stream_disconnection(self):
        """
        ストリーム切断時の欠損期間を補完
        """
        
        # 1. 最後の正常なティック時刻から現在までのギャップを特定
        for instrument in self.instruments:
            last_tick = self.stream_state.get(instrument)
            if not last_tick:
                continue
            
            gap_start = last_tick.timestamp
            gap_end = datetime.utcnow()
            gap_duration = (gap_end - gap_start).total_seconds()
            
            # 2. ギャップが許容範囲外（例：2分以上）の場合、REST APIで補完
            if gap_duration > 120:  # 2分
                await self._fill_gap_with_rest_api(
                    instrument=instrument,
                    start_time=gap_start,
                    end_time=gap_end
                )
    
    async def _fill_gap_with_rest_api(
        self,
        instrument: str,
        start_time: datetime,
        end_time: datetime
    ):
        """
        REST API で欠損期間のバー/ティックを取得
        
        戦略:
        1. 1秒足で全期間をカバー（API呼び出し複数回）
        2. 各1秒バーの OHLC を疑似ティックとして記録
           (Open/High/Low/Close 計4つの疑似ティック)
        """
        
        delta = end_time - start_time
        num_requests = int(delta.total_seconds() / 300) + 1  # 5分単位で分割
        
        for i in range(num_requests):
            chunk_start = start_time + timedelta(seconds=300*i)
            chunk_end = min(
                chunk_start + timedelta(seconds=300),
                end_time
            )
            
            # REST API で 1秒足を取得
            try:
                candles = await self.oanda_client.get_candles(
                    instrument=instrument,
                    granularity="S1",
                    from_time=chunk_start.isoformat() + "Z",
                    to_time=chunk_end.isoformat() + "Z",
                    price="MBA"  # Mid, Bid, Ask を取得
                )
                
                # 各1秒バーを疑似ティックに変換
                for candle in candles:
                    # Open tick
                    await self._write_tick(
                        instrument=instrument,
                        bid=candle.bid.o,
                        ask=candle.ask.o,
                        timestamp=candle.time,
                        source="REST_FILL"
                    )
                    # High tick
                    await self._write_tick(
                        instrument=instrument,
                        bid=candle.bid.h,
                        ask=candle.ask.h,
                        timestamp=candle.time + timedelta(milliseconds=250),
                        source="REST_FILL"
                    )
                    # Low tick
                    await self._write_tick(
                        instrument=instrument,
                        bid=candle.bid.l,
                        ask=candle.ask.l,
                        timestamp=candle.time + timedelta(milliseconds=500),
                        source="REST_FILL"
                    )
                    # Close tick
                    await self._write_tick(
                        instrument=instrument,
                        bid=candle.bid.c,
                        ask=candle.ask.c,
                        timestamp=candle.time + timedelta(milliseconds=750),
                        source="REST_FILL"
                    )
            
            except Exception as e:
                logger.error(f"Gap fill failed for {instrument}: {e}")
                # 補完失敗時：該当期間を Data Quality FAIL として記録
                await self._mark_period_failed(
                    instrument=instrument,
                    start=chunk_start,
                    end=chunk_end,
                    reason="REST_API_FILL_FAILED"
                )
```

#### 5-3. リサンプリング（1分足、5分足等）への対応仕様が不明確

**改善案 - Bar Builder リサンプリング仕様**:

```python
class BarBuilder:
    """ティックから複数時間足のバーを構築"""
    
    def __init__(self):
        self.tick_buffers = {}  # {(instrument, timeframe) -> List[Tick]}
        self.open_bars = {}     # {(instrument, timeframe) -> Bar (open, high, low)}
    
    async def build_bars_from_ticks(
        self,
        tick: MarketTick,
        target_timeframes: List[str] = ["1m", "5m", "1h", "1d"]
    ) -> List[Bar]:
        """
        Tick から複数時間足バーを生成
        
        Args:
            tick: 1つのティック
            target_timeframes: 生成対象の時間足
        
        Returns:
            新規確定したバーのリスト（empty も存在）
        """
        
        completed_bars = []
        
        for timeframe in target_timeframes:
            buf_key = (tick.instrument, timeframe)
            
            # 1. バッファに Tick を追加
            if buf_key not in self.tick_buffers:
                self.tick_buffers[buf_key] = []
            self.tick_buffers[buf_key].append(tick)
            
            # 2. Open bar を初期化（必要に応じて）
            bar_key = (tick.instrument, timeframe)
            if bar_key not in self.open_bars:
                bar_start = self._round_time_to_bar(tick.timestamp, timeframe)
                self.open_bars[bar_key] = Bar(
                    instrument=tick.instrument,
                    timeframe=timeframe,
                    open_time=bar_start,
                    open=tick.bid,  # Bid を使用（保守的）
                    high=tick.bid,
                    low=tick.bid,
                    close=tick.bid,
                    volume=1,
                    tick_count=1
                )
            
            current_bar = self.open_bars[bar_key]
            
            # 3. 次のバー時刻に到達したかチェック
            bar_end = current_bar.open_time + self._get_timeframe_delta(timeframe)
            
            if tick.timestamp >= bar_end:
                # 現在のバーを確定
                current_bar.close = self.tick_buffers[buf_key][-1].bid
                current_bar.bar_complete = True
                completed_bars.append(current_bar)
                
                # 新しいバーを開始
                self.open_bars[bar_key] = Bar(
                    instrument=tick.instrument,
                    timeframe=timeframe,
                    open_time=bar_end,
                    open=tick.bid,
                    high=tick.bid,
                    low=tick.bid,
                    close=tick.bid,
                    volume=1,
                    tick_count=1
                )
                
                # バッファをクリア
                self.tick_buffers[buf_key] = [tick]
            
            else:
                # 現在のバーを更新
                current_bar.high = max(current_bar.high, tick.ask)  # Ask を高値に
                current_bar.low = min(current_bar.low, tick.bid)    # Bid を安値に
                current_bar.close = tick.bid
                current_bar.volume += (tick.ask - tick.bid)  # 疑似ボリューム
                current_bar.tick_count += 1
        
        return completed_bars
```

---

## 6. Redis キャッシュと PostgreSQL の役割分担の明確性

### 現在の仕様状況

セクション19では以下が記載されている：
- Redis にリアルタイム書き込み（低レイテンシ）
- PostgreSQL に定期スナップショット（耐久性）
- WAL パターン

### 発見した問題点

#### 6-1. データタイプごとの配置が不定義

**改善案 - Redis / PostgreSQL 配置マップ**:

```yaml
データ層 配置・TTL・同期仕様:

1. Market Data（市場データ）
   保存先:
     - Redis: 直近 1 時間分の ティック / 特徴量キャッシュ
       TTL: 1 hour（自動削除）
       キー: market_ticks:{instrument}:{timestamp}
     
     - PostgreSQL (TimescaleDB): 全ティック（無期限 or 定期アーカイブ）
       保存: Raw Tick Storage（改変不可）
       保持期間: 180日 → S3 Parquet に退避
   
   同期パターン:
     - Redis → PostgreSQL: 非同期バッチ（毎秒、バッファサイズ超過時）
     - RPO（Recovery Point Objective）: 最大 1秒の欠損許容

2. Feature Store（特徴量キャッシュ）
   保存先:
     - Redis: 直近バー＋ α の特徴量値キャッシュ
       TTL: staleness_threshold（特徴量ごとに異なる）
       キー: feature:{feature_id}:{version}:{timestamp}
       例：feature:RSI_14:v1.2:2026-04-03T12:00:00Z → {value: 45.3, confidence: 0.95}
     
     - PostgreSQL: 特徴量定義・バージョン履歴・変更記録
       テーブル: feature_registry, feature_versions
       保持期間: 無期限（監査対応）
   
   同期パターン:
     - Redis キャッシュはティック毎に自動更新
     - PostgreSQL には定期的に特徴量スナップショットを書き込み
       （例：Bar 確定時）

3. Trade Context Log（注文判断根拠ログ）
   保存先:
     - Redis: 未約定注文のコンテキスト（一時保存）
       TTL: 注文ライフサイクル終了後 + 24時間
     
     - PostgreSQL: 全取引履歴（無期限）
       テーブル: trade_context_snapshots
       キー: {order_id, timestamp}
   
   同期パターン:
     - 注文約定 or キャンセル後、即座に PostgreSQL に永続化
     - WAL パターン適用：Redis 書き込み → Event Log → PostgreSQL

4. State Store（実行状態）
   保存先:
     - Redis: 現在のポジション、注文、リスク状態（ホット）
       TTL: セッション中有効（セッション終了後削除）
       キー: state:{entity_type}:{entity_id}
       例：state:position:EUR_USD → {quantity: 10000, entry_price: 1.0845}
     
     - PostgreSQL: State Store スナップショット（定期保存）
       テーブル: state_snapshots（ポイントインタイム復元用）
       保存タイミング: Graceful Shutdown 時, 1分ごと定期バッチ
   
   同期パターン:
     - クラッシュ復旧時：PostgreSQL スナップショット復元 → OANDA 照合

5. Rule Store（運用ルール）
   保存先:
     - Redis: 現在有効なルール（読み取り専用キャッシュ）
       TTL: 無期限（明示的なクリア or ルール更新時のみ削除）
     
     - PostgreSQL: ルール定義・変更履歴・承認記録
       テーブル: rules, rule_change_history
       保持期間: 無期限（監査対応）
   
   同期パターン:
     - ルール更新 → PostgreSQL に記録 → Redis キャッシュをクリア
       → 全ワーカーが新ルール取得

6. Economic Calendar（経済イベント）
   保存先:
     - Redis: 今後 30 日間のイベント（読み取り専用キャッシュ）
       TTL: 24 時間（毎日深夜にリフレッシュ）
     
     - PostgreSQL: イベント履歴・取得ログ
   
   同期パターン:
     - 外部 API（Forex Factory等）から毎日深夜に定期取得
     - Redis にキャッシュ → 戦略/Risk Engine が参照

Failover & Replication Strategy:
  Redis:
    - Sentinel mode（3ノード以上）で HA 構成
    - Replication lag: < 100ms（同期レプリケーション推奨）
    - キー有効期限により、データ損失の影響を最小化
  
  PostgreSQL:
    - Streaming Replication でスタンバイ構成
    - Replication lag: < 1秒
    - 定期バックアップ（毎日、最低1年保持）
```

#### 6-2. Redis → PostgreSQL 同期プロトコルが曖昧

**改善案 - WAL + Event Sourcing パターン**:

```python
class StateStoreSync:
    """
    Redis / PostgreSQL 間の整合性保証
    WAL（Write-Ahead Logging）+ Event Sourcing パターン
    """
    
    async def update_state_atomic(
        self,
        entity_type: str,  # "position", "order", "risk_state" etc.
        entity_id: str,
        new_state: dict
    ):
        """
        状態更新の原子性を保証
        
        フロー:
        1. Event Log に書き込み（append-only）
        2. Redis を更新（失敗時はロールバック）
        3. PostgreSQL への定期同期
        """
        
        # Step 1: Event Log に追記
        event = StateChangeEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            old_state=await self.redis.get(f"state:{entity_type}:{entity_id}"),
            new_state=new_state,
            timestamp=datetime.utcnow(),
            source="state_update"
        )
        
        event_log_id = await self.append_event_log(event)
        
        # Step 2: Event Log 書き込み成功を確認
        if event_log_id is None:
            raise StateUpdateError("Event Log write failed")
        
        # Step 3: Redis を更新（トランザクション）
        try:
            await self.redis.set(
                key=f"state:{entity_type}:{entity_id}",
                value=json.dumps(new_state),
                ttl=None  # セッション中有効
            )
        except RedisError:
            # Redis 書き込み失敗時は Event Log から復帰可能
            logger.error(f"Redis update failed for {entity_type}:{entity_id}")
            # PostgreSQL から復元するまで待機（別タスク）
            raise
        
        # Step 4: PostgreSQL への同期（非同期、バッチ処理）
        # 定期的なバッチジョブが Event Log を読み込んで PostgreSQL に反映
        # Latency: 最大 1 秒（バッチ間隔）
    
    async def recovery_from_crash(self):
        """
        クラッシュからの復旧フロー
        """
        
        # 1. Event Log から最後の確認済みイベントID を取得
        last_committed_event_id = await self.postgres.get_last_committed_event_id()
        
        # 2. Event Log の last_committed_event_id より後のイベントを再生
        pending_events = await self.event_log.get_events_after(
            last_committed_event_id
        )
        
        # 3. 各イベントを Redis に再適用（冪等性保証）
        for event in pending_events:
            await self.redis.set(
                key=f"state:{event.entity_type}:{event.entity_id}",
                value=json.dumps(event.new_state)
            )
        
        # 4. OANDA API と照合
        await self.position_reconciler.reconcile()
```

---

## 7. バックテスト用ヒストリカルデータの調達・管理仕様

### 現在の仕様状況

セクション19では以下が記載されている：
- Raw Tick Storage は生データの原本
- Phase 2 で Parquet エクスポート
- リードレプリカ or Parquet エクスポート

### 発見した問題点

#### 7-1. OANDA ヒストリカルデータAPI の調達上限が記載されていない

**改善案 - ヒストリカルデータ調達仕様**:

```yaml
OANDA ヒストリカルデータ調達・管理仕様:

Phase 1: 初期システム構築（初回のみ）
  対象期間: 過去 3 年間
  取得方法:
    - OANDA REST API /instruments/{id}/candles エンドポイント
    - 1時間足（最大 5000 candles/request）で取得
    - 各1時間足から疑似ティック生成
  調達計画:
    - 対象通貨ペア: EUR/USD, GBP/USD, USD/JPY 他（初期 10ペア）
    - 1ペアあたり取得時間:
      3年 × 365日 × 24時間 = 26,280 時間足
      → 26,280 / 5,000 = 約 6 API 呼び出し
      → Rate limit (120/sec) で十分カバー可能
    - 全ペア調達: 約 1～2 時間で完了
  保存先: S3 Parquet（初期セット）
  費用: API 呼び出しのみ（無料範囲内）

Phase 2+: ライブ運用中の自動蓄積
  新規取得: ストリーミング TICK で継続取得
  自動アーカイブ:
    - 毎日深夜バッチ: Raw Tick Storage から当日分を Parquet に集約
    - S3 に保存
    - 保持期間: 7年間（規制要件対応）

バックテスト用データセット管理:
  
  Dataset A: "研究用フルデータセット"
    - 対象期間: 過去 3～5 年
    - 保存形式: Parquet（instrument + date でパーティション）
    - 保存先: S3 + ローカルNVMe（大規模バックテスト対応）
    - 更新頻度: 日次（当日分を追加）
    - 利用シーン: Walk Forward, Monte Carlo, 長期戦略検証
    - アクセスパターン: Sequential Read（最適化されたParquet レイアウト）
  
  Dataset B: "ライブ運用用ホットデータセット"
    - 対象期間: 過去 180 日
    - 保存形式: TimescaleDB（ホット）
    - 保存先: PostgreSQL
    - 更新頻度: リアルタイム
    - 利用シーン: 短期的なリプレイテスト、デバッグ
    - アクセスパターン: Random Read（インデックス活用）
```

#### 7-2. Parquet フォーマット仕様が未定義

**改善案 - Parquet スキーマ定義**:

```python
# PyArrow Parquet スキーマ定義

import pyarrow as pa

# Market Ticks Parquet Schema
MARKET_TICKS_SCHEMA = pa.schema([
    pa.field("timestamp", pa.timestamp("us"), nullable=False),  # UTC, マイクロ秒精度
    pa.field("instrument", pa.string(), nullable=False),
    pa.field("bid", pa.decimal128(10, 5), nullable=False),
    pa.field("ask", pa.decimal128(10, 5), nullable=False),
    pa.field("bid_volume", pa.float32(), nullable=True),
    pa.field("ask_volume", pa.float32(), nullable=True),
    pa.field("spread", pa.float32()),  # bid - ask（計算フィールド）
    pa.field("data_quality_score", pa.float32(), nullable=False),
    pa.field("source", pa.string(), nullable=False),
])

# Market Bars Parquet Schema
MARKET_BARS_SCHEMA = pa.schema([
    pa.field("timestamp", pa.timestamp("us"), nullable=False),
    pa.field("instrument", pa.string(), nullable=False),
    pa.field("timeframe", pa.string(), nullable=False),  # "1m", "5m", "1h", "1d"
    pa.field("open", pa.decimal128(10, 5), nullable=False),
    pa.field("high", pa.decimal128(10, 5), nullable=False),
    pa.field("low", pa.decimal128(10, 5), nullable=False),
    pa.field("close", pa.decimal128(10, 5), nullable=False),
    pa.field("volume", pa.float64()),
    pa.field("tick_count", pa.int32()),
    pa.field("bar_complete", pa.bool_(), nullable=False),
])

# パーティション戦略
PARQUET_PARTITIONING = {
    "market_ticks": [
        ("instrument", "string"),  # 第1レベルパーティション
        ("year", "int32"),         # 第2レベル
        ("month", "int32"),        # 第3レベル
    ],
    "market_bars": [
        ("instrument", "string"),
        ("timeframe", "string"),
        ("year", "int32"),
    ]
}

# 実装例
async def write_ticks_to_parquet(
    ticks: List[MarketTick],
    s3_path: str = "s3://trading-data-archive/ticks/"
):
    """ティックを Parquet に書き込み（パーティション自動分割）"""
    
    import pyarrow.parquet as pq
    import pyarrow as pa
    
    # DataFrame に変換
    df = pa.table({
        "timestamp": [t.timestamp for t in ticks],
        "instrument": [t.instrument for t in ticks],
        "bid": [t.bid for t in ticks],
        "ask": [t.ask for t in ticks],
        # ... 他フィールド
    }, schema=MARKET_TICKS_SCHEMA)
    
    # パーティション付きで S3 に書き込み
    pq.write_to_dataset(
        table=df,
        root_path=s3_path,
        partition_cols=["instrument", "year", "month"],
        filesystem=s3_filesystem,
        compression="snappy"
    )
```

#### 7-3. バックテスト時のデータ整合性検証が不明確

**改善案 - バックテスト用データセット検証**:

```python
class BacktestDataValidator:
    """バックテスト用データの整合性・完全性を検証"""
    
    async def validate_dataset(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime
    ) -> DatasetValidationReport:
        """
        バックテスト前のデータ品質チェック
        
        検証項目:
        1. 時系列完全性（ギャップ検知）
        2. データ型・値域チェック
        3. スプレッド異常検知
        4. タイムスタンプ順序性
        """
        
        # 1. 日付ごとのティック数を集計
        daily_tick_counts = {}
        for date in self._date_range(start_date, end_date):
            count = await self._count_ticks_for_date(instrument, date)
            daily_tick_counts[date] = count
        
        # 2. 異常な日を検出（ティック数が通常の 50% 以下）
        median_ticks = sorted(daily_tick_counts.values())[len(daily_tick_counts)//2]
        anomalous_dates = [
            date for date, count in daily_tick_counts.items()
            if count < median_ticks * 0.5
        ]
        
        # 3. 金曜夜 → 月曜朝のギャップは許容（市場休場）
        allowed_gaps = self._get_allowed_market_holidays(start_date, end_date)
        unexpected_gaps = [
            d for d in anomalous_dates
            if d not in allowed_gaps
        ]
        
        return DatasetValidationReport(
            instrument=instrument,
            start_date=start_date,
            end_date=end_date,
            total_days=len(daily_tick_counts),
            days_with_gaps=len(anomalous_dates),
            expected_gaps=len(allowed_gaps),
            unexpected_gaps=unexpected_gaps,
            validation_status="PASS" if not unexpected_gaps else "WARN"
        )
```

---

## 総括

データ層・Feature Store・データ品質に関する実装に向けて、以下のドキュメント作成が緊急要件です：

1. **Feature Store 詳細仕様書**
   - Version 管理・キャッシュ無効化ロジック
   - バックテスト/本番共用の整合性保証
   - Point-in-Time 復元方法

2. **TimescaleDB スキーマ・パーティション定義書**
   - ハイパーテーブル具体定義
   - インデックス戦略
   - コールドストレージ連携

3. **データ品質スコア算出仕様**
   - 計算式、ウェイト、閾値
   - 低下時の自動対応フロー

4. **Market Regime Detection 実装仕様**
   - Phase 1 指標の閾値テーブル
   - 複合レジーム判定マトリックス

5. **OANDA API 適応戦略仕様**
   - レート制限・API上限対応
   - ストリーム切断時の欠損補完フロー

6. **Redis / PostgreSQL 配置・同期仕様**
   - データタイプ別配置マップ
   - WAL パターンの詳細

7. **ヒストリカルデータ調達・管理仕様**
   - Parquet スキーマ
   - バックテスト用データセット管理

これらの仕様書が完成すれば、実装チームは依存関係なく並行開発可能となります。

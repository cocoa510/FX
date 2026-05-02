# FTS 結果表示

FTS のペーパー/Live トレード結果、PnL、最新シグナル、log tail をターミナルに出力します。

## 引数
`$ARGUMENTS`:
- 引数なし — 全戦略の合計 PnL + Top/Bottom 5 + 最新シグナル
- `<strategy_id>` — 特定戦略のトレード履歴 + PnL 推移
- `--forward-test` — `forward_test_atlas_champions.json` の結果
- `--audit` — 直近 audit log (PTRC 判定) tail
- `--tail <N>` — Runner ログの最新 N 行 (デフォルト 20)
- `--pnl` — PnL 集計のみ (戦略別降順)

## 実行手順

### 引数なし (全体結果サマリー)
```bash
cd /c/data/works/FX/fx_trading_system && python -c "
import json
from pathlib import Path

state_dir = Path('logs/unified_state')
states = []
for sf in state_dir.glob('*.state.json'):
    try:
        s = json.loads(sf.read_text(encoding='utf-8'))
        states.append(s)
    except Exception:
        pass

if not states:
    print('(unified_state/ に state ファイルなし、Runner 未起動)')
    exit(0)

total_pnl = sum(s.get('total_realized_pnl_jpy', 0) or 0 for s in states)
total_orders = sum(s.get('orders_submitted', 0) or 0 for s in states)
total_fills = sum(s.get('orders_filled', 0) or 0 for s in states)
total_closes = sum(s.get('closes_completed', 0) or 0 for s in states)
open_pos = sum(1 for s in states if s.get('open_trade_id'))

print('=== FTS トレード結果サマリー ===')
print(f'戦略数: {len(states)}')
print(f'累計 orders: {total_orders} / fills: {total_fills} / closes: {total_closes}')
print(f'open ポジション: {open_pos}')
print(f'累計 realized PnL: {total_pnl:.2f} JPY')
print()

# PnL 降順 Top 5 / Bottom 5
states.sort(key=lambda s: s.get('total_realized_pnl_jpy', 0) or 0, reverse=True)
profitable = [s for s in states if (s.get('total_realized_pnl_jpy', 0) or 0) > 0]
unprofitable = [s for s in states if (s.get('total_realized_pnl_jpy', 0) or 0) < 0]

if profitable:
    print('--- Top 5 (利益) ---')
    for s in profitable[:5]:
        sid = s.get('strategy_id', '')
        pnl = s.get('total_realized_pnl_jpy', 0) or 0
        cl = s.get('closes_completed', 0) or 0
        print(f'  {sid}: {pnl:+.2f} JPY ({cl} closes)')

if unprofitable:
    print()
    print('--- Bottom 5 (損失) ---')
    for s in unprofitable[-5:]:
        sid = s.get('strategy_id', '')
        pnl = s.get('total_realized_pnl_jpy', 0) or 0
        cl = s.get('closes_completed', 0) or 0
        print(f'  {sid}: {pnl:+.2f} JPY ({cl} closes)')
"
```

### `<strategy_id>` 指定時 (戦略別トレード履歴)
```bash
cd /c/data/works/FX/fx_trading_system && python -c "
import json
from pathlib import Path
import sys

sid = '$ARGUMENTS'.split()[0]
sf = Path('logs/unified_state') / f'{sid}.state.json'
if not sf.exists():
    print(f'(state ファイルなし: {sf})'); sys.exit(0)

s = json.loads(sf.read_text(encoding='utf-8'))
print(f'=== {sid} トレード結果 ===')
print(f'実行モード: {s.get(\"execution_mode\")}')
print(f'処理 bar 数: {s.get(\"bars_processed\")}')
print(f'最終 bar: {s.get(\"last_bar_time\")}')
print()
print('--- シグナル統計 ---')
print(f'  LONG signals:  {s.get(\"signals_long\", 0)}')
print(f'  FLAT signals:  {s.get(\"signals_flat\", 0)}')
print(f'  SHORT signals: {s.get(\"signals_short\", 0)}')
print()
print('--- 注文統計 ---')
print(f'  submitted: {s.get(\"orders_submitted\", 0)}')
print(f'  filled:    {s.get(\"orders_filled\", 0)}')
print(f'  rejected:  {s.get(\"orders_rejected\", 0)}')
print(f'  closes:    {s.get(\"closes_completed\", 0)}')
print()
print('--- PnL ---')
print(f'  daily_realized_pnl_jpy: {s.get(\"daily_realized_pnl_jpy\", 0):.2f}')
print(f'  total_realized_pnl_jpy: {s.get(\"total_realized_pnl_jpy\", 0):.2f}')
print()
print('--- ポジション ---')
print(f'  open_trade_id:    {s.get(\"open_trade_id\")}')
print(f'  open_entry_price: {s.get(\"open_entry_price\")}')
print(f'  open_units:       {s.get(\"open_units\")}')
print(f'  intended:         {s.get(\"intended_direction\")}')
print(f'  updated_at:       {s.get(\"updated_at\")}')
"
```

### `--forward-test`
```bash
cd /c/data/works/FX/fx_trading_system && python -c "
import json
from pathlib import Path

f = Path('logs/forward_test_atlas_champions.json')
if not f.exists():
    print(f'(forward test 結果なし)'); exit(0)

d = json.loads(f.read_text(encoding='utf-8'))
print('=== Forward Test 結果 (atlas champions) ===')
print(f'期間: {d.get(\"period_start\")} ~ {d.get(\"period_end\")}')
print(f'holdout bars: {d.get(\"holdout_bars\")}')
print()
print(f'{\"strategy_id\":<25} | {\"label\":<25} | {\"signals\":>7} | {\"trades\":>6} | {\"WR\":>5} | {\"PnL JPY\":>10} | {\"PnL pips\":>8}')
print('-' * 110)
for r in d.get('results', []):
    sid = r.get('strategy_id', '')
    label = (r.get('label', '') or '')[:25]
    sigs = r.get('signals_generated', 0)
    closed = r.get('closed_trades', 0)
    wins = r.get('winning_trades', 0)
    wr = (wins / closed * 100) if closed else 0
    pnl_jpy = r.get('realized_pnl_jpy', 0) or 0
    pnl_pips = r.get('realized_pnl_pips', 0) or 0
    print(f'{sid:<25} | {label:<25} | {sigs:>7} | {closed:>6} | {wr:>4.1f}% | {pnl_jpy:>10.2f} | {pnl_pips:>8.2f}')
"
```

### `--audit` (PTRC 判定 tail)
```bash
cd /c/data/works/FX/fx_trading_system && \
  ls -t logs/audit/round_*/  2>/dev/null | head -1 | xargs -I {} ls -t logs/audit/{}/*.jsonl 2>/dev/null | head -3
echo "---LATEST AUDIT EVENTS---"
find /c/data/works/FX/fx_trading_system/logs/audit/ -name "*.jsonl" -type f 2>/dev/null | xargs ls -t 2>/dev/null | head -1 | xargs tail -10
```

### `--tail <N>` (Runner ログ tail)
```bash
N="${ARG:-20}"
echo "=== unified_runner.log tail $N ==="
tail -${N} /c/data/works/FX/fx_trading_system/logs/unified_runner.log 2>/dev/null
echo ""
echo "=== unified_runner.stderr.log tail ${N} ==="
tail -${N} /c/data/works/FX/fx_trading_system/logs/unified_runner.stderr.log 2>/dev/null
echo ""
echo "=== unified_runner.jsonl tail 5 (latest events) ==="
tail -5 /c/data/works/FX/fx_trading_system/logs/unified_runner.jsonl 2>/dev/null
```

### `--pnl` (PnL 集計のみ)
```bash
cd /c/data/works/FX/fx_trading_system && python -c "
import json
from pathlib import Path

def _fts_display_name(sid: str) -> str:
    mp = Path('trading_platform/strategies/imported') / sid / 'metadata.json'
    if not mp.exists(): return ''
    try:
        return json.loads(mp.read_text(encoding='utf-8')).get('display_name') or ''
    except Exception:
        return ''

states = []
for sf in Path('logs/unified_state').glob('*.state.json'):
    try:
        s = json.loads(sf.read_text(encoding='utf-8'))
        sid = s.get('strategy_id', sf.stem)
        states.append((sid, _fts_display_name(sid), s.get('total_realized_pnl_jpy', 0) or 0, s.get('closes_completed', 0) or 0))
    except Exception:
        pass

states.sort(key=lambda x: x[2], reverse=True)
print(f'{\"strategy_id\":<25} | {\"display_name\":<35} | {\"PnL JPY\":>12} | {\"closes\":>6}')
print('-' * 90)
total = 0
for sid, dn, pnl, cl in states:
    total += pnl
    print(f'{sid:<25} | {dn:<35} | {pnl:>12.2f} | {cl:>6}')
print('-' * 90)
print(f'{\"TOTAL\":<25} | {\"\":<35} | {total:>12.2f} |')
"
```

## 出力例

```
=== FTS トレード結果サマリー ===
戦略数: 18
累計 orders: 0 / fills: 0 / closes: 0
open ポジション: 0
累計 realized PnL: 0.00 JPY

(まだトレード未発生、Runner 起動後に動作開始)
```

```
=== Forward Test 結果 (atlas champions) ===
期間: 2025-12-01 ~ 2026-04-08
holdout bars: 8640

strategy_id               | label                     | signals | trades |   WR |    PnL JPY | PnL pips
--------------------------------------------------------------------------------------------------------------
ATLAS-2026-0408-041       | Gen41 旧ベースライン      |      14 |      7 | 71.4% |    5346.03 |    53.46
ATLAS-2026-0408-065       | Gen65 SL=1.8              |       9 |      4 | 50.0% |   -1234.56 |   -12.35
ATLAS-2026-0408-085       | Gen85 現チャンピオン      |      11 |      5 | 60.0% |    2102.34 |    21.02
```

## エラーハンドリング
- `unified_state/` 空 → 「Runner 未起動」
- forward_test_atlas_champions.json 欠落 → 「`python scripts/forward_test_atlas_champions.py` 実行を案内」
- audit ログ空 → 「PTRC 判定未発生」

## 注意事項
- **stdout のみ出力**、Streamlit Dashboard は使用しない
- PnL は state.json の `total_realized_pnl_jpy` 直接読み (DB 経由なし)
- Runner ログ tail は `tail -N` で柔軟に行数指定可能
- 詳細な戦略 state は `/fts-status <strategy_id>` を参照

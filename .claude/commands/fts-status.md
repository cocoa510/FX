# FTS ステータス表示

FTS (fx_trading_system) の運用状態をターミナルに出力します。Web UI なし、stdout のみ。

## 引数
`$ARGUMENTS`:
- 引数なし — 全体サマリー (戦略数、Runner 稼働状況、各戦略の最新 state、合計 PnL)
- `<strategy_id>` — 特定戦略の詳細 state
- `--runner` — Runner プロセス稼働状態のみ表示
- `--strategies` — imported 戦略一覧のみ表示

## 実行手順

### 引数なし (全体サマリー)
```bash
cd /c/data/works/FX/fx_trading_system && python -c "
import json, glob, subprocess
from pathlib import Path
from datetime import datetime, timezone

# 1) imported 戦略一覧
imported = sorted(p.name for p in Path('trading_platform/strategies/imported').glob('ATLAS-*'))
fwdtest = sorted(p.name for p in Path('trading_platform/strategies/imported').glob('FWDTEST-*'))

print('=== FTS ステータス ===')
print(f'imported 戦略: {len(imported)} 件 (ATLAS) + {len(fwdtest)} 件 (FWDTEST)')

# 2) Runner プロセス稼働確認 (Windows: tasklist or ps)
runner_alive = False
try:
    result = subprocess.run(['ps', '-ef'], capture_output=True, text=True, timeout=5)
    runner_alive = 'run_unified.py' in result.stdout
except Exception:
    pass
runner_state = '稼働中' if runner_alive else '停止'

# 3) Runner 最終イベント
last_event = None
last_bar_time = None
jl = Path('logs/unified_runner.jsonl')
if jl.exists():
    try:
        with jl.open(encoding='utf-8') as f:
            lines = f.readlines()
        if lines:
            last = json.loads(lines[-1])
            last_event = last.get('event')
            last_bar_time = last.get('bar_time') or last.get('ts')
    except Exception:
        pass

print(f'Runner: {runner_state}')
if last_event:
    print(f'  最終イベント: {last_event} @ {last_bar_time}')

# 4) 各戦略の state サマリー
state_dir = Path('logs/unified_state')

def _fts_display_name(sid: str) -> str:
    '''FTS imported 戦略の metadata.json から display_name を取得。'''
    mp = Path('trading_platform/strategies/imported') / sid / 'metadata.json'
    if not mp.exists():
        return ''
    try:
        return json.loads(mp.read_text(encoding='utf-8')).get('display_name') or ''
    except Exception:
        return ''

if state_dir.exists():
    print()
    print('--- 戦略別 state サマリー ---')
    print(f'{\"strategy_id\":<25} | {\"display_name\":<35} | {\"bars\":>6} | {\"signals\":>7} | {\"fills\":>5} | {\"PnL JPY\":>10} | {\"open\":>6}')
    print('-' * 130)
    total_pnl = 0.0
    open_count = 0
    for sf in sorted(state_dir.glob('*.state.json')):
        try:
            s = json.loads(sf.read_text(encoding='utf-8'))
        except Exception:
            continue
        sid = s.get('strategy_id', sf.stem)
        dn = _fts_display_name(sid)
        bars = s.get('bars_processed', 0)
        sigs = (s.get('signals_long', 0) or 0) + (s.get('signals_flat', 0) or 0) + (s.get('signals_short', 0) or 0)
        fills = s.get('orders_filled', 0)
        pnl = s.get('total_realized_pnl_jpy') or 0.0
        total_pnl += pnl
        open_id = s.get('open_trade_id')
        open_mark = '★' if open_id else ''
        if open_id:
            open_count += 1
        print(f'{sid:<25} | {dn:<35} | {bars:>6} | {sigs:>7} | {fills:>5} | {pnl:>10.2f} | {open_mark:>6}')

    print()
    print(f'合計 realized PnL: {total_pnl:.2f} JPY')
    print(f'open ポジション: {open_count} 件')
"
```

### `<strategy_id>` 指定時 (戦略詳細)
```bash
cd /c/data/works/FX/fx_trading_system && python -c "
import json, sys
from pathlib import Path

sid = '$ARGUMENTS'.split()[0]

# display_name lookup
dn = ''
mp = Path('trading_platform/strategies/imported') / sid / 'metadata.json'
if mp.exists():
    try:
        dn = json.loads(mp.read_text(encoding='utf-8')).get('display_name') or ''
    except Exception:
        pass
header = f'{sid} ({dn})' if dn else sid

# state.json
sf = Path('logs/unified_state') / f'{sid}.state.json'
if not sf.exists():
    print(f'=== {header} ===')
    print(f'(state ファイル未作成: {sf}、Runner 未起動 or 戦略未動作)')
else:
    s = json.loads(sf.read_text(encoding='utf-8'))
    print(f'=== {header} 詳細 state ===')
    for k, v in s.items():
        print(f'  {k}: {v}')

# imported config
cf = Path('trading_platform/strategies/imported') / sid / 'config.json'
if cf.exists():
    c = json.loads(cf.read_text(encoding='utf-8'))
    print()
    print('--- config (主要パラメータ) ---')
    print(f'  instrument: {c.get(\"instrument\")} / {c.get(\"timeframe\")}')
    params = c.get('parameters', {}) or {}
    for k, v in list(params.items())[:10]:
        print(f'  {k}: {v}')

# gate_results.json
gf = Path('trading_platform/strategies/imported') / sid / 'gate_results.json'
if gf.exists():
    g = json.loads(gf.read_text(encoding='utf-8'))
    print()
    print('--- gate_results (BT 由来) ---')
    print(f'  overall_passed: {g.get(\"overall_passed\")}')
    gc = g.get('gate_check', {}) or {}
    print(f'  Tier1 PASS: {gc.get(\"tier1\", {}).get(\"passed_count\") or gc.get(\"passed_count\", \"?\")}')
    print(f'  soft_score: {gc.get(\"soft_score\")}')
"
```

### `--runner` (Runner 稼働状態のみ)
```bash
ps -ef | grep -E "run_unified.py|fx_trading_system" | grep -v grep
echo "---"
tail -5 /c/data/works/FX/fx_trading_system/logs/unified_runner.log 2>/dev/null
echo "---LATEST EVENT---"
tail -1 /c/data/works/FX/fx_trading_system/logs/unified_runner.jsonl 2>/dev/null
```

### `--strategies` (戦略一覧のみ)
```bash
ls /c/data/works/FX/fx_trading_system/trading_platform/strategies/imported/ | sort
echo "---計 $(ls /c/data/works/FX/fx_trading_system/trading_platform/strategies/imported/ | wc -l) 件---"
```

## 出力例

```
=== FTS ステータス ===
imported 戦略: 17 件 (ATLAS) + 1 件 (FWDTEST)
Runner: 停止
  最終イベント: new_bar @ 2026-04-10T20:59:00.000000000Z

--- 戦略別 state サマリー ---
strategy_id               |   bars | signals | orders | fills |    PnL JPY |   open | updated
--------------------------------------------------------------------------------------------------------------
ATLAS-2026-0408-041       |     52 |       0 |      0 |     0 |       0.00 |        | 2026-04-11T04:06:08
ATLAS-2026-0408-065       |     52 |       0 |      0 |     0 |       0.00 |        | 2026-04-11T04:06:08
ATLAS-2026-0408-085       |     52 |       0 |      0 |     0 |       0.00 |        | 2026-04-11T04:06:08
...

合計 realized PnL: 0.00 JPY
open ポジション: 0 件
```

## エラーハンドリング
- `unified_state/` 空 → 「Runner 未起動。`python scripts/run_unified.py` を実行してください」
- 戦略 ID 存在しない → imported 戦略一覧を表示
- Runner プロセス検出失敗 (Windows ps コマンド非対応) → unified_runner.log の最終更新時刻で代替判定

## 注意事項
- **stdout のみ出力**、Streamlit Dashboard は使用しない
- Runner 稼働確認は `ps` ベース。Windows 環境では `tasklist /fi "imagename eq python.exe"` 推奨
- 詳細な PnL/トレード分析は `/fts-results` を使用

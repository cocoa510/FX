# ATLAS ステータス表示

ATLAS 戦略の現状をターミナルに出力します。Web UI なし、stdout のみ。

## 引数
`$ARGUMENTS`:
- 引数なし — 全体サマリー (戦略数、Gate PASS 率、最新 atlas-loop セッション、上位 5 件)
- `<generation_id>` — 特定戦略の Gate 詳細 + L1/L2 metrics
- `--top <N>` — Gate 通過戦略の上位 N 件 (デフォルト 10)
- `--all` — 全戦略を Gate 状態でフィルタリングして表示
- `--instrument <USD_JPY>` — 特定通貨ペアのみ
- `--type <mean_reversion>` — 特定タイプのみ

## 実行手順

### 引数なし (全体サマリー)
```bash
cd ATLAS && .venv/Scripts/python.exe -c "
import json, glob
from pathlib import Path

def _display_name(sid: str) -> str:
    '''metadata.json から display_name を取得（無ければ空文字）。'''
    mp = Path('strategies') / sid / 'metadata.json'
    if not mp.exists():
        return ''
    try:
        return json.loads(mp.read_text(encoding='utf-8')).get('display_name') or ''
    except Exception:
        return ''

def _label(sid: str) -> str:
    '''表示用ラベル: ATLAS-... (display_name) を返す。'''
    dn = _display_name(sid)
    return f'{sid} ({dn})' if dn else sid

strategy_dirs = sorted(glob.glob('strategies/ATLAS-*'))
total = len(strategy_dirs)
passed = 0
gate_pass_strategies = []
edge_candidates = []

for d in strategy_dirs:
    sid = Path(d).name
    rj = Path(d) / 'backtest' / 'result.json'
    if not rj.exists():
        continue
    try:
        r = json.loads(rj.read_text(encoding='utf-8'))
    except Exception:
        continue
    if r.get('overall_passed'):
        passed += 1
        gate_pass_strategies.append((sid, r))
        continue
    g = r.get('gate_check', {}) or {}
    pc = g.get('passed_count', 0)
    tc = g.get('total_conditions', 0)
    soft = g.get('soft_score', 0) or 0
    if pc >= 4 and tc == 6:
        l1 = r.get('layer1', {}) or {}
        edge_candidates.append((sid, r, l1, pc, tc, soft))

print(f'=== ATLAS ステータス ===')
print(f'総戦略数: {total}')
print(f'Full Gate PASS: {passed}/{total} ({passed/max(total,1)*100:.1f}%)')
print(f'エッジ候補 (Tier1 4/6+): {len(edge_candidates)}')
print()

if gate_pass_strategies:
    print('--- Full Gate PASS 戦略 ---')
    for sid, r in gate_pass_strategies[:10]:
        l1 = r.get('layer1', {}) or {}
        print(f'  {_label(sid)}: PF={l1.get(\"profit_factor\"):.3f} Sharpe={l1.get(\"sharpe_ratio\"):.3f} trades={l1.get(\"total_trades\")}')
else:
    print('--- Full Gate PASS 戦略: 0 件 ---')

if edge_candidates:
    print()
    print('--- エッジ候補 (Tier1 4/6+) Top 5 ---')
    edge_candidates.sort(key=lambda x: x[5], reverse=True)
    for sid, r, l1, pc, tc, soft in edge_candidates[:5]:
        pf = l1.get('profit_factor')
        sharpe = l1.get('sharpe_ratio')
        trades = l1.get('total_trades')
        print(f'  {_label(sid)}: Tier1 {pc}/{tc} soft={soft:.3f} PF={pf:.2f} Sharpe={sharpe:.2f} trades={trades}')
"
```

### 最新 atlas-loop セッション状態
```bash
cd ATLAS && cat logs/loop_session.json 2>/dev/null | .venv/Scripts/python.exe -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'\n--- 最新 atlas-loop セッション ---')
    print(f'session_id: {d.get(\"session_id\")}')
    print(f'phase: {d.get(\"phase\")}')
    print(f'elapsed: {d.get(\"elapsed_minutes\")} min / {d.get(\"limit_minutes\")} min')
    print(f'completed_generations: {len(d.get(\"completed_generations\", []))}')
    print(f'gate_pass_generations: {d.get(\"gate_pass_generations\", [])}')
    if d.get('last_alert'):
        a = d['last_alert']
        print(f'last_alert: [{a.get(\"level\")}] {a.get(\"alert_type\")}: {a.get(\"reason\",\"\")[:80]}')
except Exception as e:
    print(f'(loop_session.json 読み取り失敗: {e})')
"
```

### `<generation_id>` 指定時 (特定戦略)
```bash
cd ATLAS && .venv/Scripts/python.exe -c "
import json, sys
from pathlib import Path
sid = '$ARGUMENTS'.split()[0]
d = Path('strategies') / sid
if not d.exists():
    print(f'戦略 {sid} が見つかりません'); sys.exit(1)

rj = d / 'backtest' / 'result.json'
if not rj.exists():
    print(f'{sid}: backtest/result.json なし (未実行)'); sys.exit(0)

r = json.loads(rj.read_text(encoding='utf-8'))
l1 = r.get('layer1', {}) or {}
l2 = r.get('layer2', {}) or {}
g = r.get('gate_check', {}) or {}

# display_name 取得（人間表示用エイリアス、metadata.json::display_name 参照）
mp = d / 'metadata.json'
display_name = ''
if mp.exists():
    try:
        display_name = json.loads(mp.read_text(encoding='utf-8')).get('display_name') or ''
    except Exception:
        pass
header = f'{sid} ({display_name})' if display_name else sid

print(f'=== {header} ===')
print(f'instrument: {r.get(\"instrument\")} / {r.get(\"timeframe\")}')
print(f'overall_passed: {r.get(\"overall_passed\")}')
print()
print('--- Layer 1 (vectorbt) ---')
print(f'  PF: {l1.get(\"profit_factor\")}')
print(f'  Sharpe: {l1.get(\"sharpe_ratio\")}')
print(f'  trades: {l1.get(\"total_trades\")}')
print(f'  WR: {l1.get(\"win_rate\")}')
print(f'  MaxDD %: {l1.get(\"max_drawdown_pct\")}')
print()
print('--- Layer 2 (Event-Driven) ---')
print(f'  PF: {l2.get(\"profit_factor\")}')
print(f'  Sharpe: {l2.get(\"sharpe_ratio\")}')
print(f'  trades: {l2.get(\"total_trades\")}')
print()
print('--- Gate Check ---')
print(f'  Tier1 passed: {g.get(\"passed_count\")}/{g.get(\"total_conditions\")}')
print(f'  Soft Score: {g.get(\"soft_score\")} (threshold 0.70)')
fc = g.get('failed_conditions') or []
if fc:
    print(f'  Failed conditions:')
    for c in fc:
        print(f'    - {c}')
"
```

### `--top <N>` 指定時 (Gate 通過上位)
```bash
cd ATLAS && .venv/Scripts/python.exe -m atlas.main history top --limit ${N:-10} 2>/dev/null | .venv/Scripts/python.exe -c "
import sys, json
from pathlib import Path
data = json.load(sys.stdin)
print('=== ATLAS Top スコア戦略 ===')
print(f'{\"順位\":>3} | {\"戦略ID\":<22} | {\"表示名\":<35} | {\"世代\":>4} | {\"スコア\":>6} | {\"状態\":<12} | {\"Effort\":<18}')
print('-' * 132)
for i, s in enumerate(data, 1):
    sid = s.get('strategy_id', '')
    # display_name と agent_effort を metadata.json から取得
    dn = ''
    effort = ''
    mp = Path('strategies') / sid / 'metadata.json'
    if mp.exists():
        try:
            meta = json.loads(mp.read_text(encoding='utf-8'))
            dn = meta.get('display_name') or ''
            cfg = meta.get('generation_agent_config') or {}
            fx_e = cfg.get('fx_strategist_effort', '')
            qa_e = cfg.get('quant_analyst_effort', '')
            if fx_e or qa_e:
                effort = f'fx:{fx_e}/qa:{qa_e}' if fx_e != qa_e else fx_e
        except Exception:
            pass
    print(f'{i:>3} | {sid:<22} | {dn:<35} | {s.get(\"generation\",0):>4} | {s.get(\"final_score\",0):>6.3f} | {s.get(\"status\",\"\"):<12} | {effort:<18}')
"
```

## 出力例

```
=== ATLAS ステータス ===
総戦略数: 92
Full Gate PASS: 0/92 (0.0%)
エッジ候補 (Tier1 4/6+): 1

--- Full Gate PASS 戦略: 0 件 ---

--- エッジ候補 (Tier1 4/6+) Top 5 ---
  ATLAS-2026-0426-014: Tier1 4/6 soft=0.468 PF=1.57 Sharpe=0.65 trades=31

--- 最新 atlas-loop セッション ---
session_id: ATLAS-LOOP-2026-0426-002
phase: completed_94pct_guard
elapsed: 269 min / 300 min
completed_generations: 14
gate_pass_generations: []
last_alert: [INFO] session_completed_94pct_guard: ...
```

## エラーハンドリング
- `strategies/` 空 → 「戦略未生成、`/atlas-loop` で生成してください」
- 指定 ID 存在しない → 利用可能な戦略 ID を 5 件提示
- result.json 読込失敗 → 戦略単位で skip、warning 出力

## 注意事項
- 出力は stdout のみ、Web UI / ファイル書き込みなし
- History Store (SQLite) ではなく **戦略ディレクトリ直接走査** が一次データソース (確実性優先)
- 詳細な比較は `/atlas-compare`、系譜表示は `/atlas-history` を使用

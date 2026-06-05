$code = @'
import json, pathlib

OUT = pathlib.Path('C:/data/works/FX/logs/audit/AUDIT-2026-0525-002/validation_fts_core.json')

ip = '_in_position'
bp = '_bars_in_position'
po = '_position'
id_ = '_intended_direction'
dqe = 'DataQualityEngine'
ptrc_cls = 'PreTradeRiskControl'
occ = 'OandaCurrencyConverter'

def mk(i, osev, val, asev, repro, adopt, rat):
    return {'id':i,'original_severity':osev,'validated':val,'adjusted_severity':asev,'reproducible':repro,'adoption_level':adopt,'rationale':rat}

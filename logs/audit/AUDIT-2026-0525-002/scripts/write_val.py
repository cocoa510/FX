import json, pathlib

OUTFILE = pathlib.Path("C:/data/works/FX/logs/audit/AUDIT-2026-0525-002/validation_fts_core.json")

def mk(id, osev, val, asev, repro, adopt, rat):
    return {"id":id,"original_severity":osev,"validated":val,"adjusted_severity":asev,"reproducible":repro,"adoption_level":adopt,"rationale":rat}

results = []
results.append(mk("PA-101","high","true","high",True,"must_fix","strategy_slot.py:1287: if hasattr(self.strategy, _in_position) guard confirmed. ATLAS-0501-004/strategy.py:210-212: _position/_bars_in_position defined, _in_position absent. ATLAS-0511-059/strategy.py:61: _intended_direction defined, _in_position absent. grep imported 60 strategies: _in_position attribute 0 matches, _bars_in_position 25 matches. Restore block dead code for all 60 strategies. _intended_direction-type partially rescued at line:1262. _position+_bars_in_position type left FLAT after restart. Live: max_hold never fires, double-entry risk. must_fix."))
print("first result ok")

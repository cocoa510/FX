import json, pathlib
out = pathlib.Path(r'C:/data/works/FX/logs/audit/AUDIT-2026-0525-002/verification/fix_review_wave2.json')
items = []
items.append({'fix_id': 'DM-106', 'file': 'scripts/run_unified.py', 'verdict': 'APPROVE_WITH_NOTES', 'intent_adequate': True, 'intent_note': 'Prometheus exposition server 追加の意図に完全適合。port=0 early-return, ImportError/OSError catch, getattr registry 安全パターンすべて実装済み。', 'issues': [{'severity': 'WARNING_ADVISORY', 'title': 'OSError 時にポートが使用中かどうかを明示しない', 'detail': '_start_metrics_server の OSError ハンドラはログに留まりプロセス継続する。port 衝突時に Prometheus scrape が無言で失敗しアラート不発になるリスク。', 'recommendation': '現状のログ記録で十分。次回改良時に FTS_METRICS_PORT の別ポートを自動試行する改善を検討。'}], 'secrets_found': False, 'regression_risk': 'LOW'})
items.append({'fix_id': 'DM-103', 'file': 'trading_platform/core/risk_engine/ptrc.py', 'verdict': 'APPROVE', 'intent_adequate': True, 'intent_note': 'fire-and-forget asyncio タスクの GC 喪失防止を正確に解消。_fire_risk_alert (RE-101) と _fire_ptrc_audit の両方に同一パターンを適用。', 'issues': [], 'ptrc_safety': {'result': 'SAFE', 'detail': 'RE-101 の _fire_risk_alert 呼び出しロジック（None チェック、RuntimeError ハンドラ）はそのまま保持。task 参照保持は asyncio スケジューラに影響しないため PTRC 判定フローへの副作用なし。done callback の discard により set は O(1) 定常サイズを維持。'}, 'secrets_found': False, 'regression_risk': 'VERY_LOW'})
items.append({'fix_id': 'DM-101', 'file': 'trading_platform/dashboard/app.py', 'verdict': 'APPROVE_WITH_NOTES', 'intent_adequate': True, 'intent_note': 'API_BASE_URL env 化と state ファイル直接読み取りの両対応が意図に適合。HTTP モード/ファイルモードのフォールバック設計は本番監視に有効。', 'issues': [{'severity': 'WARNING_ADVISORY', 'title': 'state ファイル読み取り時の並行書き込みレース', 'detail': '_read_state_files() は glob した各 .state.json を json.loads() するが、UnifiedRunner が同時書き込み中の場合に部分読み取りで JSONDecodeError が発生しうる。現状は try/except で吸収し空 dict を返すため表示が欠落するだけで致命的ではない。', 'recommendation': 'ファイル読み取りの try/except は現状で十分安全。次回改良時にアトミック書き込み（tmp -> rename）を UnifiedRunner 側で実装することを推奨。'}], 'secrets_found': False, 'regression_risk': 'LOW'})
items.append({'fix_id': 'PA-103', 'file': 'trading_platform/main.py', 'verdict': 'APPROVE', 'intent_adequate': True, 'intent_note': 'initialize() 冒頭のガードが ENV=production の main.py 経由 LIVE 起動を確実に拒否。エスケープハッチ (1/true/yes 大文字小文字無視) も正確に実装。', 'issues': [], 'fail_closed_validation': {'result': 'VALID', 'production_blocked': True, 'staging_unaffected': True, 'research_unaffected': True, 'runner_unaffected': True, 'detail': 'UnifiedRunner は TradingPlatform.initialize() を呼ばない別経路 (scripts/run_unified.py -> runner.py) であり PA-103 ガードは本番運用に影響しない。DE-101/RE-101 の hunk はガード後に配置されており既存ウォイヤリングは破壊されない。RuntimeError メッセージに PA-103/run_unified.py/UnifiedRunner を全含み、テスト contract に一致。'}, 'secrets_found': False, 'regression_risk': 'VERY_LOW'})
items.append({'fix_id': 'DM-104', 'file': '.env.example', 'verdict': 'APPROVE', 'intent_adequate': True, 'intent_note': '追加された 4 変数 (FTS_METRICS_PORT/FTS_DASHBOARD_API_BASE_URL/FTS_DASHBOARD_STATE_DIR/FTS_WATCHDOG_WEBHOOK_URL) はすべてコメントアウトまたはプレースホルダー値のみ。', 'issues': [], 'secrets_found': False, 'secrets_detail': 'Webhook URL は https://hooks.slack.com/services/xxx/yyy/zzz のプレースホルダーのみ。実キーの混入なし。Windows 絶対パスの FTS_DASHBOARD_STATE_DIR は移植性の観点で WARNING_ADVISORY だが機微情報ではない。', 'regression_risk': 'NONE'})
items.append({'fix_id': 'QT-102', 'file': 'tests/parity/*.py, tests/integration/fixtures/atlas_scenario_fixtures.py 他複数', 'verdict': 'APPROVE', 'intent_adequate': True, 'intent_note': 'OHLC 整合化 (high = max(open,close)*(1+...) ) がテスト fixture のみに適用。本番コード変更なし。', 'issues': [], 'parity_invariant': {'result': 'PRESERVED', 'detail': '両側（ATLAS _SimpleFeatureStore / Live LiveFeatureStore）に同一 fixture データを投入するため、high/low 値がどのように変わっても差は 0 のまま。parity 不変条件 (delta=0) は維持される。'}, 'production_code_changed': False, 'regression_risk': 'VERY_LOW'})
items.append({'fix_id': 'QT-101', 'file': 'tests/fault/test_reconnect_cycle.py', 'verdict': 'APPROVE', 'intent_adequate': True, 'intent_note': 'list[dict] -> list[OpenTrade] への型修正。PR52-M-C3 で導入された OpenTrade Pydantic モデルに合わせたテスト fixture の整合化。', 'issues': [], 'secrets_found': False, 'regression_risk': 'VERY_LOW'})
items.append({'fix_id': 'QT-103', 'file': 'tests/integration/test_atlas_top3_strategies.py', 'verdict': 'APPROVE', 'intent_adequate': True, 'intent_note': 'signal=0 ケースの warnings.warn (偽陽性 PASS) を pytest.xfail に置換。既知の失敗を正しく追跡する形式に修正。', 'issues': [], 'secrets_found': False, 'regression_risk': 'VERY_LOW'})
items.append({'fix_id': 'TEST_UNIT_DM101_DM103_DM106_DM104', 'file': 'tests/unit/test_dm101_dm103_dm106_dm104.py', 'verdict': 'APPROVE_WITH_NOTES', 'intent_adequate': True, 'intent_note': 'DM-101/103/106/104 の各機能を適切にカバー。sys.modules delete + reimport による dashboard モジュール再ロードは env 依存テストとして正しい手法。', 'issues': [{'severity': 'WARNING_ADVISORY', 'title': 'atlas パッケージへの CI 依存', 'detail': 'DM-103 テストが from atlas.common.models import SignalDirection をインポートする。CI 環境に atlas パッケージが存在しない場合はテスト収集段階で ImportError になる。', 'recommendation': 'pytest.importorskip または conftest の sys.path 設定で対処。fx_trading_system の既存 CI は ATLAS パスを追加しているため現状環境では問題なし。'}], 'secrets_found': False, 'regression_risk': 'LOW'})
items.append({'fix_id': 'TEST_UNIT_PA103', 'file': 'tests/unit/test_main_production_live_guard.py', 'verdict': 'APPROVE', 'intent_adequate': True, 'intent_note': '_reset_prometheus_registry autouse fixture がテスト間の重複登録エラーを防止。PA-103 ガードの全ケース（拒否 / 通過 / エスケープハッチ truthy/falsy）を網羅。非同期テスト (initialize 経由) も含む。', 'issues': [], 'secrets_found': False, 'regression_risk': 'VERY_LOW'})

overall_verdicts = [i["verdict"] for i in items]
has_reject = any(v == "REJECT" for v in overall_verdicts)
has_blocking = False
blockers = []

overall_notes = [
    "DM-106: OSError 時のポート衆突はログ記録のみで継続。Prometheus scrape 不発リスクは許容範囲。次回改良時に対処推奨。",
    "DM-101: state ファイル並行書き込みレースは try/except で安全に吸収済み。アトミック書き込みは将来課題。",
    "TEST_UNIT_DM101_DM103_DM106_DM104: atlas パッケージの CI 可用性を確認すること。",
    ".env.example の Windows 絶対パスは移植性の観点から WARNING_ADVISORY。機微情報なし。"
]

commit_rec = "コミット可。blocker なし。APPROVE_WITH_NOTES 3 件はいずれも WARNING_ADVISORY（次回改良時対処）。PA-103/DM-103 のセキュリティ・安全性修正は正確に実装されており本番適用を推奨する。"

report = {
    "audit_id": "AUDIT-2026-0525-002",
    "review_wave": 2,
    "review_type": "medium_cluster_diff_review",
    "reviewed_at": "2026-05-25T00:00:00+09:00",
    "reviewer": "code-safety-reviewer (claude-sonnet-4-6)",
    "overall_verdict": "REJECT" if has_reject else ("APPROVE_WITH_NOTES" if any(v == "APPROVE_WITH_NOTES" for v in overall_verdicts) else "APPROVE"),
    "commit_ok": not has_reject and not has_blocking,
    "blockers": blockers,
    "summary": {
        "total_fixes_reviewed": len(items),
        "approve": sum(1 for v in overall_verdicts if v == "APPROVE"),
        "approve_with_notes": sum(1 for v in overall_verdicts if v == "APPROVE_WITH_NOTES"),
        "reject": sum(1 for v in overall_verdicts if v == "REJECT"),
        "advisory_warnings": 4
    },
    "items": items,
    "overall_notes": overall_notes,
    "commit_recommendation": commit_rec
}

out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("done", out.stat().st_size, "bytes")

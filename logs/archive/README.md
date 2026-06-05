# logs/archive — 完了済み監査・修正サイクルの履歴

2026-05-26 に `logs/` 直下を整理した際、**完了済みサイクルの履歴レポート**をここへ退避した。
現行の正本は `logs/` 直下・`logs/audit/` ツリーに残置。中間版（v1/v2）と pytest 一時ログは削除済み。

## 退避ファイル（時系列）

| ファイル | 内容 | 位置付け |
|---------|------|---------|
| `audit_report_2026_0521.md` | 0521 総合監査レポート（専門家7名） | 完了サイクルの起点 |
| `remediation_plan_2026_0521.md` | 0521 修正計画 v2（A/B/C/D 完了済） | 〃 |
| `execution_playbook_2026_0521.md` | 0521 PR 実行プレイブック | 〃 |
| `audit_report_2026_0524_v2.md` | 0524 再監査レポート v2（H-19 撤回・最終版） | A/B/C/D 後の再監査 |
| `audit_r2_completion_2026_0524.md` | R2 完了レポート（PR25-36） | R2 完了記録 |
| `audit_r2_meta_2026_0524.md` | R2 メタ監査レポート（4専門家） | R2 検証記録 |
| `summary_AUDIT-2026-0525-001.md` | AUDIT-001 総括（2026-05-28 退避） | AUDIT-002 に「全件完了」が誤りと判明し被超越 |
| `data_review_detailed_report.md` | データ品質詳細調査レポート（2026-04-07、2026-05-28 にリポジトリルートから退避） | 機能以前の改善調査ドキュメント |

## 現行の正本（`logs/` 直下・`logs/audit/`、退避していない）

- `logs/audit_2026_0524_remediation_plan_v3.md` — FTS 修正計画 正本（実行可能版）
- `logs/audit/summary_AUDIT-2026-0525-002.md` — AUDIT-002 正本
- `logs/audit/round_1/fixes_applied*.json` — AUDIT-001 正本
- `logs/audit/AUDIT-2026-0525-002/` — AUDIT-002 エビデンス一式
- `logs/audit_loop_session.json` — /audit-loop セッション状態

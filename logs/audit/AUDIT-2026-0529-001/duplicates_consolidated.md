# 重複 Finding 統合宣言 — AUDIT-2026-0529-001

作成日: 2026-05-29
担当エージェント: devops-monitor

## 統合対象: QT-307 / QT-317 / DM-313

これら 3 finding は同一根因（parity.yml に unit テストが混在している）を
異なる角度から指摘したものであり、実質的に重複している。

| Finding | 元の指摘 |
|---------|---------|
| QT-307  | parity.yml に unit tests ステップが含まれ CI の意図が不明確 |
| QT-317  | unit.yml が存在せず unit テスト専用ワークフローがない |
| DM-313  | unit tests 失敗通知が "Parity CI" 件名で届き parity 破壊と区別できない |

## 対応方針

本セッションでは **別ワークフロー分離は重い** と判断し、以下の軽量対処を実施した:

1. `.github/workflows/parity.yml:83` の "Run unit tests" ステップ直前に
   finding ID・影響範囲・将来分離計画を明記したコメントを追加
2. 運用上のリスクは低いため（動作には影響なし）、LOW として受容

## 将来対応指針

中規模タスクとして `.github/workflows/unit.yml` を新設し、
`parity.yml` から unit tests ステップを切り出す。
これにより:
- 通知メールの件名で unit 失敗と parity/contract 破壊を区別できる
- CI のステップ責務が明確になる

本 finding は QT-307 を正本とし、QT-317 / DM-313 を重複として統合する。

# EVOLUTION.md — jarvis-todo-management

進化レビュー (`scripts/evolve.py review`) の提案・適用履歴を追記する (append-only)。

学習対象:

- 見積精度 (タスク種別ごとの所要時間の傾向)
- ファイルスキーマ (todo/memo/report に必要な列の昇格・削除)
- 聞き方 (チェックインでの問いの量・トーン、ストッパー確認の言い回し)
- backlog 推薦 (「今日やる候補」の選出ロジック)

---

(まだ進化レビューは実行されていない)
## 2026-08-06T01:44:41Z — auto-review

- **対象**: `jarvis-todo-management`
- **観測サイクル数 (window)**: 10
- **検出 signal 数**: 0

シグナルなし: 改善候補は見つかりませんでした。

メモ: 進化レビューを 1 サイクルとして pipeline.jsonl に記録すること (actions に `evolve.py` を含める)。

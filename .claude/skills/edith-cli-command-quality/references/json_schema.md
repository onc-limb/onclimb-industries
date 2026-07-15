# command-metrics.json スキーマ (ダッシュボード連携用)

`scripts/analyze_commands.py --out <dir>` が出力する `command-metrics.json` の形式。
外部のダッシュボードプロダクトはこのファイルを読み込んでメトリクスを可視化する。
`schema_version` で後方互換を判断する（破壊的変更時にインクリメント）。

```jsonc
{
  "schema_version": "1.0",
  "generated_at": "2026-07-03",          // 分析実行日 (YYYY-MM-DD)
  "source": {
    "root": "…/worklog-data/raw",        // 走査したログのルート
    "files_scanned": 128,                // 走査した *.jsonl の数
    "bash_invocations": 1543,            // Bash ツール呼び出しの総数
    "segments_analyzed": 2110            // パイプ/連結で分解した後のコマンド片数
  },
  "coverage": {                          // 網羅範囲(edith 原則: 打ち切りを明示)
    "scanned_glob": "**/*.jsonl",
    "notes": ["…"]                       // 取りこぼす条件など
  },
  "summary": {
    "unique_commands": 74,
    "ranked_commands": 40,
    "human_common_in_top": 22,           // 上位のうち「人間もよく使う」コマンド数
    "dangerous_hit_kinds": 3,            // 一致した危険パターンの種類数
    "dangerous_hit_total": 9             // 危険コマンドの延べ出現回数
  },

  // === 品質コマンドランキング (ダッシュボードの主データ) ===
  "commands": [
    {
      "rank": 1,
      "command": "git",                  // コマンド名(先頭語)
      "count": 312,                      // 出現回数
      "share": 0.1478,                   // 全コマンド片に占める割合(0-1)
      "category": "vcs",                 // 分類(catalog 由来)
      "human_common": true,              // 人間もよく使うか(学習の主対象)
      "in_catalog": true,                // 品質カタログに定義があるか
      "subcommands": [                   // 頻度上位のサブコマンド(git commit 等)
        { "name": "status", "count": 88 },
        { "name": "add", "count": 61 }
      ],
      "quality_checkpoints": [           // 使うとき確認すべき品質観点(学習ポイント)
        "コミット前に差分を確認したか", "…"
      ],
      "antipatterns_found": [            // ログ中で実際に見つかったアンチパターン
        {
          "label": "素の --force push",
          "advice": "--force-with-lease を使う",
          "count": 2,
          "examples": ["git push --force origin main"]  // 最大3件
        }
      ]
    }
    // … rank 順に continue
  ],

  // === 危険コマンド出現チェック ===
  "dangerous": [
    {
      "pattern_id": "rm_rf_var",
      "label": "変数展開先の再帰強制削除",
      "severity": "critical | high | medium | low",
      "advice": "空変数ガードを入れる",
      "count": 4,
      "occurrences": [                   // 最大15件
        { "command": "rm -rf $DIR/cache", "file": "session-xyz.jsonl" }
      ]
    }
  ]
}
```

## ダッシュボード側の想定利用

- **コマンドランキング棒グラフ**: `commands[].command` × `count`(または `share`)。
  `human_common` で色分け／フィルタすると「人間の学習対象」を強調できる。
- **品質バッジ**: `antipatterns_found` が空でない command に注意バッジ。
  `antipatterns_found[].count` の合計を「品質フラグ数」として集計できる。
- **危険コマンドパネル**: `dangerous[]` を `severity` で色分けし `count` を表示。
  `summary.dangerous_hit_total` を KPI タイルに出す。
- **学習ビュー**: `commands[].quality_checkpoints` をコマンド詳細のチェックリストに表示。

## 安定性の約束

- フィールドの**削除・意味変更**は `schema_version` のメジャー更新を伴う。
- フィールドの**追加**はマイナー更新（`1.0` → `1.1`）。既存フィールドは維持する。
- ダッシュボードは未知フィールドを無視して前方互換を保つこと。

# 自己進化パイプライン仕様

このドキュメントは「自己進化パイプライン」の厳密仕様です。SKILL.md は概要、ここは契約。

---

## 1. 用語

- **サイクル (cycle)**: 1 つの (instruction → reasoning → action → output → evaluation) の最小ループ。
- **ユーザー入力 (user_turn)**: ユーザーから来た 1 回のメッセージ。複数サイクルを含み得る。
- **完了条件 (completion_state)**: サイクルの結末を 4 値で分類するラベル。

---

## 2. サイクルの開始 / 終了

各サイクルは **必ず開始イベントと終了イベントの 2 行** を `logs/pipeline.jsonl` に持ちます。
ペアになっていないログは破損とみなし、進化レビュー時にスキップします。

### 開始イベント (event=`start`)

```json
{
  "event": "start",
  "cycle_id": "20260519T120000Z-a1b2",
  "parent_cycle_id": null,
  "skill_name": "karen-self-evolving-skill-creator",
  "started_at": "2026-05-19T12:00:00Z",
  "instruction": "ユーザーの指示要約 (PII マスク済み)",
  "context_hash": "sha1 of normalized inputs (任意)"
}
```

### 終了イベント (event=`end`)

```json
{
  "event": "end",
  "cycle_id": "20260519T120000Z-a1b2",
  "ended_at": "2026-05-19T12:00:18Z",
  "reasoning_summary": "...",
  "actions": [
    {"tool": "Read", "target": "SKILL.md"},
    {"tool": "Write", "target": "out.md"}
  ],
  "output_summary": "概要 + パス",
  "followup_feedback": null,
  "completion_state": "success",
  "completion_reason": "ユーザー基準すべて満たした",
  "assumption_notes": []
}
```

---

## 3. 完了条件 (completion_state) のセマンティクス

| 値 | 意味 | 例 |
|---|---|---|
| `success` | 達成基準を満たし、追加情報不要で受け渡し可能 | 「PDF を要約して」→ 要約が完成し検証済み |
| `failure` | 達成不可と判断した。原因も特定済み | 入力 PDF が破損しており復元不可 |
| `unknown` | 出力はしたが満たしているか判断不能 | 「これで合っていますか?」と聞く必要がある |
| `error` | 例外・ツール失敗・前提欠落で完遂できず | API 429、ファイル not found |

### 取り扱いルール

- `unknown` で終わったサイクルは、**同じ user_turn 内で次サイクルを起動** するか、**ユーザーに確認質問** を返す。確認質問で user_turn を閉じる場合、追加サイクルの起動は不要 (放置だけ禁止)。
- `error` は同サイクル内で復旧しない。新しいサイクルで対処する (parent_cycle_id を付ける)。
- `success` を宣言する条件は「**外部から検証可能な達成基準**」を満たしたことに限る。自己満足での `success` は禁止。

---

## 4. しきい値判定

`pipeline.py log-end` は終了イベント追記後に `pipeline.config.json` の `evolution_threshold` を読みます。
直近の進化レビュー以降にカウントされた **start イベントの累計** が閾値以上なら、戻り値で `evolution_due=true` を返します。
SKILL.md / 子スキルの利用フローは `evolution_due=true` を受け取ったら `evolve.py review` を呼び出さねばなりません。

---

## 5. 必須運用ルール

1. **append-only**: `pipeline.jsonl` は追記のみ。修正は新しい行として書き、誤りは `event: "amend"` で参照する。
2. **PII / 機密マスク**: instruction / output_summary に APIキー・トークン・個人連絡先を直接入れない。`***` でマスク。
3. **巨大成果物の外出し**: 1 KB を超える生成物は `logs/artifacts/<cycle_id>/<filename>` に保存しパスを書く。
4. **時刻**: 全て UTC ISO8601。
5. **改ざん検知**: 進化レビューは「event ペア欠損」「completion_state 未設定」を破損として無視する。

---

## 6. 例: 1 ユーザー入力 → 3 サイクルの流れ

**単純タスクは 1 サイクルで閉じてよい**。複数サイクルに分割するのは、アウトプットを 1 サイクル内で自己検証できない場合のみ。以下は複数サイクルが必要なケースの例。

```
user_turn=u123
  ├── cycle-1 (start, instruction="設計案を作って")
  │       └── end completion_state="unknown" (案を出したが妥当性不明)
  ├── cycle-2 (parent=cycle-1, instruction="設計案の弱点を洗い出す")
  │       └── end completion_state="success" (弱点 5 件特定)
  └── cycle-3 (parent=cycle-2, instruction="弱点を踏まえ改稿")
          └── end completion_state="success" (最終版完成、ユーザー提示)
```

ユーザーへの最終応答は cycle-3 の output_summary を元に組み立てる。

---

## 7. 進化レビューがログに書く行

進化レビュー自体も 1 サイクルとして `pipeline.jsonl` に記録する。

```json
{"event":"start","cycle_id":"...","skill_name":"...","instruction":"evolution review (threshold reached)"}
{"event":"end","cycle_id":"...","actions":[{"tool":"evolve.py","target":"review"}],"completion_state":"success","completion_reason":"EVOLUTION.md にN件の提案を追記"}
```

# problem-essence-organizer

フリーランス本人専用の思考整理スキル。「課題発見 → 課題整理 → 解決定義 → 手段検討」の 4 フェーズで進行を管理し、手段先行や目的喪失を批判的に指摘してオープン質問で深掘りする。

## 開発者向け

- 詳細仕様は `SKILL.md` を参照。
- 対話スタイル (固定) は `references/dialogue_style.md`。
- 判断軸 / 問いセット / 出力フォーマット (進化対象) は `references/` 配下。

### パイプライン (毎サイクル必須)

```bash
CYCLE_ID=$(python scripts/pipeline.py log-start \
  --skill-name problem-essence-organizer \
  --instruction "<受けた指示の要約>")

# ... 中核作業 ...

python scripts/pipeline.py log-end \
  --skill-name problem-essence-organizer \
  --cycle-id "$CYCLE_ID" \
  --completion-state success \
  --completion-reason "<根拠>" \
  --output-summary "<アウトプット>"
```

### 出力生成

```bash
# 自分用 md (4 フェーズ × 重要/付随)
python scripts/render_markdown.py \
  --input <input.yaml|json> --topic <kebab> \
  --out-dir ./out --phase-at-close F3 --mode postmortem

# クライアント向け HTML (Minto Pyramid)
python scripts/render_html.py \
  --input <input.yaml|json> --out-dir ./out
```

入力スキーマはスクリプトの docstring を参照。

### 進化レビュー

- 進化レビュー: `python scripts/evolve.py review`
- スナップショット: `python scripts/evolve.py snapshot`
- `pipeline.config.json` の `auto_apply` が `true` (既定) なら、`scripts/pipeline.py` と `references/dialogue_style.md` 以外を自動適用。

## 自己進化ログの場所

- `logs/pipeline.jsonl` (append-only)
- `logs/artifacts/<cycle_id>/` (大きい生成物)
- `logs/evolutions/<ts>/` (進化前スナップショット & diff)

## 想定ユーザー

- **本人 1 人のみ**。汎用化しない。
- 進化レビューで「他ユーザー向け一般化」提案は却下する (`references/user_preferences.md` 参照)。

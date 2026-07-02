# 出力フォーマット仕様 (進化対象)

このスキルが生成する 2 種類のアウトプット (自分用 md / クライアント向け HTML) の仕様。
進化対象。使用履歴から章立て・ラベリング・構成順序を最適化する。

---

## 1. 自分用 Markdown (`<topic>.md`)

### 目的
- 自分自身の思考整理。考え抜くためのフォーマット。

### ファイル命名
- 単一課題: `<topic>.md` (例: `agentic-search-quality.md`)
- 複数課題並列: `<topic>__<issue-slug>.md` で **必ず分割** (例: `client-kickoff__document-rag.md` + `client-kickoff__internal-onboarding.md`)
- 命名は kebab-case。

### 章立て (4 フェーズ固定)

```markdown
---
topic: <topic>
created: <YYYY-MM-DD>
phase_at_close: F1|F2|F3|F4
mode: realtime|postmortem|retrospective
---

# <topic>

> 1 行サマリー (中心課題と Done を 1 文で)

## F1. 課題発見 (Discovery)

### 重要 (中心)
- 課題ステートメント: 〈誰〉が〈何〉ができず、〈どんな影響〉
- 現状の観測可能な事象

### 付随 (脇に置く)
- 商談で出た手段の話 (RAG / Agentic etc.)
- 関連はするが今は触らない論点

## F2. 課題整理 (Structuring)

### 重要 (中心課題)
- 中心課題 (1 つ)
- 解いたときの影響

### 付随 (外枠課題)
- 外枠課題リスト (今は脇に置く)
- 「中心が解ければ自然に解消する」推測

## F3. 解決定義 (Done Definition)

### 重要 (Done 基準)
- Done 基準 (観測可能)
- 制約 (時間 / 予算 / 関係者 / 依存)

### 付随 (関連)
- 関連する KPI / 周辺指標 (Done ではないが見たい)

## F4. 手段検討 (Solution)

### 重要 (採用候補)
- 採用候補 (1〜2 案)
- Done を満たす根拠 / 満たさない部分

### 付随 (検討から外した手段)
- 検討して外した手段 + 理由
- 過去に試して失敗したパターン

## 未解決の問い (Open Questions) (任意)

- 対話中に投げた批判的指摘・オープン質問のうち、未回答のまま残ったもの
- 次に考えるときの入口として残す (入力キー: `open_questions`)

## 振り返り (任意)

- 今回、手段先行になりかけた瞬間
- 目的を見失いそうになった瞬間
- 次回への学び (個別好み — `user_preferences.md` への候補)
```

### 重要 / 付随の分離ルール (必須)

- 各章で必ず 2 セクション (重要・付随) を持つ。
- **手段の話は基本「付随」側** に書く (引きずられないため)。
- 「今は脇に置く」を明示する場が常にある状態にする。

### 粒度
- 100〜1000 行。簡潔さより **考え抜くこと** を優先。

---

## 2. クライアント向け HTML (`<topic>__client-proposal.html`)

### 目的
- クライアントへの提案資料。商談・キックオフで渡せる形。

### ファイル命名
- `<topic>__client-proposal.html`

### 構成 (Minto Pyramid / SCQA 流)

```
1. 結論 (Conclusion / Answer)
   - 1 ページ目。「何が課題で、どうなれば解決で、何を提案するか」を 1 画面で。
2. 根拠 (Reasoning / Situation + Complication)
   - 現状認識 (Situation)
   - 何が問題か / なぜそれが問題か (Complication)
3. 提案 (Proposal)
   - どんな解決状態を目指すか (Done)
   - そのための手段 (Solution)
   - 撤退条件 / 不確実性
4. 何をしてほしいか (Call to Action)
   - クライアントに依頼する具体的な意思決定
   - 「不足情報の可視化」セクション (必須)
     - 何が決められないか
     - それを決めるために何が要るか
     - 誰がいつまでに提供する想定か
```

### 「不足情報の可視化」セクション (必須 — round 6 で確定)

```html
<section class="missing-info">
  <h2>今、決められないこと</h2>
  <table>
    <tr><th>決められないこと</th><th>必要な情報</th><th>誰が</th><th>いつまでに</th></tr>
    <!-- ... -->
  </table>
</section>
```

### 粒度
- 3〜10 ページ相当 (ブラウザで A4 換算)
- 1 セクション = 1〜2 ページ

### スタイル / 実装メモ
- 単一の HTML ファイル (CSS インライン or `<style>`)。外部依存なし。
- 印刷 (PDF 化) しても崩れないこと (`@media print` を最低限備える)。
- 生成スクリプト: `scripts/render_html.py`
- 各本文フィールドは str / list の両対応 (str は `\n\n` 区切りで複数段落、list は箇条書き)。
  空値は `(未記入)` と明示表示する (無言で空にしない)。

---

## 3. 振り返りレポート (モード c)

### ファイル命名
- `<date>__retrospective.md`

### 生成スクリプト
- `scripts/render_markdown.py --mode retrospective --topic <date>`
- 入力キー: `facts` / `drift` / `means_first` / `learning` (+ 任意で `open_questions`)

### 章立て

```markdown
# 振り返り <date>

## 起きたこと (Facts)
- セッション / 会議 / 作業の事実列挙

## 目的を見失った瞬間 (Drift Detection)
- 「目的ってなんだっけ」が出た / 出なかった点

## 手段に飛びついた瞬間 (Means-First Detection)
- 手段先行が起きた瞬間と前後関係

## 学び (Learning)
- 個別好みの候補 → `user_preferences.md` 行きの内容
- 判断軸の更新候補 → `judgment_axes.md` 行きの内容
```

---

## 進化ノート (自動追記領域)

<!-- evolution:appended-from-here -->

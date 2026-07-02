---
name: friday-tech-article-drafter
description: >-
  ブログ・登壇向けの技術記事ドラフト生成スキル。worklog の tech digest(worklog-data/digests/tech/)や
  knowledge-base の vault(knowledge-base/)をネタ元に、ネタ選定 → 記事構成の提案と合意 → ドラフト生成 →
  清書パス(AI 感除去) → 機密マスキング → 公開前チェックリストの 6 段階で、公開に耐える Markdown 記事ドラフトを articles/ に生成する。
  顧客名・案件名・社内 URL・API キー・個人名などの機密は必ず匿名化し、機械チェックとチェックリストの
  全項目確認を通過するまで「公開可」としない(機密マスキング必須)。
  「ブログ記事のドラフト書いて」「今月の作業から技術記事のネタ探して」「Terraform のノートを Zenn 記事にして」
  「登壇ネタになりそうな話まとめて」「この記事ドラフト、公開前チェックして」等で、
  ユーザーが明示的に依頼したときだけ起動する(自動起動しない)。
metadata:
  type: skill
  pairs_with: jarvis-worklog, jarvis-knowledge-base
  data_dir: <repo>/articles
---

# tech-article-drafter — 技術記事ドラフト生成 (機密マスキング必須)

[jarvis-worklog](../jarvis-worklog/) の tech digest と [jarvis-knowledge-base](../jarvis-knowledge-base/) の
vault に溜まった知見を、**不特定多数の技術者が読む公開記事**のドラフトへ変換する。
読み手が他者（ブログ読者・勉強会聴衆）である点で friday 系。

このスキルの核は 2 つ:

1. **事実ベースの記事化** — 出典（digest / vault ノート）にある事実だけで書く。創作しない。
2. **機密マスキング** — 顧客名・案件名・社内 URL・API キー等を匿名化し、
   公開前チェックリストを全通過するまで「公開可」としない。**蓄積（vault）≠ 公開**。

## データ配置

- 入力: `<repo>/worklog-data/digests/tech/<project>_<date>.md`（tech digest）
  および `<repo>/knowledge-base/tech/<slug>.md`（vault ノート）
- 出力: `<repo>/articles/<YYYY-MM-DD>-<slug>/draft.md` + `masking-log.md`
  **(ASSUMPTION: 出力先はリポジトリ直下 `articles/`。他スキルのデータ置き場（`report-deck/` 等）と同じ流儀。
  ドラフト段階では機密が残りうるため `.gitignore` で追跡除外とする)**
- NG ワード辞書: `<repo>/articles/_ng-words.txt`（1 行 1 語。顧客名・案件コード等をユーザーが育てる。
  gitignore 配下なので実名を書いてよい）
- 雛形: [`templates/article-template.md`](templates/article-template.md)
- マスキングルール + チェックリスト: [`references/masking-checklist.md`](references/masking-checklist.md)

## トリガー

| ユーザー発話の例 | 動作 |
|---|---|
| 「ブログ記事のドラフト書いて」「テック記事にして」 | 標準フロー全体（ネタ元未指定ならネタ選定から） |
| 「今月の作業から技術記事のネタ探して」「記事にできるネタある?」 | ステップ 1（ネタ選定）のみ実行し候補を提示 |
| 「Terraform のノートを Zenn 記事にして」 | 指定ノートを出典にステップ 2 から。媒体 = Zenn |
| 「登壇ネタになりそうな話まとめて」 | 媒体 = 登壇メモとして標準フロー |
| 「この記事ドラフト、公開前チェックして」「機密残ってないか見て」 | 既存 draft.md にステップ 5〜6 のみ実行（AI 感チェック未達時はステップ 4 に戻る） |

自動起動はしない。発信は公開行為で機密リスクを伴うため、明示的な依頼があったときだけ動く。

## 標準フロー

1. **ネタ選定**（digest / vault から）
   - ネタ元の指定があればそれを Read。無ければ `knowledge-base/tech/*.md` を優先的に走査し
     （複数 digest の横断集約で厚みがあるため）、必要に応じて `worklog-data/digests/tech/*.md` を補う。
   - 記事向きの候補（トラブルシュート・技術選定・設計判断で、結論と根拠が揃っているもの）を
     3〜5 件、**出典ファイル名付き**で提示し、ユーザーに選んでもらう。
   - 「記録なし」が多く事実が薄い digest は候補から外す（膨らませると創作になる）。
2. **記事構成の提案とユーザー合意**
   - 選ばれたネタについて、下記の記事構成テンプレートに沿った**見出しレベルの構成案**
     （タイトル案・各節の要点 1 行・想定読者・想定媒体）を提示する。
   - ユーザーが合意するまでドラフト本文は書かない。構成の増減・切り口の変更はここで確定する。
3. **ドラフト生成**
   - [`templates/article-template.md`](templates/article-template.md) を雛形に、合意した構成で
     `articles/<YYYY-MM-DD>-<slug>/draft.md` を生成する（slug は英語 kebab-case）。
   - 出典にある事実・数値・エラーメッセージだけを使う。出典に無い箇所は書かない。
     一般論で補う場合は本文中でそれと分かる書き方にする（persona: 創作しない）。
   - 「試したこと」の節には、出典にある**失敗・エラー・回り道・採用しなかった案**を必ず含める
     （完璧すぎる記事は AI 感の主要因。ただし出典に無い失敗を創作しない）。
   - `articles/` に過去のドラフト・公開記事があれば 1〜2 本読み、文体（文末・語り口）を合わせる。
   - frontmatter の `sources:` に使用した digest / ノートのファイル名を列挙する。
4. **清書パス（AI 感の除去）**
   - [`personas/writing-style.md`](../../../personas/writing-style.md) の清書パスを draft.md 全文に
     適用する。意味・事実・数値を変えず、癖だけを削る（引き算のみ。体験・感情の創作で補わない）。
   - 記事固有の確認: 全節が均等な丁寧さになっていないか（記事の核となる節に厚みがあるか）、
     実際にあった未解決・回り道をきれいにしすぎて消していないか。
   - 機密マスキングの**前**に行い、マスキングを最終工程に保つ。
5. **機密マスキング**
   - [`references/masking-checklist.md`](references/masking-checklist.md) のルール表に従い、
     顧客名・案件名・個人名・社内 URL/ホスト名・認証情報・digest 由来の `<REDACTED:..>` 等を全文置換する。
   - 置換結果は `masking-log.md` に「カテゴリ + 件数 + 置換後表現」で記録する。
     **置換前の実値は masking-log.md に書かない**（ログ自体を機密対応表にしない）。
   - frontmatter を `masked: true` に更新する。
6. **公開前チェックリスト**
   - 機械チェック: references 記載の grep パターン + `articles/_ng-words.txt` を draft.md に対して実行し、
     **ヒット 0 件**を確認する。ヒットがあればステップ 5 に戻る。
   - AI 感チェック: [`personas/writing-style.md`](../../../personas/writing-style.md) の
     セルフチェックリストを draft.md に対して確認する（未達があればステップ 4 に戻る）。
   - 人間チェック: チェックリスト全項目をユーザーと 1 項目ずつ確認する（組合せ特定の観点を含む）。
   - 全通過したときのみ frontmatter を `status: ready-to-publish` に更新する。
     **1 つでも未確認なら `status: draft` のまま**とし、未通過項目を提示して終了する。
   - 完了提示: 生成パス・出典一覧・マスキング件数・チェック結果を報告する。

## 機密マスキング（要約 — 詳細は references）

- 入力の digest / vault は生成段階でマスキング済みだが、**それを信頼せず公開用マスキングを独立に行う**（多層防御）。
- 対象カテゴリ: 顧客名・案件名 / 個人名 / 社内 URL・ホスト名・IP / API キー・トークン等の認証情報 /
  メールアドレス / 未公開の事業・契約情報。置換ルールと grep パターンは
  [`references/masking-checklist.md`](references/masking-checklist.md) に定義。
- 固有名詞を消しても「時期 × 業種 × 特徴的な技術構成」の組合せで案件が特定できることがある。
  ぼかす・一般化する・複数案件の知見として書く、のいずれかで対処する。
- `<REDACTED:..>` プレースホルダは公開文には残さない（文意が通る一般表現に書き換える）。

## 記事構成テンプレート（固定骨子）

雛形は [`templates/article-template.md`](templates/article-template.md)。節構成は次の 4 部を基本とする:

1. **課題** — どんな状況で何に困ったか（読者が「自分ごと」にできる書き出し）
2. **試したこと** — 検討した選択肢と実際にやったこと（採用しなかった案と理由も価値）
3. **結果** — 何がどう解決したか / しなかったか（エラーメッセージ・数値は出典にあるものだけ）
4. **学び** — 再利用できる結論・適用条件（「いつこのやり方が有効か」まで書く）

媒体（blog / Zenn / Qiita / 登壇メモ）による差はタイトルの付け方・文体・コードブロック方言の範囲にとどめ、
骨子は変えない。

## 品質・安全性（persona: friday 準拠）

- 事実に基づいて書く。出典（digest / vault）に無い情報を創作しない。推測で補った箇所はその旨を明示する。
- 機密情報（API キー・トークン・顧客名・案件名・社内 URL）を出力に含めない。
  チェック未通過のドラフトを「公開できる」と案内しない。
- 応答・記事本文は日本語、コード・識別子・slug は英語。技術用語は原語のまま表記する。
- 入力の digest / vault（一次情報）は変更・削除しない。記事側だけを編集する。
- ユーザーの合意（構成・公開判断）を経ずに勝手に確定しない。公開作業そのもの（投稿）はスキルの範囲外。

# スキルレビュー・修正記録 (2026-07-02)

`.claude/skills/` 配下の既存 8 スキルを以下の 3 観点でレビューし、指摘 63 件をすべて修正した記録。

- **効率**: 実行効率が悪い点（不要なステップ、冗長な LLM 呼び出し、スクリプトのバグ/非効率、曖昧な指示による試行錯誤）
- **成果物**: 目的に対して成果物が不十分な点（description が謳う目的とのギャップ、エッジケース未定義）
- **テンプレート**: より見やすいテンプレートがある点

方法: スキルごとに独立したレビューエージェントが全ファイルを精査（疑わしいロジックは実行して再現確認）。指摘を精査・採用判断したうえで、スキルごとに修正を適用し、`py_compile` とスモークテストで検証した。

| スキル | 指摘数 | 高 | 中 | 低 |
|--------|-------|----|----|----|
| jarvis-worklog | 8 | 3 | 3 | 2 |
| jarvis-knowledge-base | 8 | 2 | 4 | 2 |
| jarvis-record | 7 | 1 | 3 | 3 |
| friday-daily-report | 8 | 2 | 4 | 2 |
| friday-giziroku | 8 | 2 | 4 | 2 |
| karen-problem-essence-organizer | 8 | 3 | 4 | 1 |
| karen-self-evolving-skill-creator | 8 | 3 | 3 | 2 |
| ultron-high-dividend-stock-screener | 8 | 2 | 4 | 2 |

---

## jarvis-worklog

- **[高][成果物] 簡易 YAML パーサが `keywords: []` を文字列 `"[]"` として返し誤分類**
  問題: `classify_keyword` が文字列 `"[]"` を 1 文字ずつ走査し、`"["` がログ本文（タイムスタンプ等）に部分一致 → LLM 不在時に全セッションが特定プロジェクトへ誤分類（実測再現）。
  修正: `worklog_lib.py` の `_parse_scalar` に `"[]"→[]` / `"{}"→{}` を追加し、`classify_keyword` に「keywords が list でなければ無視」の防御を追加。
- **[高][成果物] path_globs の部分一致（`g in cwd`）で別プロジェクトに誤爆**
  問題: `cwd=…/gcp-sandbox` が `gcp-sand` に確定分類される（実測再現）。決定論判定のため LLM にも回らない。
  修正: 部分一致を廃止し、完全一致＋ディレクトリ境界付き前方一致のみに変更。`projects.yaml` のコメントも同期。
- **[高][成果物] archive が classify 未実行の raw を素通しして削除**
  問題: 未整理チェックが `classified/` しか見ないため、collect 済み・classify 未実行の月は警告なく zip 化＋元ファイル削除に進む。
  修正: `archive_impl.py` で raw と classified の日付集合を突き合わせ、未分類日付があれば中断（`--force` で続行、`--check` でも報告）。
- **[中][効率] collect が実行のたびに全 JSONL を全読み（行数カーソル）**
  問題: カーソルが行数のため差分ゼロ判定にも全読みが必要で、セッション終了フックのたびに I/O が線形悪化。
  修正: カーソルを `{"offset": バイト位置, "size": 前回サイズ}` に変更。サイズ不変ならスキップ、増分は seek して差分のみ読む。旧 int 形式は一度だけ全読みで移行。
- **[中][テンプレート] 時間帯分割時の digest がテンプレ丸ごと×N連結**
  問題: 各セグメントが H1・TL;DR を繰り返し、見出し階層も逆転。下流（jarvis-record 等）の読み取りを阻害。
  修正: 分割時のセグメント用プロンプトに「H1 と冒頭 TL;DR/成果サマリは出力せず `##` から書く」指示（`SEGMENT_NOTE`）を追加。SKILL.md も同期。
- **[中][テンプレート] テンプレ H1 の `{project} {date}` が literal のままプロンプトに渡る**
  修正: プロンプト組み立て時にテンプレへ `.replace()` を適用（LLM 向け placeholder は温存）。
- **[低][効率] suggest_projects が同一リポジトリの複数 cwd を重複候補として出す**
  修正: git toplevel 単位でマージし、出力を `cwd` → `cwds` リストに変更。SKILL.md も同期。
- **[低][効率] 重複コード・デッドコード・README 齟齬**
  修正: `summarize.py` のローカル `run_claude` を削除して共通実装に統一、デッドコードの `render_log` / `Classifier.classify` を削除、desktop セッションマップを set 化して README の記述を実装に合わせて修正。

検証: 編集 5 ファイル＋classify.py の `py_compile` OK。誤分類 2 件の解消・カーソル移行・archive 中断・分割プロンプトを統合テストで確認済み。

## jarvis-knowledge-base

- **[高][成果物] `--taxonomy-only` / `--limit` 実行後、残りノートが永久に生成されない（状態汚染）**
  問題: パスA直後に全 digest を `seen` に保存するため、「お試し実行 → 本番実行」で本番側が「新規なし」で即終了する。
  修正: `--taxonomy-only` / `--limit` 時は seen を空で保存し、通常全構築時のみパスB完了後に保存するよう再構成。
- **[高][成果物] ノート生成失敗時も digest が `seen` に入り自動リトライされない**
  修正: 失敗領域の sources を seen から除外して次回自動リトライさせる。SKILL.md に `.prompt.txt` からの手動復旧手順も明記。
- **[中][効率] `claude -p` がツール使用可能なまま実行されメタ応答失敗を誘発**
  修正: `run_claude` に `--tools ""` と `--disallowedTools "*"` を追加（`claude --help` でフラグの存在を確認済み。`"*"` の MCP への効果は未確認のため `# ASSUMPTION:` 明記）。
- **[中][効率] ノート生成が直列で領域数×最大600秒**
  修正: `run_claude_many`（ThreadPoolExecutor、同時 3。worklog と同方式）を追加し、パスBと増分マージを並列化。
- **[中][成果物] 入力上限超過時に digest を黙って捨てるが seen には記録される**
  修正: 省略発生時に stderr へ id 一覧付き警告を出し、省略分は `sources`・`seen` に入れず次回持ち越し。
- **[中][成果物] `related` の実在検証なし（`[[リンク切れ]]`）＋割当ゼロ新領域が index に載る**
  修正: `related` を実在 slug 集合でフィルタし、sources 空の新領域を techs から除去。
- **[低][効率] `extract_json` が末尾から1文字ずつ縮めて `json.loads` を繰り返す O(n²)**
  修正: `json.JSONDecoder().raw_decode()` を第一経路にし、失敗時のみ従来フォールバック。
- **[低][テンプレート] title の YAML クオート未指示・「検索用タグ」節の重複・「記録なし」表記の曖昧さ**
  修正: `title: "{タイトル}"` にクオート追加＋プロンプトに「frontmatter 文字列値はダブルクオート」指示、検索用タグ節は frontmatter に無い補足のみに、トラブルシュート無しは「表自体を出さず『記録なし』」に明確化。

検証: `py_compile` OK。`extract_json`・related フィルタ・省略警告のユニット確認、ダミー digest での `--dry-run` 正常終了を確認済み。

## jarvis-record

- **[高][成果物] 同日記録の再実行時の上書き挙動が未定義（ヒアリング内容が黙って消える）**
  問題: 既存記録には digest から復元不能な `heard`（ヒアリング内容）があるのに、手順は無条件 Write。
  修正: `locate.py` に `record_exists` フィールドを追加し、SKILL.md に「既存記録の `heard` を引き継いで更新、判断がつかなければ AskUserQuestion で確認」を追記。
- **[中][効率] 旧スキル名 report-record / report-deck が description・本文に残存**
  問題: エージェントが存在しないスキル名で後段を探して試行錯誤する。
  修正: スキル参照を jarvis-record / friday-daily-report に統一（データパス `report-record/` 等は規約どおり旧名維持）。
- **[中][成果物] SKILL.md 手順の固定見出し一覧がテンプレート（正）と文言不一致**
  修正: 手順の見出し一覧を `templates/record.md` の文字列（括弧補足込み）と完全一致させた。
- **[中][効率] _unclassified 確認と不足ヒアリングが案件ごとの多重 AskUserQuestion になりがち**
  修正: 「質問を集約して原則 1 回の AskUserQuestion（最大4問）」を明記し、手順を 6 段階から 5 段階に統合。
- **[低][成果物] ステータスマーカー体系の不整合（worklog 3種 vs record 4種）**
  修正: テンプレのコメントに `[中断]` を追加し、SKILL.md に「`[中断]` は digest からは来ない。ヒアリングで確定してから付ける」を追記。
- **[低][テンプレート] テンプレ冒頭コメントの誤解（全見出しにマーカー？）＋ `- [進行中]` プレフィルの残留リスク**
  修正: 「『## やったこと』の各項目のみに付ける」に修正し、プレフィルを `- ` のみに変更。
- **[低][成果物] 複数日・範囲指定の扱いが未定義**
  修正: トリガー表に「範囲指定 → 日付ごとにループ（1日1ファイル維持）」を追加。

検証: `py_compile` OK。

## friday-daily-report

- **[高][成果物/テンプレート] JS 無効環境（メール添付のプレビュー等）では表紙以外が一切表示されない**
  問題: `.slide{display:none}` 既定＋JS で表示する設計のため、「メール添付でそのまま開ける」という宣言に反して本文が読めない。
  修正: プログレッシブエンハンスメントに変更。既定は全スライド縦並び表示、JS 有効時のみ `js` クラス経由でスライドモードになる。
- **[高][効率] 旧スキル名 report-record / report-deck の記載が残存**
  修正: description・見出し・フローのスキル参照を jarvis-record / friday-daily-report に統一（データパスは旧名維持）。
- **[中][成果物] 印刷時にステータスバッジ・「案件」ラベルの白文字が消える＋末尾空白ページ**
  修正: `@media print` に `print-color-adjust:exact` と `.slide:last-of-type{page-break-after:auto}` を追加。
- **[中][効率/成果物] 週次・範囲指定（「今週分を1枚に」）が未サポート**
  修正: `render_deck.py` に date の形式検証（`YYYY-MM-DD`）と表紙表示用の任意フィールド `date_label` を追加。SKILL.md に「1枚集約時は date=範囲末日、date_label='6/23〜6/27'」を明記。
- **[中][テンプレート] クリックは前進のみ・操作ヒントなしで全スライドに辿り着けない**
  修正: 右半分クリックで前進・左半分で後退・テキスト選択中は無視に変更し、表紙に操作ヒント（印刷時非表示）を追加。
- **[中][成果物] `status` / `next` が空だとセクションごと消え「毎回同じフォーマット」が崩れる**
  修正: 「今どうなっているか」「この先」を常に出力（空は「なし」）に統一。
- **[低][効率] 不正入力を黙って通す（未知 status・案件0件）**
  修正: 未知 status は stderr 警告、`projects` 空は exit 1 でエラー終了。
- **[低][成果物] glossary 追記運用の規約なし**
  修正: 重複チェック（既存 term/aliases との照合）と五十音順維持の規約を SKILL.md に追記。

検証: `py_compile` OK。サンプル payload で生成成功、JS 無効時の縦並び・警告・エラー終了を機械チェックで確認済み。

## friday-giziroku

- **[高][効率] timeline が全セグメントを出力し、長時間会議で JSON が数万字に膨張**
  問題: 400 ターンで約 57,000 字。Phase B でも原文を読むため二重にコンテキストを消費。
  修正: 5 分バケット集約（時刻なしは 10 件ごと）＋最大 40 ブロックに変更。修正後は 400 ターンで 2,544 字。
- **[高][効率] 時刻を含む本文行を話者ヘッダと誤検出（偽話者が発生）**
  修正: NAME パターンを `[^\s:：]{1,20}` に厳格化し、助詞始まり・文末表現含み等を棄却する `_valid_name()` を追加。
- **[中][効率] docstring が謳う「名前: 発言」インライン形式が未対応で silent に推定話者へ落ちる**
  修正: インラインパターンを人名対応に拡張し、誤検出対策として「同一名 2 回以上出現のみ有効」の頻度フィルタを追加。
- **[中][効率] ヘッダ前の前文セグメントが「(不明)」話者として speaker_count を水増し**
  修正: 話者を持つセグメントのみ集計するようフィルタを修正。
- **[中][効率] Phase C の適用範囲が曖昧で、長大 transcript の全文書き換えを誘発**
  修正: 「中間ファイルとして清書 transcript を生成しない。補正・マスキング・話者置換は Phase D で書き出す文面にのみ適用」を明記し、「原文 3 万字超は Read 分割・timeline を索引に」を追加。
- **[中][成果物] 日時が確定できない場合のフォールバック未定義（当日日付を創作するリスク）**
  修正: 「日付が採れない場合のみ Phase B の確認バッチで会議日を 1 問追加（当日日付で埋めない）」を追記。
- **[低][効率] サンプル固有の誤変換例（船種等）が完了条件に残存**
  修正: 固有例を削除し、音写崩れ一般則に置換。
- **[低][テンプレート] TODO が箇条書きで決定事項との対応・担当が追いにくい**
  修正: TODO を `| # | タスク | 担当 | 期日 | 関連 |` テーブルに変更し、決定由来タスクは関連列に `[Dn]` を記す規約を追加。

検証: `py_compile` OK。21 ケースのテストで全パス（誤検出解消・インライン話者・timeline 集約・speaker_count）。

## karen-problem-essence-organizer

- **[高][効率] pipeline.py / evolve.py が skill root を cwd から解決し、ログが迷子になる**
  問題: リポジトリルートから実行すると repo 直下に `logs/` ができ、進化閾値は永遠に到達しない（実証済み）。
  修正: 既定を `Path(__file__).resolve().parent.parent`（scripts/ の親）に変更。repo ルートからの `status` 実行でスキル配下に解決され、既存 2 サイクルを認識することを確認。
- **[高][効率] `auto_apply` は実装が存在しない死に設定で、既定値の記述もファイル間で矛盾**
  修正: 「evolve.py は提案の起草まで。適用は EVOLUTION.md を読んだ Claude が snapshot 後に Edit で行う」に記述を統一し、「自動適用される」という虚偽の記述を削除。
- **[高][効率] 進化トリガーのリセットが「log-end に `--action evolve.py`」という指示されていない運用に依存**
  問題: 閾値到達後は毎サイクル `evolution_due=true` になり EVOLUTION.md が肥大化。
  修正: `evolve.py review` が完了時に `evolution-review` note を pipeline.jsonl へ自動追記し、pipeline.py のカウンタリセットをその note 検知に変更。
- **[中][効率] モード(a)（1〜3行の応答）にまで毎サイクルのログ計装を要求し過剰**
  修正: パイプライン記録はモード(b)(c)のみ必須とし、モード(a)は省略可（残したい気付きは note 1 行）に緩和。Step 5 の例も followup/フェーズ記録込みに充実。cluster_signals への新検出器追加はスコープ外と判断し見送り。
- **[中][成果物] 中核機能「批判的指摘＋オープン質問」の置き場が自分用 md テンプレに無い**
  修正: 入力スキーマに `open_questions` を追加し、`## 未解決の問い (Open Questions)` 章を描画。output_formats.md も同期。
- **[中][成果物] モード(c) 振り返りレポートのレンダラーが存在せず、HTML ファイル名も仕様と実装で不一致**
  修正: `--mode retrospective` に Facts / Drift / Means-First / Learning の専用テンプレ分岐を実装し、SKILL.md のファイル名を実装（`<topic>__client-proposal.html`）に合わせた。
- **[中][テンプレート] HTML テンプレが単一段落前提で崩れる・`.muted` 未定義・空欄が無言**
  修正: `render_rich()`（str は複数 `<p>`、list は `<ul><li>`、空は「(未記入)」明示）を導入し、CSS に `.muted` を追加。
- **[低][効率] SKILL.md（236行）が references と二重管理で、進化するほど乖離する構造**
  修正: キラーフレーズ・完了条件詳細・出力仕様の重複を references への参照に置換し、150 行に縮約。

検証: 4 スクリプトの `py_compile` OK。repo ルートからの `status`、md/retrospective/HTML のレンダリングをサンプル入力で確認済み。

## karen-self-evolving-skill-creator

- **[高][成果物] SKILL.md が約束する「自動適用 (auto_apply)」を evolve.py が一切実装していない**
  修正: 実装追加ではなく記述を実態に統一（review は提案起草まで。適用は Claude が snapshot → Edit → diff 保存の順に行う）。docstring の矛盾も解消。
- **[高][効率] pipeline.py の skill_root 既定が cwd のため、生成される子スキルでもログがスキル外に作られる**
  修正: 既定を `Path(__file__).resolve().parents[1]` に変更し、`evolve.py --skill-path` も同じ自動解決に統一。
- **[高][成果物] 生成される子スキルがプロジェクトのプレフィックス命名規約に従わない**
  修正: `scaffold_skill.py` に既知プレフィックス（jarvis/friday/arc-reactor/ultron/edith/karen/vision）の先頭一致チェックを追加（不一致はエラー、`--allow-no-prefix` で回避可）。SKILL.md 手順に「README.md でプレフィックス決定・personas/<prefix>.md 必読」を追加し、使用例も修正。
- **[中][成果物/テンプレート] auto_apply の既定値が 4 箇所で矛盾（true/false が混在）**
  修正: 既定 true に統一し、テンプレ本文は `{{AUTO_APPLY}}` の実値を反映する文面に変更。
- **[中][効率] ログスキーマ等が SKILL.md・references で三重記載され、起動時に読む量が過剰**
  修正: SKILL.md の重複表を references への参照に置換し、description を 4 文に圧縮。239 行 → 150 行。
- **[中][効率] 「1 ユーザー入力 = 複数サイクル必須」が単純タスクにも冗長なループを強いる**
  修正: 「単純タスクは 1 サイクルで閉じてよい。自己検証できない場合のみ複数サイクル」に緩和し、`unknown` 規則にも免除を追記。
- **[低][成果物] リネーム前の旧スキル名・旧リポジトリパスが残留**
  修正: `self-evolving-skill-creator` を現行名に一括置換し、旧絶対パスを相対表記に変更。既存ログ（logs/pipeline.jsonl）はデータとして無変更。
- **[低][テンプレート] SKILL.md.template の description 再掲・ドメイン手順の骨組み欠如**
  修正: description 再掲を削除し、「## ワークフロー」「## 出力」の TODO プレースホルダー節を追加。

検証: 3 スクリプトの `py_compile` OK。repo ルートからの `status` 解決、scaffold のプレフィックス拒否/許可/回避フラグ、子スキルへの `auto_apply: true` 展開を確認済み。

## ultron-high-dividend-stock-screener

- **[高][成果物] 除外パターン「リート」の部分一致で「日本コンクリート工業」が誤除外（実測）**
  修正: 「リート」のみ「名称末尾がリート」or「リート投資法人を含む」場合に限定する特別扱いを実装。screening_rules.md の進化メモに実測事例を記録。修正後、日本コンクリート工業は除外されず、リート銘柄は除外されることを実測確認。
- **[高][効率] 「続きから再開」に母集団側のカーソルが無く、回を重ねるほどランキング再取得が膨らむ**
  修正: `stock-data/registry/cursor.json`（source / last_page / last_yield_seen / fetched_at）を文書で定義し、「カーソル位置から開始」「全部 known なら次ページ」「利回り閾値未満で消化済み報告して終了」を SKILL.md に明文化。
- **[中][成果物] 台帳に更新手段が無く、再検証・再調査の結果を反映できない**
  修正: `registry.py update`（corp_number → ticker の順で一致行を置換）を実装し、再検証フローに「judge 後は update」を追記。追加→更新→幽霊追記なしを一時ディレクトリで実測確認。
- **[中][成果物] 株式分割時の配当推移が「減配」と誤判定される（エッジケース未定義）**
  修正: 「分割・併合は分割調整後の 1 株配当に換算して並べる（換算不能なら要再確認で保留）」を screening_rules.md と SKILL.md に明記（judge.py は換算済み前提と明記）。
- **[中][効率] 国税庁 Web-API フォールバックの アプリケーションID の扱いが未定義でフローが止まる**
  修正: 「`HOUJIN_API_ID` 未設定ならフォールバックせず `corp_number: null` + `corp_status: "unresolved"` で台帳記録して続行」を明記。
- **[中][テンプレート] 合格銘柄テーブルが 10 列で可読性が低く、ルールが要求する配当推移・EPS の記載欄も無い**
  修正: 8 列（コード|社名|利回り%|配当性向%|配当推移(円)|営業利益推移|業種|出典）に再設計。配当推移は `40→42→45→48` の実数表記、出典は脚注 `[n]` ＋「### 出典」節、法人番号・判定根拠は台帳参照へ。不合格表に利回り%列を追加。
- **[低][効率] バッチ追記が 1 件ごとに台帳全読みする O(n²)**
  修正: `append_registry_many`（全読 1 回・まとめ書き）を追加し、配列 add がこれを使うよう変更。
- **[低][成果物] normalize_ticker が末尾 0 以外の 5 桁コード（優先株等）を正規化できない**
  修正: 文書対応のみ（docstring と SKILL.md 注意欄に「突合対象外」と明記）。挙動は不変。

検証: bin/ 4 ファイルの `py_compile` OK。リート判定・registry add/update の全 10 チェック PASS。

---

## 採用判断に関する補足

- 指摘はレビューエージェントの提案を全件精査のうえ原則採用した。スコープを絞ったのは次の 3 点:
  - karen-self-evolving-skill-creator の auto_apply: 自動適用の**実装追加**ではなく、記述を実態に合わせる案を採用（リスクが低く、運用実態と一致するため）。
  - karen-problem-essence-organizer の cluster_signals への新検出器追加: 今回のスコープ外として見送り（ログ運用の改善が先）。
  - 既存ログデータ（logs/pipeline.jsonl）への追記・書き換えは行わない（一次データ保全の原則）。
- データ出力ディレクトリ名（`report-record/`、`report-deck/`、`REPORT_DECK_DIR` 等）は `.claude/skills/README.md` の例外規定どおり旧名のまま維持し、**スキル名としての参照**のみ現行名に更新した。
- 修正は未コミット。コミット粒度（スキルごと/一括）は指示があれば対応する。

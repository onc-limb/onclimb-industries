# explain-analysis — EXPLAIN の読み方と改善パターンの判定基準

slow-query-hunter の解析パート（標準フロー 4〜5）で使う判定基準。
対象は PostgreSQL / MySQL。解析実行前に必ず読む。
新しい兆候・DBMS 固有の読み方を学んだら、このファイルに追記して育てる。

## 1. EXPLAIN の取得方法

| DBMS | コマンド | 備考 |
|---|---|---|
| PostgreSQL | `EXPLAIN (ANALYZE, BUFFERS) <query>` | ANALYZE は実際に実行する。SELECT のみに使う |
| PostgreSQL（計画のみ） | `EXPLAIN <query>` | 書き込み系はこちら。実行しないので安全 |
| MySQL 8.0+ | `EXPLAIN ANALYZE <query>` | 実際に実行する。SELECT のみに使う |
| MySQL（計画のみ） | `EXPLAIN <query>` / `EXPLAIN FORMAT=JSON <query>` | JSON 形式はコスト・attached_condition が読める |

書き込み系クエリ（INSERT / UPDATE / DELETE）に ANALYZE 系を使わないのが原則。
どうしても実測が要る場合はトランザクション + ROLLBACK で保護し、実行前にユーザーへ確認する
（SKILL.md 大原則 2）。

## 2. 実行計画の読み方 — 問題シグナル別

### 2.1 seq scan / full scan

- PostgreSQL: `Seq Scan on <table>`。MySQL: `type: ALL`（EXPLAIN の type 列）。
- **それ自体は問題ではない。** 小さいテーブル（数百〜数千行）や、テーブルの大半を返すクエリでは
  seq scan が最速であり、オプティマイザの選択は正しい。
- 問題と判定する条件（両方満たすとき）:
  1. テーブル行数が大きい（目安 1 万行以上）のに seq scan / ALL が選ばれている
  2. WHERE / JOIN 条件の選択率が高い（返す行が全体のごく一部）のに、その列にインデックスが無い、
     または在っても使われていない
- インデックスが在るのに使われないパターン:
  - 列に関数・演算を適用している（`WHERE lower(email) = ...`, `WHERE created_at + interval ...`）
    → 式インデックスか、条件の書き換え（右辺に演算を寄せる）
  - 型の暗黙変換（文字列列に数値で比較、照合順序の不一致）→ 型を合わせる
  - 先頭ワイルドカードの LIKE（`LIKE '%foo'`）→ 通常の B-tree では効かない。
    PostgreSQL なら trigram インデックス（pg_trgm）を検討
  - 複合インデックスの先頭列が条件に無い（→ 3.2 の列順）
- **計測環境の注意**: 開発 DB の行数が少ないと、本番では index scan になるクエリでも
  seq scan が選ばれる（逆も起きる）。行数が本番と乖離している場合、seq scan の有無だけで
  判定せず「参考値」と明記する。

### 2.2 行数見積もりの乖離（rows estimate vs actual）

- PostgreSQL の `EXPLAIN ANALYZE` は各ノードに `rows=<推定> ... actual rows=<実際>` が出る。
  MySQL の `EXPLAIN ANALYZE` も `(estimated rows=...)` と `(actual rows=...)` が並ぶ。
- **10 倍以上の乖離**があるノードは要注意。オプティマイザが誤った前提で
  結合順序・結合方式（nested loop vs hash join）を選んでいる可能性がある。
- 典型原因と対処:
  - 統計情報が古い → `ANALYZE <table>`（PostgreSQL）/ `ANALYZE TABLE <table>`（MySQL）を提案
    （これも実行はユーザー確認のうえで。統計更新は軽いが DB 状態を変える操作）
  - 相関のある複数条件（例: 都道府県と市区町村）で選択率を掛け算して過小評価
    → PostgreSQL は拡張統計（`CREATE STATISTICS`）を提案
  - 乖離したノードの下流で nested loop が選ばれ、actual rows が大きい
    → 実測でここが支配的なら、見積もり改善（統計）を先に、書き換えを次に検討
- 乖離の指摘には必ず該当ノードの推定値・実測値を引用する（根拠のない「統計が古いかも」は書かない）。

### 2.3 filesort / ソート・一時テーブル

- MySQL: `Extra: Using filesort` / `Using temporary`。名前に反してメモリ内ソートでも filesort と出る。
  少行数なら無害。**行数が多い（目安 1 万行超）+ LIMIT 付きで全件ソートしている**ときが問題。
- PostgreSQL: `Sort Method: external merge Disk: <N>kB` はディスクスピル。
  `work_mem` 不足か、そもそもソート対象が多すぎる。
- 対処の優先順:
  1. ORDER BY（+ WHERE）をカバーするインデックスでソート自体を消す
     （`WHERE a = ? ORDER BY b` → `(a, b)` の複合インデックス。→ 3.2）
  2. LIMIT 付きページングなら keyset pagination（`WHERE (b, id) > (?, ?) ORDER BY b, id LIMIT n`）
     への書き換えを提案（OFFSET が深いページで全捨てソートになるため）
  3. それでも残るなら work_mem / sort_buffer_size の調整を「運用側の選択肢」として添える
     （設定変更は本スキルでは実行しない）

### 2.4 N+1 の兆候

**ログ側のシグナル**（ログモード）:

- 同一形状のクエリ（リテラルだけ違う）が 1 リクエスト内・短時間に多数並ぶ。
  正規化して集計したとき「平均は数 ms だが実行回数が突出して多い」クエリは N+1 の第一容疑。
- 直前に親テーブルの SELECT があり、続いて子テーブルへの単一 id 検索が行数分続くパターン。

**コード側のシグナル**（コードモード・静的検出）:

- ループ（for / each / map）の内側で ORM の検索・遅延ロードプロパティ参照・クエリ実行がある。
- 一覧取得後にテンプレート / シリアライザで関連を辿っている
  （Rails: `has_many` を view で参照 / Django: related manager をテンプレートで参照 /
  Prisma: 取得後に個別 `findUnique` を await している等）。
- 静的検出のみで実測が無い場合は「N+1 の疑い（未計測）」とし、確定と書かない。
  ループ回数が定数（例: 最大 3 件のマスタ）なら実害が無いこともある。

**対処**: eager load への修正が第一候補（→ 3.4）。JOIN で 1 本にできるなら書き換えも可。
件数がごく多い場合は IN 句のバッチロード（ORM の preload 相当）が JOIN の行膨張より安全。

### 2.5 その他のシグナル

- **不要な列・行**: `SELECT *` で大きな列（TEXT / BLOB / JSON）を毎回運んでいる、
  アプリ側で捨てる行まで取得している。EXPLAIN では出にくいので、実測時間と転送量、
  コード側の利用列を突き合わせて判定する。対処は列の明示指定・条件のプッシュダウン。
- **ロック待ち**: 実測時間が不安定に大きい（EXPLAIN のコストと合わない）場合に疑う。
  PostgreSQL: `pg_stat_activity` の `wait_event_type = 'Lock'`、MySQL:
  `performance_schema.data_lock_waits` を参照（いずれも SELECT で読めるビュー）。
  本スキルの計測は読み取りのみなので、ロック競合の再現はせず「ロック待ちの疑い + 確認方法」の
  提示に留める。
- **インデックスの読み過ぎ**: PostgreSQL の `BUFFERS` で shared read が大きい、
  MySQL で `rows examined` が返却行数より桁違いに大きい場合、
  インデックスはあっても絞り込みが後段（filter）で行われている。複合インデックスの列順を見直す。

## 3. 改善パターンの判定基準

### 3.1 インデックス追加（単一列）

- 適用条件: 選択率の高い等値 / 範囲条件の列にインデックスが無く、EXPLAIN で seq scan / ALL +
  filter になっている。
- 提案 DDL 例: `CREATE INDEX idx_orders_user_id ON orders (user_id);`
  （PostgreSQL では `CREATE INDEX CONCURRENTLY` を本番適用時の推奨として注記する。
  本スキルは DDL を実行しない。適用はマイグレーション化し、危険検出は
  db-migration-safety-checker の領分）。
- 注意として添える: 書き込みコストの増加、既存の複合インデックスで代替できないかの確認。

### 3.2 複合インデックスの列順

- 基本則: **等値条件の列を先、範囲条件・ORDER BY の列を後**。
  `WHERE tenant_id = ? AND created_at > ? ORDER BY created_at` → `(tenant_id, created_at)`。
- 範囲条件の列より後ろの列はインデックスで絞り込めない（範囲で走査が止まるため）。
  範囲列を複数持つクエリは、最も選択率の高い範囲列を 1 つだけインデックスに乗せる。
- 既存インデックスの左端プレフィックスと重複する新規インデックスは提案しない
  （`(a)` は `(a, b)` があれば不要）。逆に `(b)` 単独が必要かはクエリ全体で判断する。
- カバリング（PostgreSQL: `INCLUDE`、MySQL: 列を後ろに足す）は、
  実測で index scan 後のテーブル参照（Heap Fetches / 二次参照）が支配的なときだけ提案する。

### 3.3 クエリ書き換え

- 適用条件: インデックスでは解決しない形（列への関数適用、OR の多用、深い OFFSET、
  相関サブクエリの繰り返し評価）。
- 定石:
  - 列への関数適用 → 演算を定数側に寄せる（`WHERE created_at >= now() - interval '7 days'` は可、
    `WHERE date(created_at) = ...` は不可）
  - OR → UNION ALL への分解（各枝が別インデックスを使えるとき）
  - 深い OFFSET → keyset pagination（2.3）
  - 相関サブクエリ → JOIN / LATERAL / ウィンドウ関数へ
- 書き換え案には**必ず等価性の注意**を添える（NULL の扱い・重複行の有無が変わりうる箇所を明記し、
  結果が一致することの確認方法を 1 行書く）。

### 3.4 eager load（N+1 対処）

- 適用条件: 2.4 で N+1 と判定（実測またはログで確定）した箇所。
- ORM 別の修正先の例: Rails `includes` / `preload` / `eager_load`、
  Django `select_related`（FK・1 対 1）/ `prefetch_related`（多対多・逆参照）、
  Prisma `include`、SQLAlchemy `selectinload` / `joinedload`、
  TypeORM `relations` / `leftJoinAndSelect`。
- JOIN 型（eager_load / joinedload）と分割ロード型（preload / selectinload）の選択:
  親 1 行に対して子が多い（行膨張する）なら分割ロード型、
  関連条件で絞り込みたいなら JOIN 型。迷ったら分割ロード型を既定にする。
- 修正案は `file:line` 付きのコード diff 案として出す。適用は提案のみで、本スキルでは実行しない。

## 4. 判定に迷ったときの原則

- シグナルが 1 つしか無い・環境が本番と乖離している → 断定せず「疑い + 確認方法」で書く。
- 改善案が複数あるときは、**適用コストが低く可逆な順**（統計更新 → インデックス → 書き換え →
  設計変更）に並べて提案する。
- 期待効果の数値は、改善後に同一環境で再実測できた場合だけ書く。それ以外は定性で書く
  （SKILL.md 大原則 1 の系）。

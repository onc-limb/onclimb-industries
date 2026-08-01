# dangerous-operations — DB マイグレーション危険操作カタログ

db-migration-safety-checker が照合に使う、エンジン別の危険操作カタログ。
PostgreSQL / MySQL(InnoDB) を主対象とし、SQLite は末尾に補足としてまとめる。
各項目は 操作 / 何が起きるか（ロックの種類・時間・レプリケーション影響）/ 危険になる条件 /
安全な代替手順 の 4 点で書く。

判定の前提:

- バージョン表記が無い記述は「サポート中の全バージョン共通」の挙動。
  バージョンで挙動が変わるものは必ず「PG11+」「MySQL 8.0.12+」のように書いてある。
  対象環境のバージョンが確認できないときは、最も保守的な側で判定し、その旨を報告に書く。
- 「大きいテーブル」の目安: 100 万行または数 GB 以上。これ未満でも高トラフィックな
  テーブル（毎秒書き込みがあるもの）はロック観点で同等に扱う。
- カタログの改善（新パターン・バージョン差の追記）はこのファイルへの追記で行う。

## 0. 全操作共通: ロックキュー詰まり

**個々の DDL が速いかどうかとは別に、ロック取得の待ち行列が事故を起こす。**
すべての指摘でこの観点を前提に置く。

- 何が起きるか: PostgreSQL のほぼ全ての `ALTER TABLE` は ACCESS EXCLUSIVE ロックを取る。
  メタデータ変更だけの「一瞬で終わる」DDL でも、先行する長時間クエリ（レポート集計、
  バックアップ、放置トランザクション）がロックを握っていると DDL はキューで待たされ、
  さらに**その DDL の後ろに全ての読み書きが並ぶ**。数秒〜数分の実質的な全停止になる。
  MySQL でも同じ構図がメタデータロック (MDL) で起きる。オンライン DDL であっても
  開始時・終了時に排他 MDL を取るため、長時間クエリの後ろに並ぶと同様に詰まる。
- 危険になる条件: 対象テーブルに長時間クエリ・長時間トランザクションが走り得る環境
  （分析クエリの同居、`pg_dump` の時間帯、ORM のトランザクション張りっぱなしバグ）。
- 安全な代替手順:
  - PostgreSQL: `SET lock_timeout = '2s';` を DDL の前に置き、タイムアウトしたら
    少し待ってリトライする（マイグレーションツールのフックか手動リトライで）。
    待たされても後続を巻き込む時間を 2 秒で打ち切れる。
  - MySQL: `SET SESSION lock_wait_timeout = 5;` を設定して同様にリトライ。
  - 適用時間帯を長時間クエリ・バックアップと重ねない。

## 1. ALTER TABLE での書き換え型変更（カラム型変更など）

### PostgreSQL

- 操作: `ALTER TABLE ... ALTER COLUMN ... TYPE ...`（例: `int` → `bigint`、`text` → `jsonb`）
- 何が起きるか: ACCESS EXCLUSIVE ロックを保持したまま**テーブル全体とインデックスを書き換える**。
  行数に比例した時間（大テーブルで数分〜数時間）、その間は読み取りも含めて全アクセスがブロック。
  書き換え中は WAL が大量に出て、物理レプリカの遅延が跳ね上がる。ディスクも一時的に約 2 倍食う。
- 危険になる条件: テーブルが大きい場合は Critical。ただし**書き換えが起きない例外**がある:
  `varchar(n)` の長さ拡大、`varchar(n)` → `text`、`numeric` の精度拡大などバイナリ互換の
  変更はメタデータのみで即終わる（ロックキュー詰まりの注意だけ残る）。
- 安全な代替手順（`int` → `bigint` の典型例）:
  1. `ALTER TABLE t ADD COLUMN id_new bigint;`（PG11+ ならメタデータのみ）
  2. トリガまたはアプリで新旧カラムへ二重書き込み
  3. バッチで旧カラム値を `id_new` へバックフィル（§5 のバッチ化に従う）
  4. `CREATE UNIQUE INDEX CONCURRENTLY` で新カラムのインデックスを準備
  5. 短いトランザクションでカラムを入れ替え（rename）、旧カラムは後続リリースで削除
  - PK の型変更は手順がさらに増える（新インデックスを PK に昇格）。分割案として提示する。

### MySQL (InnoDB)

- 操作: `ALTER TABLE ... MODIFY COLUMN ...` での型変更
- 何が起きるか: 型変更は原則 `ALGORITHM=COPY`。テーブルコピー中、読み取りは可能だが
  **書き込みは全期間ブロック**。コピー時間は行数に比例。レプリケーションでは DDL が
  コミット後にレプリカへ流れ、レプリカ上でも同じ時間かかるため、**DDL 所要時間ぶんの
  レプリカ遅延**がそのまま発生する。
- 危険になる条件: 大きいテーブルで Critical。例外: `VARCHAR` の長さ拡大は、長さバイト数の
  境界（255 バイト）を跨がなければ `ALGORITHM=INPLACE` のメタデータ変更で即終わる。
  跨ぐ場合は COPY になる。
- 安全な代替手順: `gh-ost` または `pt-online-schema-change` を使う
  （シャドウテーブル + バックフィル + カットオーバー。書き込みブロックなし）。
  導入できない場合は PostgreSQL と同じ「新カラム追加 → 二重書き込み → バックフィル → 切替」を
  手組みする。適用前に `ALTER TABLE ... , ALGORITHM=INPLACE, LOCK=NONE` を明示指定して
  実行し、受け付けられなければ COPY 相当だと機械的に検出できる（拒否されるだけで安全）。

## 2. NOT NULL 制約の追加

### PostgreSQL

- 操作 A: `ALTER TABLE t ADD COLUMN c type NOT NULL DEFAULT ...`（新規カラム）
  - **PG11+**: DEFAULT が非 volatile（定数、`'{}'`, `0` 等）ならメタデータ変更のみで即終わる。
    ロックキュー詰まり（§0）だけ注意すれば安全。**これを無条件に Critical と書かない。**
  - **PG10 以前**: テーブル全体の書き換えが走る。大テーブルなら Critical。
  - DEFAULT が volatile（`random()`, `gen_random_uuid()` 等）の場合は PG11+ でも書き換えが走る。
- 操作 B: `ALTER TABLE t ALTER COLUMN c SET NOT NULL`（既存カラム）
  - 何が起きるか: ACCESS EXCLUSIVE ロックを保持したまま**全行スキャン**で NULL 不在を検証する。
    大テーブルではスキャン時間ぶん全アクセス停止。
  - 危険になる条件: 行数次第。NULL が 1 行でも残っていれば失敗してロールバック（時間だけ失う）。
  - 安全な代替手順（PG12+）:
    1. `ALTER TABLE t ADD CONSTRAINT c_not_null CHECK (c IS NOT NULL) NOT VALID;`（即終わる）
    2. `ALTER TABLE t VALIDATE CONSTRAINT c_not_null;`（SHARE UPDATE EXCLUSIVE。読み書きを止めずに検証）
    3. `ALTER TABLE t ALTER COLUMN c SET NOT NULL;`（PG12+ は有効な CHECK があるとスキャンを省略し即終わる）
    4. `ALTER TABLE t DROP CONSTRAINT c_not_null;`
  - デプロイ順序: アプリが該当カラムに値を入れ始める**前**に NOT NULL を付けると、
    旧コードの INSERT が全部失敗する。コードが先、制約が後（§4 参照）。

### MySQL (InnoDB)

- 操作: `ALTER TABLE t MODIFY c type NOT NULL`
- 何が起きるか: NULL 許可の変更は `ALGORITHM=INPLACE` で並行 DML 可（テーブル再構築あり。
  ディスク I/O と時間はかかるが書き込みは止まらない）。NULL が残っていると
  （strict モードで）失敗する。
- 危険になる条件: INPLACE でも再構築のため大テーブルではレプリカ遅延・I/O 負荷が出る。
  型も同時に変えると COPY に落ちて書き込みブロック（§1）。
- 安全な代替手順: 事前に NULL をバッチで埋める（§5）→ NOT NULL 化のみを単独の ALTER で行う。
  巨大テーブルは gh-ost / pt-osc。

## 3. CREATE INDEX

### PostgreSQL

- 操作: `CREATE INDEX ...`（無印）
- 何が起きるか: SHARE ロック。読み取りは通るが**構築完了まで書き込みが全ブロック**。
  構築時間は行数に比例。
- 危険になる条件: 書き込みのあるテーブルなら行数次第で Critical。
- 安全な代替手順: `CREATE INDEX CONCURRENTLY ...`。注意点:
  - **トランザクション内で実行できない**。マイグレーションツールの暗黙トランザクションを
    無効化する必要がある（Rails: `disable_ddl_transaction!` / Django: `atomic = False` /
    Alembic: autocommit ブロック）。これを忘れると適用自体が失敗する。**ここまで含めて指摘する。**
  - 失敗すると `INVALID` なインデックスが残る。検知（`pg_index.indisvalid = false`）と
    `DROP INDEX` → 再実行の手順をレポートに添える。
  - 通常の CREATE INDEX より時間がかかり、実行中の長時間トランザクションの完了を待つ。

### MySQL (InnoDB)

- 操作: `ALTER TABLE ... ADD INDEX` / `CREATE INDEX`
- 何が起きるか: セカンダリインデックス追加は `ALGORITHM=INPLACE, LOCK=NONE` で並行 DML 可。
  開始・終了時の MDL（§0）と、構築中の I/O・レプリカ遅延（DDL 所要時間ぶん）だけが論点。
- 危険になる条件: FULLTEXT / SPATIAL インデックスは例外で並行 DML 不可。
  また PRIMARY KEY の追加・変更はテーブル再構築（実質 COPY 相当の重さ）。
- 安全な代替手順: `ALTER TABLE ... ADD INDEX ..., ALGORITHM=INPLACE, LOCK=NONE` と明示して、
  受け付けられない場合に気付けるようにする。巨大テーブル・レプリカ遅延が許容できない場合は
  gh-ost / pt-osc。

## 4. カラム / テーブルの rename とデプロイ順序（expand-contract）

### 全エンジン共通 — DDL の速さの問題ではない

- 操作: `ALTER TABLE ... RENAME COLUMN ...` / `RENAME TABLE` / カラム・テーブルの DROP
- 何が起きるか: rename 自体はどのエンジンでもメタデータ変更で速い
  （PG: 即時 / MySQL 8.0 `RENAME COLUMN`: メタデータのみ。§0 のキュー詰まりのみ注意）。
  **事故はロックではなくデプロイ順序で起きる**:
  - マイグレーション先行 → 旧コードが旧名で参照し続けて即エラー（ローリングデプロイ中は
    旧コードが必ず生きている）
  - コード先行 → 新コードが新名を参照して即エラー
  - どちらの順でも**必ずどちらかが壊れる**。rename は原則 Critical。
  - DROP COLUMN も同種: 旧コードが SELECT に含めていれば壊れる。ORM がカラム一覧を
    キャッシュしている場合（Rails の schema cache 等）、`SELECT *` 相当で参照していなくても壊れる。
- 安全な代替手順: **expand-contract パターン**で複数リリースに分割する。
  1. **expand**: 新カラム（新テーブル）を追加。旧はそのまま
  2. 二重書き込み（アプリまたはトリガ）+ 旧データのバックフィル（§5）
  3. 読み取りを新カラムへ切替（このリリースまでに全コードが新名参照になる）
  4. 旧カラムへの書き込みを停止
  5. **contract**: 後続リリースで旧カラムを DROP
  - 「rename を 1 マイグレーションで済ませたい」に対しては、上記の分割案を
    リリース単位の表にして提示する。読み替え可能な場合（PG のビュー、MySQL 8.0 の
    不可視カラム化 `ALTER TABLE ... ALTER COLUMN ... SET INVISIBLE` で影響を先に確認する等）も選択肢に添える。
  - NOT NULL 追加・制約強化も同じ順序問題を持つ（旧コードが値を入れないまま制約が先に来ると
    INSERT が失敗）。「マイグレーションとコードのどちらが先に本番へ出るか」を必ず確認する。

## 5. 大量 UPDATE / DELETE（データマイグレーション）

### PostgreSQL

- 操作: マイグレーション内の全行 UPDATE / 大量 DELETE（バックフィル含む）
- 何が起きるか: 1 トランザクションで数百万行を更新すると、(1) 行ロックを長時間保持し
  並行更新をブロック、(2) MVCC のため全更新行が dead tuple になりテーブルとインデックスが
  肥大化（bloat）、(3) WAL 大量生成でレプリカ遅延、(4) 長時間トランザクションが
  `xmin` を押さえ、**データベース全体の** vacuum を妨げる。
- 危険になる条件: 行数次第（目安: 10 万行超なら分割を検討、100 万行超は必須）。
- 安全な代替手順:
  - PK 範囲または `LIMIT` 付きサブクエリで 1,000〜10,000 行ずつのバッチに分割し、
    バッチ間に短い sleep を入れる。各バッチを独立トランザクションにする:
    ```sql
    UPDATE t SET c = ...
    WHERE pk IN (SELECT pk FROM t WHERE <条件> LIMIT 5000 FOR UPDATE SKIP LOCKED);
    ```
  - マイグレーションツールの暗黙トランザクション内で回すと分割の意味が無い。
    トランザクション無効化とセットで指摘する。
  - テーブルの大半を消す DELETE は、残す行だけ新テーブルに入れて rename で入れ替える方が速い。
    定期削除が要件なら、この機会にパーティション化 + `DROP PARTITION` を提案する。

### MySQL (InnoDB)

- 何が起きるか: 上記に加えて、(1) undo ログの肥大、(2) バイナリログ経由のレプリケーションで
  レプリカが同じ更新を再生するため**行数に比例したレプリカ遅延**、(3) 範囲条件の UPDATE/DELETE では
  ギャップロックで想定より広い範囲の並行書き込みが止まる。
- 安全な代替手順: `DELETE ... WHERE ... ORDER BY pk LIMIT 5000` をループ、または `pt-archiver`。
  バッチ間で `SLEEP` を入れ、レプリカ遅延を監視しながら進める運用手順まで添えて提案する。

## 6. 外部キー追加

### PostgreSQL

- 操作: `ALTER TABLE child ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES parent(...)`
- 何が起きるか: **子・親の両テーブル**に SHARE ROW EXCLUSIVE ロックを取り、既存全行の
  整合性を検証するフルスキャンが走る。検証中は両テーブルへの書き込みがブロック。
  参照頻度の高い親テーブル（users 等）を巻き込むのが特に痛い。
- 危険になる条件: 子テーブルの行数次第。親テーブルが高トラフィックなら小さめの子でも Warning 以上。
- 安全な代替手順:
  1. `ALTER TABLE child ADD CONSTRAINT fk_x FOREIGN KEY ... NOT VALID;`（検証スキップ、即終わる。
     以後の新規行には制約が効く）
  2. `ALTER TABLE child VALIDATE CONSTRAINT fk_x;`（SHARE UPDATE EXCLUSIVE。読み書きを止めずに既存行を検証）
  - 検証前に孤児行の有無を確認するクエリ（`LEFT JOIN ... WHERE parent.id IS NULL`）を添える。
    孤児行があると VALIDATE が失敗する。

### MySQL (InnoDB)

- 操作: `ALTER TABLE ... ADD FOREIGN KEY ...`
- 何が起きるか: `foreign_key_checks = 1`（既定）のままだと `ALGORITHM=COPY` になり
  テーブルコピー + 書き込みブロック。`foreign_key_checks = 0` にすれば INPLACE で速いが、
  **既存行の検証が完全にスキップされ、孤児行が残ったまま制約が付く**。
- 危険になる条件: 既定のままなら大テーブルで Critical。checks=0 で逃げる場合は
  データ品質リスク（孤児行の混入）を Warning として必ず併記する。
- 安全な代替手順: 事前に孤児行を検出・掃除するクエリを流してから
  `SET foreign_key_checks = 0` + INPLACE で追加し、追加後にもう一度孤児行ゼロを確認する。
  そもそも FK 制約を DB に置かない方針のプロジェクトもある（アプリ層で担保）。
  既存スキーマに FK が 1 本も無い場合は方針の確認を先にする。

## 7. ENUM 変更

### PostgreSQL（ENUM 型）

- 操作 A: `ALTER TYPE ... ADD VALUE ...`（値の追加）
  - 速い（メタデータのみ）。ただし **PG11 以前はトランザクションブロック内で実行できない**。
    マイグレーションツールの暗黙トランザクションと衝突して適用が失敗する。PG12+ は
    トランザクション内で実行できるが、追加した値を同一トランザクション内で使えない。
  - 追加位置の指定（`BEFORE` / `AFTER`）は可能で、これ自体は安全。
- 操作 B: 値の削除・付け替え
  - `ALTER TYPE` では**できない**。新 ENUM 型を作って `ALTER COLUMN ... TYPE ... USING ...` で
    移す = §1 の書き換え型変更になり、大テーブルで Critical。
  - 値の rename だけなら PG10+ の `ALTER TYPE ... RENAME VALUE ...`（メタデータのみ）で足りる。
- 安全な代替手順: 削除を伴う変更は「新値への UPDATE をバッチで済ませる（§5）→
  型の入れ替えは §1 の手順」に分割する。頻繁に値が増減する列挙は、ENUM 型ではなく
  参照テーブル + FK か CHECK 制約付き text への移行を提案する
  （CHECK の付け替えは NOT VALID → VALIDATE で無停止にできる）。

### MySQL（ENUM カラム）

- 操作: `ALTER TABLE ... MODIFY c ENUM(...)` でのメンバー変更
- 何が起きるか: **末尾への追加**はメタデータのみ（INSTANT）で安全。
  **途中への挿入・削除・並び替え**は既存値の内部表現（順序番号）が変わるため
  テーブルコピー（COPY）になり、書き込みブロック + レプリカ遅延。
- 危険になる条件: 末尾追加以外は行数次第で Critical。削除は、削除した値を持つ既存行が
  空文字に化けるデータ破壊リスクもある（strict モードでの挙動確認が必要）。
- 安全な代替手順: 追加は必ず末尾に。削除・並び替えが必要なら、まず該当値を持つ行を
  バッチ UPDATE で移行（§5）→ 末尾追加だけで済む定義に再設計するか、
  gh-ost / pt-osc で作り直す。長期的には参照テーブル方式への移行を選択肢に添える。

## 8. デフォルト値変更

### PostgreSQL / MySQL 共通

- 操作: `ALTER TABLE ... ALTER COLUMN ... SET DEFAULT ...` / `DROP DEFAULT`
- 何が起きるか: **既存カラムのデフォルト変更はメタデータのみ**で即終わる
  （PG: ACCESS EXCLUSIVE を一瞬取るので §0 のキュー詰まりのみ注意。MySQL: INSTANT）。
  既存行の値は書き換わらない。
- 危険になる条件: DDL としては Info 相当。事故はむしろ**意味の取り違え**で起きる:
  - 「既存行も新デフォルトになる」と誤解したまま後続処理を書いている
    （既存行を埋めたいなら §5 のバッチ UPDATE が別途必要）
  - **新規カラム追加と同時**の DEFAULT は別物: PG10 以前は書き換え（§2 操作 A）、
    PG11+ でも volatile なデフォルト（`gen_random_uuid()` 等）は書き換えが走る
  - アプリ側のデフォルトと DB 側のデフォルトが食い違い、デプロイ順序によって
    どちらの値が入るかが変わる
- 安全な代替手順: デフォルト変更そのものは分割不要。既存行の穴埋めが意図に含まれるかを
  確認し、含まれるならバッチ UPDATE（§5）を別マイグレーションとして提案する。

## SQLite（補足）

組み込み用途が主で、本番サーバー DB として大規模運用されることは少ない前提の要点だけ。

- `ALTER TABLE` でできることが少ない: `RENAME TABLE` / `ADD COLUMN` /
  `RENAME COLUMN`(3.25+) / `DROP COLUMN`(3.35+、制約に使われていない場合のみ)。
  型変更・制約追加・NOT NULL 化はできず、「新テーブル作成 → データコピー → rename」の
  作り直し手順になる（多くの ORM マイグレーションはこれを自動でやる）。
- 作り直し中は DB 全体の書き込みロックを取る。単一プロセスのアプリなら問題になりにくいが、
  複数プロセスで共有している場合は `SQLITE_BUSY` の連発になる。
- `ADD COLUMN` の DEFAULT は定数のみ（`CURRENT_TIMESTAMP` 等の一部例外を除き、式は不可）。
  NOT NULL を付けるなら DEFAULT 必須。
- 外部キーは `PRAGMA foreign_keys = ON` でなければそもそも検証されていない。
  マイグレーションで FK を「追加」しても、実行時 PRAGMA が OFF なら効いていない点を指摘する。
- デプロイ順序の問題（§4）はエンジン非依存なので SQLite でも同様に見る。

## 付録: 行数見積もりクエリ

テーブル規模が不明なとき、報告に添えるクエリ（実行はユーザー判断。概算値で十分）。

- PostgreSQL:
  ```sql
  SELECT reltuples::bigint AS approx_rows,
         pg_size_pretty(pg_total_relation_size(oid)) AS total_size
  FROM pg_class WHERE oid = 'public.<table>'::regclass;
  ```
- MySQL:
  ```sql
  SELECT table_rows AS approx_rows,
         ROUND((data_length + index_length) / 1024 / 1024) AS total_mb
  FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = '<table>';
  ```
- SQLite: `SELECT count(*) FROM <table>;`（正確だがフルスキャン。ファイルサイズでの概算でも可）

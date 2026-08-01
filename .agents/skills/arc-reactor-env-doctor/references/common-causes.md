# 頻出エラー原因の分類と診断チェックリスト

env-doctor が診断（標準フロー 2）で使う原因カテゴリの定義。カテゴリごとに
**典型症状（エラーメッセージのパターン）/ 確認コマンド / 典型的な修復 / 手順書反映の観点** を定める。
上から順に確認するのではなく、まず冒頭のトリアージで環境起因かを判定し、
症状に合致するカテゴリから優先して切り分ける。

共通ルール:

- 仮説には必ず実測の根拠を添える（バージョンの実測値と期待値、`which` の結果、エラー原文の該当行）。
- 修復は 1 手ずつ。効かなかった手は記録する。
- システム状態を変える修復（インストール / グローバル設定変更）は実行前にユーザー確認。
- 新しいパターンを見つけたら該当カテゴリに追記して育てる（自分の環境で確認できた事実の範囲で書く）。

## 0. トリアージ — 環境起因かコード起因か

最初にここを判定する。コード起因なら env-doctor の範囲外と伝えて通常のデバッグに切り替える。

環境起因を示すシグナル:

- 同じコードが他の環境（CI / 同僚 / 昨日の自分）では動く・動いていた
- エラーがコードの実行前に出る（インストール・ビルド・起動の段階）
- メッセージが「見つからない / 権限がない / バージョンが合わない / 接続できない」系
  （`command not found`, `ENOENT`, `EACCES`, `EADDRINUSE`, `version mismatch`, `ModuleNotFoundError` 等）
- 直近にコード変更が無いのに壊れた（OS 更新・brew upgrade・マシン移行の後）

コード起因を示すシグナル:

- 自分のコード内のスタックトレースで、ロジック・型・null 参照のエラー
- テストのアサーション失敗
- CI でも同じエラーが出る（環境差ではなくコードの問題）

判定が割れるときは「他の環境で再現するか」を最優先の切り分けに使う。

## 1. version-mismatch — バージョン不整合

- **典型症状**: `The engine "node" is incompatible with this module`、
  `requires Python >= 3.12`、`Unsupported engine`、`SyntaxError`（新しい構文を古いランタイムで実行）、
  lock ファイル形式の非互換（`lockfileVersion` 警告）、`gem::Ruby version mismatch`。
- **確認コマンド**: `node -v` / `python --version` / `go version` / `ruby -v` の実測値と、
  リポジトリの期待値（`.tool-versions`, `.nvmrc`, `.python-version`, `package.json` の `engines`,
  `go.mod`, `Gemfile`, CI 設定）の突き合わせ。バージョンマネージャ利用時は
  `asdf current` / `nvm current` / `mise current` で「いまこのディレクトリで有効なバージョン」を確認する。
- **典型的な修復**: バージョンマネージャで期待バージョンをインストールして切り替える
  （プロジェクトローカルの切り替えを優先。グローバル切り替えは影響が他プロジェクトに及ぶため必ず確認）。
- **手順書反映の観点**: 前提バージョンが README に書かれているか。書かれたバージョンが
  `.tool-versions` 等の実体と食い違っていないか。バージョンマネージャの利用手順があるか。

## 2. path — PATH・シェル環境の問題

- **典型症状**: `command not found`、`zsh: command not found: <tool>`、
  インストールしたはずのツールが見つからない、`which` で出るパスと実行されるものが違う、
  古いバージョンが実行される（PATH の順序で別の実体が先に当たっている）。
- **確認コマンド**: `which -a <cmd>`（複数実体の検出）、`echo $PATH`、`type <cmd>`（alias / 関数の確認）、
  シェル設定（`~/.zshrc`, `~/.zprofile`）に PATH 追記があるか。GUI から起動したエディタ・ランチャーは
  シェルと PATH が異なる点にも注意。
- **典型的な修復**: シェル設定への PATH 追記（設定ファイル変更なので実行前に確認）、
  `hash -r` / シェル再起動での再読み込み、重複実体の整理。
- **手順書反映の観点**: インストール後に PATH を通す手順が書かれているか。
  「ターミナルを開き直す」の一言があるだけでハマりが減るケースが多い。

## 3. permission — 権限の問題

- **典型症状**: `EACCES: permission denied`、`Permission denied`、`Operation not permitted`、
  グローバル install 時の書き込み失敗、ソケット・ファイルの所有者違い、
  過去に `sudo` で入れたものが原因でキャッシュ・ディレクトリが root 所有になっている。
- **確認コマンド**: `ls -la <path>`（所有者・パーミッション）、`whoami`、
  npm なら `npm config get prefix` と該当ディレクトリの所有者確認。
  macOS ではプライバシー保護（TCC）によるアクセス拒否（`~/Documents` 等へのアクセス許可）も疑う。
- **典型的な修復**: 所有者の修正（`chown` は影響を確認してから）、
  グローバル install をやめてユーザー領域・プロジェクトローカルに切り替える。
  **`sudo` での install を修復手段にしない**（次の権限問題の種になる）。
- **手順書反映の観点**: `sudo` を要求する手順が残っていないか（ユーザー領域で完結する手順に直せるか）。

## 4. port-conflict — ポート衝突

- **典型症状**: `EADDRINUSE: address already in use`、`bind: address already in use`、
  `port 3000 is already allocated`（Docker）、サーバーは起動するがアクセスすると別物が応答する。
- **確認コマンド**: `lsof -i :<port>`（macOS で確実）、`lsof -i :<port> -sTCP:LISTEN`。
  Docker 利用時は `docker ps` で公開ポートも確認する。
- **典型的な修復**: 占有プロセスの特定と停止（自分のゾンビプロセスなら kill。
  他の作業中プロセスなら止めてよいかユーザーに確認）、またはポート番号を変えて起動。
- **手順書反映の観点**: 既定ポートが手順書に明記されているか。ポート変更の方法
  （環境変数・設定ファイル）が書かれているか。よく衝突するポート（3000, 5432, 8080 等）なら
  トラブルシューティング節に `lsof` の一行を載せる価値がある。

## 5. native-build — ネイティブ依存のビルド失敗

- **典型症状**: `node-gyp` のエラー、`gcc` / `clang` / `make` 起点の長大なログ、
  `fatal error: 'xxx.h' file not found`、`error: linker command failed`、
  Python の `error: Microsoft Visual C++` 系 / `Failed building wheel for <pkg>`、
  `symbol not found` / `mach-o file, but is an incompatible architecture`（arm64 / x86_64 の混在）。
- **確認コマンド**: `xcode-select -p`（Command Line Tools の有無）、`uname -m` と
  実行中プロセスのアーキテクチャ（Rosetta 経由の x86_64 シェルで arm64 ライブラリを触っていないか）、
  必要なシステムライブラリの有無（`brew list <lib>`、`pkg-config --libs <lib>`）。
  エラーログは末尾ではなく**最初に失敗した行**を探す（後続エラーは連鎖であることが多い）。
- **典型的な修復**: Command Line Tools の導入・更新（インストールなので確認）、
  不足システムライブラリの導入（同上）、アーキテクチャ不整合ならビルドキャッシュ削除 +
  正しいアーキテクチャで再インストール（プロジェクト内キャッシュの削除は確認不要）。
- **手順書反映の観点**: ネイティブ依存の前提（Xcode CLT・システムライブラリ）が
  インストール手順に書かれているか。Apple Silicon 固有の注意が要るか。

## 6. env-var — 環境変数・シークレットの欠落

- **典型症状**: `Missing required environment variable`、`KeyError: 'XXX'`、
  `connection refused`（接続先が未設定で localhost の既定値に落ちている）、
  起動直後の設定バリデーション失敗、認証エラー（キー未設定・期限切れ）。
- **確認コマンド**: `.env.example` / `.env.sample` とリポジトリ内の環境変数参照
  （`rg "process.env|os.environ|getenv"`）の突き合わせ。実際の `.env` は**中身を出力せず**、
  「必要な変数が定義されているか」だけを確認する（`grep -c` や変数名の一覧化に留める）。
- **典型的な修復**: `.env.example` からのコピーと不足変数の追加（値の入手先はユーザーに聞く。
  値を推測で埋めない）。
- **手順書反映の観点**: `.env.example` が実際の必要変数と同期しているか
  （コードが参照するのに example に無い変数は手順書バグ）。値の入手先（管理者に聞く /
  ダッシュボードの場所）が書かれているか。**値そのものは手順書にも書かない。**

## 7. os-diff — OS 差異（特に macOS）

- **典型症状**: Linux 前提の手順が macOS で失敗する。`sed: illegal option`（BSD sed と GNU sed の差）、
  `date` / `grep` / `readlink` のオプション非互換、大文字小文字を区別しないファイルシステム起因の
  import 解決差、`timeout: command not found`、Docker for Mac のファイル共有・パフォーマンス差、
  Apple Silicon で x86_64 前提のバイナリ・イメージが動かない（`platform mismatch`）。
- **確認コマンド**: `uname -sm`、失敗コマンドが BSD 版か GNU 版か（`sed --version` が通れば GNU）、
  Docker イメージのアーキテクチャ（`docker image inspect --format '{{.Architecture}}'`）。
- **典型的な修復**: GNU 版ツールの導入（coreutils / gnu-sed。インストールなので確認）、
  スクリプト側を両対応に書き換える（コード変更に踏み込む場合はユーザーに方針を確認）、
  Docker の `--platform` 指定。
- **手順書反映の観点**: 手順がどの OS で検証済みかの明記。macOS 固有の代替コマンドの併記。
  自分が検証したのは macOS だけなら、Linux への影響は「(推測)」と付けて書く。

## 8. stale-state — 古いキャッシュ・生成物・壊れた中間状態

上記のどれにも当てはまらず「理屈上は動くはず」のとき、最後に疑うカテゴリ。

- **典型症状**: 依存を更新したのに古い挙動をする、ブランチ切り替え後にビルドが壊れる、
  `Module not found` だが依存はインストール済み、一度失敗した install の中断でディレクトリが中途半端。
- **確認コマンド**: lock ファイルと `node_modules` 等の実体の更新時刻の比較、
  ビルドキャッシュディレクトリの有無（`.next/`, `dist/`, `__pycache__/`, `.gradle/` 等）。
- **典型的な修復**: プロジェクト内の生成物・依存ディレクトリの削除と再構築
  （プロジェクト内に閉じるので実行して報告。**プロジェクト外のキャッシュ**、
  例えば `~/.npm` や `~/Library/Caches` の削除は影響が広いので確認してから）。
- **手順書反映の観点**: 「壊れたらまずこれ」のクリーンビルド手順（`rm -rf node_modules && npm ci` 等）が
  トラブルシューティング節にあるか。

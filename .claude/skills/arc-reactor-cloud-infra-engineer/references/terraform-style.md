# Terraform 規約（育成中）

cloud-infra-engineer が Terraform を書くときの規約。**このファイルが正本**。
初期値は一般的なベストプラクティスのシード。案件で決めた流儀は末尾の「決定ログ」に
追記して育て、本文への反映（昇格）はユーザー確認のうえで行う。

対象プロジェクトに既存の Terraform がある場合は、**既存コードの流儀が本規約より優先**
（新しい規約を勝手に持ち込まない。乖離が大きければユーザーに揃え方を確認する）。

## ファイル構成（1 モジュール内）

```
main.tf        # リソース定義（大きくなったら関心事ごとに network.tf, compute.tf 等へ分割）
variables.tf   # 入力変数（全変数に description 必須）
outputs.tf     # 出力（他モジュール・他システムが使うものだけ）
versions.tf    # terraform / provider のバージョン制約
locals.tf      # ローカル値（命名の組み立て・共通タグ等。少なければ main.tf 冒頭でも可）
```

## ディレクトリレイアウト（新規プロジェクトの標準）

```
terraform/
  envs/
    dev/        # 環境ごとのルートモジュール（backend 設定・環境差分はここ）
    prod/
  modules/
    <name>/     # 再利用単位（下記「モジュール分割の基準」）
```

- 環境分離は **env ディレクトリ方式**を初期標準とする（workspace 方式は使わない。
  環境差分が tfvars だけで表現しきれなくなったときに壊れやすいため）。

## モジュール分割の基準

- **最初からモジュールに切らない。** まず envs/ 配下にフラットに書き、
  同じ構成の 2 回目の繰り返しが見えた時点でモジュール化を検討する。
- 切るときの単位は「ライフサイクルと責任の境界」: 一緒に作られ一緒に消えるもの、
  同じ理由で変更されるものを 1 モジュールにする（例: network / service / datastore）。
  リソース種別 1 個だけの薄いラッパーモジュールは作らない。
- モジュールの入出力は最小にする。呼び出し側の都合をモジュール内に持ち込まない。

## 命名

- リソース名（Terraform 内の第 2 ラベル）は snake_case で**役割**を表す
  （`aws_instance.web` のように。`aws_instance.my_instance` のような無意味名は禁止）。
- モジュール内で主要リソースが 1 つだけなら `this` を許容する。
- クラウド側の物理名は `<project>-<env>-<role>` を locals で組み立てて統一する。
- 変数・出力は snake_case。boolean は `enable_` / `is_` 接頭辞。

## バージョンと state

- `versions.tf` で terraform 本体と provider のバージョンを必ず制約する
  （provider は `~>` でマイナー固定を初期値とする）。
- state はリモートバックエンド（AWS は S3 + ロック、Google Cloud は GCS）。
  ローカル state のまま複数人運用に入らない。backend 設定は envs/ 側に置く。

## タグ / ラベル

- 全リソース共通のタグ（`Project` / `Env` / `ManagedBy = terraform`）を
  provider の `default_tags`（AWS）または locals の共通 labels（Google Cloud）で付ける。

## 機密情報

- シークレット値を `.tf` / `.tfvars` / state 経由で露出させない。
  Secrets Manager / Secret Manager / SSM Parameter Store の参照にする
  （正本: リポジトリ直下 `security/02-secret-management.md`）。
- 機密になり得る変数には `sensitive = true` を付ける。

## 検証

- 出荷前に `terraform fmt -check` と `terraform validate` を必ず実行する。
- tflint / trivy 等が対象プロジェクトに導入済みならそれも実行する（勝手に導入しない）。

## 決定ログ（案件で決めた流儀を追記する）

書式: `- YYYY-MM-DD [<project>] 決めたこと — 理由`

<!-- ここに追記。本文への昇格はユーザー確認のうえで行う -->

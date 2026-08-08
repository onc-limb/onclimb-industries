---
name: arc-reactor-cloud-infra-engineer
description: >-
  クラウドインフラ (AWS / Google Cloud) のスペシャリスト。「こうしたい」という対話や既存の設計記録から
  Mermaid 構成図(設計意図と非エンジニア向け説明つき)を作り、構成図から Terraform を起こし、逆に既存の
  Terraform から構成図を復元する双方向変換を担う。サービス仕様・制約・リソース引数は記憶で断定せず
  AWS / Google Cloud の公式ドキュメントと Terraform Registry で裏取りし、成果物には必ずセキュリティ・
  可用性・運用の懸念指摘を添える。「Terraform を書いて」「この Terraform を構成図にして」
  「構成図から Terraform に起こして」「インフラの懸念を見て」等で起動。
  複数案を比較する設計壁打ちは arc-reactor-infra-architecture-designer の領分。
model: opus
effort: high
metadata:
  type: skill
---

# cloud-infra-engineer — クラウドインフラのスペシャリスト (arc-reactor)

AWS / Google Cloud のインフラを **公式一次情報 → 構成図 → Terraform** の一気通貫で扱うスキル。
成果物は (1) 意図と非エンジニア向け説明の入った構成図、(2) 規約に沿った Terraform、
(3) セキュリティ・可用性・運用の懸念リスト、の 3 点セットを基本とする。

persona: [`personas/arc-reactor.md`](../../../personas/arc-reactor.md) に従う
（応答は日本語 / コード・識別子は英語 / 推測は `# ASSUMPTION:` 明記）。

> 大原則 3 つ:
>
> 1. **仕様は記憶で断定しない。** サービスの制約・リソースの引数・料金体系に関わる判断は、
>    AWS / Google Cloud 公式ドキュメントと Terraform Registry を WebFetch / WebSearch で
>    参照して裏取りし、出典 URL と取得日を成果物に残す。裏取りできなかった箇所は
>    `# ASSUMPTION:` を付けて進める。
> 2. **クラウドへの書き込み操作はしない。** `terraform apply` / `destroy` は実行しない。
>    `fmt` / `validate` は自由に実行してよい。`plan` は認証情報が要るため、実行コマンドを
>    提示してユーザーに委ねる（ユーザーが明示的に頼んだ場合のみ実行）。
> 3. **規約は育てる。** Terraform の書き方・モジュール分割・図の流儀は
>    `references/` の規約ファイルが正本。案件で新しい流儀が決まったら、その場で
>    規約ファイルに追記して育てる（下記「規約の育て方」）。

## トリガー

| ユーザー発話の例 | フロー |
|---|---|
| 「〜したいのでインフラを考えて / 構成図にして」 | A（対話 → 構成図） |
| 「この構成図（設計記録）から Terraform に起こして」 | B（構成図 → Terraform） |
| 「Terraform を書いて / このリソースを追加して」 | B（要件を確認して Terraform） |
| 「この Terraform を構成図にして / 図で説明して」 | C（Terraform → 構成図） |
| 「非エンジニアに説明できる図にして」 | C + 非エンジニア向け説明を厚めに |
| 「この構成のセキュリティ・可用性の懸念を見て」 | D（レビュー単体） |

ユーザーが明示的に依頼したときだけ起動する（インフラの話題が出たついでに自動起動しない）。

## 共通: 開始時に読むもの

1. [references/terraform-style.md](references/terraform-style.md) — Terraform の書き方・モジュール分割規約（育成中）
2. [references/diagram-style.md](references/diagram-style.md) — 構成図の流儀（意図注記・非エンジニア向け説明の書き方）
3. 対象プロジェクトに既存の Terraform / 設計記録（`infra-design/`）があれば、それを現状の正として読む

## フロー A: 対話 → 構成図

「こういうことをしたい」から構成図を作る。

1. **ヒアリング**（2〜3 問ずつ）: ワークロード種別 / トラフィック・データ量 / 可用性要件 /
   予算感 / 運用体制 / 既存資産 / コンプライアンス制約。未回答は ASSUMPTION で進める。
2. **構成の提案**: 1 案に絞って提案する。採用サービスごとに「なぜそれか」を一言つける。
   特性の異なる複数案をじっくり比較したい空気になったら
   `arc-reactor-infra-architecture-designer` へ誘導する（設計記録は本スキルの入力になる）。
3. **裏取り**: 構成の成立性に関わる仕様（サービス間の接続可否・リージョン提供状況・
   制約値など）を公式ドキュメントで確認し、出典を控える。
4. **構成図の生成**: diagram-style.md の流儀で Mermaid 構成図 + コンポーネント表 +
   設計意図注記 + 非エンジニア向け説明を出す。
5. **フロー D のレビュー**を 1 周回して懸念リストを添える。
6. 合意できたら、そのままフロー B（Terraform 化）へ進むか確認する。

## フロー B: 構成図 → Terraform

構成図・設計記録・合意済みの要件から Terraform を書く。

1. **入力の確定**: 対象の構成図（本スキル / infra-architecture-designer の成果物、または
   ユーザー持ち込みの図・箇条書き）を確認し、Terraform 化する範囲を合意する。
2. **リソース仕様の裏取り**: 使うリソースは Terraform Registry の公式ドキュメント
   （registry.terraform.io の aws / google プロバイダ）で引数・必須項目・非推奨を確認する。
   記憶にある引数名をそのまま書かない（プロバイダのバージョンで変わるため）。
3. **実装**: terraform-style.md の規約（ファイル構成・命名・モジュール分割基準・state・
   タグ付け）に従って書く。規約に無い判断が必要になったら、その場でユーザーと決めて
   規約ファイルに追記する。
4. **機密の扱い**: シークレット値を `.tf` / `.tfvars` に書かない。Secrets Manager /
   Secret Manager / SSM 参照にし、値の投入手順は README コメントで案内する
   （正本は [`security/02-secret-management.md`](../../../security/02-secret-management.md)）。
5. **検証**: `terraform fmt -check` と `terraform validate` を実行する（CLI が無い環境では
   その旨を明記して文法確認まで）。`plan` はコマンド提示に留める。
6. **対応表**: 構成図のコンポーネント ↔ Terraform リソースの対応表を添え、
   図に有って Terraform に無いもの（手動管理・スコープ外）を明示する。

## フロー C: Terraform → 構成図

既存の Terraform を読み、構成図に復元する。

1. **走査**: 対象ディレクトリの `.tf` を全て読む（module 参照があれば module 側も追う。
   レジストリ公開 module はドキュメントを参照する）。
2. **図の生成**: diagram-style.md の流儀で構成図を生成する。ネットワーク境界
   （VPC / サブネット / public・private）と通信経路が読み取れる粒度にする。
3. **意図の復元**: 設計意図はコード中のコメント・変数名・既存の設計記録から拾う。
   コードから読み取れない意図は創作せず **(要確認)** と注記してユーザーに確認する
   （もっともらしい理由をでっち上げない。これが一番の禁止事項）。
4. **非エンジニア向け説明**: diagram-style.md のテンプレートに沿って
   「この構成でできること / お金がかかる場所 / 壊れたらどうなるか」を平易に書く。
5. **差分検出**: 図にした結果、規約違反や懸念（フロー D 観点）に気づいたら、
   図の注記とは別に懸念リストとして添える。

## フロー D: セキュリティ・可用性・運用レビュー（必須・スキップ不可）

フロー A〜C の成果物には必ずこのレビューを 1 周添える（単体起動も可）。

- **セキュリティ観点**: [`arc-reactor-infra-architecture-designer/references/security-review-checklist.md`](../arc-reactor-infra-architecture-designer/references/security-review-checklist.md)
  を正本として全観点を確認する（リポジトリ直下 [`security/`](../../../security/) も参照可）。
- **可用性・運用観点**: [references/operational-review-checklist.md](references/operational-review-checklist.md)
  の全観点を確認する（単一障害点 / バックアップ・DR / 監視 / スケール / クォータ / コスト暴走 / 運用経路）。

出力:

- **指摘**: 観点 / 該当コンポーネント（file:line があれば添える）/ 重大度（High・Mid・Low）/ 対策案 の表
- **確認した観点の列挙**: 指摘が無かった観点も「確認済み」として列挙する
  （確認漏れと確認済みを読み手が区別できるようにするため）
- **免責**: 専門のセキュリティ監査・SRE アセスメントの代替ではない旨を毎回明記する

## 成果物の保存

- 構成図・設計記録・レビュー結果: 対象プロジェクト配下 `infra-design/<YYYY-MM-DD>-<topic>.md`
  （infra-architecture-designer と同じ置き場。プロジェクト固有情報はプロジェクトに閉じる）
- Terraform コード: 対象プロジェクトの既存レイアウトに従う。無ければ terraform-style.md の
  標準レイアウト（`terraform/envs/<env>/`）を提案して合意してから作る
- 対象プロジェクトの git を汚す可能性があるため、**保存前に必ずユーザーに確認**する

## 規約の育て方（自己進化）

`references/terraform-style.md` と `references/diagram-style.md` は**育成中の資産**。

- 案件の作業中に「規約に無い判断」をユーザーと決めたら、その場で該当ファイルの
  「決定ログ」に日付つきで追記する（skill-feedback.md にためない。辞書・資産系と同じ扱い）。
- 既存の規約と矛盾する決定になった場合は、上書きせずユーザーに確認してから改訂する。
- SKILL.md 本文の書き換えはこのルートでは行わない（通常のスキルフィードバック運用に従う）。

## 既存スキルとの棲み分け

- **arc-reactor-infra-architecture-designer**: 特性の異なる 2〜3 案を比較して収束させる
  「設計の壁打ち」はあちらの領分。本スキルはその設計記録を受け取って Terraform 化する後工程、
  および Terraform⇄構成図の双方向変換と懸念指摘を担う。1 案前提の軽い「対話 → 構成図」は
  本スキルで完結してよい。
- **edith-tech-selection-research**: ミドルウェア・サービスの選定比較（出典つき比較表）は
  あちらの領分。比較結果は本スキルの入力として使う。
- **friday-design-doc-generator**: 他者共有用の設計書としての清書はあちらの領分。
  本スキルの構成図・設計記録はその入力になる。

## 品質・安全性

- 仕様・制約・料金の裏取りは公式一次情報（docs.aws.amazon.com / cloud.google.com /
  registry.terraform.io）を優先し、出典 URL と取得日を成果物に残す。ブログ・Qiita 等の
  二次情報だけを根拠に断定しない。
- コスト概算は「概算」と明記し、正確な見積は公式の料金計算ツールを案内する。
- `terraform apply` / `destroy` / クラウドアカウントへの書き込み操作は行わない。
- シークレット値・アカウント ID 等の機密をコード・図・設計記録に書かない。
- レビュー出力には専門監査の代替ではない旨を毎回明記する。

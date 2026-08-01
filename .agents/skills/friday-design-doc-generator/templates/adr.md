<!--
ADR 雛形 (friday-design-doc-generator) — Michael Nygard 形式ベース
- ファイル名: adr/NNNN-<kebab-case-title>.md（連番）
- 見出しは削除・順序変更しない。埋められないセクションは TBD と書く。
- 決定の背景・理由はコードに書かれていないことが多い。ユーザーの明言を最優先の情報源とし、
  コードから逆算した理由付けには必ず「(推測)」タグを付ける。
- {{...}} は生成時に置き換えるプレースホルダ。
-->

# {{NNNN}}. {{決定のタイトル}}

- 日付: {{decision_date_or_TBD}}
- 生成日: {{generated_date}} / 対象: {{target_path}} / commit: {{commit_hash_or_TBD}}

## Status

{{Proposed / Accepted / Deprecated / Superseded by NNNN}}

## Context（背景・制約）

<!-- 決定を迫られた状況・制約。ユーザーの明言が無い部分は TBD -->
{{背景}}

## Decision（決定内容）

<!-- 何を採用・決定したか。コード上の現状（採用の痕跡）には根拠パスを添える -->
{{決定内容}}（現状のコードでの反映: `{{source_path}}`）

## Consequences（帰結）

<!-- この決定によって良くなること・悪くなること・受け入れたトレードオフ -->
- 良くなること: {{...}}
- トレードオフ: {{...}}
- TBD

## 検討した代替案

<!-- ユーザーの明言が無ければ TBD。創作しない -->
| 代替案 | 見送った理由 |
|---|---|
| {{alternative}} | {{理由 or (推測) or TBD}} |

## TBD 一覧

- [ ] {{TBD 項目と、確認したい質問}}

## 参照したソース

- `{{source_path}}`

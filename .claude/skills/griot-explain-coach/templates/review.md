<!--
  griot-explain-coach 添削レポート テンプレート
  - 配置: explain-practice-data/sessions/<YYYY-MM-DD>-<slug>/review.md
  - 見出しの削除・順序変更はしない。該当なしのセクションは「なし」と明記。
  - 指摘には必ず transcript.md からの引用を付ける。引用は原文のまま(要約引用しない)。
  - category は review_log.py の固定語彙(conclusion-first / structure / audience-fit /
    concreteness / logic / completeness / brevity / clarity / delivery)。
  - {{...}} は生成時に置換する。このコメントブロックは実体には残さない。
-->
---
date: {{YYYY-MM-DD}}
session: {{YYYY-MM-DD-slug}}
persona: {{今回の想定聞き手（前提知識まで）}}
input: transcript.md
---

# 添削: {{テーマ}}

## 想定聞き手

{{ペルソナと前提知識。note.md の audience から変更があればその旨}}

## 総評（3 行以内）

## 良かった点

- 「{{引用}}」 — {{何が・なぜ良いか}}

## 指摘

<!-- 重要な順。major 1〜3 件 + minor 数件が目安。この回で実際に問題だった点だけ -->

### 1. [{{category}} / {{major|minor}}] {{指摘の見出し}}

- 該当箇所: 「{{引用}}」
- 何が問題か: {{ペルソナ視点でどこで理解が止まるか}}
- 直し方: {{言い直し例・構成の入れ替え案など具体的に}}

## 抜けていた内容（note.md にあるのに説明で落ちた点）

## 改善版の例（冒頭 30 秒など）

> {{このペルソナに向けた言い直しモデル}}

## 次回の重点（1 つだけ）

{{カテゴリ 1 つ + 具体的にどうするか。直近の台帳傾向との連続性にも触れる}}

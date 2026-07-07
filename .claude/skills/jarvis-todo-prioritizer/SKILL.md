---
name: jarvis-todo-prioritizer
description: ToDo 台帳(todo-data/todos.json)のタスクに、プロジェクトへの影響度(impact 1-5)と緊急度(urgency 1-5)を根拠付きで評価・記録する優先順位づけスキル(jarvis 系)。jarvis-todo-management と連携し、評価の材料を 3 系統 — ①プロジェクトの実態(台帳の due/滞留・リポジトリや成果物の現状・worklog digest)、②世間の情報(外部期限・EOL・セキュリティ・制度変更など。外部要因が絡むタスクのみ WebSearch し出典 URL+取得日を付ける)、③ユーザーとの壁打ち(2〜3 件ずつ仮評価を提示し現場感で上書き) — から集め、ユーザーが確定した評価だけを `todo.py prioritize` で台帳に記録する(スコア計算・並べ替えは todo.py --sort priority が行い、Claude は暗算しない)。評価は impact×urgency の象限で着手順の目安に変換して提案する(決定はユーザー)。「ToDo の優先順位つけて」「どれからやるべき？」「このタスクの優先度を評価して」「優先度を見直して」「今のタスクを影響度と緊急度で整理して」等で、ユーザーが明示的に依頼したときだけ起動する(自動起動しない)。台帳への登録・分割・状態管理・同期は jarvis-todo-management の領分で、本スキルは優先度の評価と記録に特化する。評価は判断材料の整理であって、着手順の強制ではない。
metadata:
  type: skill
  data_dir: <repo>/todo-data
---

# todo-prioritizer — ToDo の優先順位づけスキル

ToDo 台帳のタスクに **影響度 (impact 1-5) × 緊急度 (urgency 1-5)** を根拠付きで評価し、
ユーザーが確定した値だけを台帳に記録する。読み手は自分自身と AI（次に何をやるかの判断材料）。

> **スタンス**: 優先度は「事実」ではなく**意図の決定**。jarvis-todo-management の
> 「スキルは提案、確定はユーザー」原則に従い、**ユーザーの確定なしに priority を記録しない**。
> 評価は判断材料の整理であって、着手順の強制ではない。

## 棲み分け

- **`jarvis-todo-management`**: 台帳そのものの運用（登録・分割・状態遷移・収穫・棚卸し・Google 同期）。
  棚卸し（フロー D）の「着手順の提案」で優先度が必要になったら本スキルを呼ぶ。
- **本スキル**: 影響度・緊急度の評価と記録（`priority` フィールドの唯一の書き手）。
- タスクの中身を実行する・Issue 化する（jarvis-issue-planner）のは別系統。

## データと操作

- 台帳は `todo-data/todos.json`（schema_version 2。`priority` フィールドの定義は
  [`docs/todo-management-redesign-2026-07-02.md`](../../../docs/todo-management-redesign-2026-07-02.md) 参照）。
- 操作は必ず jarvis-todo-management の `scripts/todo.py` 経由（直接編集しない）:
  ```bash
  TODO=.claude/skills/jarvis-todo-management/scripts/todo.py
  python3 $TODO list --status inbox --status todo --status in_progress --json  # 対象の取得
  python3 $TODO prioritize <task_id> --impact 4 --urgency 2 --rationale "<根拠>"  # 記録
  python3 $TODO list --sort priority                                          # ランキング
  ```
- **スコア計算（impact × urgency）と並べ替えは todo.py が行う**。Claude は暗算しない。
- `rationale` には「事実（根拠）＋ユーザー合意の要点」を 1〜2 文で残す（events.jsonl に履歴が残る）。

## 評価の材料（3 系統）

詳細な尺度と判断基準は [`references/assessment-rubric.md`](references/assessment-rubric.md)。

1. **プロジェクトの実態**（必須・ローカルで完結）
   - 台帳: due の近さ、依存（parent/sub）、滞留期間、同プロジェクトの他タスク。
   - リポジトリ・成果物の現状: 該当コード・データ・ドキュメントがどうなっているか（根拠は file:line 等）。
   - worklog digest・直近セッションの文脈。
2. **世間の情報**（外部要因が絡むタスクのみ）
   - 外部期限（税・制度・申込締切）、EOL・非推奨化、セキュリティ情報、価格改定・イベント等を WebSearch。
   - **全タスクを機械的に検索しない**。外部要因の有無をまず判断し、絡むものだけ調べる。
   - 使った情報には出典 URL と取得日を付け、事実と解釈を区別する。古い情報（12 か月超）はその旨注記。
3. **ユーザーとの壁打ち**（確定はここ）
   - 仮評価を 2〜3 件ずつ提示し、ユーザーの現場感で上書きする。ユーザーの判断が常に優先。
   - Claude の案と違う値で確定した場合も、ユーザーの理由を rationale に残す。

## フロー A: 優先順位づけセッション（メイン）

1. **対象選定**: `list --status inbox --status todo --status in_progress --json`（必要なら `--project`）。
   priority 済みのタスクは「見直し対象」（フロー C）として分ける。件数が多ければユーザーと範囲を絞る。
2. **証拠収集**: タスクごとに上記 1（＋必要なら 2）の材料を集める。判断に足りない材料は
   推測で埋めず「不明・要壁打ち」として明示する。
3. **仮評価の提示**: 評価表（タスク / impact 案 / urgency 案 / 根拠となる事実 / 解釈・仮定）を
   **2〜3 件ずつ**提示して壁打ちする（一括で全部出して圧殺しない）。
4. **記録**: ユーザーが確定した分だけ `prioritize` を実行し、**毎回一言通知**する。
   保留・意見が割れたままのタスクは記録しない（次回の壁打ちに残す）。
5. **結果の提示**: `list --sort priority` の出力を転記し、rubric の象限の目安で
   着手順の提案を添える（決定はユーザー）。
6. 区切りとして CLAUDE.md の ToDo 突き合わせ（本セッション自体の作業記録）を行う。

## フロー B: 単発評価

「このタスクの優先度つけて」等、1 件だけの評価。フロー A の 2〜4 を 1 タスクで行う。
他スキル・他セッションでタスクを追加した直後の呼び出しを想定。

## フロー C: 見直し（再評価）

- 対象: `assessed_at` から **30 日超**、または状況変化（due の変更・依存タスクの完了・
  外部イベントの発生・プロジェクト方針の変更）があったタスク。
- 過去の rationale を提示し、「何が変わったか」の差分だけ壁打ちして更新する
  （ゼロから再評価しない。変わっていなければ記録もし直さない）。
- 優先順位づけセッション（フロー A）の冒頭で、見直し候補があれば一言添える。

## 品質・安全性（jarvis persona 準拠）

- 事実（due・台帳の状態・出典付きの外部情報）と解釈（影響の見立て）を分けて提示する。
- 推測した箇所は推測であることを明示する。確証のない外部情報は評価の根拠にしない。
- priority の記録はユーザー確定後のみ。まとめて確定を促す誘導（「全部この案でいいですね？」）をしない。
- 台帳の他フィールド（status・due 等）はこのスキルでは変更しない（気づいた矛盾は
  jarvis-todo-management のフローとして提案する）。

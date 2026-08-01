# example: observation-qa

クライミングのオブザベーション（登る前のルート観察）について答える Q&A サービスの評価環境の実例。
jocasta 系ツール群の参照実装を兼ねる。

- `app/` — サンプル対象アプリ。`claude` CLI（haiku）+ システムプロンプトで質問に答える。
  実サービスを評価するときは、この app/ を実物への接続（config.json の adapter）に差し替える。
- `dataset/cases.json` — シードケース 8 件（頻出 / 重要・安全 / エッジの 3 方向）。

## 使い方

```bash
python3 .claude/skills/jocasta-eval-runner/scripts/evalkit.py init observation-qa --from-example observation-qa
python3 .claude/skills/jocasta-eval-runner/scripts/evalkit.py validate observation-qa
python3 .claude/skills/jocasta-eval-runner/scripts/evalkit.py collect observation-qa --note "baseline"
python3 .claude/skills/jocasta-eval-runner/scripts/evalkit.py judge observation-qa --run latest
python3 .claude/skills/jocasta-eval-runner/scripts/evalkit.py score observation-qa --run latest
python3 .claude/skills/jocasta-eval-runner/scripts/evalkit.py report observation-qa --run latest
```

サンプルアプリ・ジャッジとも `claude` CLI が必要（このリポジトリで作業する環境なら利用可能）。

---
tags:
  - deep-agents
  - blackboard-pattern
  - experiment
  - architecture
  - skills
  - mcp
  - hitl
  - sse
date: 2026-04-17
created: 2026-04-16
title: Deep Agents Blackboard Demo README
---

# Deep Agents Blackboard Demo

> 黒板パターンをテーマにしつつ、Deep Agents の主要機能をできるだけ広く触れるための総合デモ。  
> 目的は「黒板を自前で再実装すること」ではなく、  
> Deep Agents の流儀で黒板パターンをどう構成するかを学ぶことにある。

---

## このリポジトリでやりたいこと

このリポジトリは、Deep Agents の勉強用デモです。
ただし、機能をバラバラに並べるのではなく、ひとつのテーマで束ねたい。
そのテーマとして採用するのが **黒板パターン** です。

ここでいう黒板パターンは、昔ながらの専用 blackboard manager を自作する話ではない。
Deep Agents が最初から持っている planning、filesystem、subagents、memory、human-in-the-loop、streaming などを前提に、
**共有作業面としての黒板をどう再解釈するか** を試す。

このデモで見たいのは次の 3 点です。

1. Deep Agents にすでにある機能で、どこまで黒板パターンを自然に表現できるか
2. skills や MCP のような拡張要素を、黒板の周辺機能としてどう組み込めるか
3. 安全性や観測性まで含めて、実運用に寄せた形でどう構成するか

---

## 使い方

### 1. セットアップ

```bash
uv sync
```

`.env` に `OPENAI_API_KEY` を置く。

必要なら blackboard や memory の保存先は環境変数で変えられる。

```bash
DEEP_AGENT_DEMO_WORKSPACE_ROOT=/tmp/deep-agent-demo
DEEP_AGENT_DEMO_BLACKBOARD_ROOT=/tmp/deep-agent-demo/blackboard
DEEP_AGENT_DEMO_MEMORY_ROOT=/tmp/deep-agent-demo/memories
```

### 2. サーバー起動

```bash
uv run deep-agent-demo
```

起動後は `http://127.0.0.1:8000` で待ち受ける。

ヘルスチェック:

```bash
curl http://127.0.0.1:8000/health
```

### 3. `/chat` を叩く

```bash
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "黒板パターンを使って OSS 公開計画を立てて",
    "user_id": "demo-user",
    "thread_id": "demo-thread",
    "run_id": "run-001",
    "auto_approve_memory": true
  }'
```

SSE では少なくとも次のイベントが流れる。

- `progress`
- `blackboard`
- `hitl`
- `final`

### 4. 生成物を見る

blackboard は run 単位で分かれる。

```text
blackboard/<user_id>/<thread_id>/<run_id>/
```

この中に次のファイルが出る。

- `goal.md`
- `plan.md`
- `critique.md`
- `synthesis.md`
- `trace.md`
- `memory-proposals.md`
- `mcp-log.md`
- `state-summary.md`
- `decisions.md`
- `open-questions.md`

memory は user 単位で分かれる。

```text
memories/<user_id>/
```

### 5. テスト

通常テスト:

```bash
uv run pytest -q
```

real OpenAI-backed E2E:

```bash
DEEP_AGENT_DEMO_RUN_REAL_E2E=1 uv run pytest -q tests/test_real_runtime_path.py
```

この E2E は local MCP server と `/chat` の SSE 経路を通す。

---

## 設計の前提

この README では、次の前提を採る。

- 黒板は「専用プロセス」ではない
- 黒板は Deep Agents の shared filesystem state を中心に表現する
- タスク分解は `write_todos` に任せる
- 長期記憶は `/memories/` に任せる
- 専門家の分業は subagents で表現する
- skills は能力の追加
- MCP は外部世界との接続
- permissions と human-in-the-loop は安全境界
- SSE は観測性の入口

つまり、このデモの中心はあくまで黒板パターンだが、
黒板を成立させる部品として Deep Agents の機能を幅広く使う。

---

## このデモにおける黒板とは何か

このデモでは、黒板を `/blackboard/` というディレクトリ名そのものとしては定義しない。
黒板とは、**親エージェントとサブエージェントが共有できる scratch filesystem 上の作業面** を指す。

その上で、必要なら観測しやすさのために `/workspace/blackboard/` 以下へ
整理済みの成果物を出力する。

例:

- `/workspace/blackboard/goal.md`
- `/workspace/blackboard/plan.md`
- `/workspace/blackboard/critique.md`
- `/workspace/blackboard/synthesis.md`

ここで大事なのは、
`/workspace/blackboard/` はアーキテクチャの基盤ではなく、
**人間が観測しやすいように整えた表示面** だということです。

基盤としての黒板は、Deep Agents の backend が提供する shared state にある。

---

## 一本の総合デモとしての全体像

```text
ユーザー
  │
  ▼
FastAPI /chat
  │
  ▼
Orchestrator (Deep Agent)
  ├─ write_todos で作業計画を管理
  ├─ scratch filesystem を黒板として使う
  ├─ Planner / Critic / Synthesizer に委任
  ├─ skills を必要時に読み込む
  ├─ MCP tools で外部情報や外部操作に接続
  ├─ permissions と HITL で危険操作を止める
  ├─ /memories/ に長期知識だけ保存
  └─ SSE で途中経過を配信
```

このデモでは、Deep Agents の機能を単に列挙しない。
すべてを「黒板パターンを支える部品」として意味づける。

---

## 取り入れたい Deep Agents 機能

### 1. Planning

`write_todos` を使って、オーケストレーター自身が作業計画を管理する。
これは旧来の黒板パターンでいうタスクキューや進行表に相当する。

ここでのポイントは、Planner サブエージェントに進捗管理まで背負わせないこと。
`Planner` は「良い計画案を出す」専門家であり、
実行管理そのものは Deep Agents の planning capability に寄せる。

### 2. Shared filesystem / backends

同一 thread の scratch filesystem を黒板として扱う。
必要なものだけ `/memories/` に route して永続化する。

この分離により、

- 中間成果物は scratch
- 再利用すべき知識は memory

という境界を明確にできる。

### 3. Subagents

サブエージェントは状態共有のためではなく、
**文脈隔離と専門性のため** に使う。

候補は次の 3 つ。

- `Planner`: ゴールを実行可能な計画に分解する
- `Critic`: 計画の穴、前提漏れ、失敗条件を指摘する
- `Synthesizer`: 計画と批判を統合して最終方針をまとめる

### 4. Skills

skills は黒板の上で働くエージェントに、
ドメイン固有の手順や知識を必要時だけ注入する仕組みとして使う。

例えば、

- OSS 公開計画 skill
- 仕様レビュー skill
- 調査レポート skill

のような形で、黒板に書かれる成果物の質を上げる。

### 5. MCP

MCP は外部データや外部システムに接続するために使う。
このデモでは、黒板が内側の共有面だとすると、
MCP は **外界との接続面** です。

用途の例:

- Web 検索
- GitHub 情報取得
- 社内ツール連携
- 外部リソース参照

### 6. Permissions

permissions は built-in filesystem tools に対する安全境界として使う。
黒板のどこまでを読み書きしてよいかを宣言的に制御する。

特に、

- `/workspace/blackboard/` は許可
- `/memories/` は必要に応じて read-only
- 秘密ファイルや `.env` は deny

のようなルールは重要。

### 7. Human-in-the-loop

人間承認は、危険操作や外部操作の手前で入れる。

例:

- `write_file` を本当に実行してよいか
- MCP 経由の副作用ある操作を続けてよいか
- memory に昇格してよいか

このデモでは HITL を「おまけ」ではなく、
黒板パターンにおける **監督者の役割** として位置づける。

### 8. SSE / streaming

途中経過をそのまま観測できることが重要。
ユーザーは最終回答だけでなく、

- どの subagent が呼ばれたか
- 黒板に何が書かれたか
- どこで承認待ちになったか

を追えるべき。

---

## アーキテクチャ方針

### オーケストレーター

親エージェントの責務は次のとおり。

- 要求を理解する
- todos を持つ
- 必要ならサブエージェントへ委任する
- 黒板に中間成果物を書く
- skills を必要時に読む
- MCP tools を必要時に使う
- memory に保存すべきものを判断する
- 危険操作の前で停止する
- 最終回答を SSE で返す

### Planner

- ゴールから実行計画を作る
- 必要なら専用 skill を読む
- 黒板に `plan.md` を残す
- できれば structured output でも親へ返す

### Critic

- `goal.md` と `plan.md` を読み、穴を指摘する
- リスクと改善案を分けて整理する
- `critique.md` を残す

### Synthesizer

- 計画と批判を統合する
- 取るべき最終方針をまとめる
- `synthesis.md` を残す

この構成にすることで、
「黒板の上で複数の専門家が段階的に知識を追加する」
というパターンを、Deep Agents らしい形で再現できる。

---

## 状態設計

このデモでは状態を 4 層で扱う。

### 1. Conversation state

メッセージ履歴とグラフ実行状態。
LangGraph / Deep Agents が保持する基本状態。

### 2. Blackboard scratch

同一 thread 内で共有される中間成果物。
ここが主たる黒板。

例:

- goal
- draft plan
- critique
- synthesis
- 調査メモ

### 3. Long-term memory

`/memories/` に置く長期知識。
黒板から昇格するのは、再利用価値があるものだけ。

例:

- プロジェクト方針
- ドメイン知識
- 継続的なユーザー設定

### 4. External context

MCP から取得する外部情報。
これは黒板そのものではないが、
黒板に書き込まれる判断材料として使う。

---

## このデモで自前実装しないもの

Deep Agents で既にあるものを、わざわざ作り直さない。

- 独自黒板マネージャー
- 独自タスクキュー
- 独自メモリ基盤
- 独自サブエージェント起動基盤
- 独自承認フレームワーク

自前で設計するのは、
「何をどこへ置くか」
「誰に何を任せるか」
「どこで止めるか」
です。

---

## 想定するプロジェクト構成

```text
deep-agent-demo/
├── .env
├── pyproject.toml
├── langgraph.json
├── src/
│   ├── main.py
│   ├── orchestrator.py
│   ├── subagents/
│   │   ├── planner.py
│   │   ├── critic.py
│   │   └── synthesizer.py
│   ├── mcp/
│   │   └── client.py
│   └── safety/
│       └── permissions.py
├── skills/
│   ├── planning/
│   ├── critique/
│   └── synthesis/
├── AGENTS.md
└── README.md
```

必要であれば、観測用に次のような scratch 出力を使う。

```text
/workspace/blackboard/
├── goal.md
├── plan.md
├── critique.md
└── synthesis.md
```

---

## 実験シナリオ

一本の総合デモとして、次の流れを想定する。

1. ユーザーが課題を投げる
2. Orchestrator が `write_todos` で実行計画を持つ
3. `goal.md` を黒板へ書く
4. Planner が計画案を作って `plan.md` を書く
5. Critic が `critique.md` を書く
6. 必要なら MCP で追加情報を取りにいく
7. Synthesizer が `synthesis.md` を書く
8. 保存価値のある知識だけ `/memories/` に昇格する
9. SSE で途中経過と最終回答を返す
10. 危険操作があれば HITL で止まる

この一連の流れの中で、Deep Agents の主要機能をひととおり触れる。

---

## 検証したいこと

| 項目 | 期待する学び |
|---|---|
| planning | `write_todos` だけで十分に進行管理できるか |
| blackboard | shared scratch state を黒板として扱えるか |
| subagents | 役割分担が本当に効くか |
| skills | 必要時読み込みで文脈量を抑えられるか |
| MCP | 外部情報を黒板へ自然に流し込めるか |
| memory | scratch と長期知識の境界を保てるか |
| permissions | 安全境界を宣言的に管理できるか |
| HITL | 副作用のある操作を人間承認で制御できるか |
| streaming | 内部の進行をユーザーに見せられるか |

---

## 段階的な実装順

全部を一気に入れず、次の順で積み上げる。

1. Orchestrator + SSE
2. scratch filesystem を黒板として使う
3. Planner / Critic / Synthesizer を追加
4. `/memories/` を追加
5. skills を追加
6. permissions を追加
7. HITL を追加
8. MCP を追加

この順番にする理由は、
最初に黒板の核を成立させてから拡張機能を載せた方が、
どの機能が本当に必要か見えやすいからです。

---

## このデモのゴール

最終的に作りたいのは、
「Deep Agents の主要機能をひとつの流れで理解できる、黒板パターン中心の総合デモ」です。

だからこのリポジトリは、

- 単なる multi-agent サンプルでもなく
- 単なる MCP サンプルでもなく
- 単なる skills サンプルでもなく
- 単なる SSE チャットでもない

**黒板パターンを軸に、それらを一つへ束ねた学習用プロジェクト**
として設計する。

---

## 参考にした Deep Agents / LangChain Docs

- Deep Agents overview  
  https://docs.langchain.com/oss/python/deepagents/overview
- Backends  
  https://docs.langchain.com/oss/python/deepagents/backends
- Skills  
  https://docs.langchain.com/oss/python/deepagents/skills
- Permissions  
  https://docs.langchain.com/oss/python/deepagents/permissions
- Human-in-the-loop  
  https://docs.langchain.com/oss/python/deepagents/human-in-the-loop
- Prebuilt middleware  
  https://docs.langchain.com/oss/python/deepagents/middleware
- LangChain MCP  
  https://docs.langchain.com/oss/python/langchain/mcp
- deepagents GitHub repository  
  https://github.com/langchain-ai/deepagents

---

*更新: 2026-04-17 JST*

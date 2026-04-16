---
tags:
  - deep-agents
  - blackboard-pattern
  - experiment
  - readme
  - codex
  - sse
date: 2026-04-16
created: 2026-04-16
title: Deep Agents 黒板パターン実験 README
---

# 🧪 Deep Agents 黒板パターン実験

> 黒板パターンをDeep Agentsで再実装する最小実験。  
> Codexがオーケストレーターとして、PlannerとCriticを自律的に呼び出し、  
> 共有ファイルシステム（`/blackboard/`）を介して状態を受け渡す。  
> 結果はSSEでリアルタイムにユーザーへ届く。

---

## 🎯 何を実験するのか

### 旧・黒板パターンの問題

以前の`controller.py`（約1,600行）では、以下を**全部自前で実装**していましたわ：

- エージェント間の共有状態（黒板）の管理
- タスクキューへの書き込み・読み出し
- エージェントの呼び出し順序の制御
- セッションを越えた状態の永続化

### Deep Agentsで何が変わるか

| 旧・自前実装 | Deep Agentsの対応機能 |
|---|---|
| 黒板（共有状態） | `FilesystemMiddleware`の`/blackboard/`パス |
| タスクキュー管理 | `TodoListMiddleware`（`write_todos`/`read_todos`） |
| エージェント呼び出し順の制御 | Codexが自律判断（LLMに委ねる） |
| 状態永続化 | `CompositeBackend`の`/memories/`パス |
| 非同期処理 | `AsyncSubAgent`（ASGIトランスポート） |

**狙い：1,600行のコントローラーが何行になるか。**

---

## 🏗️ 実験のアーキテクチャ

```
ユーザーのリクエスト
      │
      ▼ POST /chat （SSE開始）
┌─────────────────────────────────────┐
│  Orchestrator（Codex）              │
│                                     │
│  1. ゴールを /blackboard/goal.md    │
│     に書き込む                      │
│                                     │
│  2. Plannerに委任                   │◀─── 自律判断
│     → /blackboard/plan.md に書く    │
│                                     │
│  3. Criticに委任                    │◀─── 自律判断
│     → /blackboard/critique.md に書く│
│                                     │
│  4. 黒板を読んで最終回答を生成      │
└─────────────────────────────────────┘
      │
      ▼ SSEで逐次ユーザーへ送信
```

### 黒板の構造

```
/blackboard/
├── goal.md        ← オーケストレーターが書くゴール定義
├── plan.md        ← Plannerが書くタスク分解結果
└── critique.md    ← Criticが書く批判・改善提案
```

### サブエージェントの役割

**Planner（タスク分解）**
- `/blackboard/goal.md`を読む
- ゴールを具体的なステップに分解する
- `/blackboard/plan.md`に書き込む
- 「何を・どの順番で・なぜその順番か」を明示する

**Critic（批判的検証）**
- `/blackboard/goal.md`と`/blackboard/plan.md`を読む
- 計画の穴・リスク・見落としを指摘する
- `/blackboard/critique.md`に書き込む
- 「このままだと失敗する理由」と「改善案」をセットで出す

---

## 📁 プロジェクト構成

```
deep-agents-blackboard/
├── .env                    ← OpenAI APIキー
├── pyproject.toml          ← uvプロジェクト設定
├── langgraph.json          ← グラフ登録（非同期サブエージェント用）
├── src/
│   ├── main.py             ← FastAPIサーバー（SSEエンドポイント）
│   ├── orchestrator.py     ← メインエージェント（Codex）
│   ├── planner.py          ← Plannerサブエージェントグラフ
│   └── critic.py           ← Criticサブエージェントグラフ
├── skills/                 ← SKILL.mdを置くディレクトリ（後で追加予定）
├── blackboard/             ← 実験中の黒板ファイルが生成される場所
└── AGENTS.md               ← エージェントへの共通ドメイン知識
```

---

## 🚀 セットアップ

### 1. プロジェクト作成

```bash
mkdir deep-agents-blackboard
cd deep-agents-blackboard
uv init
uv add deepagents langchain-openai fastapi uvicorn
```

### 2. `.env`ファイルを作成

```
OPENAI_API_KEY=sk-...
LANGSMITH_TRACING=false
```

### 3. `pyproject.toml`の確認

`uv init`後、Pythonバージョンを確認しますわ：

```toml
[project]
name = "deep-agents-blackboard"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "deepagents",
    "langchain-openai",
    "fastapi",
    "uvicorn",
]
```

---

## 💻 実装コード

### `AGENTS.md`（共通ドメイン知識）

```markdown
# プロジェクト共通ルール

## 黒板の使い方
- ゴールは必ず /blackboard/goal.md に書くこと
- 計画は必ず /blackboard/plan.md に書くこと
- 批判は必ず /blackboard/critique.md に書くこと
- 読む前に ls /blackboard/ で存在確認すること

## 出力フォーマット
- すべての出力は日本語で書くこと
- 見出し・箇条書きを使って構造化すること
- 根拠のない主張は書かないこと
```

---

### `src/planner.py`（Plannerサブエージェント）

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

model = init_chat_model("openai:gpt-4o", temperature=0)

backend = FilesystemBackend(root_dir="./")

graph = create_deep_agent(
    model=model,
    backend=backend,
    system_prompt="""\
あなたはタスク分解の専門家（Planner）です。

## 手順
1. read_file /blackboard/goal.md でゴールを読む
2. ゴールを具体的な実行ステップに分解する
3. 各ステップに「なぜその順番か」の理由をつける
4. write_file /blackboard/plan.md に結果を書く

## 出力形式
# タスク分解計画
## ステップ1: [タイトル]
- 内容：...
- 理由：...
（以下繰り返し）
""",
    memory=["./AGENTS.md"],
)
```

---

### `src/critic.py`（Criticサブエージェント）

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

model = init_chat_model("openai:gpt-4o", temperature=0)

backend = FilesystemBackend(root_dir="./")

graph = create_deep_agent(
    model=model,
    backend=backend,
    system_prompt="""\
あなたは批判的思考の専門家（Critic）です。
計画の穴を見つけるのが仕事ですわ。

## 手順
1. read_file /blackboard/goal.md でゴールを読む
2. read_file /blackboard/plan.md で計画を読む
3. 計画の問題点・リスク・見落としを特定する
4. write_file /blackboard/critique.md に結果を書く

## 出力形式
# 批判的レビュー
## 問題点
- [問題]: [なぜ問題か]
## リスク
- [リスク]: [発生条件と影響]
## 改善提案
- [提案]: [具体的な修正案]
""",
    memory=["./AGENTS.md"],
)
```

---

### `src/orchestrator.py`（Codexオーケストレーター）

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent, AsyncSubAgent
from deepagents.backends import FilesystemBackend, CompositeBackend, StateBackend, StoreBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

model = init_chat_model("openai:gpt-5.3-codex", temperature=0)

store = InMemoryStore()

graph = create_deep_agent(
    model=model,
    system_prompt="""\
あなたはオーケストレーターです。
黒板（/blackboard/）を共有状態として使い、
PlannerとCriticを適切なタイミングで呼び出して問題を解決してください。

## 基本フロー
1. write_todos でタスクを計画する
2. write_file /blackboard/goal.md にゴールを書く
3. Plannerにタスクを委任する（計画書を作らせる）
4. Criticにタスクを委任する（計画を批判させる）
5. 黒板を全部読んで最終回答を生成する

## 重要なルール
- 黒板への書き込みは必ず read_file で確認してから次へ進む
- PlannerとCriticは並列で呼び出せる場合は並列で呼ぶ
- 最終回答は批判を踏まえて改善した計画を含めること
""",
    memory=["./AGENTS.md"],
    subagents=[
        AsyncSubAgent(
            name="planner",
            description="ゴールをステップに分解し /blackboard/plan.md に書く",
            graph_id="planner",
            # url省略 → ASGIトランスポート（ローカル内通信）
        ),
        AsyncSubAgent(
            name="critic",
            description="計画の穴・リスク・改善案を /blackboard/critique.md に書く",
            graph_id="critic",
            # url省略 → ASGIトランスポート（ローカル内通信）
        ),
    ],
    backend=lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={"/memories/": StoreBackend(rt)},
    ),
    store=store,
    checkpointer=MemorySaver(),
)
```

---

### `langgraph.json`（グラフ登録）

```json
{
  "graphs": {
    "orchestrator": "./src/orchestrator.py:graph",
    "planner": "./src/planner.py:graph",
    "critic": "./src/critic.py:graph"
  }
}
```

---

### `src/main.py`（FastAPIサーバー＋SSE）

```python
import json
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import BaseMessage

load_dotenv()

# orchestratorを遅延インポート（.env読み込み後に初期化）
from orchestrator import graph  # noqa: E402

app = FastAPI()


def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _serialize_message(message: BaseMessage) -> dict:
    d = message.model_dump()
    d["type"] = message.type
    return d


async def sse_generator(content: str, thread_id: str) -> AsyncIterator[str]:
    input_data = {"messages": [{"role": "user", "content": content}]}

    async for chunk in graph.astream(
        input_data,
        config={"configurable": {"thread_id": thread_id}},
        stream_mode=["updates", "messages", "custom"],
        subgraphs=True,
        version="v2",
    ):
        stream_type = chunk["type"]
        ns = chunk.get("ns", ())
        event_name = f"{stream_type}|{'|'.join(ns)}" if ns else stream_type

        if stream_type == "messages":
            message, metadata = chunk["data"]
            data = json.dumps(
                [_serialize_message(message), metadata],
                default=_serialize,
                ensure_ascii=False,
            )
        else:
            data = json.dumps(chunk["data"], default=_serialize, ensure_ascii=False)

        yield f"event: {event_name}\ndata: {data}\n\n"

    yield "event: done\ndata: {}\n\n"


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    return StreamingResponse(
        sse_generator(
            content=body["content"],
            thread_id=body.get("thread_id", "default"),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## ▶️ 起動方法

```bash
# ローカル開発サーバー（LangSmith不要）
langgraph dev --n-jobs-per-worker 5

# 別ターミナルでFastAPIも起動する場合
uv run uvicorn src.main:app --reload --port 8000
```

---

## 🧪 動作確認

### curlでテスト

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"content": "新しいPythonライブラリのOSS公開計画を立ててください", "thread_id": "test-1"}'
```

### 期待される動作の流れ

```
[event: updates]        write_todos → タスクリスト作成
[event: updates]        write_file /blackboard/goal.md
[event: updates|tools:xxx]  planner: read_file goal.md
[event: updates|tools:xxx]  planner: write_file plan.md
[event: updates|tools:yyy]  critic: read_file goal.md + plan.md
[event: updates|tools:yyy]  critic: write_file critique.md
[event: messages]       最終回答トークンが流れてくる...
[event: done]           完了
```

### 黒板ファイルの確認

```bash
cat blackboard/goal.md
cat blackboard/plan.md
cat blackboard/critique.md
```

---

## 📊 検証したいこと

実験で確認すべきポイントですわ：

| 確認項目 | 期待値 | 実際の結果 |
|---|---|---|
| Plannerが自律的に呼ばれるか | ✅ | |
| Criticが自律的に呼ばれるか | ✅ | |
| 黒板への書き込みが正しく行われるか | ✅ | |
| PlannerとCriticが並列実行されるか | ✅（Codexが判断） | |
| SSEで中間状態が流れてくるか | ✅ | |
| セッションを越えて黒板が残るか | ✅（`/memories/`ルーティング時） | |
| コード量は旧実装より減ったか | 1,600行→？行 | |

---

## 🔜 次のステップ（実験後）

1. **SKILL.mdを追加する** — Plannerに「ドメイン固有の分解パターン」をスキルとして渡す
2. **Synthesizerを追加する** — PlannerとCriticの結果を統合する第3のエージェント
3. **黒板の永続化をPostgresに変える** — `InMemoryStore` → `PostgresStore`
4. **A2Aプロトコルへの移行を検討する** — ローカルASGIが安定したら

---

*作成：リー | 2026-04-16 JST*

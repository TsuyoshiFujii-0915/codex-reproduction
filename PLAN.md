# 詳細仕様書 v1.0

## Python 製・CLI 限定・学習用 Codex風コーディングエージェント

## 1. 目的

本プロジェクトの目的は、**Codex の公開構造を参考にした最小限の CLI コーディングエージェント**を Python で実装することです。

このエージェントは次を満たすことを目標にします。

* **CLI のみ**を提供する
* **OpenAI Responses API** と **LM Studio の Responses API 互換 endpoint** の両方を利用できる
* デフォルト backend は **LM Studio**
* backend 切替は **endpoint URL と model 名** で行う
* 学習用・個人利用前提で、**コア agent loop / prompt builder / tool execution / context management / safety policy** のみ実装する
* 商用プロダクト向けの周辺機能は実装しない

---

## 2. 設計方針

### 2.1 この仕様で再現する「Codexらしさ」

公開記事から見る Codex の本質は、単なる chat UI ではなく、次の loop にあります。

```text
ユーザー要求
  -> prompt を構築
  -> Responses API で推論
  -> model が tool call を返す
  -> agent が tool を実行
  -> 観測結果を input item として追加
  -> 再度推論
  -> assistant message が出たら 1 turn 終了
```

Codex は Responses API の `instructions` / `tools` / `input` を使って prompt を構成し、会話は message ではなく **Items** を単位に蓄積します。また、prompt caching のために **前回 prompt の exact prefix を保つ**よう注意し、長くなりすぎたら compaction を行います。OpenAI の記事では、初期 prompt に permissions 指示、AGENTS.md 系の instructions、environment context を入れる構造も説明されています。

この仕様では、そのうち以下を v1 のコアとして再現します。

* Responses API ベースの agent loop
* item ベースの会話履歴
* tool call / tool result の明示的な往復
* AGENTS.md の読み込み
* permissions / environment context を prompt に入れる構造
* ローカル stateless history 管理
* 簡易 compaction
* CLI 上の approvals と workspace 制約

### 2.2 この仕様で意図的に削るもの

実際の Codex は Skills、MCP、Web search、IDE 連携、App 連携などを扱えますが、本仕様では **学習用の必要十分なコア**に絞るため v1 では除外します。Codex が skills を progressive disclosure で扱うこと、また tools に web search や MCP が入りうることは公開 docs にありますが、本実装ではそれらは future scope とします。

---

## 3. スコープ

### 3.1 In Scope

* Python 3.11+ での CLI 実装
* OpenAI / LM Studio 共通の Responses API client
* 一問一答モードと対話継続モード
* shell 実行
* ファイル読取/書込
* 会話履歴の保存
* AGENTS.md 読み込み
* approval mode
* workspace path guard
* plain-text compaction
* ローカル plan / progress 記録
* 基本的なログと resume

### 3.2 Out of Scope

* VS Code 拡張
* デスクトップアプリ
* ブラウザ UI
* SaaS 用 multi-user 機能
* telemetry / analytics / DB 保存
* distributed traffic handling
* remote MCP
* built-in web search
* skills marketplace
* OS レベルの厳密 sandbox
* proprietary / hidden prompt の複製
* OpenAI の `/responses/compact` の opaque encrypted compaction の再現

OpenAI の現行 Codex は compaction に `/responses/compact` と `type=compaction` item を使いますが、これは OpenAI 側の API 進化に乗った実装です。本仕様では、LM Studio 互換性と学習目的を優先し、**自前の plain-text summary compaction** に置き換えます。

---

## 4. プロダクト像

### 4.1 ユーザーが得るもの

この CLI は、ざっくり言うと次のように動く。

```text
$ agent "tests が落ちている原因を調べて修正して"

[plan を表示]
[model が shell / read_file / write_file を呼ぶ]
[CLI が tool 実行]
[結果を model に返す]
[必要なら追加編集]
[最後に変更内容・テスト結果・次のアクションを表示]
```

### 4.2 UI 原則

* 画面は terminal only
* 進捗は短い plan と tool 実行ログで見せる
* reasoning をそのまま長文表示しない
* 最終回答は「何をしたか」「どのファイルを触ったか」「何を確認したか」で締める
* failure 時は、どこで止まったかを progress に残す

---

## 5. システム全体構成

```text
[CLI]
  |
  v
[Session Controller]
  |- Config Loader
  |- Prompt Builder
  |- Agent Loop
  |   |- Model Client (Responses API)
  |   |- Tool Dispatcher
  |   |- Context Manager
  |
  |- Safety Policy
  |- Project Memory
  |- Renderer
```

### 5.1 モジュール一覧

```text
agent_cli/
  cli.py
  config.py
  session.py
  model_client.py
  responses_types.py
  prompt_builder.py
  context_manager.py
  token_estimator.py
  approval.py
  policy.py
  renderer.py
  agents_loader.py
  progress_store.py
  plan_store.py
  tools/
    base.py
    shell.py
    read_file.py
    write_file.py
    update_plan.py
  storage/
    transcript.py
    session_store.py
  tests/
```

---

## 6. backend / model abstraction 仕様

### 6.1 基本方針

backend の違いは **provider 名**ではなく、**`base_url` と `model` の設定**として扱う。

### 6.2 既定値

* default `base_url`: `http://localhost:1234/v1`
* default backend label: `lmstudio`
* default `model`: **未設定**
* model 未設定時は起動失敗し、設定を促す

理由は、LM Studio はローカル環境ごとに loaded model が異なるため、固定 model 名を埋め込まないほうが安全だからです。LM Studio docs は OpenAI client の `base_url` を `http://localhost:1234/v1` に向け替える例を示しており、`POST /v1/responses` をサポートしています。

### 6.3 設定項目

```toml
# ~/.agent/config.toml

[model]
base_url = "http://localhost:1234/v1"
model = "openai/gpt-oss-20b"
api_key_env = "OPENAI_API_KEY"   # LM Studioでは未使用でも可
timeout_seconds = 120
stream = true
store = false

[agent]
max_turns = 40
compact_trigger_tokens = 24000
keep_last_turns_after_compact = 4
approval_mode = "on-request"     # never | on-request | always
sandbox_mode = "workspace-write" # read-only | workspace-write | full-access
workspace_root = "."
shell = "/bin/bash"

[ui]
show_plan = true
show_tool_logs = true
show_diff_summary = true

[files]
project_memory_dir = ".agent"
```

### 6.4 リクエスト方針

すべての model 呼び出しは `POST {base_url}/responses` を使用する。
OpenAI Responses API は新規 project に推奨されており、Items を基礎単位として扱います。Responses は server-side state を使うこともできますが、本仕様では Codex の公開記事に合わせて **local stateless history** を基本とし、`previous_response_id` には依存しません。OpenAI docs は `previous_response_id` を使った継続も案内していますが、Codex 記事では Codex 自体は stateless 性を保つためこれを使っていないと説明しています。

### 6.5 `store` の扱い

OpenAI docs では Responses は保存され、`store: false` で無効化できます。学習用・個人利用・最小限実装の方針に合わせて、本仕様では **`store=false` を既定**にします。LM Studio 側で無視されても問題ありません。

---

## 7. CLI 仕様

### 7.1 コマンド

```text
agent [PROMPT]
agent chat
agent resume [SESSION_ID]
agent doctor
agent config init
```

### 7.2 振る舞い

#### `agent [PROMPT]`

* prompt が与えられたら one-shot task 開始
* prompt がなければ interactive REPL を開始

#### `agent chat`

* 明示的に interactive REPL を開始

#### `agent resume [SESSION_ID]`

* 保存済み session を読み込み、履歴と summary を復元して継続

#### `agent doctor`

* base_url 到達確認
* `/models` または簡易 `/responses` で疎通確認
* 設定値、workspace、permission の自己診断を表示

#### `agent config init`

* 初期 config を生成

### 7.3 共通フラグ

```text
--base-url
--model
--api-key
--cwd
--approval [never|on-request|always]
--sandbox [read-only|workspace-write|full-access]
--stream / --no-stream
--max-turns
--compact-trigger-tokens
--debug
```

CLI 引数は config より優先する。

---

## 8. Prompt Builder 仕様

### 8.1 設計原則

Codex の公開記事に合わせ、prompt を「ただの文字列」ではなく、**`instructions` + `tools` + `input items`** として構成する。OpenAI docs でも Responses は message 配列より広い **Items** を基本単位としています。

### 8.2 初回 turn の構成

`instructions`:

* ベースとなる system / developer instruction 文字列
* エージェントの共通ルール
* 回答フォーマット
* 安全方針

`tools`:

* custom function tool schemas
* 名前順で安定ソートすること

`input`:

1. developer: permissions instructions
2. developer: runtime developer note（任意）
3. user: AGENTS / project instructions
4. user: environment context
5. user: 現在の依頼

### 8.3 permissions instructions

例:

```text
<permissions_instructions>
sandbox_mode=workspace-write
approval_mode=on-request
writable_roots:
- /abs/path/to/workspace

Rules:
- Do not write outside writable_roots.
- Ask before destructive operations.
- Ask before network-related shell commands.
- Prefer reading before editing.
</permissions_instructions>
```

Codex も初期 input に permissions を表す developer message を追加します。

### 8.4 AGENTS.md 読み込み

Codex docs では、グローバルと project 配下の `AGENTS.md` / `AGENTS.override.md` を積み上げる構造が説明されています。本仕様では v1 として次を実装する。

* 読み込み対象:

  * `~/.agent/AGENTS.md`
  * `~/.agent/AGENTS.override.md`
  * repo root から current working directory までの各階層にある

    * `AGENTS.md`
    * `AGENTS.override.md`
* 優先順位:

  * global → repo root → 下位ディレクトリ
  * より近い階層の内容を後ろに置く
* サイズ上限:

  * 合計 32 KiB まで
* override がある場合でも、v1 では「完全に片方を無視」ではなく、単純に後勝ちの連結ルールとする
* fallback filename は v1 では未実装

### 8.5 environment context

例:

```text
<environment_context>
cwd=/abs/path/to/workspace
shell=/bin/bash
platform=linux
sandbox_mode=workspace-write
approval_mode=on-request
</environment_context>
```

Codex 公開記事でも、`cwd` と shell を user item として入れる構造が示されています。

### 8.6 turn 継続時の構成

新 turn では以下を `input` に保持する。

* 先頭の静的 instructions 相当部分
* 既存 conversation items
* 直前 assistant message
* 新 user message

Codex 記事では、後続 turn でも過去 items を積み増しし、前回 prompt の exact prefix を維持することが caching 上重要だと説明されています。したがって本仕様でも、**静的部分を前、変動部分を後ろ**に置く。

---

## 9. Tool 仕様

v1 では **最小限の custom tools** のみ実装する。

### 9.1 必須 tools

#### 1) `shell`

```json
{
  "type": "function",
  "name": "shell",
  "description": "Run a shell command in the workspace and return stdout, stderr, exit_code.",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "command": { "type": "array", "items": { "type": "string" } },
      "workdir": { "type": "string" },
      "timeout_ms": { "type": "integer" }
    },
    "required": ["command"]
  }
}
```

#### 2) `read_file`

```json
{
  "type": "function",
  "name": "read_file",
  "description": "Read a UTF-8 text file from the workspace.",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "start_line": { "type": "integer" },
      "end_line": { "type": "integer" }
    },
    "required": ["path"]
  }
}
```

#### 3) `write_file`

```json
{
  "type": "function",
  "name": "write_file",
  "description": "Write a UTF-8 text file within the workspace.",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "content": { "type": "string" },
      "mode": { "type": "string", "enum": ["overwrite", "append"] }
    },
    "required": ["path", "content"]
  }
}
```

#### 4) `update_plan`

```json
{
  "type": "function",
  "name": "update_plan",
  "description": "Update the current task plan shown to the user.",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "plan": {
        "type": "array",
        "items": { "type": "string" }
      },
      "explanation": { "type": "string" }
    },
    "required": ["plan"]
  }
}
```

Codex の公開記事でも `shell` と `update_plan` の例が示されています。本仕様はそれに学習用の `read_file` / `write_file` を足して、編集の安定性を上げます。

### 9.2 実装ルール

* tool 定義の順序は **名前順固定**
* tool 実行は **逐次**
* parallel tool calls は v1 ではサポートしない
* tool result は必ず `function_call_output` 相当の item として履歴に残す
* 大きすぎる出力は truncate し、先頭 + 末尾 + 行数情報を返す

---

## 10. Agent Loop 仕様

### 10.1 基本アルゴリズム

```python
while turn_count < max_turns:
    request = prompt_builder.build(...)
    response = model_client.create_response(request, stream=cfg.stream)

    renderer.show_stream(response.events)

    items = collect_output_items(response)

    if contains_tool_calls(items):
        for call in tool_calls_in_order(items):
            result = tool_dispatcher.execute(call)
            history.append(call_as_item)
            history.append(tool_result_as_item)
        maybe_compact()
        continue

    if contains_assistant_message(items):
        history.append(assistant_message_item)
        save_session()
        break
```

### 10.2 streaming

LM Studio docs は Responses endpoint で streaming を案内しており、OpenAI の Codex 記事でも SSE イベントを前提に loop を説明しています。したがって本仕様でも **streaming を既定**とします。

ただし実装上は安定性のため次を許容する。

* `stream=true` が既定
* backend 互換性問題があれば `--no-stream` で通常レスポンスに fallback
* streaming parser は最低限次のイベントを扱えばよい

  * text delta
  * output item done
  * response completed
  * error

### 10.3 終了条件

以下のどちらかで 1 turn を終了。

* assistant message が返ってきた
* `max_turns` に達した

`max_turns` 到達時は failure 扱いではなく、**途中経過を progress に残して停止**する。

---

## 11. Session / Memory 仕様

### 11.1 local stateless history

Codex の公開記事では、Codex は `previous_response_id` に依存せず stateless request を維持していると説明されています。本仕様もこれに合わせ、**会話状態はすべてローカルに保持**します。

### 11.2 保存場所

project root 配下に `.agent/` を作る。

```text
.agent/
  sessions/
    20260306-153000.jsonl
  latest_session.txt
  plan.json
  progress.md
  compact_summary.md
```

### 11.3 各ファイルの役割

#### `sessions/*.jsonl`

イベントログ。1 行 1 JSON。

例:

```json
{"ts":"...","kind":"request","data":{...}}
{"ts":"...","kind":"tool_call","data":{...}}
{"ts":"...","kind":"tool_result","data":{...}}
{"ts":"...","kind":"assistant","data":{...}}
```

#### `plan.json`

現在の plan を構造化保存。

```json
{
  "current_goal": "Fix failing tests in parser module",
  "steps": [
    {"text":"Run tests","status":"done"},
    {"text":"Inspect parser.py","status":"done"},
    {"text":"Patch edge case","status":"doing"},
    {"text":"Re-run tests","status":"todo"}
  ],
  "updated_at": "2026-03-06T15:30:00+09:00"
}
```

#### `progress.md`

人間向け working memory。

テンプレート:

```md
# Progress

## Goal
...

## What was done
...

## Current state
...

## Next likely action
...

## Risks / open questions
...
```

### 11.4 resume

`agent resume` は以下を行う。

* latest session id を読む
* compact summary があれば先に読む
* recent raw turns を復元
* AGENTS / environment context を再構築
* 新 turn を開始

---

## 12. Context 管理と compaction

### 12.1 背景

Codex 記事は、長い会話では context window 管理が重要で、Codex は compaction を使うと説明しています。OpenAI の Responses API 自体も compaction endpoint を持ちます。

### 12.2 v1 方針

v1 では proprietary / encrypted compaction を再現しない。代わりに **plain-text summary compaction** を実装する。

### 12.3 発火条件

* 推定 token 数 > `compact_trigger_tokens`

### 12.4 token 推定

厳密 tokenization は backend により異なるため、v1 では簡易推定でよい。

```text
estimated_tokens = len(text) / 4
```

または item ごとの文字数合計で見積もる。

### 12.5 compaction 手順

1. 古い履歴を対象に要約用 prompt を作る
2. 要約項目:

   * ユーザーの目的
   * 既に終わった作業
   * 変更したファイル
   * 重要な観測
   * 未解決点
   * 次に取るべきアクション
3. summary を `.agent/compact_summary.md` に保存
4. history を次の形に置換:

   * 静的 instructions
   * permissions item
   * AGENTS summary
   * environment context
   * compact summary item
   * 直近 `keep_last_turns_after_compact` turn の raw items

### 12.6 注意点

* compaction 後も assistant の約束事や安全ルールは落とさない
* summary は human-readable にする
* backend 互換性を優先し、 `/responses/compact` は使わない

---

## 13. Safety / Approval 仕様

### 13.1 前提

v1 は **OS レベル sandbox ではなく policy-level guard** とする。
つまり「完全隔離」ではなく「危険操作を弾く・確認する」方式。

### 13.2 mode 一覧

#### `read-only`

* `write_file` 禁止
* shell は allowlist の読み取り系コマンドのみ
* 例: `pwd`, `ls`, `find`, `cat`, `sed -n`, `grep`, `git status`

#### `workspace-write`

* 読み書きは `workspace_root` 配下のみ
* shell は許可するが、危険操作は approval 必須
* path traversal を防ぐ

#### `full-access`

* path 制限なし
* それでも明示的破壊操作は approval 推奨

### 13.3 approval mode

#### `never`

* 可能な限り自動実行
* ただし policy violation は拒否

#### `on-request`

* 危険コマンドのみ確認

#### `always`

* すべての書込み系 / shell 系を確認

### 13.4 approval 対象の例

* `rm`, `mv`, `chmod`, `chown`
* `git reset --hard`
* `git clean -fd`
* `curl`, `wget`, `ssh`, `scp`
* `sudo`
* workspace 外 path への書込み
* 1000 行を超える上書き
* バイナリファイルの直接上書き

### 13.5 path guard

すべての file tool は `resolve()` した絶対パスで検証し、`workspace_root` の配下かどうかを確認する。
symlink 経由の逸脱も拒否する。

---

## 14. Renderer / UX 仕様

### 14.1 表示内容

* セッション開始時

  * backend
  * model
  * cwd
  * sandbox / approval

* 実行中

  * plan 更新
  * tool 実行中の短い行
  * assistant text delta

* 終了時

  * summary
  * touched files
  * tests run
  * unresolved issues

### 14.2 表示しないもの

* 生の long reasoning
* 巨大 JSON 全文
* 巨大 stdout 全文

### 14.3 エラー表示

失敗時は以下をセットで表示。

* どの phase で失敗したか
* request failure / tool failure / policy rejection の別
* 復旧候補
* progress 保存先

---

## 15. 実装技術仕様

### 15.1 Python バージョン

* Python 3.11+

### 15.2 推奨依存

最小構成:

* `httpx`
* `rich`

標準ライブラリ中心:

* `argparse`
* `dataclasses`
* `typing`
* `pathlib`
* `subprocess`
* `json`
* `time`
* `os`
* `tomllib`

### 15.3 非推奨

* フレームワーク過多
* DB
* 非同期分散実行
* heavy GUI dependency

### 15.4 transport 実装

* 基本は `httpx.Client`
* streaming は SSE 行 parser を自前実装
* request / response raw dump は `--debug` 時のみ保存

---

## 16. データモデル

### 16.1 内部オブジェクト

```python
@dataclass
class AgentConfig:
    base_url: str
    model: str
    api_key: str | None
    stream: bool
    store: bool
    max_turns: int
    compact_trigger_tokens: int
    approval_mode: str
    sandbox_mode: str
    workspace_root: Path

@dataclass
class SessionState:
    session_id: str
    history_items: list[dict]
    plan: list[str]
    assistant_last_message: str | None
    compact_summary: str | None

@dataclass
class ToolResult:
    ok: bool
    output: str
    exit_code: int | None = None
    metadata: dict[str, Any] | None = None
```

### 16.2 Responses request 形

```json
{
  "model": "...",
  "instructions": "...",
  "tools": [...],
  "input": [...],
  "stream": true,
  "store": false
}
```

### 16.3 history item の扱い

内部では OpenAI Responses の item 形式に寄せる。

* `message`
* `function_call`
* `function_call_output`

これにより OpenAI / LM Studio の共通面に寄せられる。OpenAI docs でも Responses は `message`, `function_call`, `function_call_output` などの Items を基本単位としています。

---

## 17. AGENTS / project memory の扱い

### 17.1 AGENTS.md は必須機能

理由:

* Codex らしい instruction layering の中核
* 実装コストが低い
* project ごとの作法をモデルに安定供給できる

### 17.2 skills は v1 では未実装

Codex docs では skills は metadata だけ先に渡し、必要時に `SKILL.md` を読む progressive disclosure 方式です。これは強力ですが、今回は scope 外です。v1 では `skills/` を読まない。将来拡張ポイントだけ残す。

---

## 18. Git との関係

v1 では git を独立 tool にせず、shell 経由で扱う。
ただし UX 向上のため次は実装する。

* セッション開始時 `git status --short`
* 終了時 touched files をまとめる
* `resume` 時に直近差分の要約を見せる

`git commit` の自動実行は v1 では **デフォルト無効**。

---

## 19. テスト仕様

### 19.1 単体テスト

* config 読み込み
* path guard
* AGENTS loader
* token estimator
* plan store
* tool output truncation

### 19.2 結合テスト

#### ケース A: LM Studio backend

* `base_url=http://localhost:1234/v1`
* model を明示
* simple prompt で text response を取得

#### ケース B: OpenAI backend

* `base_url=https://api.openai.com/v1`
* `OPENAI_API_KEY`
* 同一コードで response を取得

LM Studio docs は OpenAI client を `base_url` 差し替えで再利用できると説明しているため、この 2 backend を同一抽象で通すことが本仕様の中核 acceptance criteria です。

#### ケース C: tool loop

* shell 呼び出し
* tool result を history に戻す
* 再推論する

#### ケース D: AGENTS layering

* root と subdir に AGENTS を置く
* subdir 起動時に両方読み込まれる

#### ケース E: workspace guard

* workspace 外への書込みを拒否

#### ケース F: compaction

* 長い history を作る
* summary に置換される
* 直近 turn は残る

### 19.3 手動 acceptance テスト

1. `agent doctor` が通る
2. LM Studio で `agent "README を要約して"` が動く
3. OpenAI に `--base-url https://api.openai.com/v1 --model ...` で切り替え可能
4. `AGENTS.md` の制約が実際の応答に反映される
5. `workspace-write` で workspace 外編集が防がれる
6. 長会話で compaction が発火する
7. `resume` で続きから再開できる

---

## 20. 実装マイルストーン

### M1: transport / config / simple text

* config loader
* `POST /responses`
* one-shot text generation
* CLI skeleton

### M2: item-based history

* message item 管理
* session save/load
* streaming renderer

### M3: tools

* shell
* read_file
* write_file
* update_plan
* function_call_output 往復

### M4: safety

* path guard
* approval mode
* sandbox mode

### M5: AGENTS / project memory

* AGENTS loader
* plan.json
* progress.md
* resume

### M6: compaction

* token estimator
* summary compaction
* recent turn retention

### M7: polish

* doctor
* touched file summary
* better error rendering

---

## 21. 実装完了の定義

以下を満たしたら v1 完了とする。

* OpenAI / LM Studio の両 backend で同じ CLI が動く
* backend 切替は `base_url` と `model` だけで行える
* CLI で multi-turn coding loop が動く
* tool call を受けて shell / file 操作を実行できる
* AGENTS.md を読める
* progress / plan / session がローカル保存される
* workspace-write 制約が機能する
* 長い会話で compaction できる
* GUI, IDE, DB, telemetry を含まない

---

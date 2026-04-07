# agent-cli テストドキュメント

## プロジェクト概要

**agent-cli** は、Python で実装されたミニマルな **CLI コーディングエージェント** です。OpenAI Codex スタイルのローカルコーディングアシスタントです。

### 主な特徴

- 🐍 **Python 製**：Python 3.11+ と `uv` パッケージマネージャを使用
- 💻 **CLI 限定**：コマンドラインから直接使用可能
- 🗄️ **軽量設計**：GUI、IDE、データベース、Telemetry を含まないシンプルな構造
- 📂 **ローカル保存**：プロンプト管理・進捗追跡・計画・セッション情報をローカルに保存

### 基本機能

```bash
# チャットモードで対話
uv run agent chat

# 一発で処理（例：要約）
uv run agent "README を要約して"

# ヘルスチェック
uv run agent doctor

# 設定初期化
uv run agent config init
```

### 概要

このプロジェクトは、**「シンプルなローカルコーディングエージェント」**として設計されています。複雑なインフラではなく、基本的なコード作成タスクを CLI から直接実行できることが目的です。

## Requirements

- Python 3.11+
- `uv`

## Setup

```bash
uv sync
```

## Initialize config

```bash
uv run agent config init
```

このコマンドは `~/.agent/config.toml` を作成します。

### 設定項目

少なくとも以下を設定する必要があります：

```toml
[model]
base_url = "http://localhost:1234/v1"
model = "openai/gpt-oss-20b"
api_key_env = "OPENAI_API_KEY"
stream = false
```

`stream` はデフォルトで `false` です。必要な場合は `--stream` フラグを明示的に使用します。

## Test

```bash
uv run python -m unittest discover -v
```

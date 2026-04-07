以下、指定資料を軸にしたレポート形式でまとめます。なお Anthropic の記事は Claude Code そのものの内部実装を全面公開した資料 ではなく、Claude Agent SDK を長時間安定稼働させるための harness 設計 を述べたものです。したがって本レポートでは、Codex 側は OpenAI の 2026年1月23日公開記事 + openai/codex リポジトリ、Anthropic 側は 2025年11月26日公開の long-running harness 記事 をもとに、「現状のフロンティア・コーディングエージェントはどう組まれているか」を読み解きます。 ￼

まず結論

一番大事なポイントは、フロンティア・コーディングエージェント = 高性能なモデルではない、ということです。実際には、モデルの外側にある harness（現場監督） がかなり重要で、そこが「どんなプロンプトを組むか」「どのツールをいつ使うか」「履歴が長くなったらどう圧縮するか」「どこまで権限を与えるか」「次のセッションに何を残すか」を管理しています。OpenAI の Codex 記事は主に 1セッション内で回る agent loop を、Anthropic 記事は主に 複数セッションをまたぐ long-running harness を詳しく説明しています。 ￼

私の読みでは、現状の最前線は次の一文で要約できます。「モデルの賢さを上げる競争」から、「モデルを外側の仕組みでどれだけ安定・安全・長距離対応にできるかの競争」へ移っている、ということです。Codex は prompt 構築・ツール実行・キャッシュ・compaction・sandbox/approval をかなり明示的に設計し、Anthropic は progress ファイル・feature list・git・end-to-end テストで“記憶と作業の継続性”を作っています。 ￼

1. 全体像

理解しやすく言い換えると、coding agent はこんな層でできています。これは 3資料をまとめた抽象図です。 ￼

```
[ユーザーの依頼]
      |
      v
[Harness / Agent Runtime]
  ├─ Prompt Builder        何をどの順でモデルに渡すか
  ├─ Tool Router           shell / web / MCP / test をどう呼ぶか
  ├─ Context Manager       履歴・要約・compaction・cache
  ├─ Memory Artifacts      AGENTS, skills, progress, feature list, git
  └─ Safety Layer          sandbox / approvals / network policy
      |
      v
    [モデル]
      |
      v
[考える] -> [道具を使う] -> [結果を見る] -> [再び考える] -> ... -> [最終応答]
                                   |
                                   v
                              [コード変更・commit・ログ]
```

ここで重要なのは、**agent の本体は“会話”ではなく“実行系”**だという点です。モデルは中心部品ですが、品質を決めるのはむしろ周辺です。データサイエンス寄りに例えるなら、モデルが推論器で、agent はその周囲の feature injection + executor + state store + guardrail を含むランタイムだ、と捉えるとしっくりきます。 ￼

2. Codex の具体的な構造

Codex CLI は OpenAI の ローカルで動くオープンソースの coding agent で、公式 docs では Rust 製 と明記されています。公開リポジトリは monorepo になっており、少なくとも表層から見える構成として codex-cli、codex-rs、docs、sdk/typescript、shell-tool-mcp、.codex/skills などのディレクトリを持っています。つまり Codex は「ただの CLI」ではなく、コア実装 + ツール接続 + SDK + スキル拡張 を抱えた実行基盤です。 ￼

2-1. Codex の心臓部は 1ターン内の loop

OpenAI の記事で最も重要なのはここです。Codex はユーザー入力を受けると、モデルに推論させ、最終返答を出すか、ツール呼び出しを要求するか を見ます。ツールが必要なら harness がそれを実行し、その観測結果を prompt に追記して、もう一度モデルを呼びます。これを、ツール呼び出しが止まって assistant message が出るまで反復します。 ￼

```
user request
   -> prompt を組む
   -> model inference
   -> function_call が出る
   -> shell / web / MCP を実行
   -> function_call_output を input に追加
   -> 再推論
   -> assistant message で終了
```

さらに具体的には、Codex は Responses API の SSE ストリーム を受け取り、response.output_text.delta のような UI 向けイベントはそのまま表示しつつ、response.output_item.added や response.output_item.done から得た reasoning / function_call / function_call_output を 次回の input に再投入する構造 を取っています。ここが「思考 → 行動 → 観測 → 再思考」を explicit に回す中核です。 ￼

2-2. Codex は prompt をかなり“構造的”に組み立てる

Codex の prompt は「ユーザーの文章をそのまま投げる」ものではありません。OpenAI 記事では、初期 prompt 生成時に instructions、tools、input を組み合わせ、しかも role の優先度を system > developer > user > assistant として扱うことが説明されています。 ￼

読みやすく並べ直すと、Codex の最初の入力はだいたい次のような形です。 ￼

```
[モデル固有 instructions]
[使える tools の定義]
[permissions instructions: sandbox / approval]
[developer_instructions（任意）]
[AGENTS.md 由来の project guidance]
[skills metadata / 必要に応じた skill instructions]
[environment_context: cwd, shell]
[今回の user request]
```

ここでかなり面白いのが、AGENTS.md と skills が prompt 構築の正式部品として入っていることです。Codex は起動時に instruction chain を作り、~/.codex の global guidance と、プロジェクト root から current working directory までの AGENTS.md / AGENTS.override.md を順に探索します。また skills は最初から全文を入れるのではなく、まず metadata だけを載せ、必要になったときだけ SKILL.md を読む progressive disclosure を使います。これは「長い説明書を毎回丸ごと入れない」ための、かなり実務的なコンテキスト節約術です。 ￼

2-3. Codex は“速さ”のために prompt の形まで設計している

Codex の設計で見落とされがちですが、本質的なのは prompt caching 前提の loop 設計 です。OpenAI は、ツール実行後の新しい prompt が 古い prompt の exact prefix になるように作っていると説明しています。これは cache hit を得るためで、途中で tools の順序や model や sandbox や current working directory を不用意に変えると cache miss になります。だから Codex は、設定変更が起きても「昔の prompt を書き換える」のではなく、「新しい message を後ろに足す」方向を好みます。 ￼

もう一つ重要なのが statelessness です。記事によると Codex は previous_response_id を使わず、会話を継続するときも必要な input を毎回送り直す設計を取っています。これは Zero Data Retention 構成と相性がよく、その代わり prompt は伸び続けるので、一定トークン数を超えると /responses/compact で compaction をかけます。この compact は encrypted_content を含む type=compaction item を返し、会話全体の理解を小さな形で次ターンに持ち越します。 ￼

2-4. Codex は安全装置と拡張機構を“製品として”持っている

Codex のもう一つの特徴は、安全性と拡張性が最初から一級市民なことです。CLI docs では approval mode と sandbox mode が明示されていて、Auto は workspace 内なら読み書きとコマンド実行を自動許可しつつ、workspace 外や network は確認を求めます。デフォルトの workspace-write sandbox は network をオフにしたまま使え、必要時だけ有効化できます。 ￼

同時に Codex は MCP を通じて third-party tools と context を追加できます。公式 docs では browser や Figma、developer docs などを例に挙げており、CLI と IDE extension で同じ MCP 設定を共有します。さらに current Codex docs には experimental な multi-agent もあり、default、worker、explorer、monitor などの role を持つ sub-agent を並列に走らせ、結果を統合できます。これは frontier が「1個の agent を賢くする」だけでなく、「どの仕事をどの agent に切るか」という段階へ進んでいることを示しています。 ￼

3. Anthropic が示す long-running harness の構造

Anthropic 記事の価値は、compaction だけでは長期案件は回らないとかなり率直に言っている点です。彼らの観察では、コンテキスト窓をまたぐ長時間タスクでは、agent は 1回で全部やろうとして途中で壊れたり、進捗を見て「もう終わった」と誤判定したり、テスト不十分のまま完了宣言したりしがちでした。つまり問題は「モデルが少し足りない」ではなく、セッションが切り替わるたびに作業継続性が失われることにあります。 ￼

そこで Anthropic は、long-running harness を 2段構成 にしています。最初の 1回だけ動く initializer agent が init.sh、claude-progress.txt、初期 git commit、feature requirements の JSON を作り、その後の coding agent は毎セッション「1機能ずつ前進し、最後に構造化された更新を残す」役割を持ちます。feature list は 200 個以上の end-to-end 機能記述を持てるようにし、初期状態では全部 passes: false にしておく。しかも Markdown ではなく JSON を使うのは、モデルが勝手に書き換えにくいからです。これはかなり実践的です。 ￼

Anthropic 版の全体像はこうです。 ￼

```
Session 0: Initializer Agent
  -> init.sh を作る
  -> claude-progress.txt を作る
  -> feature_list.json を作る
  -> initial git commit を切る

Session 1..N: Coding Agent
  -> pwd / git log / progress / feature list を読む
  -> 開発サーバを起動
  -> end-to-end テストを走らせる
  -> 1機能だけ実装する
  -> git commit + progress 更新を残す
```

特に重要なのは、“次の自分のためのファイル”を残すことです。毎回 fresh context で始まる新しい agent が、claude-progress.txt と git history を見れば、前の agent が何をして、どこで止まり、何が壊れているかをすぐ理解できる。Anthropic はこれを「人間の良いソフトウェアエンジニアの習慣」に学んだ、と説明しています。要するに long-running agent は、会話履歴よりも 作業痕跡の設計 が重要なのです。 ￼

さらに testing も重要で、Anthropic は unit test や curl だけでは不十分で、人間ユーザーのような end-to-end 検証 が必要だと述べています。実例では Puppeteer MCP を使い、毎セッション最初にアプリを立ち上げ、基本機能が壊れていないかを確認してから次の feature に着手させています。これは「新機能の前に、まず現在の世界を壊していないか確かめる」という運用思想です。 ￼

4. Codex と Anthropic を並べると、何が見えるか

私の整理では、両者は同じ問題を 違う時間スケール で解いています。Codex は主に 1ターン内の loop をどう速く・安全に・安定に回すか に強く、Anthropic 記事は 複数ターン・複数コンテキスト窓をまたいで、どう作業継続性を保つか に強いです。前者は Responses API items、prompt caching、compaction、sandbox、approval、AGENTS、skills、MCP をきれいに組み上げており、後者は init script、progress file、feature list、git、browser automation を“外部記憶”として使っています。 ￼

ここから導ける、かなり重要な設計原理が 3つあります。第一に、会話履歴だけを memory にしないこと。Codex は AGENTS/skills/compaction を使い、Anthropic は progress/gig/feature list/init.sh を使います。第二に、ツール出力を明示的な観測として loop に戻すこと。Codex の function_call_output はまさにそれです。第三に、安全性は後付けではなく runtime の一部であること。Codex の sandbox/approval はその好例です。 ￼

もう一つ面白い差があります。Anthropic は記事の最後で、single general-purpose coding agent と multi-agent architecture のどちらが本当に良いかは未解決だと書いています。一方、OpenAI の current Codex docs では、multi-agent はまだ experimental ではあるものの、すでに role ベースで並列運用できる形に入っています。つまり frontier は、「単体 agent を成立させる」段階から、「どこを分業すると得か」を探る段階に入りつつあります。 ￼

5. あなたが Python で Codex 風エージェントを再実装するなら、最初に再現すべき部品

ここからは、あなたの最終目標に寄せた実装観点の要約です。最初に真似るべきはモデルではなく、harness です。おすすめの最小構成は次の 7 部品です。これは上の資料を Python 向けに翻訳した設計図です。 ￼
	1.	Prompt Builder
role 付きで prompt を組む部品です。最低でも
model instructions / permissions / project guidance / environment context / user request
を順番どおりに作れるようにします。Codex の理解でいちばん大事な部品です。 ￼
	2.	Tool Runtime
最初は shell と file read/write だけで十分です。次に web、git、test runner、最後に MCP 的な拡張を足すとよいです。Codex も Anthropic も、結局は「モデルが外界を見る/触る」経路で性能を出しています。 ￼
	3.	State Store
会話履歴を「ただの文字列」ではなく、items の列として持つことを勧めます。reasoning、function_call、function_call_output、assistant message を JSON で保持すると、Codex 方式に近づきます。 ￼
	4.	Context Manager
長くなったら要約/compaction する仕組みです。最初は自前 summarization でも構いませんが、設計思想としては「履歴を小さな代表表現に落とす」ことが重要です。Codex の compaction はこの正式版です。 ￼
	5.	Project Memory Files
ここは Anthropic から借りると強いです。progress.md か progress.json、feature_list.json、init.sh に相当するものを置いて、毎回そこから始めるようにします。長距離性能がかなり上がります。 ￼
	6.	Safety Layer
read-only / workspace-write / full-access のような権限モードを分け、network や workspace 外編集は確認制にします。ここを早い段階で入れると、ローカル実行エージェントとしてかなり “Codex らしく” なります。 ￼
	7.	Optional Multi-Agent Layer
これは最後で十分です。まず single-agent を安定化し、その後に explorer、worker、monitor 的な役割分割を足すのが自然です。Anthropic もここは未解決だと言っており、Codex でも experimental 扱いです。 ￼

実装順としては、(1) prompt builder → (2) shell tool + approvals → (3) item-based state store → (4) compaction → (5) progress/feature artifacts → (6) test/browser automation → (7) multi-agent の順が堅いです。これなら「Codex を丸ごと真似する」のではなく、Codex の本質部品を Python で一つずつ再現する 形になります。これはたぶん、あなたの最終目標に一番近い進み方です。 ￼

まとめ

この3資料から見える現在像を、一文でまとめるとこうです。現状のフロンティア・コーディングエージェントは、LLM に shell をつないだものではなく、prompt 構築・ツール実行・コンテキスト圧縮・外部記憶・安全制御・ときに並列分業までを含む“ソフトウェア実行基盤”である、ということです。Codex はその loop を製品レベルで整え、Anthropic はその loop を長期案件で壊れないようにする harness を掘り下げています。 ￼

そして、あなたの目的が「Python でオリジナルの Codex 系エージェントを作る」ことなら、最初に学ぶべき本体は model API ではなく harness design です。幸い Codex は open-source / Apache-2.0 で、OpenAI 自身も設計判断の細部は repo の issues / PRs に残っていると書いています。なので、今後は“ブラックボックスを無理に逆張りで解剖する”より、公開 repo と記事から振る舞いを抽出して Python で再実装する ほうが、実務的で強い進め方になります。 ￼

次に進むなら、このレポートをそのまま Python のクラス設計図（AgentLoop / PromptBuilder / ToolExecutor / ContextManager / SafetyPolicy / ProjectMemory） に落とす段階が自然です。
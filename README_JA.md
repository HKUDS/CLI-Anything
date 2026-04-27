<h1 align="center"><img src="assets/icon.png" alt="" width="64" style="vertical-align: middle;">&nbsp; CLI-Anything: すべてのソフトウェアをエージェントネイティブに</h1>

<p align="center">
  <strong>今日のソフトウェアは人間👨‍💻のためのもの。明日のユーザーはエージェント🤖。<br>
CLI-Anything: AIエージェントと世界のソフトウェアの架け橋</strong><br>
</p>

**🌐 [CLI-Hub](https://hkuds.github.io/CLI-Anything/)**: コミュニティが構築した全CLIを **[CLI-Hub](https://hkuds.github.io/CLI-Anything/)** で探索、ワンコマンドでインストール。自分のCLIを追加したい？[PRを送信](https://github.com/HKUDS/CLI-Anything/blob/main/CONTRIBUTING.md) — Hubは即座に更新されます。

<p align="center">
  <a href="#-クイックスタート"><img src="https://img.shields.io/badge/Quick_Start-5_min-blue?style=for-the-badge" alt="クイックスタート"></a>
  <a href="#-デモンストレーション"><img src="https://img.shields.io/badge/Demos-12_Apps-green?style=for-the-badge" alt="デモ"></a>
  <a href="#-テスト結果"><img src="https://img.shields.io/badge/Tests-1%2C540_Passing-brightgreen?style=for-the-badge" alt="テスト"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="ライセンス"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/click-≥8.0-green" alt="Click">
  <img src="https://img.shields.io/badge/pytest-100%25_pass-brightgreen" alt="Pytest">
  <img src="https://img.shields.io/badge/coverage-unit_%2B_e2e-orange" alt="Coverage">
  <img src="https://img.shields.io/badge/output-JSON_%2B_Human-blueviolet" alt="Output">
  <a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
<a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
</p>

**ワンコマンド**: あらゆるソフトウェアをOpenClaw、nanobot、Cursor、Claude Codeなどのエージェント対応に。&nbsp;&nbsp;[**English**](README.md) | [**中文文档**](README_CN.md)

<p align="center">
  <img src="assets/cli-typing.gif" alt="CLI-Anything タイピングデモ" width="800">
</p>

<p align="center">
  <img src="assets/teaser.png" alt="CLI-Anything ティーザー" width="800">
</p>

---

## 🤔 なぜCLIなのか？

CLIは人間とAIエージェント両方にとって普遍的なインターフェースです：

• **構造化 & 組み合わせ可能** - テキストコマンドはLLMのフォーマットに適合し、複雑なワークフローのために連鎖可能

• **軽量 & 汎用的** - 最小限のオーバーヘッドで、依存関係なくすべてのシステムで動作

• **自己記述的** - --helpフラグがエージェントが発見できる自動ドキュメントを提供

• **実証済みの成功** - Claude Codeは毎日何千もの実際のワークフローをCLIを通じて実行

• **エージェントファースト設計** - 構造化されたJSON出力がパース処理の複雑さを排除

• **決定論的 & 信頼性** - 一貫した結果が予測可能なエージェントの動作を実現

## 🚀 クイックスタート

### 前提条件

- **Python 3.10+**
- 対象ソフトウェアがインストール済みであること（例：GIMP、Blender、LibreOffice、または独自のアプリケーション）
- サポートされているAIコーディングエージェント: [Claude Code](#-claude-code) | [OpenClaw](#-openclaw) | [OpenCode](#-opencode) | [Codex](#-codex) | [Qodercli](#-qodercli) | [GitHub Copilot CLI](#-github-copilot-cli) | [その他のプラットフォーム](#-その他のプラットフォーム近日公開)

### プラットフォームを選択

<details open>
<summary><h4 id="-claude-code">⚡ Claude Code</h4></summary>

**ステップ1: マーケットプレイスの追加**

CLI-AnythingはGitHub上でホストされるClaude Codeプラグインマーケットプレイスとして配布されています。

```bash
# CLI-Anythingマーケットプレイスを追加
/plugin marketplace add HKUDS/CLI-Anything
```

**ステップ2: プラグインのインストール**

```bash
# マーケットプレイスからcli-anythingプラグインをインストール
/plugin install cli-anything
```

これで完了です。プラグインがClaude Codeセッションで利用可能になります。

**ステップ3: ワンコマンドでCLIを構築**

```bash
# /cli-anything:cli-anything <ソフトウェアのパスまたはリポジトリ>
# GIMPの完全なCLIを生成（全7フェーズ）
/cli-anything:cli-anything ./gimp

# 注: Claude Codeが2.x未満の場合は、"/cli-anything"を代わりに使用してください。
```

これにより完全なパイプラインが実行されます：
1. 🔍 **分析** — ソースコードをスキャンし、GUIアクションをAPIにマッピング
2. 📐 **設計** — コマンドグループ、状態モデル、出力フォーマットを設計
3. 🔨 **実装** — REPL、JSON出力、アンドゥ/リドゥ機能を備えたClick CLIを構築
4. 📋 **テスト計画** — ユニットテスト + E2Eテスト計画のTEST.mdを作成
5. 🧪 **テスト作成** — 包括的なテストスイートを実装
6. 📝 **ドキュメント** — TEST.mdを結果で更新
7. 📦 **公開** — `setup.py`を作成し、PATHにインストール

**ステップ4（オプション）: CLIの改善と拡張**

初回ビルド後、CLIを反復的に改善してカバレッジを拡大し、不足している機能を追加できます：

```bash
# 広範な改善 — エージェントがすべての機能のギャップを分析
/cli-anything:refine ./gimp

# 集中的な改善 — 特定の機能領域をターゲット
/cli-anything:refine ./gimp "画像のバッチ処理とフィルタのCLIを追加したい"
```

refineコマンドは、ソフトウェアの全機能と現在のCLIカバレッジの間のギャップ分析を行い、特定されたギャップに対して新しいコマンド、テスト、ドキュメントを実装します。複数回実行してカバレッジを着実に拡大できます — 各実行はインクリメンタルで非破壊的です。

<details>
<summary><strong>代替方法: 手動インストール</strong></summary>

マーケットプレイスを使用しない場合：

```bash
# リポジトリをクローン
git clone https://github.com/HKUDS/CLI-Anything.git

# プラグインをClaude Codeのプラグインディレクトリにコピー
cp -r CLI-Anything/cli-anything-plugin ~/.claude/plugins/cli-anything

# プラグインをリロード
/reload-plugins
```

</details>

</details>

<details>
<summary><h4 id="-opencode">⚡ OpenCode（実験的）</h4></summary>

**ステップ1: コマンドのインストール**

CLI-Anythingのコマンド**と** `HARNESS.md` をOpenCodeのコマンドディレクトリにコピーします：

```bash
# リポジトリをクローン
git clone https://github.com/HKUDS/CLI-Anything.git

# グローバルインストール（すべてのプロジェクトで利用可能）
cp CLI-Anything/opencode-commands/*.md ~/.config/opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md ~/.config/opencode/commands/

# またはプロジェクトレベルのインストール
cp CLI-Anything/opencode-commands/*.md .opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md .opencode/commands/
```

> **注:** `HARNESS.md`はすべてのコマンドが参照する方法論の仕様書です。コマンドと同じディレクトリに配置する必要があります。

これにより5つのスラッシュコマンドが追加されます: `/cli-anything`、`/cli-anything-refine`、`/cli-anything-test`、`/cli-anything-validate`、`/cli-anything-list`。

**ステップ2: ワンコマンドでCLIを構築**

```bash
# GIMPの完全なCLIを生成（全7フェーズ）
/cli-anything ./gimp

# GitHubリポジトリからビルド
/cli-anything https://github.com/blender/blender
```

コマンドはサブタスクとして実行され、Claude Codeと同じ7フェーズの方法論に従います。

**ステップ3（オプション）: CLIの改善と拡張**

```bash
# 広範な改善 — エージェントがすべての機能のギャップを分析
/cli-anything-refine ./gimp

# 集中的な改善 — 特定の機能領域をターゲット
/cli-anything-refine ./gimp "バッチ処理とフィルタ"
```

</details>

<details>

<summary><h4 id="-qodercli">⚡ Qodercli <sup><code>コミュニティ</code></sup></h4></summary>

**ステップ1: プラグインの登録**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
bash CLI-Anything/qoder-plugin/setup-qodercli.sh
```

これにより`~/.qoder.json`にcli-anythingプラグインが登録されます。登録後、新しいQodercliセッションを開始してください。

**ステップ2: QodercliからCLI-Anythingを使用**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "バッチ処理とフィルタ"
/cli-anything:validate ./gimp
```
</details>

<details>

<summary><h4 id="-openclaw">⚡ OpenClaw</h4></summary>

**ステップ1: スキルのインストール**

CLI-Anything はネイティブな OpenClaw `SKILL.md` ファイルを提供しています。OpenClaw のスキルディレクトリにコピーしてください：

```bash
# リポジトリをクローン
git clone https://github.com/HKUDS/CLI-Anything.git

# グローバルスキルフォルダにインストール
mkdir -p ~/.openclaw/skills/cli-anything
cp CLI-Anything/openclaw-skill/SKILL.md ~/.openclaw/skills/cli-anything/SKILL.md
```

**ステップ2: CLIの構築**

インストール後、OpenClaw 内で以下のようにスキルを呼び出せます：

`@cli-anything build a CLI for ./gimp`

このスキルは Claude Code や OpenCode と同じ7段階の方法論に従っています。

</details>

<details>

<summary><h4 id="-codex">⚡ Codex <sup><code>実験的</code></sup> <sup><code>コミュニティ</code></sup></h4></summary>

**ステップ1: スキルのインストール**

同梱のインストーラーを実行します：

```bash
# リポジトリをクローン
git clone https://github.com/HKUDS/CLI-Anything.git

# スキルをインストール
bash CLI-Anything/codex-skill/scripts/install.sh
```

Windows PowerShellの場合：

```powershell
.\CLI-Anything\codex-skill\scripts\install.ps1
```

これにより`$CODEX_HOME/skills/cli-anything`（`CODEX_HOME`が未設定の場合は`~/.codex/skills/cli-anything`）にスキルがインストールされます。

インストール後、検出されるようにCodexを再起動してください。

**ステップ2: CodexからCLI-Anythingを使用**

自然言語でタスクを説明します。例：

```text
CLI-Anythingを使って./gimpのハーネスを構築して
CLI-Anythingを使って./shotcutのピクチャーインピクチャーワークフローを改善して
CLI-Anythingを使って./libreofficeを検証して
```

CodexスキルはClaude CodeプラグインおよびOpenCodeコマンドと同じ方法論を適用しつつ、生成されるPythonハーネスのフォーマットは変更されません。
</details>

<details>

<summary><h4 id="-github-copilot-cli">⚡ GitHub Copilot CLI <sup><code>コミュニティ</code></sup></h4></summary>

**ステップ1: プラグインのインストール**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything
copilot plugin install ./cli-anything-plugin
```

これにより、CLI-Anything プラグインが GitHub Copilot CLI にインストールされます。プラグインはすでに GitHub Copilot CLI セッションで利用できるはずです。

**ステップ2: GitHub Copilot CLIからCLI-Anythingを使用**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "バッチ処理とフィルタ"
/cli-anything:validate ./gimp
```

</details>

<details>
<summary><h4 id="-その他のプラットフォーム近日公開">🔮 その他のプラットフォーム（近日公開）</h4></summary>

CLI-Anythingはプラットフォーム非依存で設計されています。より多くのAIコーディングエージェントのサポートを予定しています：

- **Codex** — `codex-skill/` 内の同梱スキルで利用可能
- **Cursor** — 近日公開
- **Windsurf** — 近日公開
- **お好みのツール** — コントリビューション歓迎！リファレンス実装については`opencode-commands/`ディレクトリをご覧ください。

</details>

### 生成されたCLIの使用

どのプラットフォームでビルドしても、生成されたCLIは同じ方法で動作します：

```bash
# PATHにインストール
cd gimp/agent-harness && pip install -e .

# どこからでも使用可能
cli-anything-gimp --help
cli-anything-gimp project new --width 1920 --height 1080 -o poster.json
cli-anything-gimp --json layer add -n "Background" --type solid --color "#1a1a2e"

# インタラクティブREPLに入る
cli-anything-gimp
```

---

## 💡 CLI-Anythingのビジョン: エージェントネイティブソフトウェアの構築

• 🌐 **ユニバーサルアクセス** - すべてのソフトウェアが構造化されたCLIを通じて即座にエージェント制御可能に。

• 🔗 **シームレスな統合** - エージェントがAPI、GUI、再構築、複雑なラッパーなしにあらゆるアプリケーションを制御。

• 🚀 **未来志向のエコシステム** - ワンコマンドで人間向けに設計されたソフトウェアをエージェントネイティブツールに変換。

---

## 🔧 CLI-Anythingの活用シーン

| カテゴリ | エージェントネイティブにする方法 | 代表例 |
|----------|----------------------|----------|
| **📂 GitHubリポジトリ** | あらゆるオープンソースプロジェクトを自動CLI生成でエージェント制御可能なツールに変換 | VSCodium, WordPress, Calibre, Zotero, Joplin, Logseq, Penpot, Super Productivity |
| **🤖 AI/MLプラットフォーム** | 構造化されたコマンドでモデルの訓練、推論パイプライン、ハイパーパラメータチューニングを自動化 | Stable Diffusion WebUI, ComfyUI, InvokeAI, Text-generation-webui, Open WebUI, Fooocus, Kohya_ss, AnythingLLM, SillyTavern |
| **📊 データ & アナリティクス** | プログラマティックなデータ処理、可視化、統計分析ワークフローを実現 | JupyterLab, Apache Superset, Metabase, Redash, DBeaver, KNIME, Orange, OpenSearch Dashboards, Lightdash |
| **💻 開発ツール** | コマンドインターフェースでコード編集、ビルド、テスト、デプロイプロセスを効率化 | Jenkins, Gitea, Hoppscotch, Portainer, pgAdmin, SonarQube, ArgoCD, OpenLens, Insomnia, Beekeeper Studio |
| **🎨 クリエイティブ & メディア** | コンテンツ作成、編集、レンダリングワークフローをプログラムで制御 | Blender, GIMP, OBS Studio, Audacity, Krita, Kdenlive, Shotcut, Inkscape, Darktable, LMMS, Ardour |
| **🔬 科学計算** | 研究ワークフロー、シミュレーション、複雑な計算を自動化 | ImageJ, FreeCAD, QGIS, ParaView, Gephi, LibreCAD, Stellarium, KiCad, JASP, Jamovi |
| **🏢 エンタープライズ & オフィス** | ビジネスアプリケーションと生産性ツールをエージェントがアクセス可能なシステムに変換 | NextCloud, GitLab, Grafana, Mattermost, LibreOffice, AppFlowy, NocoDB, Odoo (Community), Plane, ERPNext |
| **📞 コミュニケーション & コラボレーション** | 構造化されたCLIで会議のスケジュール、参加者管理、録画取得、レポートを自動化 | Zoom, Jitsi Meet, BigBlueButton, Mattermost |
| **📐 ダイアグラム & ビジュアライゼーション** | ダイアグラム、フローチャート、アーキテクチャ図、ビジュアルドキュメントをプログラムで作成・操作 | Draw.io (diagrams.net), Mermaid, PlantUML, Excalidraw, yEd |
| **✨ AIコンテンツ生成** | AI搭載のクラウドAPIを通じてプロフェッショナルな成果物（スライド、ドキュメント、ダイアグラム、ウェブサイト、調査レポート）を生成 | [AnyGen](https://www.anygen.io), Gamma, Beautiful.ai, Tome |

---

## CLI-Anythingの主な特徴

### エージェントとソフトウェアのギャップ
AIエージェントは推論には優れていますが、実際のプロフェッショナルソフトウェアの操作は苦手です。現在のソリューションは脆弱なUI自動化、限定的なAPI、または機能の90%を失う簡素化された再実装です。

**CLI-Anythingの解決策**: あらゆるプロフェッショナルソフトウェアを機能を損なうことなくエージェントネイティブツールに変換。

| **現在の課題** | **CLI-Anythingの解決策** |
|----------|----------------------|
| 🤖 「AIは実際のツールを使えない」 | 実際のソフトウェアバックエンド（Blender、LibreOffice、FFmpeg）との直接統合 — フルプロフェッショナル機能、妥協ゼロ |
| 💸 「UI自動化はすぐ壊れる」 | スクリーンショットなし、クリックなし、RPA的な脆弱性なし。構造化インターフェースによる純粋なコマンドラインの信頼性 |
| 📊 「エージェントには構造化データが必要」 | シームレスなエージェント利用のための組み込みJSON出力 + デバッグ用の人間が読める形式 |
| 🔧 「カスタム統合はコストが高い」 | 1つのClaudeプラグインが実証済みの7フェーズパイプラインで任意のコードベースのCLIを自動生成 |
| ⚡ 「プロトタイプと本番のギャップ」 | 1,508以上のテストと実際のソフトウェアでの検証。11の主要アプリケーションで実戦検証済み |

---

## 🎯 CLI-Anythingで何ができる？

<table>
<tr>
<td width="33%">

### 🛠️ エージェントにワークフローを任せる

プロフェッショナルでも日常でも — コードベースを`/cli-anything`に渡すだけ。クリエイティブ作業にはGIMP、Blender、Shotcut。日常タスクにはLibreOffice、OBS Studio。ソースがない？オープンソースの代替を見つけてそれを渡しましょう。エージェントが使える完全なCLIが即座に手に入ります。

</td>
<td width="33%">

### 🔗 散在するAPIを1つのCLIに統合

断片化されたWebサービスAPIの管理にうんざりしていませんか？ドキュメントやSDKの原稿を`/cli-anything`に渡せば、エージェントが個々のエンドポイントを一貫したコマンドグループにまとめた**強力でステートフルなCLI**を手に入れます。数十のAPIコール代わりに1つのツール — トークンを節約しながらより強力な機能を。

</td>
<td width="33%">

### 🚀 GUIエージェントの置き換えまたは強化

CLI-Anythingは**GUIベースのエージェントアプローチを完全に置き換え**可能 — スクリーンショットも脆弱なピクセルクリックも不要。さらに面白いのは：ソフトウェアを`/cli-anything`すれば、コードとターミナルだけで**エージェントタスク、評価器、ベンチマークを合成**できます — 完全自動化、反復改善可能、圧倒的に効率的。

</td>
</tr>
</table>

---

## ✨ ⚙️ CLI-Anythingの仕組み

<table>
<tr>
<td width="50%">

### 🏗️ 完全自動化された7フェーズパイプライン
コードベース分析からPyPI公開まで — プラグインがアーキテクチャ設計、実装、テスト計画、テスト作成、ドキュメンテーションを完全に自動で処理します。

</td>
<td width="50%">

### 🎯 本物のソフトウェア統合
実際のレンダリングのための実アプリケーションへの直接呼び出し。LibreOfficeがPDFを生成し、Blenderが3Dシーンをレンダリングし、Audacityがsoxを通じてオーディオを処理します。**妥協ゼロ**、**おもちゃの実装ゼロ**。

</td>
</tr>
<tr>
<td width="50%">

### 🔁 スマートセッション管理
アンドゥ/リドゥ機能を備えた永続的なプロジェクト状態と、すべてのCLIで一貫したインタラクティブ体験を提供する統合REPLインターフェース（ReplSkin）。

</td>
<td width="50%">

### 📦 設定不要のインストール
シンプルな pip install -e . で cli-anything-<software> がPATHに直接追加されます。エージェントは標準的なwhichコマンドでツールを発見します。セットアップ不要、ラッパー不要。

</td>
</tr>
<tr>
<td width="50%">

### 🧪 プロダクショングレードのテスト
多層的な検証: 合成データによるユニットテスト、実際のファイルとソフトウェアによるエンドツーエンドテスト、さらにインストール済みコマンドのCLIサブプロセス検証。

</td>
<td width="50%">

### 🐍 クリーンなパッケージアーキテクチャ
すべてのCLIがcli_anything.*名前空間で整理 — 競合なし、pip installable、一貫した命名規則: cli-anything-gimp、cli-anything-blenderなど。

</td>
</tr>
</table>

---

## 🎬 デモンストレーション

### 🎯 汎用
CLI-Anythingはコードベースを持つあらゆるソフトウェアで動作します — ドメインの制限やアーキテクチャの制約はありません。

### 🏭 プロフェッショナルグレードのテスト
クリエイティブ、生産性、コミュニケーション、ダイアグラム、AIコンテンツ生成、GPUデバッグなど、以前はAIエージェントがアクセスできなかった12の多様で複雑なアプリケーションでテスト済み。

### 🎨 多様なドメインカバレッジ
クリエイティブワークフロー（画像編集、3Dモデリング、ベクターグラフィックス）からプロダクションツール（オーディオ、オフィス、ライブストリーミング、動画編集）まで。

### ✅ 完全なCLI生成
各アプリケーションに対して完全な本番対応のCLIインターフェースを生成 — デモではなく、全機能へのアクセスを保持した包括的なツールアクセス。

<table>
<tr>
<th align="center">ソフトウェア</th>
<th align="center">ドメイン</th>
<th align="center">CLIコマンド</th>
<th align="center">バックエンド</th>
<th align="center">テスト</th>
</tr>
<tr>
<td align="center"><strong>🎨 GIMP</strong></td>
<td>画像編集</td>
<td><code>cli-anything-gimp</code></td>
<td>Pillow + GEGL/Script-Fu</td>
<td align="center">✅ 107</td>
</tr>
<tr>
<td align="center"><strong>🧊 Blender</strong></td>
<td>3Dモデリング & レンダリング</td>
<td><code>cli-anything-blender</code></td>
<td>bpy (Pythonスクリプティング)</td>
<td align="center">✅ 208</td>
</tr>
<tr>
<td align="center"><strong>✏️ Inkscape</strong></td>
<td>ベクターグラフィックス</td>
<td><code>cli-anything-inkscape</code></td>
<td>直接SVG/XML操作</td>
<td align="center">✅ 202</td>
</tr>
<tr>
<td align="center"><strong>🎵 Audacity</strong></td>
<td>オーディオ制作</td>
<td><code>cli-anything-audacity</code></td>
<td>Python wave + sox</td>
<td align="center">✅ 161</td>
</tr>
<tr>
<td align="center"><strong>📄 LibreOffice</strong></td>
<td>オフィススイート (Writer, Calc, Impress)</td>
<td><code>cli-anything-libreoffice</code></td>
<td>ODF生成 + ヘッドレスLO</td>
<td align="center">✅ 158</td>
</tr>
<tr>
<td align="center"><strong>📚 <a href="calibre/agent-harness/">Calibre</a></strong></td>
<td>電子書籍ライブラリ管理</td>
<td><code>cli-anything-calibre</code></td>
<td>calibredb + ebook-meta + ebook-convert</td>
<td align="center">✅ <a href="calibre/agent-harness/">新規</a></td>
</tr>
<tr>
<td align="center"><strong>📹 OBS Studio</strong></td>
<td>ライブストリーミング & 録画</td>
<td><code>cli-anything-obs-studio</code></td>
<td>JSONシーン + obs-websocket</td>
<td align="center">✅ 153</td>
</tr>
<tr>
<td align="center"><strong>🎞️ Kdenlive</strong></td>
<td>動画編集</td>
<td><code>cli-anything-kdenlive</code></td>
<td>MLT XML + meltレンダラー</td>
<td align="center">✅ 155</td>
</tr>
<tr>
<td align="center"><strong>🎬 Shotcut</strong></td>
<td>動画編集</td>
<td><code>cli-anything-shotcut</code></td>
<td>直接MLT XML + melt</td>
<td align="center">✅ 154</td>
</tr>
<tr>
<td align="center"><strong>📞 Zoom</strong></td>
<td>ビデオ会議</td>
<td><code>cli-anything-zoom</code></td>
<td>Zoom REST API (OAuth2)</td>
<td align="center">✅ 22</td>
</tr>
<tr>
<td align="center"><strong>📐 Draw.io</strong></td>
<td>ダイアグラム</td>
<td><code>cli-anything-drawio</code></td>
<td>mxGraph XML + draw.io CLI</td>
<td align="center">✅ 138</td>
</tr>
<tr>
<td align="center"><strong>✨ AnyGen</strong></td>
<td>AIコンテンツ生成</td>
<td><code>cli-anything-anygen</code></td>
<td>AnyGen REST API (anygen.io)</td>
<td align="center">✅ 50</td>
</tr>
<tr>
<td align="center"><strong>🟩 <a href="nsight-graphics/agent-harness/">Nsight Graphics CLI</a></strong></td>
<td>GPUデバッグ & プロファイリング</td>
<td><code>cli-anything-nsight-graphics</code></td>
<td>公式 ngfx / ngfx-capture オーケストレーション + GPU Trace サマリー</td>
<td align="center">✅ 40</td>
</tr>
<tr>
<td align="center" colspan="4"><strong>合計</strong></td>
<td align="center"><strong>✅ 1,547</strong></td>
</tr>
</table>

> **全1,547テストで100%パス** — 1,108ユニットテスト + 439エンドツーエンドテスト。

---

## 📊 テスト結果

各CLIハーネスは本番環境の信頼性を確保するために厳格な多層テストを実施しています：

| レイヤー | テスト内容 | 例 |
|-------|---------------|---------|
| **ユニットテスト** | 合成データによるすべてのコア関数の分離テスト | `test_core.py` — プロジェクト作成、レイヤー操作、フィルタパラメータ |
| **E2Eテスト（ネイティブ）** | プロジェクトファイル生成パイプライン | 有効なODF ZIP構造、正しいMLT XML、SVGの整形式性 |
| **E2Eテスト（実バックエンド）** | 実際のソフトウェア呼び出し + 出力検証 | LibreOffice → `%PDF-`マジックバイトを持つPDF、Blender → レンダリングされたPNG |
| **CLIサブプロセステスト** | `subprocess.run`によるインストール済みコマンド | `cli-anything-gimp --json project new` → 有効なJSON出力 |

```
================================ テストサマリー ================================
gimp          107 passed  ✅   (64 unit + 43 e2e)
blender       208 passed  ✅   (150 unit + 58 e2e)
inkscape      202 passed  ✅   (148 unit + 54 e2e)
audacity      161 passed  ✅   (107 unit + 54 e2e)
libreoffice   158 passed  ✅   (89 unit + 69 e2e)
obs-studio    153 passed  ✅   (116 unit + 37 e2e)
kdenlive      155 passed  ✅   (111 unit + 44 e2e)
shotcut       154 passed  ✅   (110 unit + 44 e2e)
zoom           22 passed  ✅   (22 unit + 0 e2e)
drawio        138 passed  ✅   (116 unit + 22 e2e)
anygen         50 passed  ✅   (40 unit + 10 e2e)
nsight-graphics 40 passed ✅   (36 unit + 4 e2e)
──────────────────────────────────────────────────────────────────────────────
合計         1,547 passed  ✅   100% パス率
```

---

## 🏗️ CLI-Anythingのアーキテクチャ

<p align="center">
  <img src="assets/architecture.png" alt="CLI-Anything アーキテクチャ" width="750">
</p>

### 🎯 コア設計原則

1. **本物のソフトウェア統合** — CLIは有効なプロジェクトファイル（ODF、MLT XML、SVG）を生成し、レンダリングを実際のアプリケーションに委譲します。**ソフトウェアの代替ではなく、ソフトウェアへの構造化インターフェースを構築します**。

2. **柔軟なインタラクションモデル** — すべてのCLIがデュアルモードで動作: インタラクティブなエージェントセッション用のステートフルREPL + スクリプティング/パイプライン用のサブコマンドインターフェース。**素のコマンドを実行 → REPLモードに入る**。

3. **一貫したユーザー体験** — すべての生成CLIがブランドバナー、スタイル付きプロンプト、コマンド履歴、進捗表示、標準化されたフォーマットを持つ統合REPLインターフェース（repl_skin.py）を共有。

4. **エージェントネイティブ設計** — すべてのコマンドに組み込みの--jsonフラグがマシン向けの構造化データを提供し、人間が読めるテーブルがインタラクティブ用途に対応。**エージェントは標準の--helpとwhichコマンドで機能を発見**。

5. **妥協なしの依存関係** — 実際のソフトウェアは必須要件です — フォールバックなし、グレースフルデグラデーションなし。**バックエンドが見つからない場合、テストはスキップではなく失敗し、本物の機能を保証します**。

---

## 📂 プロジェクト構造

```
cli-anything/
├── 📄 README.md                          # 英語版README
├── 📁 assets/                            # 画像とメディア
│   ├── icon.png                          # プロジェクトアイコン
│   └── teaser.png                        # ティーザー画像
│
├── 🔌 cli-anything-plugin/               # Claude Codeプラグイン
│   ├── HARNESS.md                        # 方法論SOP（信頼できる唯一の情報源）
│   ├── README.md                         # プラグインドキュメント
│   ├── QUICKSTART.md                     # 5分で始めるガイド
│   ├── PUBLISHING.md                     # 配布ガイド
│   ├── repl_skin.py                      # 統合REPLインターフェース
│   ├── commands/                         # プラグインコマンド定義
│   │   ├── cli-anything.md               # メインビルドコマンド
│   │   ├── refine.md                     # 既存ハーネスカバレッジの拡張
│   │   ├── test.md                       # テストランナー
│   │   └── validate.md                   # 標準検証
│   └── scripts/
│       └── setup-cli-anything.sh         # セットアップスクリプト
│
├── 🤖 codex-skill/                      # Codexスキルエントリーポイント
├── 🎨 gimp/agent-harness/               # GIMP CLI (107テスト)
├── 🧊 blender/agent-harness/            # Blender CLI (208テスト)
├── ✏️ inkscape/agent-harness/            # Inkscape CLI (202テスト)
├── 🎵 audacity/agent-harness/           # Audacity CLI (161テスト)
├── 📄 libreoffice/agent-harness/        # LibreOffice CLI (158テスト)
├── 📚 calibre/agent-harness/            # Calibre CLI（新規、電子書籍ワークフロー）
├── 📹 obs-studio/agent-harness/         # OBS Studio CLI (153テスト)
├── 🎞️ kdenlive/agent-harness/           # Kdenlive CLI (155テスト)
├── 🎬 shotcut/agent-harness/            # Shotcut CLI (154テスト)
├── 📞 zoom/agent-harness/               # Zoom CLI (22テスト)
├── 📐 drawio/agent-harness/             # Draw.io CLI (138テスト)
├── ✨ anygen/agent-harness/             # AnyGen CLI (50テスト)
└── 🟩 nsight-graphics/agent-harness/    # Nsight Graphics CLI (40テスト)
```

各`agent-harness/`にはClick CLI、コアモジュール、ユーティリティ（`repl_skin.py`とバックエンドラッパーを含む）、包括的なテストを備えた`cli_anything.<software>/`配下のインストール可能なPythonパッケージが含まれています。

---

## 🎯 プラグインコマンド

| コマンド | 説明 |
|---------|-------------|
| `/cli-anything <ソフトウェアパスまたはリポジトリ>` | 完全なCLIハーネスを構築 — 全7フェーズ |
| `/cli-anything:refine <ソフトウェアパス> [フォーカス]` | 既存のハーネスを改善 — ギャップ分析でカバレッジを拡大 |
| `/cli-anything:test <ソフトウェアパスまたはリポジトリ>` | テストを実行しTEST.mdを結果で更新 |
| `/cli-anything:validate <ソフトウェアパスまたはリポジトリ>` | HARNESS.md標準に対して検証 |

### 使用例

```bash
# ローカルソースからGIMPの完全なCLIを構築
/cli-anything /home/user/gimp

# GitHubリポジトリからビルド
/cli-anything https://github.com/blender/blender

# 既存のハーネスを改善 — 広範なギャップ分析
/cli-anything:refine /home/user/gimp

# 特定のフォーカスエリアで改善
/cli-anything:refine /home/user/shotcut "ビデオインビデオとピクチャーインピクチャーの合成"

# テストを実行しTEST.mdを更新
/cli-anything:test /home/user/inkscape

# HARNESS.md標準に対して検証
/cli-anything:validate /home/user/audacity
```

---

## 🎮 デモ: 生成されたCLIの使用

`cli-anything-libreoffice`でエージェントができることの例：

```bash
# 新しいWriterドキュメントを作成
$ cli-anything-libreoffice document new -o report.json --type writer
✓ Writerドキュメントを作成: report.json

# コンテンツを追加
$ cli-anything-libreoffice --project report.json writer add-heading -t "Q1レポート" --level 1
✓ 見出しを追加: "Q1レポート"

$ cli-anything-libreoffice --project report.json writer add-table --rows 4 --cols 3
✓ 4×3テーブルを追加

# LibreOfficeヘッドレスで実際のPDFにエクスポート
$ cli-anything-libreoffice --project report.json export render output.pdf -p pdf --overwrite
✓ エクスポート完了: output.pdf (42,831 bytes) via libreoffice-headless

# エージェント用のJSONモード
$ cli-anything-libreoffice --json document info --project report.json
{
  "name": "Q1 Report",
  "type": "writer",
  "pages": 1,
  "elements": 2,
  "modified": true
}
```

### REPLモード

```
$ cli-anything-blender
╔══════════════════════════════════════════╗
║       cli-anything-blender v1.0.0       ║
║     Blender CLI for AI Agents           ║
╚══════════════════════════════════════════╝

blender> scene new --name ProductShot
✓ シーンを作成: ProductShot

blender[ProductShot]> object add-mesh --type cube --location 0 0 1
✓ メッシュを追加: Cube at (0, 0, 1)

blender[ProductShot]*> render execute --output render.png --engine CYCLES
✓ レンダリング完了: render.png (1920×1080, 2.3 MB) via blender --background

blender[ProductShot]> exit
Goodbye! 👋
```

---

## 📖 標準プレイブック: HARNESS.md

HARNESS.mdは、自動CLI生成によってあらゆるソフトウェアをエージェントアクセス可能にするための決定版SOPです。

自動生成プロセスを通じて洗練された実証済みのパターンと方法論をエンコードしています。

このプレイブックは、11の多様な本番対応ハーネスの構築から得られた主要な知見を集約しています。

### 重要な教訓

| 教訓 | 説明 |
|--------|-------------|
| **実際のソフトウェアを使用する** | CLIはレンダリングのために実際のアプリケーションを呼び出す必要があります。GIMPの代わりにPillowを使ったり、Blenderのカスタムレンダラーを作ったりしないこと。有効なプロジェクトファイルを生成 → 実際のバックエンドを呼び出す。 |
| **レンダリングギャップ** | GUIアプリはレンダリング時にエフェクトを適用します。CLIがプロジェクトファイルを操作していても素朴なエクスポートツールを使うと、エフェクトが暗黙的にドロップされます。解決策: ネイティブレンダラー → フィルタ変換 → レンダースクリプト。 |
| **フィルタ変換** | フォーマット間でエフェクトをマッピング（MLT → ffmpeg）する際、重複フィルタのマージ、インターリーブされたストリーム順序、パラメータ空間の違い、マッピング不可能なエフェクトに注意。 |
| **タイムコード精度** | 非整数フレームレート（29.97fps）は累積的な丸め誤差を引き起こします。`int()`ではなく`round()`を使用し、表示には整数演算を使い、テストでは±1フレームの許容差を持たせること。 |
| **出力検証** | 終了コード0だからといってエクスポートが成功したと信頼しないこと。検証: マジックバイト、ZIP/OOXML構造、ピクセル分析、オーディオRMSレベル、長さチェック。 |

> 完全な方法論はこちら: [`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md)

---

## 📦 インストール & 使用方法

### プラグインユーザー向け（Claude Code）

```bash
# マーケットプレイスの追加とインストール（推奨）
/plugin marketplace add HKUDS/CLI-Anything
/plugin install cli-anything

# 任意のコードベースを持つソフトウェアのCLIを構築
/cli-anything <ソフトウェア名>
```

### 生成されたCLI向け

```bash
# 生成されたCLIをインストール
cd <software>/agent-harness
pip install -e .

# 確認
which cli-anything-<software>

# 使用
cli-anything-<software> --help
cli-anything-<software>                    # REPLに入る
cli-anything-<software> --json <command>   # エージェント用JSON出力
```

### テストの実行

```bash
# 特定のCLIのテストを実行
cd <software>/agent-harness
python3 -m pytest cli_anything/<software>/tests/ -v

# force-installedモード（検証に推奨）
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s
```

---

## 🤝 コントリビューション

コントリビューションを歓迎します！CLI-Anythingは拡張可能に設計されています：

- **新しいソフトウェアターゲット** — プラグインを使用して任意のコードベースのCLIを生成し、[`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md)を通じてハーネスを提出してください。
- **方法論の改善** — 新しい教訓をエンコードした`HARNESS.md`へのPR
- **プラグインの強化** — 新しいコマンド、フェーズの改善、より良い検証
- **テストカバレッジ** — より多くのE2Eシナリオ、エッジケース、ワークフローテスト

### 制限事項

- **強力な基盤モデルが必要** — CLI-Anythingは信頼性のあるハーネス生成のためにフロンティアクラスのモデル（例：Claude Opus 4.6、Claude Sonnet 4.6、GPT-5.4）に依存しています。弱いまたは小さいモデルでは、大幅な手動修正が必要な不完全または不正確なCLIが生成される可能性があります。
- **利用可能なソースコードに依存** — 7フェーズパイプラインはソースコードから分析・生成します。対象ソフトウェアがデコンパイルが必要なコンパイル済みバイナリのみを提供する場合、ハーネスの品質とカバレッジは大幅に低下します。
- **反復的な改善が必要な場合がある** — 1回の`/cli-anything`実行ですべての機能を完全にカバーできないことがあります。CLIのパフォーマンスとカバレッジを本番品質にするためには、`/refine`を1回以上実行することがしばしば必要です。

### ロードマップ

- [ ] より多くのアプリケーションカテゴリのサポート（CAD、DAW、IDE、EDA、科学ツール）
- [ ] エージェントタスク完了率のベンチマークスイート
- [ ] 社内/カスタムソフトウェア向けコミュニティ提供CLIハーネス
- [ ] Claude Code以外の追加エージェントフレームワークとの統合
- [ ] クローズドソースソフトウェアとWebサービスのAPIをCLIにパッケージ化するサポート
- [ ] エージェントスキルの発見とオーケストレーション用のSKILL.mdをCLIと共に生成

---

## 📖 ドキュメント

| ドキュメント | 説明 |
|----------|-------------|
| [`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md) | 方法論SOP — 信頼できる唯一の情報源 |
| [`cli-anything-plugin/README.md`](cli-anything-plugin/README.md) | プラグインドキュメント — コマンド、オプション、フェーズ |
| [`cli-anything-plugin/QUICKSTART.md`](cli-anything-plugin/QUICKSTART.md) | 5分で始めるガイド |
| [`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md) | 配布・公開ガイド |

各生成ハーネスにも以下が含まれます：
- `<SOFTWARE>.md` — そのアプリケーション固有のアーキテクチャSOP
- `tests/TEST.md` — テスト計画と結果のドキュメント

---

## ⭐ スター履歴

CLI-Anythingがあなたのソフトウェアをエージェントネイティブにするのに役立ったら、スターをお願いします！ ⭐

<div align="center">
  <a href="https://star-history.com/#HKUDS/CLI-Anything&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
      <img alt="スター履歴チャート" src="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
    </picture>
  </a>
</div>

---

## 📄 ライセンス

MITライセンス — 自由に使用、変更、配布できます。

---

<div align="center">

**CLI-Anything** — *コードベースを持つあらゆるソフトウェアをエージェントネイティブに。*

<sub>AIエージェント時代のための方法論 | 11のプロフェッショナルソフトウェアデモ | 1,508のパステスト</sub>

<br>

<img src="assets/icon.png" alt="CLI-Anything アイコン" width="80">

</div>

<p align="center">
  <em> CLI-Anythingをご覧いただきありがとうございます ✨</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.CLI-Anything&style=for-the-badge&color=00d4ff" alt="Views">
</p>

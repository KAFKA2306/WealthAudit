# Private financial master migration

`master/accounts.csv` と `master/payment_methods.csv` は個人の金融サービス構成を含み得るため、公開リポジトリでは追跡しません。公開treeには schema/example 用の `*.example.csv` だけを置きます。

## merge 前に必要な作業

既存の実データを使っているcloneでは、PRを取り込む前に次の2ファイルをGit管理外の安全な場所へ退避してください。

- `master/accounts.csv`
- `master/payment_methods.csv`

PR取り込み後、必要な実ファイルを同じpathへローカル復元できます。両pathは `.gitignore` 対象なので、以後は通常の `git add` で公開treeへ再追加されません。

公開exampleは実金融機関・カード構成を表さないsyntheticデータです。実ファイルをexampleで上書きしないでください。

## Git history

重要: current treeから削除済みでも、`master/accounts.csv` と `master/payment_methods.csv` は過去commitを含む公開履歴から参照可能です。current treeの削除を履歴削除とは扱いません。

2026-08-11時点でGitHub APIを用いて `master/accounts.csv` の履歴を再監査し、少なくとも `15a244f4ad317474177be89422a58bc80307c3b6`、`c8c1bd7785c0755c517a84f417f13c1aa6cf91b2`、`3e08c37f91531c6907e3d4506f2eab9fcf9c9ecb`、`8bee11d9fcdb3bd56be8b2f1f9901ba36e69aaac` が同pathの履歴として公開されていることを確認しています。これは口座番号・認証情報の存在を意味する記述ではなく、当該pathの履歴露出を示す監査証跡です。

### 方針

- 履歴書換えを未実施の状態を明示し、削除済みと誤認しない。
- `tests/test_public_history_financial_metadata.py` で、private masterがcurrent treeへ復活していないことと、履歴露出がある場合にこのpolicyが存在することをCI監査する。
- 認証情報、口座番号、API key/token等が履歴に含まれることが確認された場合は、履歴書換えより先に当該credentialを失効・ローテーションする。
- Git履歴そのものを除去する場合は、mainだけでなく全branch/tag、fork、既存cloneへの影響を列挙し、force-pushを伴う独立した破壊的migrationとして実施する。通常のPR mergeでは履歴削除を完了扱いにしない。

このPRでは履歴書換えを未実施です。したがって公開履歴から参照可能なmetadataの除去は未完了であり、Issue #3をこの条件だけでcloseしません。

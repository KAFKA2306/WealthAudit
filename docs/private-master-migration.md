# Private financial master migration

`master/accounts.csv` と `master/payment_methods.csv` は個人の金融サービス構成を含み得るため、公開リポジトリでは追跡しません。公開treeには schema/example 用の `*.example.csv` だけを置きます。

## merge 前に必要な作業

既存の実データを使っているcloneでは、PRを取り込む前に次の2ファイルをGit管理外の安全な場所へ退避してください。

- `master/accounts.csv`
- `master/payment_methods.csv`

PR取り込み後、必要な実ファイルを同じpathへローカル復元できます。両pathは `.gitignore` 対象なので、以後は通常の `git add` で公開treeへ再追加されません。

公開exampleは実金融機関・カード構成を表さないsyntheticデータです。実ファイルをexampleで上書きしないでください。

## Git history

current treeからファイルを削除しても過去commitからは参照できます。履歴書換えはbranch/PR/fork/cloneへ影響するため、このPRでは実施しません。履歴からの除去が必要かは、影響するrefとcloneを列挙してから別途判断します。

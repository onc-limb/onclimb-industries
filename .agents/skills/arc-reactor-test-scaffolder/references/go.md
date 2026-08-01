# Go デフォルト流儀（既存テストが無い場合に使う）

デフォルト FW: **標準 `testing` パッケージ + table-driven tests**。
`go.mod` に `stretchr/testify` があれば `assert`/`require` を使ってよい（既存に合わせる）。

## 配置・命名

- 配置: **実装ファイルと同一パッケージに併置**。例: `user/service.go` → `user/service_test.go`
- パッケージ名: 同一パッケージ `package user`（公開 API のみ検証する方針の既存テストが
  `package user_test` なら external test に従う）
- テスト関数名: `TestXxx`（対象シンボル名を含める）。サブテスト名は `snake_case` か文で。

## スタイル: table-driven + subtests

```go
func TestGetUser(t *testing.T) {
	tests := []struct {
		name    string
		id      string
		want    User
		wantErr error
	}{
		{name: "valid id returns user", id: "u1", want: User{ID: "u1"}},
		{name: "empty id returns validation error", id: "", wantErr: ErrValidation},
		{name: "unknown id returns not found", id: "nope", wantErr: ErrNotFound},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			svc := NewUserService(newFakeRepo())
			got, err := svc.GetUser(tt.id)
			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("GetUser(%q) error = %v, want %v", tt.id, err, tt.wantErr)
			}
			if err == nil && got.ID != tt.want.ID {
				t.Errorf("GetUser(%q) = %+v, want %+v", tt.id, got, tt.want)
			}
		})
	}
}
```

- 正常系・境界値・異常系は table の行として表現する（テスト関数を分けない）。
- エラー検証: `errors.Is` / `errors.As`。エラー文字列の比較はしない。
- フェイク: インタフェースを満たす小さな fake struct を test ファイル内に定義する
  （モックライブラリは既存で使われている場合のみ）。
- 並列化: 既存テストが `t.Parallel()` を使っていれば合わせる。無ければ付けない。
- 未確定ケース: `t.Skip("expected value TBD")`。

## 実行

```bash
go test -run TestGetUser ./user/...   # 対象テストのみ
go vet ./user/...                     # 併せて静的チェック
```

FW 検出の手がかり: `*_test.go` の import（`testify` の有無）、`t.Run` + table の有無。

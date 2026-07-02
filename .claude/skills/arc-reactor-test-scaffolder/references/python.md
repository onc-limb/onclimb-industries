# Python デフォルト流儀（既存テストが無い場合に使う）

デフォルト FW: **pytest**（unittest スタイルの既存テストがあるプロジェクトではそちらに従う）。

## 配置・命名

- 配置: リポジトリ直下 `tests/` に、`src/`（またはパッケージ）のディレクトリ構造をミラーする。
  例: `src/service/user.py` → `tests/service/test_user.py`
- ファイル名: `test_<module>.py`
- テスト関数名: `test_<対象>_<条件>_<期待>` 形式のスネークケース。
  例: `test_get_user_with_empty_id_raises_validation_error`
- クラスでまとめる場合: `class TestUserService:`（`__init__` を持たない）

## スタイル

- アサーション: 素の `assert`（pytest の introspection に任せる）。例外は `pytest.raises`。

```python
def test_get_user_returns_user():
    # Arrange
    service = UserService(repo=FakeUserRepo())
    # Act
    user = service.get_user("u1")
    # Assert
    assert user.id == "u1"


def test_get_user_with_unknown_id_raises_not_found():
    service = UserService(repo=FakeUserRepo())
    with pytest.raises(NotFoundError):
        service.get_user("nope")
```

- 構造: AAA（Arrange / Act / Assert）。1 テスト 1 アサーション主題。
- パラメタライズ: `@pytest.mark.parametrize("value,expected", [...])` を境界値テストに使う。
- fixture: 共有 setup は `@pytest.fixture`（複数ファイルで使うなら `conftest.py`）。
- モック: 標準は `unittest.mock`（`mocker` fixture がある = pytest-mock 導入済みならそちら）。
  外部 I/O 境界のみモックし、自作ロジックはモックしない。
- 未確定ケース: `@pytest.mark.skip(reason="expected value TBD")`

## 実行

```bash
pytest tests/service/test_user.py -v          # 生成ファイルのみ
pytest tests/service/test_user.py::test_get_user_returns_user  # 1 ケースのみ
```

FW 検出の手がかり: `pyproject.toml` の `[tool.pytest.ini_options]` / `pytest.ini` /
`setup.cfg` / `tox.ini`、依存の `pytest`。`unittest.TestCase` 継承の既存テストが多数派なら unittest 流儀。

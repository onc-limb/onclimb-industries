# Java デフォルト流儀（既存テストが無い場合に使う）

デフォルト FW: **JUnit 5 (Jupiter)** + AssertJ（依存にあれば）。
`pom.xml` / `build.gradle(.kts)` の `junit-jupiter` / `junit`(4.x) / `assertj` / `mockito` を確認する。
JUnit 4 の既存テスト（`org.junit.Test` import）が多数派ならそちらに従う。

## 配置・命名

- 配置: Maven/Gradle 標準レイアウト。実装と同じパッケージで `src/test/java` 配下にミラーする。
  例: `src/main/java/com/example/user/UserService.java`
  → `src/test/java/com/example/user/UserServiceTest.java`
- クラス名: `<対象クラス>Test`
- メソッド名: `@DisplayName` で振る舞いを文で書き、メソッド名は
  `methodName_condition_expected` 形式（既存の命名慣習があればそちら優先）。

## スタイル

```java
class UserServiceTest {

    private UserService service;

    @BeforeEach
    void setUp() {
        service = new UserService(new FakeUserRepository());
    }

    @Test
    @DisplayName("valid id returns the user")
    void getUser_validId_returnsUser() {
        User user = service.getUser("u1");
        assertThat(user.getId()).isEqualTo("u1");   // AssertJ
    }

    @Test
    @DisplayName("unknown id throws NotFoundException")
    void getUser_unknownId_throws() {
        assertThatThrownBy(() -> service.getUser("nope"))
            .isInstanceOf(NotFoundException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " "})
    void getUser_blankId_throwsValidation(String id) {
        assertThatThrownBy(() -> service.getUser(id))
            .isInstanceOf(ValidationException.class);
    }
}
```

- アサーション: AssertJ (`assertThat`) 優先。無ければ JUnit 5 の `Assertions.assertEquals` /
  `assertThrows`。
- パラメタライズ: `@ParameterizedTest` + `@ValueSource` / `@CsvSource` / `@MethodSource`。
- モック: Mockito（`@ExtendWith(MockitoExtension.class)` + `@Mock`）。依存にある場合のみ。
  無ければ手書きの Fake クラスを使う。
- 未確定ケース: `@Disabled("expected value TBD")`。

## 実行

```bash
mvn -Dtest=UserServiceTest test                      # Maven
./gradlew test --tests "com.example.user.UserServiceTest"  # Gradle
```

FW 検出の手がかり: ビルドファイルの依存宣言、既存テストの import
（`org.junit.jupiter` = JUnit 5 / `org.junit.Test` = JUnit 4）、Spring 系なら
`@SpringBootTest` の使用範囲（単体では使わずスライステストか素の JUnit に留める）。

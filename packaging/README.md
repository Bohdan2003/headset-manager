# Сборка программы Arena

## Mac

```bash
cd server && uv run python ../packaging/build.py
```

Результат: `dist/Arena.app`. Нужны uv, Node.js, JDK 17 (`JAVA_HOME`), Android SDK и adb.
Сборка обновляет `packaging/prebuilt/agent.apk`.

Программа не подписана сертификатом Apple: на другом Mac первый запуск — правый клик → Open.

## Windows

Экзешник собирается только на Windows. Нужны uv и Node.js, Android SDK не нужен.

1. Скопировать проект вместе с `packaging/prebuilt/` (там готовый агент, собранный на Mac).
2. Выполнить:

   ```bat
   cd server
   uv run python ..\packaging\build.py
   ```

Результат: папка `dist\Arena` с `Arena.exe`. Переносить надо всю папку. Скрипт сам скачает adb для Windows.

Для USB-подключения шлема на Windows может понадобиться драйвер Oculus ADB Driver.
Брандмауэр Windows при первом запуске спросит разрешение на входящие подключения: без него шлемы не подключатся.

Агента на Windows не пересобираем: он должен быть подписан тем же ключом, что и на Mac.

## GitHub Actions

Проверки при каждом пуше: `.github/workflows/ci.yml`. Сборка: `.github/workflows/release.yml`.

- Тег `v*` (например, `git tag v1.2.0 && git push origin v1.2.0`) собирает Mac и Windows и выкладывает архивы в Releases.
- Запуск вручную (Actions → Build Arena → Run workflow) только собирает: архивы лежат на странице запуска, релиз не создаётся.

На машинах GitHub нет ключа подписи, поэтому агент там не пересобирается: берётся `packaging/prebuilt/agent.apk` из репозитория (`ARENA_PREBUILT_AGENT=1`). Если версия агента в коде изменилась, сначала соберите программу на Mac и закоммитьте новый `packaging/prebuilt/`. Иначе сборка остановится с ошибкой.

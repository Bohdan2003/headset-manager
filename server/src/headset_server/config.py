from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения с префиксом HM_ (или из файла .env)."""

    model_config = SettingsConfigDict(env_prefix="HM_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./headsets.db"
    # Токен для админских запросов (регистрация шлема из provision.sh). Без него сервер не стартует.
    admin_token: str

    host: str = "0.0.0.0"
    port: int = 8000

    heartbeat_interval_s: int = 5
    # Шлем считается офлайн, если столько секунд нет ни одного сообщения
    offline_after_s: int = 15
    # Как часто сохранять текущее состояние шлемов в БД (в памяти оно обновляется сразу)
    state_snapshot_s: int = 10
    # Сколько ждать первое сообщение hello после подключения агента
    hello_timeout_s: float = 10.0
    # Выход из игры с возвратом в неё в течение стольких секунд — та же сессия
    session_grace_s: int = 60
    # Вход на дашборд по паролю. Файл с хешем пароля; выключать только в тестах
    auth_enabled: bool = True
    auth_file: str = "./auth.json"
    # Собранный дашборд (npm run build). Если папка есть, сервер раздаёт его на «/»
    dashboard_dir: str = "../dashboard/dist"

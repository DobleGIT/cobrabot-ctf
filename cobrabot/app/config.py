from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    admin_user: str
    admin_password: str
    admin_hash_md5: str
    flag: str

    # Reto de la tienda (ZumoShop)
    shop_flag: str = "CTF{placeholder_shop_flag}"

    turnstile_enabled: bool = True
    turnstile_site_key: str
    turnstile_secret_key: str

    llm_base_url: str
    llm_api_key: str
    llm_model: str

    filter_enabled: bool = True
    output_filter_enabled: bool = True

    max_history_turns: int = 8

    db_path: str = "data/cobrabot.db"
    shop_db_path: str = "data/shop.db"

    domain: str = "localhost"

    system_prompt_path: str = "prompts/system.txt"
    blocked_phrases_path: str = "filters/blocked_phrases.txt"
    log_path: str = "logs/events.jsonl"
    session_cookie_name: str = "cobrabot_session"
    shop_session_cookie_name: str = "shop_session"
    max_message_length: int = 2000


settings = Settings()

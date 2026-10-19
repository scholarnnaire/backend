import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API settings
    PROJECT_NAME: str = "Who Wants To be A Scholarnnaire API"
    ALLOWED_ORIGINS: str = "*"

    # Email Settings
    MAIL_MAILER: str = "smtp"
    MAIL_HOST: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_ENCRYPTION: str = "tls"

    # Database Settings
    DATABASE_URL: str = "mysql+pymysql://root:@localhost/quiz_cart"

    # JWT Settings
    SECRET_KEY: str = "supersecretkey_please_change_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days

    # Paystack Settings
    PAYSTACK_SECRET_KEY: str = "sk_test_f9fff245108ced6af1333e5510ef017746ce7e0e"
    PAYSTACK_PUBLIC_KEY: str = "pk_test_032f4c03caebe8bf87195e7bb735d444a84481f6"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()

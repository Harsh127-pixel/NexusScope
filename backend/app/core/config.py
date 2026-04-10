from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "NexusScope"
    DEBUG: bool = True
    
    # Firebase
    GOOGLE_APPLICATION_CREDENTIALS: str = "shared/service-account.json"
    FIREBASE_PROJECT_ID: str = "nexus-scope-placeholder"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Modules
    USER_AGENT: str = "NexusScope/1.0"
    PLAYWRIGHT_HEADLESS: bool = True
    
    class Config:
        env_file = ".env"
        extra = "ignore" # Allow extra fields in .env without crashing

settings = Settings()

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "NexusScope"
    DEBUG: bool = True
    
    # Firebase
    FIREBASE_PROJECT_ID: str = "nexus-scope-placeholder"
    
    class Config:
        env_file = ".env"

settings = Settings()

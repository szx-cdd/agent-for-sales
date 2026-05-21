from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Kimi (Moonshot) API 配置
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k-vision-preview"  # 支持图片识别的模型

    # 文本分析模型（可选更大的上下文）
    kimi_text_model: str = "moonshot-v1-32k"

    max_tokens: int = 4096
    temperature: float = 0.7

    class Config:
        env_file = ".env"

settings = Settings()

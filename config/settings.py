from pydantic import BaseSettings


class AppSetting(BaseSettings):
    log_level: str = 'DEBUG'
    api_prefix: str = '/api/v1'
    enable_file_logging: bool = False
    log_file_path: str = 'app.log'

    class Config:
        env_prefix = 'APP_'


app_settings = AppSetting()

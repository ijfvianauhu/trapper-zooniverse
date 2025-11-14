from pydantic import BaseModel, Field, validator, SecretStr, HttpUrl
from pathlib import Path
from typing import Optional, Any, Callable
import yaml
import logging

# ✅ Valor por defecto
def default_get_base_path() -> Path:
    """Directorio base por defecto."""
    return Path.home() / ".wildintel"

# 🔧 Esta variable global puede ser redefinida desde main.py
get_base_path: Callable[[], Path] = default_get_base_path

class I18nConfig(BaseModel):
    language: str = Field(default="en", description="Idioma de la aplicación")
    locale_dir: Path = Field(
        default_factory=lambda: (Path(__file__).parent / ".." / ".." / "locales").resolve(),
        description="Directorio de traducciones (dos niveles más abajo del fichero)"
    )
    @validator('language')
    def validate_language(cls, v):
        valid_languages = ['es', 'en', 'fr', 'de']  # Añade los idiomas que soportes
        if v not in valid_languages:
            raise ValueError(f'Idioma debe ser uno de: {", ".join(valid_languages)}')
        return v

class LoginConfig(BaseModel):
    trapper_username: str = Field(default="myuser", description="Usuario para Trapper")
    trapper_password: SecretStr = Field(
        default_factory=lambda: SecretStr("mypassword"),
        description="Contraseña para Trapper"
    )
    trapper_url: HttpUrl = Field(
        default_factory=lambda: HttpUrl("https://wildintel-trap.uhu.es"),
        description="URL del servicio Trapper"
    )
    trapper_access_token: SecretStr = Field(
        default_factory=lambda: SecretStr("mi_token_secreto"),
        description="Token de acceso para Trapper"
    )
    zooniverse_project_id: str = Field(default="tu_id_de_proyecto", description="ID del proyecto en Zooniverse")
    zooniverse_username: str = Field(default="tu_usuario", description="Usuario para Zooniverse")
    zooniverse_password: SecretStr = Field(
        default_factory=lambda: SecretStr("mi_token_secreto"),
        description="Contraseña pa Zooniverse"
    )

class LoggerConfig(BaseModel):
    #lang: str = Field(default="en", description="Idioma de los logs")
    loglevel: str = Field(default="INFO", description="Nivel de logging")
    logfilename: Path = Field(
        default_factory=lambda: get_base_path() / "app.log",
        description="Archivo de log"
    )

    @validator('loglevel')
    def validate_loglevel(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Nivel de log debe ser uno de: {", ".join(valid_levels)}')
        return v.upper()

class UploadCollectionConfig(BaseModel):
    n_images_seq: int = Field(default=5, ge=1, description="Imágenes por secuencia")
    max_interval: int = Field(default=120, ge=1, description="Máximo segundos entre imágenes de secuencia")
    attempts: int = Field(default=5, ge=1, description="Intentos globales de upload")
    delay: int = Field(default=15, ge=1, description="Segundos entre reintentos")
    max_attempts_per_subject: int = Field(default=5, ge=1, description="Máximos intentos por sujeto")
    delay_seconds_per_subject: int = Field(default=30, ge=1, description="Segundos de espera entre intentos por sujeto")

class DownloadClassificationsConfig(BaseModel):
    # Puedes añadir campos aquí según necesites
    pass

class AppConfig(BaseModel):
    login: LoginConfig = Field(default_factory=LoginConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    upload_collection: UploadCollectionConfig = Field(default_factory=UploadCollectionConfig)
    download_classifications: DownloadClassificationsConfig = Field(default_factory=DownloadClassificationsConfig)
    i18n: I18nConfig = Field(default_factory=I18nConfig)

class ConfigManager:
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or self.get_default_config_file()
        self._config: Optional[AppConfig] = None

    @staticmethod
    def get_default_config_file() -> Path:
        """Obtiene la ruta por defecto del archivo de configuración."""
        return Path.home() / ".wildintel" / "config.yaml"

    def ensure_config_file(self) -> Path:
        """Crea el archivo de configuración con valores por defecto si no existe."""
        if not self.config_file.exists():
            default_config = AppConfig()
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.save_config(default_config)

            # Crear archivo de log
            log_file = Path(default_config.logger.logfilename)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()

        return self.config_file

    def load_config(self) -> AppConfig:
        """Carga la configuración desde el archivo."""
        if self._config is None:
            self.ensure_config_file()

            with open(self.config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}

            self._config = AppConfig(**config_data)

        return self._config

    def save_config(self, config: Optional[AppConfig] = None) -> None:
        if config is None:
            config = self._config or AppConfig()

        raw = config.model_dump()
        serializable = self._serialize_value(raw)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # Guardar en YAML
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(
                serializable,
                f,
                default_flow_style=False,
                indent=2,
                sort_keys=False
            )

        # Actualizar instancia en memoria
        self._config = config

    def update_config(self, **kwargs) -> AppConfig:
        """Actualiza la configuración con nuevos valores."""
        current_config = self.load_config()

        # Convertir a dict para facilitar la actualización
        config_dict = current_config.dict()

        # Actualizar recursivamente
        self._update_dict_recursive(config_dict, kwargs)

        # Crear nueva instancia de configuración
        updated_config = AppConfig(**config_dict)
        self.save_config(updated_config)

        return updated_config

    def _update_dict_recursive(self, original: dict, updates: dict) -> None:
        """Actualiza recursivamente un diccionario."""
        for key, value in updates.items():
            if isinstance(value, dict) and key in original and isinstance(original[key], dict):
                self._update_dict_recursive(original[key], value)
            else:
                original[key] = value

    def _serialize_value(self, value: Any) -> Any:
        """
        Convierte objetos de Pydantic (SecretStr, HttpUrl, BaseModel, etc.)
        en tipos nativos serializables por YAML (str, dict, list...).
        """
        if value is None or isinstance(value, (int, float, bool, str)):
            return value

        if isinstance(value, SecretStr):
            # ⚠️ Esto guarda el secreto en texto plano
            # Cambia por "**********" si no quieres exponerlo
            return value.get_secret_value()

        if isinstance(value, HttpUrl):
            return str(value)

        if isinstance(value, BaseModel):
            # Convertir el submodelo en dict y serializar recursivamente
            return self._serialize_value(value.model_dump())

        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [self._serialize_value(v) for v in value]

        if isinstance(value, Path):
            return str(value)

        return str(value)

    def get_logger(self) -> logging.Logger:
        """Configura y retorna un logger basado en la configuración."""
        config = self.load_config()
        logger_config = config.logger

        # Configurar el logger
        logging.basicConfig(
            level=getattr(logging, logger_config.loglevel),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(logger_config.logfilename),
                logging.StreamHandler()
            ]
        )

        return logging.getLogger(__name__)

    def reload_config(self) -> AppConfig:
        """Recarga la configuración desde el archivo."""
        self._config = None
        return self.load_config()
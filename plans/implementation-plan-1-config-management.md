# Implementation Plan: Configuration Management Migration

## Overview
Migrate from the current `GlyphConfig` class (static dictionary-based) to Pydantic Settings for type-safe, validated configuration management.

## Current State Analysis

### Current Configuration Values (from config.yml)
```yaml
ghidra_location: /home/dsu/ghidra_10.3.1_PUBLIC/
ghidra_project_location: /home/dsu/
ghidra_project_name: glyph
glyph_script_location: /home/dsu/ghidra_10.3.1_PUBLIC/Ghidra/Features/Base/ghidra_scripts/
prediction_probability_threshold: 50.0
max_file_size_mb: 512
cpu_cores: 2
```

### Current Usage Locations
1. [`app/config/settings.py`](app/config/settings.py) - Definition
2. [`app/core/lifespan.py`](app/core/lifespan.py:20) - `load_config()`
3. [`app/api/v1/endpoints/binaries.py`](app/api/v1/endpoints/binaries.py:112) - `get_config_value()`, `_config` access
4. [`app/api/v1/endpoints/config.py`](app/api/v1/endpoints/config.py:21) - `set_max_file_size()`, `_config` access
5. [`app/web/endpoints/web.py`](app/web/endpoints/web.py:39) - `get_config_value()`
6. [`app/processing/task_management.py`](app/processing/task_management.py:211) - `get_config_value()`

## Implementation Plan

### Step 1: Create New Pydantic Settings Class

**File:** `app/config/settings.py`

Create a `GlyphSettings` class using `pydantic-settings`:

```python
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, YamlSettingsSource


class GlyphSettings(BaseSettings):
    """Pydantic-based configuration for Glyph application."""
    
    # Ghidra configuration
    ghidra_location: Path = Field(..., description="Path to Ghidra installation")
    ghidra_project_location: Path = Field(..., description="Path to Ghidra project directory")
    ghidra_project_name: str = Field(..., description="Name of Ghidra project")
    glyph_script_location: Path = Field(..., description="Path to Glyph Ghidra scripts")
    
    # Prediction configuration
    prediction_probability_threshold: float = Field(
        default=50.0,
        ge=0,
        le=100,
        description="Minimum probability threshold for predictions (0-100)"
    )
    
    # File upload configuration
    max_file_size_mb: int = Field(
        default=512,
        ge=1,
        le=2048,
        description="Maximum file size for uploads in MB"
    )
    
    # Processing configuration
    cpu_cores: int = Field(
        default=2,
        ge=1,
        le=32,
        description="Number of CPU cores for processing"
    )
    
    # Computed/derived values
    upload_folder: Path = Field(default=Path("./binaries"), description="Upload directory")
    
    class Config:
        env_prefix = "GLYPH_"
        extra = "ignore"
    
    @classmethod
    def settings_customise_sources(cls, *args, **kwargs):
        """Customize settings sources to prioritize YAML file."""
        return (
            YamlSettingsSource(cls, "config.yml"),
            # Add environment variables as fallback
        )
    
    @field_validator('ghidra_location', 'ghidra_project_location', 'glyph_script_location', mode='before')
    @classmethod
    def convert_to_path(cls, v):
        """Convert string paths to Path objects."""
        return Path(v) if isinstance(v, str) else v


# Singleton instance
settings: GlyphSettings | None = None


def get_settings() -> GlyphSettings:
    """Get or create the settings singleton instance.
    
    Returns:
        GlyphSettings: The application settings instance.
        
    Raises:
        RuntimeError: If settings fail to load.
    """
    global settings
    if settings is None:
        try:
            settings = GlyphSettings()
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}") from e
    return settings


def reload_settings() -> GlyphSettings:
    """Reload settings from config file.
    
    Returns:
        GlyphSettings: Fresh settings instance.
    """
    global settings
    settings = GlyphSettings()
    return settings
```

### Step 2: Update `app/config/__init__.py`

Export the new settings interface:

```python
from app.config.settings import get_settings, GlyphSettings, reload_settings, MAX_CPU_CORES

__all__ = ["get_settings", "GlyphSettings", "reload_settings", "MAX_CPU_CORES"]
```

### Step 3: Update `app/core/lifespan.py`

Replace `GlyphConfig.load_config()` with `get_settings()`:

```python
from app.config.settings import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown logic correctly."""
    logger.info("Starting up Glyph service...")

    # 1. Initialize config
    try:
        get_settings()  # This will load and validate config
        logger.info("✅ Configuration loaded successfully.")
    except RuntimeError as e:
        logger.critical("Configuration failed: %s", e)
        raise

    # ... rest of the code
```

### Step 4: Update `app/api/v1/endpoints/binaries.py`

Replace `GlyphConfig.get_config_value()` and `_config` access:

```python
from app.config.settings import get_settings

# In upload endpoint:
settings = get_settings()
max_file_size_mb = settings.max_file_size_mb
upload_folder = settings.upload_folder

# In list binaries endpoint:
settings = get_settings()
directory_path = settings.upload_folder
```

### Step 5: Update `app/api/v1/endpoints/config.py`

Replace `GlyphConfig.set_max_file_size()` and direct `_config` access:

```python
from app.config.settings import get_settings, reload_settings, GlyphSettings

@router.post("/update")
async def update_config(payload: ConfigUpdateRequest):
    settings = get_settings()
    
    # Update max_file_size_mb
    if payload.max_file_size_mb is not None:
        settings.max_file_size_mb = payload.max_file_size_mb
    
    # Update cpu_cores
    if payload.cpu_cores is not None:
        if 1 <= payload.cpu_cores <= MAX_CPU_CORES:
            settings.cpu_cores = payload.cpu_cores
    
    # Persist changes back to YAML if needed
    # (optional: implement save method)
    
    return JSONResponse(content={"status": "updated"}, status_code=200)
```

### Step 6: Update `app/web/endpoints/web.py`

Replace `GlyphConfig.get_config_value()`:

```python
from app.config.settings import get_settings

@router.get("/config")
async def config(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "max_cpu_cores": MAX_CPU_CORES,
            "current_cpu_cores": settings.cpu_cores,
            "current_max_file_size": settings.max_file_size_mb,
        },
    )
```

### Step 7: Update `app/processing/task_management.py`

Replace `GlyphConfig.get_config_value()`:

```python
from app.config.settings import get_settings

# In Predictor class:
settings = get_settings()
threshold_value = settings.prediction_probability_threshold

# In Ghidra class:
settings = get_settings()
ghidra_location = settings.ghidra_location
ghidra_project_name = settings.ghidra_project_name
ghidra_project_location = settings.ghidra_project_location
glyph_script_location = settings.glyph_script_location
```

## Benefits of This Migration

1. **Type Safety**: All configuration values are strongly typed
2. **Validation**: Automatic validation on load (e.g., `cpu_cores` must be 1-32)
3. **IDE Support**: Autocomplete for configuration keys
4. **Environment Variable Override**: Set `GLYPH_CPU_CORES=4` to override config.yml
5. **Clear Schema**: Pydantic generates JSON schema for documentation
6. **Single Source of Truth**: One settings instance throughout the app

## Testing Checklist

- [ ] App starts successfully with existing `config.yml`
- [ ] All configuration values are accessible via `get_settings()`
- [ ] Invalid configuration values raise appropriate errors
- [ ] Environment variable overrides work correctly
- [ ] All existing functionality continues to work

## Next Steps

After approval, I will:
1. Create the new Pydantic Settings class
2. Update each file one at a time
3. Test each change before proceeding

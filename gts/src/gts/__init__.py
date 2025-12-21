from .gts import (
    GtsIdSegment,
    GtsID,
    GtsWildcard,
)
from .entities import (
    ValidationError,
    ValidationResult,
    GtsFile,
    GtsEntity,
    GtsConfig,
    DEFAULT_GTS_CONFIG,
)
from .path_resolver import GtsPathResolver
from .store import (
    GtsReader,
    GtsStore,
)
from .files_reader import (
    GtsFileReader,
)

__all__ = [
    "GtsIdSegment",
    "GtsID",
    "GtsWildcard",
    "ValidationError",
    "ValidationResult",
    "GtsFile",
    "GtsEntity",
    "GtsPathResolver",
    "GtsConfig",
    "DEFAULT_GTS_CONFIG",
    "GtsReader",
    "GtsStore",
    "GtsFileReader",
    # Backward compatibility aliases
    "JsonFile",
    "JsonEntity",
    "JsonPathResolver",
]

# Backward compatibility aliases
JsonFile = GtsFile
JsonEntity = GtsEntity
JsonPathResolver = GtsPathResolver

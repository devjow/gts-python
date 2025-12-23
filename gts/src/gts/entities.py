from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from .gts import GtsID
from .schema_cast import GtsEntityCastResult, SchemaCastError

if TYPE_CHECKING:
    from .path_resolver import GtsPathResolver


@dataclass
class ValidationError:
    instancePath: str
    schemaPath: str
    keyword: str
    message: str
    params: Dict[str, Any]
    data: Any | None = None


@dataclass
class ValidationResult:
    errors: List[ValidationError] = field(default_factory=list)


@dataclass
class GtsFile:
    path: str
    name: str
    content: Any
    sequencesCount: int = 0
    sequenceContent: Dict[int, Any] = field(default_factory=dict)
    validation: ValidationResult = field(default_factory=ValidationResult)

    def __post_init__(self) -> None:
        items = self.content if isinstance(self.content, list) else [self.content]
        for i, it in enumerate(items):
            self.sequencesCount += 1
            self.sequenceContent[i] = it


@dataclass
class GtsConfig:
    entity_id_fields: List[str]
    schema_id_fields: List[str]


DEFAULT_GTS_CONFIG = GtsConfig(
    entity_id_fields=[
        "$id",
        "gtsId",
        "gtsIid",
        "gtsOid",
        "gtsI",
        "gts_id",
        "gts_oid",
        "gts_iid",
        "id",
    ],
    schema_id_fields=[
        "gtsTid",
        "gtsType",
        "gtsT",
        "gts_t",
        "gts_tid",
        "gts_type",
        "type",
        "schema",
    ],
)


@dataclass
class GtsEntity:
    gts_id: Optional[GtsID] = None
    is_schema: bool = False
    file: Optional[GtsFile] = None
    list_sequence: Optional[int] = None
    label: str = ""
    content: Any = None
    gts_refs: List[Dict[str, str]] = field(default_factory=list)
    validation: ValidationResult = field(default_factory=ValidationResult)
    schemaId: Optional[str] = None
    selected_entity_field: Optional[str] = None
    selected_schema_id_field: Optional[str] = None
    description: str = ""
    schemaRefs: List[Dict[str, str]] = field(default_factory=list)

    def __init__(
        self,
        *,
        file: Optional[GtsFile] = None,
        list_sequence: Optional[int] = None,
        content: Any = None,
        cfg: Optional[GtsConfig] = None,
        gts_id: Optional[GtsID] = None,
        is_schema: bool = False,
        label: str = "",
        validation: Optional[ValidationResult] = None,
        schemaId: Optional[str] = None,
    ) -> None:
        self.file = file
        self.list_sequence = list_sequence
        self.content = content
        self.gts_id = gts_id
        self.is_schema = is_schema
        self.label = label
        self.validation = validation or ValidationResult()
        self.schemaId = schemaId
        self.selected_entity_field = None
        self.selected_schema_id_field = None
        self.gts_refs = []
        self.schemaRefs = []
        self.description = ""

        # Auto-detect if this is a schema
        if content is not None and self._is_json_schema_entity():
            self.is_schema = True

        # Calculate IDs if config provided
        if cfg is not None:
            idv = self._calc_json_entity_id(cfg)
            self.schemaId = self._calc_json_schema_id(cfg)
            # If no valid GTS ID found in entity fields, use schema ID as fallback
            if not (idv and GtsID.is_valid(idv)):
                if self.schemaId and GtsID.is_valid(self.schemaId):
                    idv = self.schemaId
            self.gts_id = GtsID(idv) if idv and GtsID.is_valid(idv) else None

        # Set label
        if self.file and self.list_sequence is not None:
            self.label = f"{self.file.name}#{self.list_sequence}"
        elif self.file:
            self.label = self.file.name
        elif self.gts_id:
            self.label = self.gts_id.id
        elif not self.label:
            self.label = ""

        # Extract description
        self.description = (
            (self.content or {}).get("description", "")
            if isinstance(self.content, dict)
            else ""
        )

        # Extract references
        self.gts_refs = self._extract_gts_ids_with_paths()
        if self.is_schema:
            self.schemaRefs = self._extract_ref_strings_with_paths()

    def _is_json_schema_entity(self) -> bool:
        if not isinstance(self.content, dict):
            return False
        url = self.content.get("$schema")
        if not isinstance(url, str):
            return False
        if url.startswith("http://json-schema.org/"):
            return True
        if url.startswith("https://json-schema.org/"):
            return True
        # Issue #25: strict check, no GTS IDs in $schema
        return False

    def resolve_path(self, path: str) -> "GtsPathResolver":
        from .path_resolver import GtsPathResolver

        resolver = GtsPathResolver(self.gts_id.id if self.gts_id else "", self.content)
        return resolver.resolve(path)

    def cast(
        self,
        to_schema: "GtsEntity",
        from_schema: "GtsEntity",
        resolver: Optional[Any] = None,
    ) -> GtsEntityCastResult:
        if self.is_schema:
            # When casting a schema, from_schema might be a standard JSON Schema (no gts_id)
            # In that case, skip the sanity check
            if from_schema.gts_id and self.gts_id.id != from_schema.gts_id.id:
                raise SchemaCastError(
                    f"Internal error: {self.gts_id.id} != {from_schema.gts_id.id}"
                )
        if not to_schema.is_schema:
            raise SchemaCastError("Target must be a schema")
        if not from_schema.is_schema:
            raise SchemaCastError("Source schema must be a schema")
        return GtsEntityCastResult.cast(
            self.gts_id.id,
            to_schema.gts_id.id,
            self.content,
            from_schema.content,
            to_schema.content,
            resolver=resolver,
        )

    def _walk_and_collect(
        self,
        content: Any,
        collector: List[Dict[str, str]],
        matcher: Any,  # Callable but avoiding import
    ) -> None:
        """Generic tree walker that collects matching nodes.

        Args:
            content: Content to walk through
            collector: List to append matches to
            matcher: Function that takes (node, path) and returns Optional[Dict[str, str]]
        """

        def walk(node: Any, current_path: str = "") -> None:
            if node is None:
                return

            # Try to match current node
            match_result = matcher(node, current_path)
            if match_result:
                collector.append(match_result)

            # Recurse into structures
            if isinstance(node, dict):
                for k, v in node.items():
                    next_path = f"{current_path}.{k}" if current_path else k
                    walk(v, next_path)
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    next_path = f"{current_path}[{idx}]"
                    walk(item, next_path)

        walk(content)

    def _deduplicate_by_id_and_path(
        self, items: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Deduplicate items by their id and sourcePath."""
        uniq: Dict[str, Dict[str, str]] = {}
        for item in items:
            key = f"{item['id']}|{item['sourcePath']}"
            uniq[key] = item
        return list(uniq.values())

    def _extract_gts_ids_with_paths(self) -> List[Dict[str, str]]:
        """Extract all GTS IDs from content with their paths."""
        found: List[Dict[str, str]] = []

        def gts_id_matcher(node: Any, path: str) -> Optional[Dict[str, str]]:
            """Match GTS ID strings."""
            if isinstance(node, str):
                val = node
                if val.startswith("gts://"):
                    val = val[6:]
                if GtsID.is_valid(val):
                    return {"id": val, "sourcePath": path or "root"}
            return None

        self._walk_and_collect(self.content, found, gts_id_matcher)
        return self._deduplicate_by_id_and_path(found)

    def _extract_ref_strings_with_paths(self) -> List[Dict[str, str]]:
        """Extract $ref strings with their paths (for schemas)."""
        refs: List[Dict[str, str]] = []

        def ref_matcher(node: Any, path: str) -> Optional[Dict[str, str]]:
            """Match $ref properties in dict nodes."""
            if isinstance(node, dict) and isinstance(node.get("$ref"), str):
                val = node["$ref"]
                # Issue #32: handle gts:// prefix
                if val.startswith("gts://"):
                    val = val[6:]
                ref_path = f"{path}.$ref" if path else "$ref"
                return {"id": val, "sourcePath": ref_path}
            return None

        self._walk_and_collect(self.content, refs, ref_matcher)
        return self._deduplicate_by_id_and_path(refs)

    def _get_field_value(self, field: str) -> Optional[str]:
        """Get string value from content field."""
        if not isinstance(self.content, dict):
            return None
        v = self.content.get(field)
        if isinstance(v, str) and v.strip():
            # Issue #31, #32: Handle gts:// prefix in fields (e.g. $id)
            if v.startswith("gts://"):
                v = v[6:]
            return v
        return None

    def _first_non_empty_field(self, fields: List[str]) -> Optional[Tuple[str, str]]:
        """Find first non-empty field, preferring valid GTS IDs."""
        # First pass: look for valid GTS IDs
        for f in fields:
            v = self._get_field_value(f)
            if v and GtsID.is_valid(v):
                return f, v
        # Second pass: any non-empty string
        for f in fields:
            v = self._get_field_value(f)
            if v:
                return f, v
        return None

    def _calc_json_entity_id(self, cfg: GtsConfig) -> str:
        cand = self._first_non_empty_field(cfg.entity_id_fields)
        if cand:
            self.selected_entity_field = cand[0]
            return cand[1]
        if self.file and self.list_sequence is not None:
            return f"{self.file.path}#{self.list_sequence}"
        return self.file.path if self.file else ""

    def _calc_json_schema_id(self, cfg: GtsConfig) -> str:
        cand = self._first_non_empty_field(cfg.schema_id_fields)
        if cand:
            self.selected_schema_id_field = cand[0]
            return cand[1]
        idv = self._calc_json_entity_id(cfg)
        if idv and isinstance(idv, str) and GtsID.is_valid(idv):
            if idv.endswith("~"):
                return idv
            last = idv.rfind("~")
            if last > 0:
                self.selected_schema_id_field = self.selected_entity_field
                return idv[: last + 1]
        if self.file and self.list_sequence is not None:
            return f"{self.file.path}#{self.list_sequence}"
        return self.file.path if self.file else ""

    def _extract_uuid_from_content(self) -> Optional[str]:
        """Extract a UUID value from content to use as instance identifier."""
        if not isinstance(self.content, dict):
            return None
        # Look for common UUID fields
        for field_name in ["id", "uuid", "instanceId", "instance_id"]:
            val = self.content.get(field_name)
            if isinstance(val, str) and val.strip():
                # Check if it looks like a UUID (basic check)
                import re

                if re.match(
                    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                    val.lower(),
                ):
                    # Convert UUID to a valid GTS segment format
                    return val.replace("-", "_")
        return None

    def get_graph(self) -> Dict[str, Set[str]]:
        refs = {}
        for r in self.gts_refs:
            refs[r["sourcePath"]] = r["id"]
        return {"id": self.gts_id.id, "schema_id": self.schemaId, "refs": refs}

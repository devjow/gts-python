"""Tests for JsonEntity and related classes."""

from gts.entities import (
    JsonFile,
    JsonEntity,
    ValidationError,
    ValidationResult,
    DEFAULT_GTS_CONFIG,
)
from gts.gts import GtsID


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_validation_error_creation(self):
        """Test creating a validation error."""
        error = ValidationError(
            instancePath="/property",
            schemaPath="#/properties/property",
            keyword="type",
            message="must be string",
            params={"type": "string"},
        )
        assert error.instancePath == "/property"
        assert error.keyword == "type"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_empty_validation_result(self):
        """Test empty validation result."""
        result = ValidationResult()
        assert result.errors == []

    def test_validation_result_with_errors(self):
        """Test validation result with errors."""
        error = ValidationError(
            instancePath="/prop",
            schemaPath="#/prop",
            keyword="required",
            message="missing",
            params={},
        )
        result = ValidationResult(errors=[error])
        assert len(result.errors) == 1


class TestJsonFile:
    """Tests for JsonFile dataclass."""

    def test_json_file_single_content(self):
        """Test JsonFile with single content."""
        content = {"name": "test"}
        jf = JsonFile(path="/path/to/file.json", name="file.json", content=content)

        assert jf.path == "/path/to/file.json"
        assert jf.name == "file.json"
        assert jf.sequencesCount == 1
        assert jf.sequenceContent[0] == content

    def test_json_file_list_content(self):
        """Test JsonFile with list content."""
        content = [{"id": 1}, {"id": 2}, {"id": 3}]
        jf = JsonFile(path="/path/to/file.json", name="file.json", content=content)

        assert jf.sequencesCount == 3
        assert jf.sequenceContent[0] == {"id": 1}
        assert jf.sequenceContent[1] == {"id": 2}
        assert jf.sequenceContent[2] == {"id": 3}


class TestGtsConfig:
    """Tests for GtsConfig."""

    def test_default_config(self):
        """Test default config has expected fields."""
        assert "$id" in DEFAULT_GTS_CONFIG.entity_id_fields
        assert "gtsId" in DEFAULT_GTS_CONFIG.entity_id_fields
        assert "$schema" in DEFAULT_GTS_CONFIG.schema_id_fields
        assert "gtsType" in DEFAULT_GTS_CONFIG.schema_id_fields


class TestJsonEntity:
    """Tests for JsonEntity class."""

    def test_entity_with_gts_id(self):
        """Test entity creation with explicit GTS ID."""
        gts_id = GtsID("gts.vendor.package.namespace.type.v1~")
        entity = JsonEntity(
            content={"name": "test"},
            gts_id=gts_id,
        )

        assert entity.gts_id == gts_id
        assert entity.content == {"name": "test"}

    def test_entity_schema_detection_http(self):
        """Test schema detection via http json-schema.org URL."""
        entity = JsonEntity(
            content={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
            },
        )

        assert entity.is_schema is True

    def test_entity_schema_detection_https(self):
        """Test schema detection via https json-schema.org URL."""
        entity = JsonEntity(
            content={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
            },
        )

        assert entity.is_schema is True

    def test_entity_schema_detection_gts_uri(self):
        """Test schema detection via gts:// URI."""
        entity = JsonEntity(
            content={
                "$schema": "gts://vendor.package.namespace.meta.v1~",
                "type": "object",
            },
        )

        assert entity.is_schema is True

    def test_entity_schema_detection_gts_prefix(self):
        """Test schema detection via gts. prefix."""
        entity = JsonEntity(
            content={
                "$schema": "gts.vendor.package.namespace.meta.v1~",
                "type": "object",
            },
        )

        assert entity.is_schema is True

    def test_entity_not_schema(self):
        """Test non-schema entity."""
        entity = JsonEntity(
            content={"name": "test", "value": 42},
        )

        assert entity.is_schema is False

    def test_entity_id_calculation(self):
        """Test entity ID calculation from content fields."""
        entity = JsonEntity(
            content={
                "$id": "gts.vendor.package.namespace.type.v1~",
                "name": "test",
            },
            cfg=DEFAULT_GTS_CONFIG,
        )

        assert entity.gts_id is not None
        assert entity.gts_id.id == "gts.vendor.package.namespace.type.v1~"
        assert entity.selected_entity_field == "$id"

    def test_entity_schema_id_calculation(self):
        """Test schema ID calculation from content fields."""
        entity = JsonEntity(
            content={
                "$schema": "gts.vendor.package.namespace.type.v1~",
                "name": "test",
            },
            cfg=DEFAULT_GTS_CONFIG,
        )

        assert entity.schemaId == "gts.vendor.package.namespace.type.v1~"
        assert entity.selected_schema_id_field == "$schema"

    def test_entity_label_from_file(self):
        """Test entity label derived from file."""
        jf = JsonFile(path="/path/to/file.json", name="file.json", content={})
        entity = JsonEntity(
            file=jf,
            list_sequence=0,
            content={"name": "test"},
        )

        assert entity.label == "file.json#0"

    def test_entity_label_from_gts_id(self):
        """Test entity label derived from GTS ID."""
        gts_id = GtsID("gts.vendor.package.namespace.type.v1~")
        entity = JsonEntity(
            content={},
            gts_id=gts_id,
        )

        assert entity.label == "gts.vendor.package.namespace.type.v1~"

    def test_entity_description_extraction(self):
        """Test description extraction from content."""
        entity = JsonEntity(
            content={
                "description": "This is a test entity",
                "name": "test",
            },
        )

        assert entity.description == "This is a test entity"

    def test_entity_description_empty(self):
        """Test empty description when not present."""
        entity = JsonEntity(
            content={"name": "test"},
        )

        assert entity.description == ""


class TestJsonEntityRefs:
    """Tests for GTS reference extraction in JsonEntity."""

    def test_extract_gts_refs_simple(self):
        """Test extracting GTS refs from content."""
        entity = JsonEntity(
            content={
                "ref": "gts.vendor.package.namespace.other.v1~",
            },
        )

        assert len(entity.gts_refs) == 1
        assert entity.gts_refs[0]["id"] == "gts.vendor.package.namespace.other.v1~"
        assert entity.gts_refs[0]["sourcePath"] == "ref"

    def test_extract_gts_refs_nested(self):
        """Test extracting nested GTS refs."""
        entity = JsonEntity(
            content={
                "data": {"nested": {"ref": "gts.vendor.package.namespace.deep.v1~"}}
            },
        )

        assert len(entity.gts_refs) == 1
        assert entity.gts_refs[0]["sourcePath"] == "data.nested.ref"

    def test_extract_gts_refs_in_array(self):
        """Test extracting GTS refs from arrays."""
        entity = JsonEntity(
            content={
                "items": [
                    "gts.vendor.package.namespace.item0.v1~",
                    "gts.vendor.package.namespace.item1.v1~",
                ]
            },
        )

        assert len(entity.gts_refs) == 2
        paths = [r["sourcePath"] for r in entity.gts_refs]
        assert "items[0]" in paths
        assert "items[1]" in paths

    def test_extract_schema_refs(self):
        """Test extracting $ref strings from schema."""
        entity = JsonEntity(
            content={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "user": {"$ref": "gts.vendor.package.namespace.user.v1~"}
                },
            },
        )

        assert entity.is_schema is True
        assert len(entity.schemaRefs) == 1
        assert entity.schemaRefs[0]["id"] == "gts.vendor.package.namespace.user.v1~"

    def test_deduplicate_refs(self):
        """Test that duplicate refs are deduplicated."""
        entity = JsonEntity(
            content={
                "ref1": "gts.vendor.package.namespace.same.v1~",
                "ref2": "gts.vendor.package.namespace.same.v1~",
            },
        )

        # Both should be included as they have different paths
        assert len(entity.gts_refs) == 2


class TestJsonEntityResolvePath:
    """Tests for resolve_path method."""

    def test_resolve_path_simple(self):
        """Test simple path resolution."""
        gts_id = GtsID("gts.vendor.package.namespace.type.v1~")
        entity = JsonEntity(
            content={"name": "test", "value": 42},
            gts_id=gts_id,
        )

        result = entity.resolve_path("name")
        assert result.resolved is True
        assert result.value == "test"

    def test_resolve_path_nested(self):
        """Test nested path resolution."""
        gts_id = GtsID("gts.vendor.package.namespace.type.v1~")
        entity = JsonEntity(
            content={"data": {"inner": "deep"}},
            gts_id=gts_id,
        )

        result = entity.resolve_path("data.inner")
        assert result.resolved is True
        assert result.value == "deep"


class TestJsonEntityGetGraph:
    """Tests for get_graph method."""

    def test_get_graph_basic(self):
        """Test basic graph generation."""
        gts_id = GtsID("gts.vendor.package.namespace.type.v1~")
        entity = JsonEntity(
            content={
                "ref": "gts.vendor.package.namespace.other.v1~",
            },
            gts_id=gts_id,
            schemaId="gts.vendor.package.namespace.type.v1~",
        )

        graph = entity.get_graph()
        assert graph["id"] == "gts.vendor.package.namespace.type.v1~"
        assert graph["schema_id"] == "gts.vendor.package.namespace.type.v1~"
        assert "refs" in graph

"""Tests for JsonPathResolver."""

from gts.path_resolver import JsonPathResolver


class TestJsonPathResolverBasic:
    """Basic path resolution tests."""

    def test_resolve_simple_key(self):
        """Test resolving a simple top-level key."""
        content = {"name": "test", "value": 42}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("name")

        assert result.resolved is True
        assert result.value == "test"
        assert result.error is None

    def test_resolve_nested_key(self):
        """Test resolving a nested key."""
        content = {"level1": {"level2": {"level3": "deep_value"}}}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("level1.level2.level3")

        assert result.resolved is True
        assert result.value == "deep_value"

    def test_resolve_array_index(self):
        """Test resolving an array index."""
        content = {"items": ["first", "second", "third"]}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("items[1]")

        assert result.resolved is True
        assert result.value == "second"

    def test_resolve_nested_array(self):
        """Test resolving nested array access."""
        content = {"matrix": [[1, 2], [3, 4], [5, 6]]}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("matrix[1][0]")

        assert result.resolved is True
        assert result.value == 3

    def test_resolve_mixed_path(self):
        """Test resolving a path with both objects and arrays."""
        content = {"users": [{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("users[1].name")

        assert result.resolved is True
        assert result.value == "bob"


class TestJsonPathResolverSlashSyntax:
    """Test slash-based path syntax."""

    def test_resolve_slash_path(self):
        """Test resolving a slash-separated path."""
        content = {"level1": {"level2": "value"}}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("level1/level2")

        assert result.resolved is True
        assert result.value == "value"

    def test_resolve_mixed_slash_and_dot(self):
        """Test that slashes are normalized to dots."""
        content = {"a": {"b": {"c": "value"}}}
        resolver = JsonPathResolver("gts.test~", content)

        result1 = resolver.resolve("a/b/c")
        result2 = resolver.resolve("a.b.c")

        assert result1.value == result2.value == "value"


class TestJsonPathResolverErrors:
    """Error handling tests for path resolution."""

    def test_path_not_found(self):
        """Test handling of non-existent path."""
        content = {"name": "test"}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("nonexistent")

        assert result.resolved is False
        assert result.error is not None
        assert "not found" in result.error.lower()
        assert "name" in result.available_fields

    def test_index_out_of_range(self):
        """Test handling of out-of-range array index."""
        content = {"items": ["a", "b"]}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("items[5]")

        assert result.resolved is False
        assert "out of range" in result.error.lower()

    def test_invalid_index_format(self):
        """Test handling of non-integer array index."""
        content = {"items": ["a", "b"]}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("items[abc]")

        assert result.resolved is False
        assert "index" in result.error.lower()

    def test_descend_into_scalar(self):
        """Test handling of descending into a scalar value."""
        content = {"value": 42}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("value.subkey")

        assert result.resolved is False
        assert result.error is not None

    def test_array_index_on_dict(self):
        """Test handling of array index on dictionary."""
        content = {"obj": {"key": "value"}}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("obj[0]")

        assert result.resolved is False
        assert result.error is not None


class TestJsonPathResolverAvailableFields:
    """Tests for available_fields feature."""

    def test_available_fields_on_dict(self):
        """Test that available fields are listed for dict."""
        content = {"name": "test", "age": 30, "nested": {"inner": "value"}}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("nonexistent")

        assert "name" in result.available_fields
        assert "age" in result.available_fields
        assert "nested" in result.available_fields
        assert "nested.inner" in result.available_fields

    def test_available_fields_on_array(self):
        """Test that available indices are listed for array."""
        content = {"items": ["a", "b", "c"]}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("items.nonexistent")

        assert "[0]" in result.available_fields
        assert "[1]" in result.available_fields
        assert "[2]" in result.available_fields


class TestJsonPathResolverToDict:
    """Tests for to_dict() method."""

    def test_to_dict_success(self):
        """Test to_dict on successful resolution."""
        content = {"key": "value"}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("key")

        d = result.to_dict()
        assert d["gts_id"] == "gts.test~"
        assert d["path"] == "key"
        assert d["value"] == "value"
        assert d["resolved"] is True
        assert "error" not in d

    def test_to_dict_failure(self):
        """Test to_dict on failed resolution."""
        content = {"key": "value"}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("nonexistent")

        d = result.to_dict()
        assert d["resolved"] is False
        assert "error" in d
        assert "available_fields" in d


class TestJsonPathResolverEdgeCases:
    """Edge case tests."""

    def test_empty_path(self):
        """Test resolving empty path returns root content."""
        content = {"key": "value"}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("")

        assert result.resolved is True
        assert result.value == content

    def test_resolve_null_value(self):
        """Test resolving a null value."""
        content = {"nullable": None}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("nullable")

        assert result.resolved is True
        assert result.value is None

    def test_resolve_boolean_false(self):
        """Test resolving a false boolean."""
        content = {"flag": False}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("flag")

        assert result.resolved is True
        assert result.value is False

    def test_resolve_zero(self):
        """Test resolving zero value."""
        content = {"count": 0}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("count")

        assert result.resolved is True
        assert result.value == 0

    def test_resolve_empty_string(self):
        """Test resolving empty string."""
        content = {"text": ""}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("text")

        assert result.resolved is True
        assert result.value == ""

    def test_resolve_empty_array(self):
        """Test resolving empty array."""
        content = {"items": []}
        resolver = JsonPathResolver("gts.test~", content)
        result = resolver.resolve("items")

        assert result.resolved is True
        assert result.value == []

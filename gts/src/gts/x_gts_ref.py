"""
x-gts-ref validation support for GTS schemas (optimized version).

This module implements validation for the x-gts-ref extension as specified
in the GTS specification section 9.5.

Key optimizations:
1. Use jsonpointer library for JSON Pointer resolution
2. Consolidate duplicate validation logic
3. Simplify recursive traversal with a generic walker
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
import re

from .gts import GtsID, GTS_URI_PREFIX


class XGtsRefValidationError(Exception):
    """Exception raised when x-gts-ref validation fails."""

    def __init__(self, field_path: str, value: Any, ref_pattern: str, reason: str):
        super().__init__(
            f"x-gts-ref validation failed for field '{field_path}': {reason}"
        )
        self.field_path = field_path
        self.value = value
        self.ref_pattern = ref_pattern
        self.reason = reason


class XGtsRefValidator:
    """Validator for x-gts-ref constraints in GTS schemas."""

    def __init__(self, store: Optional[Any] = None):
        """
        Initialize validator.

        Args:
            store: Optional GtsStore for resolving entity references
        """
        self.store = store

    def validate_instance(
        self, instance: Dict[str, Any], schema: Dict[str, Any], instance_path: str = ""
    ) -> List[XGtsRefValidationError]:
        """
        Validate an instance against x-gts-ref constraints in schema.

        Args:
            instance: The data instance to validate
            schema: The JSON schema with x-gts-ref extensions
            instance_path: Current path in instance (for error reporting)

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        def visit_instance(inst, sch, path):
            """Visit instance nodes and validate x-gts-ref constraints."""
            if not isinstance(sch, dict):
                return

            # Check for x-gts-ref constraint
            if "x-gts-ref" in sch and isinstance(inst, str):
                error = self._validate_ref_value(inst, sch["x-gts-ref"], path, schema)
                if error:
                    errors.append(error)

            # Recurse into object properties
            if sch.get("type") == "object" and "properties" in sch:
                if isinstance(inst, dict):
                    for prop_name, prop_schema in sch["properties"].items():
                        if prop_name in inst:
                            prop_path = f"{path}.{prop_name}" if path else prop_name
                            visit_instance(inst[prop_name], prop_schema, prop_path)

            # Recurse into array items
            if sch.get("type") == "array" and "items" in sch:
                if isinstance(inst, list):
                    for idx, item in enumerate(inst):
                        item_path = f"{path}[{idx}]"
                        visit_instance(item, sch["items"], item_path)

        visit_instance(instance, schema, instance_path)
        return errors

    def validate_schema(
        self,
        schema: Dict[str, Any],
        schema_path: str = "",
        root_schema: Optional[Dict[str, Any]] = None,
    ) -> List[XGtsRefValidationError]:
        """
        Validate x-gts-ref fields in a schema definition.

        Args:
            schema: The JSON schema to validate
            schema_path: Current path in schema (for error reporting)
            root_schema: The root schema (for resolving relative refs)

        Returns:
            List of validation errors (empty if valid)
        """
        if root_schema is None:
            root_schema = schema

        errors = []

        def visit_schema(sch, path):
            """Recursively visit schema nodes."""
            if not isinstance(sch, dict):
                return

            # Check for x-gts-ref field
            if "x-gts-ref" in sch:
                ref_value = sch["x-gts-ref"]
                ref_path = f"{path}/x-gts-ref" if path else "x-gts-ref"
                error = self._validate_ref_pattern(ref_value, ref_path, root_schema)
                if error:
                    errors.append(error)

            # Recurse into nested structures
            for key, value in sch.items():
                if key == "x-gts-ref":
                    continue
                nested_path = f"{path}/{key}" if path else key
                if isinstance(value, dict):
                    visit_schema(value, nested_path)
                elif isinstance(value, list):
                    for idx, item in enumerate(value):
                        if isinstance(item, dict):
                            visit_schema(item, f"{nested_path}[{idx}]")

        visit_schema(schema, schema_path)
        return errors

    def _validate_ref_value(
        self, value: str, ref_pattern: str, field_path: str, schema: Dict[str, Any]
    ) -> Optional[XGtsRefValidationError]:
        """
        Validate an instance value against its x-gts-ref constraint.

        Args:
            value: The field value to validate
            ref_pattern: The x-gts-ref pattern
            field_path: Path to the field (for error reporting)
            schema: The complete schema (for resolving relative refs)

        Returns:
            XGtsRefValidationError if validation fails, None otherwise
        """
        if not isinstance(value, str):
            return XGtsRefValidationError(
                field_path,
                value,
                ref_pattern,
                f"Value must be a string, got {type(value).__name__}",
            )

        # Resolve pattern if it's a relative reference
        if ref_pattern.startswith("/"):
            resolved_pattern = self._resolve_pointer(schema, ref_pattern)
            if resolved_pattern is None:
                return XGtsRefValidationError(
                    field_path,
                    value,
                    ref_pattern,
                    f"Cannot resolve reference path '{ref_pattern}'",
                )
            if not isinstance(resolved_pattern, str) or not resolved_pattern.startswith(
                "gts."
            ):
                return XGtsRefValidationError(
                    field_path,
                    value,
                    ref_pattern,
                    f"Resolved reference '{ref_pattern}' -> '{resolved_pattern}' is not a GTS pattern",
                )
            ref_pattern = resolved_pattern

        # Validate against GTS pattern
        return self._validate_gts_pattern(value, ref_pattern, field_path)

    def _validate_ref_pattern(
        self, ref_pattern: str, field_path: str, root_schema: Dict[str, Any]
    ) -> Optional[XGtsRefValidationError]:
        """
        Validate an x-gts-ref pattern in a schema definition.

        Args:
            ref_pattern: The x-gts-ref value
            field_path: Path to the field (for error reporting)
            root_schema: The root schema (for resolving relative refs)

        Returns:
            XGtsRefValidationError if validation fails, None otherwise
        """
        if not isinstance(ref_pattern, str):
            return XGtsRefValidationError(
                field_path,
                ref_pattern,
                "",
                f"x-gts-ref value must be a string, got {type(ref_pattern).__name__}",
            )

        # Case 1: Absolute GTS pattern
        if ref_pattern.startswith("gts."):
            return self._validate_gts_id_or_pattern(ref_pattern, field_path)

        # Case 2: Relative reference
        if ref_pattern.startswith("/"):
            resolved = self._resolve_pointer(root_schema, ref_pattern)
            if resolved is None:
                return XGtsRefValidationError(
                    field_path,
                    ref_pattern,
                    ref_pattern,
                    f"Cannot resolve reference path '{ref_pattern}'",
                )
            if not isinstance(resolved, str) or not GtsID.is_valid(resolved):
                return XGtsRefValidationError(
                    field_path,
                    ref_pattern,
                    ref_pattern,
                    f"Resolved reference '{ref_pattern}' -> '{resolved}' is not a valid GTS identifier",
                )
            return None

        return XGtsRefValidationError(
            field_path,
            ref_pattern,
            ref_pattern,
            f"Invalid x-gts-ref value: '{ref_pattern}' must start with 'gts.' or '/'",
        )

    def _validate_gts_id_or_pattern(
        self, pattern: str, field_path: str
    ) -> Optional[XGtsRefValidationError]:
        """Validate a GTS ID or pattern in schema definition."""
        if pattern == "gts.*":
            return None  # Valid wildcard

        if "*" in pattern:
            # Wildcard pattern - validate prefix
            prefix = pattern.rstrip("*")
            if not prefix.startswith("gts."):
                return XGtsRefValidationError(
                    field_path,
                    pattern,
                    pattern,
                    f"Invalid GTS wildcard pattern: {pattern}",
                )
            return None

        # Specific GTS ID
        if not GtsID.is_valid(pattern):
            return XGtsRefValidationError(
                field_path, pattern, pattern, f"Invalid GTS identifier: {pattern}"
            )
        return None

    def _validate_gts_pattern(
        self, value: str, pattern: str, field_path: str
    ) -> Optional[XGtsRefValidationError]:
        """
        Validate value matches a GTS pattern.

        Args:
            value: The value to validate
            pattern: GTS pattern (e.g., "gts.*", "gts.x.core.modules.*")
            field_path: Path to field (for error reporting)

        Returns:
            Error if validation fails, None otherwise
        """
        # Validate it's a valid GTS ID
        if not GtsID.is_valid(value):
            return XGtsRefValidationError(
                field_path,
                value,
                pattern,
                f"Value '{value}' is not a valid GTS identifier",
            )

        # Check pattern match
        if pattern == "gts.*":
            pass  # Any valid GTS ID matches
        elif pattern.endswith("*"):
            prefix = pattern[:-1]
            if not value.startswith(prefix):
                return XGtsRefValidationError(
                    field_path,
                    value,
                    pattern,
                    f"Value '{value}' does not match pattern '{pattern}'",
                )
        elif not value.startswith(pattern):
            return XGtsRefValidationError(
                field_path,
                value,
                pattern,
                f"Value '{value}' does not match pattern '{pattern}'",
            )

        # Optionally check if entity exists in store
        if self.store:
            entity = self.store.get(value)
            if not entity:
                return XGtsRefValidationError(
                    field_path,
                    value,
                    pattern,
                    f"Referenced entity '{value}' not found in registry",
                )

        return None

    def _normalize_gts_value(self, value: str) -> str:
        """Strip gts:// URI prefix if present."""
        if value.startswith(GTS_URI_PREFIX):
            return value[len(GTS_URI_PREFIX) :]
        return value

    def _resolve_pointer(self, schema: Dict[str, Any], pointer: str) -> Optional[str]:
        """
        Resolve a JSON Pointer in the schema.

        Args:
            schema: The schema to search
            pointer: JSON Pointer (e.g., "/$id", "/properties/type")

        Returns:
            The resolved value or None if not found
        """

        path = pointer.lstrip("/")
        if not path:
            return None

        parts = path.split("/")
        current = schema

        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None

        # If current is a string, return it (normalizing gts:// prefix)
        if isinstance(current, str):
            return self._normalize_gts_value(current)

        # If current is a dict with x-gts-ref, resolve it
        if isinstance(current, dict) and "x-gts-ref" in current:
            ref_value = current["x-gts-ref"]
            if isinstance(ref_value, str):
                if ref_value.startswith("/"):
                    return self._resolve_pointer(schema, ref_value)
                return self._normalize_gts_value(ref_value)

        return None

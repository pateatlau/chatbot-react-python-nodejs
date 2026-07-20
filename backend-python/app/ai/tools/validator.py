"""Validate tool call arguments against tool JSON Schema parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.tools.schemas import ToolDefinition


@dataclass(frozen=True)
class ValidationErrorDetail:
    message: str


class ToolValidator:
    """Lightweight JSON Schema validation for V1 tool parameters."""

    def validate(
        self,
        tool: ToolDefinition,
        arguments: dict[str, object],
    ) -> ValidationErrorDetail | None:
        schema = tool.parameters
        if schema.get("type", "object") != "object":
            return ValidationErrorDetail(
                message="Tool parameters schema must be a JSON Schema object"
            )

        properties = schema.get("properties")
        if properties is not None and not isinstance(properties, dict):
            return ValidationErrorDetail(message="Invalid properties schema")

        required = schema.get("required", [])
        if not isinstance(required, list):
            return ValidationErrorDetail(message="Invalid required field schema")

        for field_name in required:
            if field_name not in arguments:
                return ValidationErrorDetail(
                    message=f"Missing required argument: {field_name}"
                )

        if properties is None:
            return None

        for key, value in arguments.items():
            if key not in properties:
                return ValidationErrorDetail(message=f"Unknown argument: {key}")

            prop_schema = properties[key]
            if not isinstance(prop_schema, dict):
                return ValidationErrorDetail(
                    message=f"Invalid schema for argument: {key}"
                )

            type_error = self._validate_type(key, value, prop_schema.get("type"))
            if type_error is not None:
                return type_error

        return None

    def _validate_type(
        self,
        key: str,
        value: object,
        expected_type: Any,
    ) -> ValidationErrorDetail | None:
        if expected_type is None:
            return None

        if isinstance(expected_type, list):
            if any(self._value_matches_type(value, option) for option in expected_type):
                return None
            return ValidationErrorDetail(message=f"Argument '{key}' has invalid type")

        if not isinstance(expected_type, str):
            return ValidationErrorDetail(
                message=f"Invalid type schema for argument: {key}"
            )

        if not self._value_matches_type(value, expected_type):
            return ValidationErrorDetail(
                message=f"Argument '{key}' must be of type {expected_type}"
            )
        return None

    @staticmethod
    def _value_matches_type(value: object, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "null":
            return value is None
        return True

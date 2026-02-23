"""Keel error hierarchy — all errors inherit ClickException for clean CLI output."""

import click


class KeelError(click.ClickException):
    """Base error for all keel operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ConfigError(KeelError):
    """Invalid or missing configuration."""


class StateError(KeelError):
    """Invalid state transition or corrupt state file."""


class ClaudeError(KeelError):
    """Claude Code subprocess failure."""


class FetchError(KeelError):
    """Network fetch failure (Brave, RSS, PDF download)."""

"""Sanitized failures for recorded local market-data adapters."""

from __future__ import annotations


class RecordedAdapterError(Exception):
    """Base error with stable public text and no payload details."""

    public_message = "Recorded market-data adapter operation failed."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class InvalidRecordedPayloadError(RecordedAdapterError):
    """A recorded payload is malformed, unsafe, or unsupported."""

    public_message = "Recorded market-data payload is invalid."


class RecordedAdapterUnavailableError(RecordedAdapterError):
    """Replay was requested while the adapter was not running."""

    public_message = "Recorded market-data adapter is not running."


class ReplaySequenceError(RecordedAdapterError):
    """Recorded sequence ordering would make replay ambiguous."""

    public_message = "Recorded market-data sequence is invalid."


class RecordedReplayError(RecordedAdapterError):
    """A validated recorded event could not be ingested."""

    public_message = "Recorded market-data replay failed."


__all__ = (
    "InvalidRecordedPayloadError",
    "RecordedAdapterError",
    "RecordedAdapterUnavailableError",
    "RecordedReplayError",
    "ReplaySequenceError",
)

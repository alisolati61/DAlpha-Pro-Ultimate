from __future__ import annotations


class EventBusError(Exception):
    """
    Base exception for the Event Bus.
    """


class SubscriptionError(EventBusError):
    """
    Raised when a subscription operation fails.
    """


class EventDispatchError(EventBusError):
    """
    Raised when an event cannot be dispatched.
    """


class DuplicateSubscriptionError(SubscriptionError):
    """
    Raised when attempting to register
    the same handler more than once.
    """


class HandlerNotFoundError(SubscriptionError):
    """
    Raised when trying to remove
    a handler that is not registered.
    """
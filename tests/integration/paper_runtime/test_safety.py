from __future__ import annotations

import _thread
import asyncio
import builtins
import io
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable

import dotenv
import httpx
import pytest
import websockets

from src.drivers.paper_driver import PaperDriver
from src.exchange.base import BaseExchange
from src.exchange.bingx_adapter import BingXAdapter
from src.exchange.bingx_client import BingXHttpClient
from src.exchange.ccxt_exchange import CCXTExchange
from src.exchange.connectors.crypto_connector import CryptoConnector
from src.exchange.exchange_factory import ExchangeFactory
from src.execution.execution_engine import ExecutionEngine
from src.execution.execution_manager import ExecutionManager
from src.execution.order_manager import OrderManager
from src.execution.paper_trading import PaperTradingEngine
from src.execution.smart_router import SmartRouter
from src.execution_intent.models import (
    ExecutionIntent,
    IntentOrderType,
    IntentReason,
    IntentSide,
    IntentStatus,
    IntentTimeInForce,
    OrderSpecification,
)
from src.interfaces.exchange_interface import ExchangeInterface
from src.paper_runtime import (
    PaperAccountSnapshot,
    PaperExecutionCoordinator,
    PaperExecutionPolicy,
    PaperMarketEvent,
)

_SOURCE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _ready_intent() -> ExecutionIntent:
    quantity = Decimal("2")
    entry = OrderSpecification(
        IntentSide.BUY,
        IntentOrderType.LIMIT,
        Decimal("100"),
        quantity,
        IntentTimeInForce.GTC,
        False,
    )
    stop = OrderSpecification(
        IntentSide.SELL,
        IntentOrderType.STOP,
        Decimal("90"),
        quantity,
        IntentTimeInForce.GTC,
        True,
    )
    target = OrderSpecification(
        IntentSide.SELL,
        IntentOrderType.TAKE_PROFIT,
        Decimal("120"),
        quantity,
        IntentTimeInForce.GTC,
        True,
    )
    return ExecutionIntent(
        "intent-safety",
        "decision-safety",
        IntentStatus.READY,
        "BTCUSDT",
        "recorded",
        "1m",
        entry,
        stop,
        target,
        "market-structure",
        "1.0.0",
        Decimal("20"),
        "constraints-v1",
        _SOURCE_TIME,
        (IntentReason.INTENT_READY,),
    )


def _account() -> PaperAccountSnapshot:
    return PaperAccountSnapshot(
        Decimal("10000"),
        Decimal("10000"),
        Decimal("10000"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        0,
    )


def _policy() -> PaperExecutionPolicy:
    return PaperExecutionPolicy(
        "paper-safety-v1",
        Decimal("10"),
        Decimal("5"),
        Decimal("10"),
        Decimal("0.01"),
        Decimal("2"),
    )


def _event(
    sequence: int,
    *,
    price: str,
    low: str,
    high: str,
) -> PaperMarketEvent:
    return PaperMarketEvent(
        sequence,
        "BTCUSDT",
        _SOURCE_TIME + timedelta(minutes=sequence),
        Decimal(price),
        Decimal(low),
        Decimal(high),
        Decimal("10"),
    )


def _fail_fast(
    calls: list[str],
    name: str,
) -> Callable[..., None]:
    def blocked(*args: object, **kwargs: object) -> None:
        calls.append(name)
        raise AssertionError(f"forbidden side effect: {name}")

    return blocked


def test_ready_fill_and_protective_exit_have_zero_external_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    external_methods = (
        (ExecutionEngine, "execute"),
        (ExecutionManager, "execute"),
        (ExecutionManager, "execute_many"),
        (ExecutionManager, "iter_execute"),
        (OrderManager, "create_order"),
        (OrderManager, "create_market_order"),
        (OrderManager, "create_limit_order"),
        (PaperTradingEngine, "execute"),
        (SmartRouter, "execute"),
        (PaperDriver, "place_order"),
        (PaperDriver, "cancel_order"),
        (ExchangeInterface, "place_order"),
        (ExchangeInterface, "cancel_order"),
        (ExchangeInterface, "get_balance"),
        (ExchangeInterface, "get_positions"),
        (BaseExchange, "connect"),
        (BaseExchange, "create_order"),
        (BaseExchange, "cancel_order"),
        (BaseExchange, "fetch_balance"),
        (BaseExchange, "fetch_positions"),
        (BingXAdapter, "connect"),
        (BingXAdapter, "create_order"),
        (BingXAdapter, "cancel_order"),
        (BingXAdapter, "fetch_balance"),
        (BingXAdapter, "fetch_positions"),
        (BingXAdapter, "get_balance"),
        (BingXAdapter, "get_positions"),
        (BingXAdapter, "close_all_positions"),
        (BingXHttpClient, "request"),
        (BingXHttpClient, "_send"),
        (BingXHttpClient, "_require_credentials"),
        (BingXHttpClient, "place_order"),
        (BingXHttpClient, "cancel_order"),
        (BingXHttpClient, "cancel_all_orders"),
        (BingXHttpClient, "get_balance"),
        (BingXHttpClient, "get_positions"),
        (BingXHttpClient, "close_all_positions"),
        (CCXTExchange, "connect"),
        (CCXTExchange, "create_order"),
        (CCXTExchange, "cancel_order"),
        (CCXTExchange, "fetch_balance"),
        (CCXTExchange, "fetch_positions"),
        (CryptoConnector, "connect"),
        (CryptoConnector, "create_order"),
        (CryptoConnector, "cancel_order"),
        (CryptoConnector, "fetch_balance"),
        (CryptoConnector, "fetch_positions"),
        (ExchangeFactory, "create"),
    )

    with monkeypatch.context() as guarded:
        for owner, method_name in external_methods:
            qualified_name = f"{owner.__name__}.{method_name}"
            guarded.setattr(
                owner,
                method_name,
                _fail_fast(calls, qualified_name),
            )

        for owner, method_name, qualified_name in (
            (socket, "socket", "socket.socket"),
            (socket, "create_connection", "socket.create_connection"),
            (httpx, "request", "httpx.request"),
            (httpx.Client, "request", "httpx.Client.request"),
            (httpx.AsyncClient, "request", "httpx.AsyncClient.request"),
            (websockets, "connect", "websockets.connect"),
            (os, "getenv", "os.getenv"),
            (dotenv, "load_dotenv", "dotenv.load_dotenv"),
            (dotenv, "dotenv_values", "dotenv.dotenv_values"),
            (dotenv, "find_dotenv", "dotenv.find_dotenv"),
            (builtins, "open", "builtins.open"),
            (io, "open", "io.open"),
            (os, "open", "os.open"),
            (Path, "open", "pathlib.Path.open"),
            (Path, "write_text", "pathlib.Path.write_text"),
            (Path, "write_bytes", "pathlib.Path.write_bytes"),
            (threading.Thread, "start", "threading.Thread.start"),
            (_thread, "start_new_thread", "_thread.start_new_thread"),
            (
                ThreadPoolExecutor,
                "submit",
                "concurrent.futures.ThreadPoolExecutor.submit",
            ),
            (asyncio, "create_task", "asyncio.create_task"),
            (asyncio, "ensure_future", "asyncio.ensure_future"),
            (asyncio, "to_thread", "asyncio.to_thread"),
            (
                asyncio.BaseEventLoop,
                "create_task",
                "asyncio.BaseEventLoop.create_task",
            ),
            (
                asyncio.BaseEventLoop,
                "run_in_executor",
                "asyncio.BaseEventLoop.run_in_executor",
            ),
        ):
            guarded.setattr(
                owner,
                method_name,
                _fail_fast(calls, qualified_name),
            )

        coordinator = PaperExecutionCoordinator(_policy(), _account())
        coordinator.initialize()
        coordinator.start()
        submission = coordinator.submit_intent(
            _ready_intent(),
            source_sequence=1,
        )
        assert submission.accepted
        assert submission.order is not None

        entry_events = coordinator.advance_market(
            _event(2, price="100", low="99", high="101")
        )
        exit_events = coordinator.advance_market(
            _event(3, price="120", low="119", high="121")
        )

        assert entry_events
        assert exit_events
        assert len(coordinator.fills) == 2
        assert coordinator.fills[-1].protective
        assert coordinator.fills[-1].trigger == "take_profit"
        assert coordinator.position("BTCUSDT").quantity == 0
        assert coordinator.account.exposure == 0
        coordinator.stop()

    assert calls == []

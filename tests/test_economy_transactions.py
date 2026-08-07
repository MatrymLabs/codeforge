"""Test twin for the idempotent economy transaction boundary."""

from __future__ import annotations

import pytest

from kernel.world.economy_transactions import (
    CurrencyTransfer,
    EconomyTransactionService,
    InMemoryTransactionStore,
    ItemTransfer,
    SqlTransactionStore,
    TransactionError,
    TransactionRequest,
)


def test_currency_and_item_transfer_commits_as_one_receipt() -> None:
    wallets = {"alia": 100, "bram": 10}
    owners = {"ruby": "alia"}
    service = EconomyTransactionService(InMemoryTransactionStore())
    request = TransactionRequest(
        transaction_id="trade-1",
        idempotency_key="trade-request-1",
        actor="alia",
        source="alia",
        destination="bram",
        currency_amount=30,
        item_ids=("ruby",),
        reason="player_trade",
    )

    receipt = service.execute(request, wallets=wallets, item_owners=owners)

    assert receipt.status == "committed"
    assert wallets == {"alia": 70, "bram": 40}
    assert owners["ruby"] == "bram"
    assert [entry.delta for entry in receipt.ledger_entries] == [-30, 30]


def test_exact_replay_returns_receipt_without_duplicate_value() -> None:
    wallets = {"alia": 100, "bram": 0}
    owners = {"ruby": "alia"}
    service = EconomyTransactionService(InMemoryTransactionStore())
    request = TransactionRequest(
        transaction_id="trade-2",
        idempotency_key="trade-request-2",
        actor="alia",
        source="alia",
        destination="bram",
        currency_amount=25,
        item_ids=("ruby",),
        reason="player_trade",
    )

    first = service.execute(request, wallets=wallets, item_owners=owners)
    replay = service.execute(request, wallets=wallets, item_owners=owners)

    assert first.transaction_id == replay.transaction_id
    assert replay.status == "replayed"
    assert wallets == {"alia": 75, "bram": 25}
    assert owners == {"ruby": "bram"}


def test_reusing_idempotency_key_with_changed_request_is_refused() -> None:
    wallets = {"alia": 100, "bram": 0}
    owners = {"ruby": "alia"}
    service = EconomyTransactionService(InMemoryTransactionStore())
    first = TransactionRequest(
        transaction_id="trade-3",
        idempotency_key="trade-request-3",
        actor="alia",
        source="alia",
        destination="bram",
        currency_amount=25,
        item_ids=("ruby",),
    )
    changed = TransactionRequest(
        transaction_id="trade-3-changed",
        idempotency_key="trade-request-3",
        actor="alia",
        source="alia",
        destination="bram",
        currency_amount=50,
        item_ids=("ruby",),
    )
    service.execute(first, wallets=wallets, item_owners=owners)

    with pytest.raises(TransactionError, match="changed request"):
        service.execute(changed, wallets=wallets, item_owners=owners)


def test_invalid_item_or_insufficient_currency_leaves_all_state_untouched() -> None:
    wallets = {"alia": 10, "bram": 0}
    owners = {"ruby": "alia"}
    service = EconomyTransactionService(InMemoryTransactionStore())
    request = TransactionRequest(
        transaction_id="trade-4",
        idempotency_key="trade-request-4",
        actor="alia",
        source="alia",
        destination="bram",
        currency_amount=50,
        item_ids=("missing",),
    )

    with pytest.raises(TransactionError):
        service.execute(request, wallets=wallets, item_owners=owners)

    assert wallets == {"alia": 10, "bram": 0}
    assert owners == {"ruby": "alia"}


def test_sql_store_replays_a_committed_receipt_after_service_recreation() -> None:
    wallets = {"alia": 100, "bram": 0}
    owners = {"ruby": "alia"}
    request = TransactionRequest(
        transaction_id="sql-trade-1",
        idempotency_key="sql-trade-request-1",
        actor="alia",
        source="alia",
        destination="bram",
        currency_amount=20,
        item_ids=("ruby",),
        reason="player_trade",
    )

    EconomyTransactionService(SqlTransactionStore()).execute(
        request, wallets=wallets, item_owners=owners
    )
    owners["ruby"] = "bram"
    replay = EconomyTransactionService(SqlTransactionStore()).execute(
        request, wallets=wallets, item_owners=owners
    )

    assert replay.status == "replayed"
    assert replay.ledger_entries[0].delta == -20


def test_multi_leg_swap_moves_both_sides_as_one_authoritative_receipt() -> None:
    wallets = {"alia": 100, "bram": 80}
    owners = {"ruby": "alia", "sword": "bram"}
    service = EconomyTransactionService(InMemoryTransactionStore())
    request = TransactionRequest(
        transaction_id="swap-1",
        idempotency_key="swap-request-1",
        actor="alia",
        reason="player_trade",
        currency_transfers=(
            CurrencyTransfer("alia", "bram", 30, "player_trade"),
            CurrencyTransfer("bram", "alia", 10, "player_trade"),
        ),
        item_transfers=(
            ItemTransfer("ruby", "alia", "bram"),
            ItemTransfer("sword", "bram", "alia"),
        ),
    )

    receipt = service.execute(request, wallets=wallets, item_owners=owners)

    assert receipt.status == "committed"
    assert wallets == {"alia": 80, "bram": 100}
    assert owners == {"ruby": "bram", "sword": "alia"}
    assert len(receipt.item_transfers) == 2
    assert sum(entry.delta for entry in receipt.ledger_entries) == 0

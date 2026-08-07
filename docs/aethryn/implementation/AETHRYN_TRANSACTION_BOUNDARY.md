# Aethryn Transaction Boundary

The transaction foundation is additive. It does not replace the existing trade, auction, shop, or
crafting commands until those commands can commit gameplay state and ledger state through one
persistence boundary.

## Contract

`TransactionRequest` identifies the transaction id, idempotency key, actor, source, destination,
currency amount, item ids, and reason. `EconomyTransactionService` validates the complete request
before applying copied wallet and item-owner maps. It commits one receipt and signed currency ledger
entries through a `TransactionStore`.

An exact replay returns the original receipt without moving value again. Reusing an idempotency key
with different request data is refused.

## Persistence

`InMemoryTransactionStore` is the deterministic contract adapter used by focused tests.
`SqlTransactionStore` writes `economy_transactions` and `currency_ledger` rows through the existing
SQLAlchemy archive boundary. Migration `d6a7b8c9e0f1` adds both tables and has a tested downgrade.

The SQL store records the transaction and ledger receipt. It does not silently pretend that the
existing process-local Session purse, global item map, character save, or auction escrow is part of
the same SQL transaction.

## Integration gate

Before an existing economy command uses this service in production paths, it must prove:

1. item custody and currency balances are read from one authoritative adapter;
2. gameplay mutation and ledger receipt commit atomically;
3. a retry after disconnect returns the original receipt;
4. a failed persistence commit leaves item and currency state unchanged;
5. reconciliation compares balances, item custody, and ledger entries.

Until those proofs exist, the transaction core is `VERIFIED_PARTIAL`, not a claim that the entire
economy is authoritative.

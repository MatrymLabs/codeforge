"""CARD: auction_store -- persistence for the auction house's escrowed listings.

The storage half of the marketplace. A listing holds an ESCROWED item (a snapshot, like a vaulted
item) plus its seller, price, and expiry beat. The item lives here, out of the world, from listing
to sale-or-return, so it can never be double-sold or duped. A `Listing` value object crosses the
boundary so callers never touch an ORM row; SQLAlchemy and parts.world.db import LAZILY, off the hot
`import forge` path (EXP-003).

buy() removes and returns a listing in one transaction, so two buyers can never both win the same
item. No auth is stored; a listing is gameplay data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Listing:
    """One active auction listing: the escrowed item snapshot, its seller and price."""

    id: int
    seller: str
    price: int
    expiry_beat: int
    item: dict[str, Any]  # the escrowed item snapshot: {prototype, name, mods, rarity}


def _to_listing(row: Any) -> Listing:
    try:
        mods = json.loads(row.mods)
    except (ValueError, TypeError):
        mods = {}
    item = {
        "prototype": row.prototype,
        "name": row.name,
        "mods": mods if isinstance(mods, dict) else {},
        "rarity": row.rarity,
    }
    return Listing(row.id, row.seller, row.price, row.expiry_beat, item)


def create(seller: str, item: dict[str, Any], price: int, expiry_beat: int) -> int:
    """List an escrowed item for sale and return the new listing id."""
    from parts.world.db import AuctionRow, open_archive_session

    with open_archive_session() as db:
        row = AuctionRow(
            seller=seller,
            price=price,
            expiry_beat=expiry_beat,
            prototype=str(item["prototype"]),
            name=str(item.get("name", "")),
            mods=json.dumps(item.get("mods", {}), sort_keys=True),
            rarity=str(item.get("rarity", "common")),
        )
        db.add(row)
        db.commit()
        return row.id


def active() -> list[Listing]:
    """Every live listing, oldest first, for the browse view."""
    from sqlalchemy import select

    from parts.world.db import AuctionRow, open_archive_session

    with open_archive_session() as db:
        rows = db.scalars(select(AuctionRow).order_by(AuctionRow.id))
        return [_to_listing(row) for row in rows]


def get(listing_id: int) -> Listing | None:
    """One listing by id, or None if it is gone (sold or expired)."""
    from parts.world.db import AuctionRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(AuctionRow, listing_id)
        return _to_listing(row) if row is not None else None


def buy(listing_id: int) -> Listing | None:
    """Remove and return a listing in one transaction (a sale). None if it is already gone, so two
    buyers can never both win the same item."""
    from parts.world.db import AuctionRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(AuctionRow, listing_id)
        if row is None:
            return None
        listing = _to_listing(row)
        db.delete(row)
        db.commit()
        return listing


def expired(now_beat: int) -> list[Listing]:
    """Every listing whose expiry beat has passed, for the sweep to return to its seller."""
    from sqlalchemy import select

    from parts.world.db import AuctionRow, open_archive_session

    with open_archive_session() as db:
        rows = db.scalars(select(AuctionRow).where(AuctionRow.expiry_beat <= now_beat))
        return [_to_listing(row) for row in rows]


def remove(listing_id: int) -> None:
    """Delete a listing by id (after its item was returned on expiry). A no-op if already gone."""
    from parts.world.db import AuctionRow, open_archive_session

    with open_archive_session() as db:
        row = db.get(AuctionRow, listing_id)
        if row is not None:
            db.delete(row)
            db.commit()

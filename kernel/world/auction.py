"""CARD: auction -- the marketplace: list an item for coin, buy another's, expiry returns unsold.

The economy's flagship, built on everything the persistence keystone unlocked. Listing an item
ESCROWS it: a snapshot goes onto the auction table and the live instance leaves your world, so it
cannot be double-sold. A buyer pays coin (credited to the seller whether they are online or not) and
re-clones the item into their bag. A listing lapses after AUCTION_BEATS world beats; a scheduler
sweep then MAILS the item back to its seller (reusing mail attachments), so nothing is ever lost.

It composes the parts already built: auction_store for the escrow rows, characters.snapshot_item /
reclone_item for the item, the CharacterStore's add_coins to pay an offline seller, mail_store for
the expiry return, and the scheduler for the sweep. It moves coin and items only through these
validated seams, never fabricating either.
"""

from __future__ import annotations

from datetime import UTC, datetime

from kernel.world.session import Session, sentence_case

AUCTION_BEATS = 500  # how many world beats a listing lives before it lapses and is mailed back
SWEEP_EVERY = 50  # how often (in beats) the scheduler sweeps for lapsed listings


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_item(session: Session, arg: str) -> str:
    """`auction list <item> <price>`: escrow a carried item for sale at a coin price. Refused for a
    bad price, a worn item, or one you are not carrying."""
    from kernel.world import auction_store, climate
    from kernel.world.characters import snapshot_item
    from kernel.world.items import ITEMS, carrier, trace_item

    parts = arg.rsplit(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        return "List what, for how much? (auction list <item> <price>)"
    item_kw, price = parts[0].strip().lower(), int(parts[1])
    if price <= 0:
        return "A price must be a positive number of coins."
    iid = trace_item(item_kw, carrier(session.player_id))
    if iid is None:
        return "You aren't carrying that."
    if iid in set(session.equipped.values()):
        return "That is worn. Unequip it before you list it."
    snapshot = snapshot_item(iid)
    if snapshot is None:
        return "You aren't carrying that."
    name = ITEMS[iid]["name"]
    auction_store.create(session.player_id, snapshot, price, climate.now() + AUCTION_BEATS)
    ITEMS.pop(iid, None)  # escrowed: it leaves the world until sold or returned
    return f"You list {name} on the auction house for {price} coins."


def browse(session: Session) -> str:
    """`auction`: the live listings, numbered by id, with price and seller."""
    from kernel.world import auction_store

    listings = auction_store.active()
    if not listings:
        return "The auction house is empty. (auction list <item> <price>)"
    lines = [f"Auction house ({len(listings)} listing(s)):"]
    for listing in listings:
        who = sentence_case(session.player_id) if listing.seller == session.player_id else "another"
        name = sentence_case(str(listing.item["name"]))
        lines.append(f"  #{listing.id}. {name} - {listing.price} coins (from {who})")
    lines.append("(auction buy <#>, auction list <item> <price>)")
    return "\n".join(lines)


def buy(session: Session, id_word: str) -> str:
    """`auction buy <#>`: buy a listing. Pays the seller (online or not) and re-clones the item into
    your bag. Refused for a bad number, your own listing, or too little coin."""
    from kernel.world import auction_store
    from kernel.world.characters import _default_store, reclone_item, save_character
    from kernel.world.events import announce_to
    from kernel.world.items import carrier
    from kernel.world.session import SESSIONS, display_name

    try:
        listing_id = int(id_word.strip())
    except (ValueError, AttributeError):
        return "Buy which listing? (auction buy <#>)"
    listing = auction_store.get(listing_id)
    if listing is None:
        return "There is no such listing. (auction to browse)"
    if listing.seller == session.player_id:
        return "That is your own listing. (auction cancel is not needed; it returns on expiry)"
    if session.coins < listing.price:
        return f"You cannot afford that ({listing.price} coins; you have {session.coins})."
    sold = auction_store.buy(listing_id)  # atomic remove: nobody else can win it now
    if sold is None:
        return "That listing was just taken."
    session.coins -= sold.price  # the buyer pays
    save_character(session)
    seller_session = SESSIONS.get(sold.seller)  # the seller is paid, online or not
    if seller_session is not None:
        seller_session.coins += sold.price
        save_character(seller_session)
        announce_to(
            [sold.seller],
            f"\n{display_name(session.player_id)} bought your {sold.item['name']} for "
            f"{sold.price} coins.",
        )
    else:
        _default_store().add_coins(sold.seller, sold.price)
    reclone_item(sold.item, carrier(session.player_id))  # the item is yours
    from kernel.world import audit

    audit.record(  # the coin/item move is on record for economy accounting
        session.player_id,
        "auction-buy",
        f"{sold.item['name']} from {sold.seller} for {sold.price}",
    )
    return f"You buy {sold.item['name']} for {sold.price} coins."


def sweep_expired() -> int:
    """Return every lapsed listing to its seller by mail (with the item attached), and remove it.
    The scheduler's recurring job. Returns how many were returned. Reuses mail attachments, so a
    seller collects an unsold item on their own time, online or not."""
    from kernel.world import auction_store, climate, mail_store

    returned = 0
    for listing in auction_store.expired(climate.now()):
        body = f"Your auction of {listing.item['name']} expired unsold. Your item is returned."
        mail_store.send(
            listing.seller, "the auction house", body, sent_utc=_stamp(), attachment=listing.item
        )
        auction_store.remove(listing.id)
        returned += 1
    return returned


def register_sweep() -> None:
    """Arm the recurring expiry sweep on the scheduler (called once at world assembly)."""
    from kernel.world import scheduler

    scheduler.schedule(SWEEP_EVERY, sweep_expired, every=SWEEP_EVERY)

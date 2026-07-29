"""CARD: metrics -- a live-ops snapshot of the world, read from canonical storage.

Phase 3 observability. A single read-only projection of the numbers an operator watches: how many
heroes exist, how much coin is in circulation (the economy's faucet-vs-sink health the sink/faucet
model needs), how many guilds, live auction listings, letters in flight, and standing bans. It all
comes from SQL, not live sessions, so it is available to any process that shares the database (the
admin surface, the dashboard) without the live-roster bus (a Phase-4 seam).

Read-only and derived: `snapshot` computes counts and sums with the database's own aggregates (never
by loading every row), and mutates nothing. Concurrent-players is deliberately absent here: it needs
the live SESSIONS map, which only the gateway process holds until the shared bus exists.
"""

from __future__ import annotations


def snapshot() -> dict[str, int]:
    """The current world metrics as {name: count}. Aggregate queries only, so it stays cheap even as
    the tables grow: characters + total coin in circulation, guilds + their treasuries, live auction
    listings, mail in flight, and standing bans."""
    from sqlalchemy import func, select

    from parts.world.db import (
        AuctionRow,
        BanRow,
        CharacterRow,
        GuildRow,
        MailRow,
        open_archive_session,
    )

    with open_archive_session() as db:

        def _count(model: type) -> int:
            return db.scalar(select(func.count()).select_from(model)) or 0

        def _sum(column: object) -> int:
            return db.scalar(select(func.coalesce(func.sum(column), 0))) or 0

        purse_coin = _sum(CharacterRow.coins)
        guild_coin = _sum(GuildRow.coins)
        return {
            "characters": _count(CharacterRow),
            "coins_in_circulation": purse_coin + guild_coin,
            "guild_treasuries": guild_coin,
            "guilds": _count(GuildRow),
            "auction_listings": _count(AuctionRow),
            "mail_in_flight": _count(MailRow),
            "bans": _count(BanRow),
        }


def render() -> str:
    """The metrics snapshot as a labelled block for the `@metrics` verb."""
    snap = snapshot()
    lines = ["World metrics (from storage):"]
    lines.append(f"  Characters:          {snap['characters']}")
    lines.append(f"  Coins in circulation: {snap['coins_in_circulation']}")
    treas = snap["guild_treasuries"]
    lines.append(f"  Guilds:              {snap['guilds']} (treasuries: {treas})")
    lines.append(f"  Auction listings:    {snap['auction_listings']}")
    lines.append(f"  Mail in flight:      {snap['mail_in_flight']}")
    lines.append(f"  Bans:                {snap['bans']}")
    return "\n".join(lines)

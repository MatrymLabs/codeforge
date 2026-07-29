"""CARD: metrics -- a live-ops snapshot of the world, read from canonical storage.

Phase 3 observability, now with the Phase-4 live-roster count folded in. A single read-only
projection of the numbers an operator watches: how many heroes exist, how much coin is circulating
(the economy's faucet-vs-sink health the sink/faucet model needs), how many guilds, live auction
listings, letters in flight, standing bans, and how many players are online right now. The stored
figures come from SQL, not live sessions, so they are available to any process that shares the
database; the online count comes from the presence roster on the message bus, so once a broker is
injected it too is a true cross-process figure, not just this gateway's sessions.

Read-only and derived: `snapshot` computes counts and sums with the database's own aggregates (never
by loading every row), reads the online count off the bus-fed roster, and mutates nothing. The
concurrent-player figure the bus made possible is the one number this panel could not name before.
"""

from __future__ import annotations


def snapshot() -> dict[str, int]:
    """The current world metrics as {name: count}. Aggregate queries only, so it stays cheap even as
    the tables grow: characters + total coin in circulation, guilds + their treasuries, live auction
    listings, mail in flight, standing bans, and players online now (off the bus-fed roster)."""
    from sqlalchemy import func, select

    from parts.world import presence
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
            "players_online": presence.count(),  # bus-fed roster; cross-process once a broker set
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
    lines = ["World metrics:"]
    lines.append(f"  Characters:          {snap['characters']}")
    lines.append(f"  Players online:      {snap['players_online']}")
    lines.append(f"  Coins in circulation: {snap['coins_in_circulation']}")
    treas = snap["guild_treasuries"]
    lines.append(f"  Guilds:              {snap['guilds']} (treasuries: {treas})")
    lines.append(f"  Auction listings:    {snap['auction_listings']}")
    lines.append(f"  Mail in flight:      {snap['mail_in_flight']}")
    lines.append(f"  Bans:                {snap['bans']}")
    return "\n".join(lines)

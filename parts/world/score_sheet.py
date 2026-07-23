"""CARD: score_sheet -- the character score-sheet text renderer (a fixed-width projection).

The renderer half of the score sheet, split from its view model (parts/world/score_sheet_model.py).
It consumes only a `CharacterSheet` -- never the database or the Session -- so the same sheet
renders from live state, a fixture, or a future personnel record without change (the Hardware
Store stance). `render_score_sheet` turns a view model into a fixed-width sheet in one of six
modes.

It is built to survive real data: long names are clipped to their column instead of breaking
the frame, a missing secondary job reads "Unassigned", absent MP is omitted, and an unknown
resistance renders as "?" rather than crashing. Formatting is pinned by one golden snapshot;
content is pinned by focused field tests. Formulas live elsewhere -- this part only displays.
"""

from __future__ import annotations

from parts.world.score_sheet_model import ATTR_ORDER, RESIST_ORDER, CharacterSheet

_WIDTH = 70  # the frame width
_LEFT = 28  # left column width; the divider sits at this index
_RIGHT = _WIDTH - _LEFT - 1  # right column width (accounts for the divider)


# --- rendering helpers -----------------------------------------------------------
def _fit(text: str, width: int) -> str:
    """Keep a cell inside its column: clip long text rather than break the frame."""
    return text if len(text) <= width else text[:width]


def _frame() -> str:
    return "=" * _WIDTH


def _divider() -> str:
    return "-" * _LEFT + "+" + "-" * _RIGHT


def _twocol(left: str, right: str, left_width: int = _LEFT) -> str:
    """One divided row: left column, the `|` divider, right column. Trailing space trimmed.

    `left_width` is parametrized because the equipment block needs a wider left column so long
    item names fit rather than clip -- the stat blocks stay at the default divider column.
    """
    right_width = _WIDTH - left_width - 1
    return f"{_fit(left, left_width):<{left_width}}|{_fit(right, right_width)}".rstrip()


def _zip_block(lefts: list[str], rights: list[str], left_width: int = _LEFT) -> list[str]:
    """Pair two column-lists into divided rows, padding the shorter side with blanks."""
    rows = max(len(lefts), len(rights))
    lefts = lefts + [""] * (rows - len(lefts))
    rights = rights + [""] * (rows - len(rights))
    return [_twocol(left, right, left_width) for left, right in zip(lefts, rights, strict=True)]


def _header(sheet: CharacterSheet) -> str:
    """Name on the left, player level and active job on the right, across the full width."""
    left = f" {sheet.display_name}"
    right = f"PLvl {sheet.player_level}   Job: {sheet.primary_job} (Lv {sheet.primary_job_level})"
    pad = max(1, _WIDTH - len(left) - len(right))
    return _fit(f"{left}{' ' * pad}{right}", _WIDTH)


def _resource_lefts(sheet: CharacterSheet) -> list[str]:
    lines = [f" HP   {sheet.hp[0]} / {sheet.hp[1]}"]
    if sheet.mp is not None:
        lines.append(f" MP   {sheet.mp[0]} / {sheet.mp[1]}")
    if sheet.power is not None:
        lines.append(f" PC   {sheet.power[0]} / {sheet.power[1]}")  # Power Cells
    lines.append(f" Race : {sheet.race}")
    if sheet.guild:
        lines.append(f" Guild : {sheet.guild}")
    if sheet.rank_title:
        lines.append(f" {sheet.primary_job} Rank : {sheet.rank_title}")
    return lines


def _resource_rights(sheet: CharacterSheet) -> list[str]:
    xp_next = f"  (next PLvl @ {sheet.next_level_xp:,})" if sheet.next_level_xp is not None else ""
    lines = [
        f"   XP   {sheet.current_xp:,}{xp_next}",
        f"   JP   {sheet.jp:,}  ({sheet.primary_job})",
    ]
    lines += [f"   TP ({tp.label})   {tp.current} / {tp.required}" for tp in sheet.tp_rows]
    return lines


def _attr_lefts(sheet: CharacterSheet) -> list[str]:
    return [f" {code:<5}{sheet.attributes.get(code, 0):>6}" for code in ATTR_ORDER]


def _loadout_rights(sheet: CharacterSheet) -> list[str]:
    secondary = sheet.secondary_job or "Unassigned"
    return [
        f"   Primary Job    {sheet.primary_job} (Lv {sheet.primary_job_level})",
        f"   Secondary Job  {secondary}",
        f"   Counter        {sheet.counter}",
        f"   Movement       {sheet.movement}",
        f"   Inherent       {sheet.inherent}",
        f'   Signature      "{sheet.signature}"',
    ]


def _derived_block(sheet: CharacterSheet) -> list[str]:
    lefts = [f" {code:<7}{sheet.derived.get(code, 0):>6}" for code in ("ATK", "EVA", "ACC")]
    rights = [f"   {code:<7}{sheet.derived.get(code, 0):>6}" for code in ("DEF", "MAG DEF")]
    return _zip_block(lefts, rights)


def _equipment_lefts(sheet: CharacterSheet) -> list[str]:
    eq = sheet.equipment
    slots = [
        ("Weapon", eq.weapon),
        ("Body", eq.body),
        ("Head", eq.head),
        ("Arm", eq.arm),
        ("Accessory 1", eq.accessory_1),
        ("Accessory 2", eq.accessory_2),
    ]
    lines = [" Equipment"]
    lines += [f" {slot} : {item}" for slot, item in slots if item]
    if sheet.key_item:
        lines.append(f" Key Item : {sheet.key_item}")
    return lines


_EQUIP_LEFT = 39  # a wider left column so long equipment names fit instead of clipping


def _resist_rights(sheet: CharacterSheet) -> list[str]:
    lines = ["  Elemental / Status Res."]
    for i in range(0, len(RESIST_ORDER), 2):
        a = RESIST_ORDER[i]
        b = RESIST_ORDER[i + 1]
        av = sheet.resistances.get(a, "?")
        bv = sheet.resistances.get(b, "?")
        lines.append(f"  {a}:{av:<9} {b}:{bv}")
    return lines


def _render_standard(sheet: CharacterSheet) -> str:
    parts = [
        _frame(),
        _header(sheet),
        _frame(),
        *_zip_block(_resource_lefts(sheet), _resource_rights(sheet)),
        _divider(),
        *_zip_block(_attr_lefts(sheet), _loadout_rights(sheet)),
        _divider(),
        *_derived_block(sheet),
        _divider(),
        *_zip_block(_equipment_lefts(sheet), _resist_rights(sheet), _EQUIP_LEFT),
        _frame(),
    ]
    return "\n".join(parts)


def _render_compact(sheet: CharacterSheet) -> str:
    """Identity, level, job, HP/MP, core stats, and the primary loadout -- the quick glance."""
    parts = [
        _frame(),
        _header(sheet),
        _frame(),
        *_zip_block(_resource_lefts(sheet)[: (2 if sheet.mp is not None else 1)], []),
        _divider(),
        *_zip_block(_attr_lefts(sheet), _loadout_rights(sheet)),
        _frame(),
    ]
    return "\n".join(parts)


def _render_jobs(sheet: CharacterSheet) -> str:
    """Every unlocked job with its level, JP, and TP -- and which is active."""
    lines = [_frame(), _header(sheet), _frame(), " Jobs"]
    for jl in sheet.jobs:
        active = "  (active)" if jl.name == sheet.primary_job else ""
        lines.append(f"   {jl.name:<16} Lv {jl.level:<3} JP {jl.jp:<6} TP {jl.tp}{active}")
    if not sheet.jobs:
        lines.append("   (no jobs unlocked yet)")
    lines.append(_frame())
    return "\n".join(lines)


def _render_equipment(sheet: CharacterSheet) -> str:
    """The worn gear and the derived stats it shapes -- equipment and its effects."""
    parts = [
        _frame(),
        _header(sheet),
        _frame(),
        *_zip_block(_equipment_lefts(sheet), [], _EQUIP_LEFT),
        _divider(),
        *_derived_block(sheet),
        _frame(),
    ]
    return "\n".join(parts)


def _render_resistances(sheet: CharacterSheet) -> str:
    """The elemental and status resistance grid."""
    lines = [_frame(), _header(sheet), _frame()]
    lines += [line.replace("  ", " ", 1) for line in _resist_rights(sheet)]
    lines.append(_frame())
    return "\n".join(lines)


def _render_developer(sheet: CharacterSheet) -> str:
    """Raw and derived values with their sources -- the internal view (prototype formulas)."""
    worn = {slot: item for slot, item in vars(sheet.equipment).items() if item}
    resisted = {code: lvl for code, lvl in sheet.resistances.items() if lvl != "Normal"}
    lines = [
        _frame(),
        f" DEVELOPER VIEW -- {sheet.display_name}",
        _frame(),
        f" player_level={sheet.player_level} xp={sheet.current_xp} next={sheet.next_level_xp}",
        f" job={sheet.primary_job!r} job_level={sheet.primary_job_level} jp={sheet.jp}",
        f" attributes={sheet.attributes}",
        f" derived={sheet.derived}  (prototype_balance_only formulas -- ADR-0006)",
        f" equipped={worn}",
        f" resistances(non-normal)={resisted}",
        _frame(),
    ]
    return "\n".join(lines)


_MODES = {
    "standard": _render_standard,
    "compact": _render_compact,
    "jobs": _render_jobs,
    "equipment": _render_equipment,
    "resistances": _render_resistances,
    "developer": _render_developer,
}


def render_score_sheet(sheet: CharacterSheet, display_mode: str = "standard") -> str:
    """Render a character sheet in the requested mode: standard, compact, jobs, equipment,
    resistances, or developer. An unknown mode is refused loud."""
    renderer = _MODES.get(display_mode)
    if renderer is None:
        raise ValueError(f"unknown display_mode {display_mode!r}; available: {sorted(_MODES)}")
    return renderer(sheet)

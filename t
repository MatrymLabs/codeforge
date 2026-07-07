[1mdiff --git a/forge.py b/forge.py[m
[1mindex 3f7a364..a564786 100644[m
[1m--- a/forge.py[m
[1m+++ b/forge.py[m
[36m@@ -1,63 +1,6 @@[m
[31m-"""CodeForge: smallest playable loop.[m
[32m+[m[32m"""CodeForge entry point: the power switch. All parts live in parts/."""[m
 [m
[31m-Current skills baked in:[m
[31m-- world as data (WORLD dict = proto world graph)[m
[31m-- render/state separation (render_room is a projection)[m
[31m-- direction normalization (DIRECTIONS = proto MUD-IL alias table)[m
[31m-- movement isolated in try_move (recognition vs execution seam)[m
[31m-"""[m
[31m-[m
[31m-# --- World data (this becomes the world graph, then Seed YAML, then DB rows) ---[m
[31m-WORLD = {[m
[31m-    "forge": {[m
[31m-        "name": "The Cold Forge",[m
[31m-        "desc": "You stand beside a cold forge beneath unfamiliar stars.\n"[m
[31m-                'A brass plaque on the anvil reads: "Every world begins as a spark."',[m
[31m-        "exits": {"north": "courtyard", "down": "cellar"},[m
[31m-    },[m
[31m-    "courtyard": {[m
[31m-        "name": "Broken Courtyard",[m
[31m-        "desc": "Cracked flagstones stretch under a violet sky. Wind hums through the ruins.",[m
[31m-        "exits": {"south": "forge", "east": "library"},[m
[31m-    },[m
[31m-    "library": {[m
[31m-        "name": "The Old Library",[m
[31m-        "desc": "Dust drifts between towering shelves. An oak door in the back is sealed shut.",[m
[31m-        "exits": {"west": "courtyard"},[m
[31m-    },[m
[31m-    "cellar": {[m
[31m-        "name": "The Forge Cellar",[m
[31m-        "desc": "Cool darkness. Crates of unworked ore line the walls, waiting for a purpose.",[m
[31m-        "exits": {"up": "forge"},[m
[31m-    },[m
[31m-}[m
[31m-[m
[31m-# --- Normalization layer: many surface forms -> one canonical direction ---[m
[31m-DIRECTIONS = {[m
[31m-    "north": "north", "n": "north",[m
[31m-    "south": "south", "s": "south",[m
[31m-    "east": "east",  "e": "east",[m
[31m-    "west": "west",  "w": "west",[m
[31m-    "up": "up",      "u": "up",[m
[31m-    "down": "down",  "d": "down",[m
[31m-}[m
[31m-[m
[31m-[m
[31m-def render_room(room_id: str) -> str:[m
[31m-    room = WORLD[room_id][m
[31m-    exits = ", ".join(room["exits"]) or "none"[m
[31m-    return f"\n== {room['name']} ==\n{room['desc']}\nExits: {exits}"[m
[31m-[m
[31m-[m
[31m-def try_move(location: str, direction: str) -> str:[m
[31m-    """Return the new room id, or the old one if movement fails."""[m
[31m-    exits = WORLD[location]["exits"][m
[31m-    if direction in exits:[m
[31m-        new_location = exits[direction][m
[31m-        print(render_room(new_location))[m
[31m-        return new_location[m
[31m-    print("You can't go that way.")[m
[31m-    return location[m
[32m+[m[32mfrom parts.world import DIRECTIONS, render_room, try_move[m
 [m
 [m
 def game_loop() -> None:[m
[36m@@ -90,4 +33,4 @@[m [mdef game_loop() -> None:[m
 [m
 [m
 if __name__ == "__main__":[m
[31m-    game_loop()[m
\ No newline at end of file[m
[32m+[m[32m    game_loop()[m
[1mdiff --git a/parts/items.py b/parts/items.py[m
[1mindex e69de29..203f21c 100644[m
[1m--- a/parts/items.py[m
[1m+++ b/parts/items.py[m
[36m@@ -0,0 +1,59 @@[m
[32m+[m[32m"""CARD: items -- objects, containment, take/drop/inventory.[m
[32m+[m
[32m+[m[32mDesign rule: an item stores its own location. Nothing else does.[m
[32m+[m[32mLocations are tagged strings: "room:library" or "player".[m
[32m+[m[32mFunctions RETURN text; the game loop decides what to print.[m
[32m+[m[32m"""[m
[32m+[m
[32m+[m[32mITEMS = {[m
[32m+[m[32m    "copper_key": {[m
[32m+[m[32m        "name": "a copper key",[m
[32m+[m[32m        "keywords": ["key", "copper", "copper key"],[m
[32m+[m[32m        "location": "room:library",[m
[32m+[m[32m    },[m
[32m+[m[32m}[m
[32m+[m
[32m+[m
[32m+[m[32mdef items_in(location: str) -> list[str]:[m
[32m+[m[32m    """All item ids currently at a location. Containment is a query."""[m
[32m+[m[32m    return [iid for iid, item in ITEMS.items() if item["location"] == location][m
[32m+[m
[32m+[m
[32m+[m[32mdef find_item(word: str, location: str) -> str | None:[m
[32m+[m[32m    """Match a player's word against keywords of items at a location."""[m
[32m+[m[32m    for iid in items_in(location):[m
[32m+[m[32m        if word in ITEMS[iid]["keywords"]:[m
[32m+[m[32m            return iid[m
[32m+[m[32m    return None[m
[32m+[m
[32m+[m
[32m+[m[32mdef take(word: str, room_id: str) -> str:[m
[32m+[m[32m    iid = find_item(word, f"room:{room_id}")[m
[32m+[m[32m    if iid is None:[m
[32m+[m[32m        return "You don't see that here."[m
[32m+[m[32m    ITEMS[iid]["location"] = "player"[m
[32m+[m[32m    return f"You take {ITEMS[iid]['name']}."[m
[32m+[m
[32m+[m
[32m+[m[32mdef drop(word: str, room_id: str) -> str:[m
[32m+[m[32m    iid = find_item(word, "player")[m
[32m+[m[32m    if iid is None:[m
[32m+[m[32m        return "You aren't carrying that."[m
[32m+[m[32m    ITEMS[iid]["location"] = f"room:{room_id}"[m
[32m+[m[32m    return f"You drop {ITEMS[iid]['name']}."[m
[32m+[m
[32m+[m
[32m+[m[32mdef inventory_text() -> str:[m
[32m+[m[32m    carried = items_in("player")[m
[32m+[m[32m    if not carried:[m
[32m+[m[32m        return "You are carrying nothing."[m
[32m+[m[32m    lines = "\n".join(f"  {ITEMS[iid]['name']}" for iid in carried)[m
[32m+[m[32m    return f"You are carrying:\n{lines}"[m
[32m+[m
[32m+[m
[32m+[m[32mdef room_items_text(room_id: str) -> str:[m
[32m+[m[32m    """Extra line(s) for room rendering. Empty string if nothing here."""[m
[32m+[m[32m    here = items_in(f"room:{room_id}")[m
[32m+[m[32m    if not here:[m
[32m+[m[32m        return ""[m
[32m+[m[32m    return "\n".join(f"You see {ITEMS[iid]['name']} here." for iid in here)[m
[1mdiff --git a/pyproject.toml b/pyproject.toml[m
[1mindex e69de29..60c16f0 100644[m
[1m--- a/pyproject.toml[m
[1m+++ b/pyproject.toml[m
[36m@@ -0,0 +1,14 @@[m
[32m+[m[32m[project][m
[32m+[m[32mname = "codeforge"[m
[32m+[m[32mversion = "0.1.0"[m
[32m+[m[32mdescription = "A Python-native modular MUD engine and reusable code workshop."[m
[32m+[m[32mrequires-python = ">=3.13"[m
[32m+[m
[32m+[m[32m[tool.ruff][m
[32m+[m[32mline-length = 100[m
[32m+[m[32mtarget-version = "py313"[m
[32m+[m
[32m+[m[32m[tool.ruff.lint][m
[32m+[m[32m# E/F: core errors  I: import sorting  UP: modernize syntax[m
[32m+[m[32m# B: common bug patterns  SIM: simplifications[m
[32m+[m[32mselect = ["E", "F", "I", "UP", "B", "SIM"][m
\ No newline at end of file[m
[1mdiff --git a/tests/test_items.py b/tests/test_items.py[m
[1mindex e69de29..5ec2762 100644[m
[1m--- a/tests/test_items.py[m
[1m+++ b/tests/test_items.py[m
[36m@@ -0,0 +1,45 @@[m
[32m+[m[32m"""Test twin for parts/items.py -- containment and item commands."""[m
[32m+[m
[32m+[m[32mimport copy[m
[32m+[m
[32m+[m[32mimport pytest[m
[32m+[m
[32m+[m[32mfrom parts import items[m
[32m+[m[32mfrom parts.items import drop, inventory_text, items_in, take[m
[32m+[m
[32m+[m
[32m+[m[32m@pytest.fixture(autouse=True)[m
[32m+[m[32mdef fresh_world():[m
[32m+[m[32m    """Snapshot ITEMS before each test, restore after. No leakage."""[m
[32m+[m[32m    snapshot = copy.deepcopy(items.ITEMS)[m
[32m+[m[32m    yield[m
[32m+[m[32m    items.ITEMS = snapshot[m
[32m+[m
[32m+[m
[32m+[m[32mdef test_key_starts_in_library():[m
[32m+[m[32m    assert "copper_key" in items_in("room:library")[m
[32m+[m
[32m+[m
[32m+[m[32mdef test_take_moves_key_to_player():[m
[32m+[m[32m    result = take("key", "library")[m
[32m+[m[32m    assert "take" in result[m
[32m+[m[32m    assert items.ITEMS["copper_key"]["location"] == "player"[m
[32m+[m
[32m+[m
[32m+[m[32mdef test_take_fails_in_wrong_room():[m
[32m+[m[32m    result = take("key", "forge")[m
[32m+[m[32m    assert result == "You don't see that here."[m
[32m+[m[32m    assert items.ITEMS["copper_key"]["location"] == "room:library"[m
[32m+[m
[32m+[m
[32m+[m[32mdef test_drop_returns_key_to_room():[m
[32m+[m[32m    take("key", "library")[m
[32m+[m[32m    result = drop("key", "cellar")[m
[32m+[m[32m    assert "drop" in result[m
[32m+[m[32m    assert items.ITEMS["copper_key"]["location"] == "room:cellar"[m
[32m+[m
[32m+[m
[32m+[m[32mdef test_inventory_empty_then_full():[m
[32m+[m[32m    assert inventory_text() == "You are carrying nothing."[m
[32m+[m[32m    take("key", "library")[m
[32m+[m[32m    assert "copper key" in inventory_text()[m

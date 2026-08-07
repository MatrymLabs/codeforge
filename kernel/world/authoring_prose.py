# ruff: noqa: E501

"""Authored voice layer for the materialized Aethryn world.

The world factories provide topology and population. This module supplies the prose that makes a
place feel authored: each region has a physical identity, a human pressure, a historical shadow,
and a route through the land. The offline materializer bakes these sentences into ordinary seed
records, so player boot never composes them procedurally.

This is deliberately a prose pass, not a canon generator. The Seven Crowns and unresolved questions
remain named as history, evidence, or belief; no local paragraph resolves what the canon leaves open.
"""

from __future__ import annotations

from typing import Any

REGION_VOICES: dict[str, dict[str, Any]] = {
    "veridia": {
        "name": "Veridia",
        "terrain": "Green fields fold around clear rivers, old hedges, and roads worn bright by generations of feet.",
        "weather": "The air smells of wet earth, hearth smoke, and the first rain after a long day.",
        "history": "The old roads are older than the towns that claim them, and some milestones remember a kingdom no one can name.",
        "pressure": "Farmers keep finding worked metal in their furrows, while the river carries ash from somewhere upstream.",
        "route": "Every road here points outward, but the river and the watchtowers keep drawing travellers back to the cradle.",
        "wildlife": (
            "an ember-antler hart",
            "a riverglass fox",
            "a hedgerow wolf",
            "a watchful barrow crow",
        ),
        "warden": "the green-road warden",
        "boss": "the keeper beneath the drowned barrow",
        "wild_line": "It moves through the grass with the confidence of something that knows the old paths better than you do.",
        "foe_line": "The creature has made a territory of the wound, and every step you take tells it that the territory is being tested.",
        "resident_line": "The road has carried more strangers since the old signs began pointing in different directions. We still leave a lamp for them.",
    },
    "duskwood_vale": {
        "name": "Duskwood Vale",
        "terrain": "Black trunks rise from mist and standing water, their roots gripping the valley like fingers around a secret.",
        "weather": "Dusk gathers beneath the canopy even at noon, and rain arrives as a whisper before it becomes a wall.",
        "history": "The forest has grown over roads, shrines, and the foundations of houses whose doors still open on moonless nights.",
        "pressure": "Ravens are carrying bright fragments from the hollow, and the people of the vale disagree about whether to bury them or follow them.",
        "route": "Lanterns, streams, and rope marks are the true map; a straight road is usually the first sign that the wood has noticed you.",
        "wildlife": (
            "a velvet-antler stag",
            "a mireback boar",
            "a lantern-eyed lynx",
            "a rootbound wolf",
        ),
        "warden": "the vale's lantern warden",
        "boss": "the hollow-rooted keeper",
        "wild_line": "Its eyes catch the lantern light and give it back changed, as if the forest has taught it another colour.",
        "foe_line": "Something in the black hollow has learned to imitate a living heartbeat. It does not beat in time with yours.",
        "resident_line": "Do not follow a voice that knows your name in this wood. The trees remember names, but they do not understand people.",
    },
    "caeloria": {
        "name": "Caeloria",
        "terrain": "Golden plains run to chartered roads and high stone towers, with grain fields laid out as carefully as arguments.",
        "weather": "Sunlight comes clean across the heartland, but dust from the high road settles on every window and official seal.",
        "history": "The kingdom built its certainty on records, then discovered that the oldest records disagree with one another in the same handwriting.",
        "pressure": "The Order of Knowing wants every relic catalogued, while farmers and relic hunters keep finding evidence that refuses to stay in its drawer.",
        "route": "The high road is safe enough to invite complacency; every side track leads toward a question the capital would rather classify.",
        "wildlife": (
            "a goldmane aurochs",
            "a charter-hawk",
            "a fieldglass coyote",
            "a brass-winged kestrel",
        ),
        "warden": "the charter-road warden",
        "boss": "the starfall adjudicator",
        "wild_line": "Its hide carries the colour of dry grain and old brass, and it watches the road as if waiting for a ruling.",
        "foe_line": "The ruin's guardian does not roar. It announces a correction, then advances with the calm of a law already passed.",
        "resident_line": "A record is not the truth. It is the shape a truth leaves behind after enough people have needed it to be useful.",
    },
    "eldryn_forest": {
        "name": "Eldryn Forest",
        "terrain": "The forest rises in shelves of ancient green, where enormous roots bridge ravines and the ground remembers every fallen thing.",
        "weather": "Mist hangs in the upper boughs, carrying birdsong, pollen, and the cool mineral scent of deep water.",
        "history": "Eldryn does not conceal the past so much as absorb it; old walls become ridges, machines become nests, and memories become weather.",
        "pressure": "The Greenward Compact is trying to keep the forest alive without deciding which of its engineered lives count as natural.",
        "route": "The safe path changes with growth. Follow the marked roots, not the spaces between them, and never cut a living bridge without leaving an offering.",
        "wildlife": (
            "a moss-crowned elk",
            "a greenmist panther",
            "a pollen drake",
            "a barkhide ursine",
        ),
        "warden": "the root-memory warden",
        "boss": "the rotwood remnant",
        "wild_line": "Leaves tremble along its spine before it moves, as though the forest is giving warning to something that will not listen.",
        "foe_line": "The thing is neither wholly beast nor wholly garden. Its body carries the patient engineering of a civilization that believed growth could be perfected.",
        "resident_line": "The forest does not hate the old machines. It has simply given them new work, and they are not always grateful for the promotion.",
    },
    "frostspire_peaks": {
        "name": "Frostspire Peaks",
        "terrain": "Blue ice and black rock rise into knife-edged peaks, with rope bridges stretched between shelters cut into the snow.",
        "weather": "The wind comes hard enough to strip speech from the mouth, and the cold turns every distant sound into a false direction.",
        "history": "The high passes preserve footprints from expeditions that never returned and signal towers whose lamps still wake beneath the ice.",
        "pressure": "Strongholds compete for ore, heat, and the right to close a pass, while the glaciers retreat from chambers they have guarded for centuries.",
        "route": "The mountain is crossed by patience: cairn, rope, shelter, beacon. Lose one and the open sky becomes a maze.",
        "wildlife": (
            "a frostmane ram",
            "an ice-veined wolf",
            "a snowglass wyvern",
            "a whiteclaw ursine",
        ),
        "warden": "the beacon-pass warden",
        "boss": "the bastion beneath the glacier",
        "wild_line": "Frost has silvered its fur, but not its tracks. Something with this much weight should not be moving so quietly.",
        "foe_line": "Ice has sealed the machine's joints and preserved its old instruction. It still believes the storm is an invading army.",
        "resident_line": "When the beacon burns blue, come home. When it burns white, bring a shovel. When it burns red, do not ask who lit it.",
    },
    "zhaar_desert": {
        "name": "Zhaar Desert",
        "terrain": "Dunes of red and pale salt break around black glass outcrops, with buried streets surfacing whenever the wind changes its mind.",
        "weather": "Daylight burns the eyes and night drains the heat from bone; the horizon is always one mirage farther away than it was.",
        "history": "The desert exposes the old cities a piece at a time, offering a stair, a painted wall, and then the roof of a buried world.",
        "pressure": "Water, salvage rights, and the interpretation of the buried inscriptions keep the caravan cities allied only as long as the next storm is elsewhere.",
        "route": "Travel by shade, star, and memory. A marked dune is a promise made to yesterday and may not survive the afternoon.",
        "wildlife": (
            "a glassback hyena",
            "a red-sand basilisk",
            "a saltwind vulture",
            "an obsidian jackal",
        ),
        "warden": "the red-dune warden",
        "boss": "the obsidian pit's buried judge",
        "wild_line": "Its silhouette breaks into heat shimmer, then gathers again with one more set of teeth than before.",
        "foe_line": "The buried mechanism wakes beneath the sand, not because it senses you, but because your footsteps resemble an old authorization code.",
        "resident_line": "The desert keeps no secrets. It keeps pieces, and waits for a person patient enough to mistake pieces for an answer.",
    },
    "xilnath_jungle": {
        "name": "Xil'nath Jungle",
        "terrain": "Vines climb through the ruins and the ruins climb back, a green architecture of buttress roots, wet stone, and flowering cables.",
        "weather": "Rain falls warm and sudden, shaking silver insects from the canopy while the soil exhales a sweet, medicinal rot.",
        "history": "The Heart of Xil'nath was built to make life abundant; the jungle inherited the work and forgot the difference between care and control.",
        "pressure": "The Greenward Compact, local hunters, and relic surgeons all claim to be protecting the jungle while cutting different pieces from it.",
        "route": "The canopy is a second road. On the ground, follow water and marked resin; above it, trust no bridge that has grown since sunrise.",
        "wildlife": (
            "a bloomback jaguar",
            "a vinejaw saurian",
            "a pollenwing moth",
            "a rootcoil constrictor",
        ),
        "warden": "the living-loom warden",
        "boss": "the heart's unfinished gardener",
        "wild_line": "Flowers open along its shoulders when it inhales. The scent is beautiful, and the instinct to stop breathing is older.",
        "foe_line": "The jungle has made a body around an ancient directive. It does not know whether you are prey, patient, or unfinished work.",
        "resident_line": "If a vine offers you fruit, thank it before you cut it. If it offers you a door, ask what it remembers being on the other side.",
    },
    "thalorin": {
        "name": "Thalorin",
        "terrain": "Grey mountains shoulder one another above moorland, fortress roads, and mine mouths breathing warm iron into the rain.",
        "weather": "Clouds snag on the peaks and break into cold sheets, while the high wind carries hammering from settlements miles away.",
        "history": "Every fort is built over an older foundation. The miners say the deepest stone is not stone at all, but the cooled edge of a machine.",
        "pressure": "The Ashforged Houses contest the mines and the passes, each calling extraction a duty and exhaustion a temporary inconvenience.",
        "route": "The mountain grants passage through gates, ledges, and old military roads. A closed gate is a political statement before it is a physical obstacle.",
        "wildlife": (
            "a thunderhorn goat",
            "an ironhide boar",
            "a moorland wyvern",
            "a coal-eyed wolf",
        ),
        "warden": "the high-pass warden",
        "boss": "the maw beneath Dreadmaw Hold",
        "wild_line": "Its hooves strike sparks from the slate. The echo answers from below, where no herd should be able to stand.",
        "foe_line": "The mine has given the creature a coat of ore and a hunger for the sound of tools. It charges whenever the mountain hears a promise of work.",
        "resident_line": "A mountain is not rich because it contains metal. It is rich because people can leave it alive after taking some metal home.",
    },
    "ashen_wastes": {
        "name": "Ashen Wastes",
        "terrain": "Volcanic flats spread beneath a red sky, broken by slag rivers, half-buried factories, and towers that still cast heatless shadows.",
        "weather": "Ash falls in fine black veils, and the ground pulses with distant pressure before every vent opens.",
        "history": "The Flamewrought Forge once turned raw matter into abundance. Its surviving lines still follow instructions written for a world that no longer exists.",
        "pressure": "The Ashforged Houses want the forge restarted, the Wardens of the Scars want it sealed, and the machines do not recognize either authority.",
        "route": "Cross the waste by cooled basalt, signal mast, and the colour of the smoke. A bright road may be the hottest road.",
        "wildlife": (
            "a cinderhide drake",
            "an ashglass raptor",
            "a slagmaw hound",
            "a furnace-backed tortoise",
        ),
        "warden": "the slag-road warden",
        "boss": "the forge's unfinished master",
        "wild_line": "Heat rolls from its body in waves, carrying the smell of metal and rain that never reaches the ground.",
        "foe_line": "The machine's limbs were made for lifting cities. Its old task has narrowed to anything that moves near the forge.",
        "resident_line": "The forge can make a hundred tools before breakfast. It cannot tell you which one your child needs, and that is the part people keep forgetting.",
    },
    "korvash_highlands": {
        "name": "Korvash Highlands",
        "terrain": "High moors and hard ridges surround a crater where roads once met beneath the command towers of an older world.",
        "weather": "The wind is clean, cold, and merciless, sweeping the grass flat enough to reveal old foundations beneath it.",
        "history": "Korvash Crater was a centre of governance and authorization. The surviving systems still ask who has the right to give an order.",
        "pressure": "The highland houses dispute identity seals, mine claims, and the legitimacy of commands issued by machines no living court can appeal.",
        "route": "The ridges offer long sightlines, but the crater breaks every sense of scale. A nearby tower can take half a day to reach.",
        "wildlife": (
            "a crownback aurochs",
            "a stormhorn ram",
            "a moorfire wolf",
            "an oath-marked wyvern",
        ),
        "warden": "the crater-road warden",
        "boss": "the authorization voice beneath Korvash",
        "wild_line": "Its horns bear old metal rings, each stamped with a mark that resembles a family crest and a machine serial number.",
        "foe_line": "The guardian waits for a command that cannot be authenticated. Every failed challenge makes it more certain that you are the answer.",
        "resident_line": "In Korvash, a name is a key, a promise, and sometimes a door that should have stayed closed.",
    },
    "shattered_isles": {
        "name": "The Shattered Isles",
        "terrain": "Storm-wracked islands rise from dark water, linked by ferries, broken bridges, and gateways that do not always agree on distance.",
        "weather": "Rain comes sideways, the sea flashes with distant fire, and every calm feels borrowed from the next storm.",
        "history": "The Maelstrom Rise once carried ships and people across the world. Its doors still open, but the sea has changed the meaning of elsewhere.",
        "pressure": "The Tidebound League protects passage, pirates tax it, and every faction wants to decide which destinations are safe enough to exist.",
        "route": "Charts, tides, and the colour of a gate's interior light matter equally. A sailor who trusts only one of them is already lost.",
        "wildlife": (
            "a stormfin shark",
            "a saltwing drake",
            "a reefback cragbeast",
            "a lightning eel",
        ),
        "warden": "the tide-gate warden",
        "boss": "the captain beneath Blackreef Citadel",
        "wild_line": "Its skin shines with stormlight. The sea around it goes still, as though even the waves are waiting to see what it will choose.",
        "foe_line": "The old gate has given the creature too many horizons. It attacks every arrival as if the world has finally sent the one it was promised.",
        "resident_line": "A map is a story about where you were brave enough to draw a line. The sea edits the story every night.",
    },
    "skyward_spires": {
        "name": "Skyward Spires",
        "terrain": "Floating islands hang above the clouds on old lift-fields, their broken paths stitched together by bridges of light and wind.",
        "weather": "The sky is bright enough to hurt, the air thin enough to sharpen every breath, and storms move below you like dark continents.",
        "history": "The Spire Nexus coordinated transit, messages, and celestial observation. Some routes still run on schedules meant for a vanished population.",
        "pressure": "The surviving cities need the machinery to remain aloft, but every repair wakes another system whose purpose no one fully understands.",
        "route": "Here, height is geography. A door may lead down to a cloud deck, across an impossible span, or into a station that has been falling for centuries.",
        "wildlife": (
            "a cloudglass mantis",
            "a sunplume drake",
            "a windborne roc",
            "a brassfeather hawk",
        ),
        "warden": "the skychain warden",
        "boss": "the observatory's last navigator",
        "wild_line": "It rides the updraft without moving its wings, a small and deliberate shape against a sky too large to forgive mistakes.",
        "foe_line": "The construct's compass spins when it sees you. It cannot decide whether you are a passenger, a threat, or a missing destination.",
        "resident_line": "Look down once, so you remember the height. Look up twice, because the thing holding us here may be older than the sky.",
    },
    "the_deepreach": {
        "name": "The Deepreach",
        "terrain": "A world beneath the world opens in shelves of basalt, buried cities, mineral rivers, and chambers large enough to have weather.",
        "weather": "Warm drafts rise from fissures and cold air sinks from forgotten shafts, making underground seasons that no surface calendar records.",
        "history": "The Crystal Labyrinth preserved memories, archives, and constructed minds. Its surviving records contradict one another with painful precision.",
        "pressure": "The Deep Archive wants the memories protected, miners want the passages opened, and the Wardens of the Scars fear what the archives remember about the strike.",
        "route": "Depth is not distance here. Mark the return, count the lights, and never trust a corridor that has learned your footsteps.",
        "wildlife": (
            "a lumengrotto crawler",
            "a crystalblind stalker",
            "a basalt tusker",
            "a memory-moth swarm",
        ),
        "warden": "the archive-depth warden",
        "boss": "the memory beneath the labyrinth",
        "wild_line": "Its body is adapted to darkness, but its movements suggest it is following a remembered room rather than the one in front of you.",
        "foe_line": "The construct speaks in fragments of other people's voices. Each one sounds like a warning recorded after the listener was already gone.",
        "resident_line": "Down here, the dark is not empty. It is storage, shelter, and sometimes the only honest witness left.",
    },
    "the_voidscar": {
        "name": "The Voidscar",
        "terrain": "The land breaks into black planes, impossible angles, and horizons that fail to meet, all gathered around the wound below Netharion's Throne.",
        "weather": "Ash falls upward in places. Sound arrives before motion. The light changes when no cloud has crossed the sky.",
        "history": "The God-Mirror was built to create an artificial god. The strike damaged the city, the laws around it, and every answer people have tried to carry out.",
        "pressure": "The Netharian Concord seeks a surviving voice, the Veiled Covenant seeks containment, and the world has not agreed whether either goal is mercy.",
        "route": "Measure travel by anchors, not horizons. A familiar landmark may be closer, farther, or a statement made by the wound itself.",
        "wildlife": (
            "a lawless emberbeast",
            "a voidglass serpent",
            "a throne-scarred hound",
            "a starved echo-form",
        ),
        "warden": "the scar's last warden",
        "boss": "the voice beneath Netharion's Throne",
        "wild_line": "Its outline refuses to settle. You see a beast, then a shadow of a beast, then the space where an answer should be.",
        "foe_line": "The thing does not guard the ruin. It is one of the ruin's remaining questions, given teeth and enough memory to resent being asked.",
        "resident_line": "Do not call the silence proof that Netharion is gone. Do not call it proof that Netharion remains. The Scar punishes certainty first.",
    },
}


ROOM_PROSE: dict[str, str] = {
    "veridia": "Veridia is the kind of country that teaches a traveller to trust roads before it teaches them why roads exist. Greenhold's bells carry across the fields, the river keeps its own old counsel, and the broken barrow at the valley edge refuses to stay merely a grave.",
    "greenhold": "Greenhold's walls are low, practical, and repaired with stones taken from older walls. Behind them, market awnings snap above sacks of grain and river salt; beyond them, the fields look gentle enough to make a person forget that the old road was laid by hands no farmer can name.",
    "elderwatch": "Elderwatch stands beneath an empty tower whose signal brazier has not burned in living memory. The town keeps the tower swept anyway. Every spring, someone finds a fresh footprint on its upper stair.",
    "riverbend": "The river curls around Riverbend in a slow silver loop, carrying willow leaves, fish scales, and things dredged from a buried channel upstream. The landing is busy at dawn and strangely quiet whenever the water runs grey.",
    "sunmeadow": "Sunmeadow's hives line the downs like little painted shrines. Honey, hay, and the warm smell of turned soil make it a peaceful place, which is why the villagers notice immediately when the bees begin returning with black dust on their wings.",
    "the_sunken_barrow": "The Sunken Barrow is not a hill so much as a roof the earth has tried to swallow. Its fallen stones bear a pattern of seven small crowns, and the stair below is dry even when the valley floods.",
    "duskwood_vale": "Duskwood Vale begins where the road loses the sun. Mist lies between the trunks, ravens trade bright fragments over the canopy, and every lantern in the settlements is hung low enough to light a face rather than the trees behind it.",
    "ravenwatch": "Ravenwatch builds its roofs steep and black, both to shed rain and to discourage the ravens from nesting in the chimneys. The people leave scraps on the watchtower steps; the birds return with buttons, teeth, and once a perfect glass key.",
    "moonshade": "Moonshade trades after dark because the lanterns make better meeting places than the daylight does. Its market is a ring of blue lamps around a spring that reflects no stars, even on a clear night.",
    "twilight_grove": "Twilight Grove is hidden behind a stand of silver birch and a path that changes its number of turns. The villagers call the permanent dusk a blessing. Their oldest houses have no windows facing the forest.",
    "the_black_hollow": "The Black Hollow opens beneath a split oak whose roots have grown around worked stone. Warm air rises from the stair with the smell of wet iron, and the tree's leaves turn toward the darkness instead of the sky.",
    "caeloria": "Caeloria is a kingdom arranged like a proof: roads laid straight, fields measured, towers crowned in gold. Every mile marker carries a date, and every date sends someone to the archive to ask what was happening there before the record began.",
    "caeloria_city": "Caeloria City gathers its towers around the high road and calls the arrangement order. Scribes, judges, relic appraisers, and hungry students fill the same squares, all of them certain that the right document will eventually make the past behave.",
    "brightwater": "Brightwater farms the river flats beneath a line of pale mills. The water is clean enough to drink and bright enough at night to show the shapes of old foundations below the surface.",
    "silverwatch": "Silverwatch guards a road that no longer leads where its maps insist. Its watchmen keep two ledgers: one for travellers who arrive, and one for travellers who arrive twice.",
    "westgate": "Westgate is Caeloria's practical face, a town of carts, weigh houses, and tired horses. Its western gate is plated in ancient metal that never rusts, though no one has found a key for the lock at its centre.",
    "starfall_temple": "Starfall Temple stands on a rise where the grass grows in a perfect circle. The priests call it a place of mourning. The astronomers call it a calibration point. Neither group explains the light that moves beneath the floor.",
    "eldryn_forest": "Eldryn Forest has outgrown the word forest. Its roots bridge ravines, its canopy makes weather, and its oldest clearings are ringed with stones that hum when someone speaks about the old civilization.",
    "eldryn_city": "Eldryn City is built in and around living trunks, with halls grown rather than raised. The city has no straight street. Its inhabitants say the forest dislikes being told where to stand.",
    "wildgrowth": "Wildgrowth is a settlement only because the people living there agree to call the same moving patch of ground home. Vines mark the paths, and the paths move when the jungle is hungry.",
    "greenmist": "Greenmist sits beneath a canopy thick enough to turn noon into twilight. Its healers collect dew from leaves that did not exist the night before and keep careful notes about which memories return after drinking it.",
    "the_great_tree": "The Great Tree is less a landmark than a mountain of bark. Its roots have split an ancient transit station, and small lights move inside the trunk in patterns that resemble a city seen from above.",
    "rotwood_deep": "Rotwood Deep begins where healthy trees give way to pale timber and warm breath from below. The old machinery here still tries to prune the forest, but it no longer knows the difference between rot and a person.",
    "frostspire_peaks": "Frostspire Peaks is a country of ice, rope, and exposed black stone. Beacon towers stitch the passes together, and every settlement keeps a spare door ready for a storm that has not happened yet.",
    "frosthold": "Frosthold is carved into the blue face of a glacier and warmed by pipes no living engineer remembers installing. The town's oldest bell rings whenever a chamber shifts beneath the ice.",
    "winters_grasp": "Winter's Grasp clings to a saddle between two peaks. Its hunters tie coloured cords to their weapons so rescuers can tell a body from a snow-covered stone at a distance.",
    "ironwall_pass": "Ironwall Pass is a fortress road with an iron gate at both ends and no visible maker's mark. The gate opens for caravans, but it closes by itself whenever someone speaks the word crown.",
    "glacial_bastion": "The Glacial Bastion is half fortress and half frozen impact site. A blue light pulses under its courtyard, steady as a heartbeat and much too deep to belong to anything alive.",
    "zhaar_desert": "Zhaar Desert reveals the old world by erosion. A red dune becomes a roof, a salt flat becomes a plaza, and an obsidian ridge becomes the wall of a city that was buried standing.",
    "sunscar_city": "Sunscar City is built around wells sunk into a buried avenue. Its market shades are patched from caravan cloth, old banners, and one piece of something that still displays a weather forecast for a sky no one has seen.",
    "red_dunes": "The Red Dunes move like a slow sea around the bones of a city. At sunset, exposed windows catch the light and look briefly occupied.",
    "sandspire_ruins": "Sandspire Ruins rise from the desert in black needles. Their stairways lead down farther than the visible foundations suggest, and every room has a different idea of where north should be.",
    "the_obsidian_pit": "The Obsidian Pit is a wound in the desert floor lined with glass. Heat rises from below without flame, and the deepest walls bear handprints pressed into the stone before it cooled.",
    "scorchstone_keep": "Scorchstone Keep was built to watch the desert and now watches the same three dunes through every window. Its garrison keeps the walls polished because the old mirrors sometimes show a second keep behind them.",
    "xilnath_jungle": "Xil'nath Jungle grows through its ruins with the confidence of a system still receiving instructions. Flowers open in metal sockets, roots drink from old conduits, and the air tastes faintly of medicine.",
    "zulkarak": "Zulkarak is a settlement of rope platforms and woven bridges above ground that floods without warning. The people paint their doors bright colours so the jungle can find them after it moves the houses.",
    "mistvale": "Mistvale gathers around a spring that exhales warm vapour all morning. The healers here have learned to distinguish a useful mutation from a beautiful one, and still get it wrong sometimes.",
    "shifting_canopy": "The Shifting Canopy is a district that cannot keep one shape for long. Walk its bridges twice and you will find different shops, different birds, and the same old stone face watching from the leaves.",
    "heart_of_xilnath": "The Heart of Xil'nath is a green machine without a central switch. Vines pulse through the halls, pools produce food faster than it can be harvested, and something beneath the roots keeps asking the jungle to grow a person.",
    "thalorin": "Thalorin is all high wind, wet stone, and the sound of hammers crossing valleys. The mountain houses measure wealth by the depth of a mine and wisdom by knowing when to stop digging.",
    "stonefang_keep": "Stonefang Keep grips a ridge above the trade road. Its outer wall is new stone laid against a foundation that bears the smooth, seamless curve of something manufactured rather than quarried.",
    "boulderfall": "Boulderfall is a mining town beneath a slope that has never stopped settling. Every house has a bell cord running to the street, and every child learns which bell means rock, fire, or stranger.",
    "khazgor_peaks": "Khazgor Peaks hold the richest visible seams in Thalorin and the worst weather. Miners leave offerings at the tunnel mouths, not to a god, but to the idea that stone can be reasoned with.",
    "dreadmaw_hold": "Dreadmaw Hold was built over a mine whose entrance is shaped like a jaw. The fortress guards the road above while the dark below keeps producing a slow, patient sound like a giant learning to breathe.",
    "irondeep_mines": "Irondeep Mines descend through ore, old rails, and rooms where the walls have been numbered in a language no miner recognizes. The deepest carts return empty but warm.",
    "ashen_wastes": "The Ashen Wastes are what remains when industry outlives its purpose. Slag rivers cool into black roads, factory towers lean over the flats, and the ground remembers every time the forge was fed.",
    "moltenhold": "Moltenhold is a city of heat shields and red stone, built where a lava channel can be made to pass harmlessly beneath a street. Its people keep their doors open to let the ash out and their secrets in.",
    "cragfire": "Cinderfire clings to a volcanic shelf above a field of vents. Children learn to read smoke before they learn letters, and the old workers still sing timing songs for machines that no longer turn.",
    "ashen_monoliths": "The Ashen Monoliths stand in a line across the waste, each one blacker than the ash around it. Their faces are blank until the sun goes down, when faint symbols describe a city that should be somewhere else.",
    "the_flamewrought_forge": "The Flamewrought Forge is a city-sized factory broken open by the strike. Conveyor lines vanish into lava, moulds continue to fill with malformed objects, and a crown-shaped furnace burns without fuel.",
    "the_scorched_gate": "The Scorched Gate is a fortress doorway cut into cooled slag. It opens onto the waste, but the heat on its inner face suggests it once opened into a building much larger than the mountain behind it.",
    "korvash_highlands": "Korvash Highlands spread beneath a hard sky in long moors and ridges. The crater at their centre is visible from almost everywhere, which has made it a landmark, a warning, and an argument about who owns the horizon.",
    "stonehelm": "Stonehelm is a town of oath stones, windbreaks, and long memories. Every public building displays the names of people authorized to speak for it, and some of those names have been crossed out by no living hand.",
    "highreach": "Highreach sits above the cloud line on a shelf of grass and grey rock. The view is magnificent until the old command lights come on below the ridge and begin searching the valley.",
    "thunderhold": "Thunderhold's walls are designed to conduct lightning away from the houses. They work often enough to make people brave and fail often enough to make everyone watch the sky.",
    "shunderhold": "Shunderhold is an older fortress beneath Thunderhold, its name preserved by an error in a surviving register. The lower gates respond to titles rather than keys.",
    "ancient_overlook": "The Ancient Overlook faces Korvash Crater across a sweep of grass. In clear weather, the ruined command towers seem close enough to touch; in poor weather, their voices still carry.",
    "korvash_crater": "Korvash Crater is too regular to be natural and too vast to have been made by any tool still understood. Broken command towers ring its edge, each waiting for an authorization that may have died with its owner.",
    "shattered_isles": "The Shattered Isles are a chain of broken destinations held together by weather, rope, and stubborn navigation. The sea has swallowed streets, but not the old doors that open above it.",
    "stormreach": "Stormreach is built on the highest island in its chain, where lightning rods crown every roof. Its harbour bells ring even when no ships are visible, warning of arrivals from routes that are not on any chart.",
    "saltwind_harbor": "Saltwind Harbor smells of tar, brine, citrus, and hot metal from the gatehouse. Sailors pay for passage in coin, stories, or favours, depending on which tide is listening.",
    "blackreef_citadel": "Blackreef Citadel rises from a reef that was not there on last season's map. Its lower halls are wet with seawater and lit by doors that open onto different storms.",
    "the_maelstrom_rise": "The Maelstrom Rise is a broken ring of towers above a permanent whirlpool. Its gates still promise the world, but the destinations arrive with unfamiliar stars in their eyes.",
    "skyward_spires": "Skyward Spires begin above the cloud deck, where floating islands drift along routes maintained by machines that have outlived their dispatchers. The sky is a road here, and the ground is a rumour below it.",
    "aurelian_city": "Aurelian City hangs from its lift-fields in terraces of pale stone and brass. Its streets are bright with sun, its lower bridges are dark with shadow, and every resident knows the city is travelling even when it appears still.",
    "celestial_observatory": "The Celestial Observatory turns slowly above the clouds, tracking stars whose names were erased from the surviving charts. Its instruments continue to point toward the same empty place.",
    "the_spire_nexus": "The Spire Nexus is a transit cathedral of suspended platforms, signal mirrors, and broken light bridges. A route begins here only after something decides that you belong at the other end.",
    "the_deepreach": "The Deepreach opens beneath the surface in a sequence of worlds rather than a single cavern. Warm rivers, buried roads, and the lights of impossible archives make distance feel like a question.",
    "deepforge_city": "Deepforge City is built around a furnace sunk into the rock. Its people mine by lamplight and memory, and every guild keeps a private map of tunnels that official maps deny exist.",
    "lumengrotto": "Lumengrotto glows with mineral light from pools and crystal veins. The town's archivists dry their records on warm stone, while moths with human voices gather around the pages.",
    "shadowfissure": "Shadowfissure is a split in the Deepreach where light bends away from the walls. Ropes cross it, but the knots on the far side are never the knots anyone tied.",
    "the_crystal_labyrinth": "The Crystal Labyrinth preserves rooms, memories, and the arguments of dead minds. Its walls shine with stored moments, some of them beautiful, some of them still in progress.",
    "the_voidscar": "The Voidscar is the deepest wound in Aethryn, a place where distance, light, and cause do not always agree. Nothing here is proof of what happened, but everything here is evidence that something did.",
    "voidspire": "Voidspire stands at the edge of a black plain, its upper floors visible only when the air forgets to be opaque. The people sheltering there speak softly, as if volume might invite a reply.",
    "dark_expanse": "The Dark Expanse has no reliable horizon. Stones cast shadows in the wrong direction, and travellers mark their route with objects that sometimes return before they do.",
    "netharions_throne": "Netharion's Throne is a city-sized apparatus at the centre of the Scar. Its broken rings surround a chamber where a voice may have been built, a god may have been wounded, or both may be the same unanswered claim.",
    "the_rifted_abyss": "The Rifted Abyss drops through layers of black geometry toward a light that has no source. The descent is not difficult because it is steep. It is difficult because the bottom keeps revising what the top meant.",
}


def _region_for_room(label: str) -> str:
    label = label.removeprefix("room:")
    for region in REGION_VOICES:
        if label.startswith(f"field_{region}_") or label == f"field_{region}":
            return region
    for region in REGION_VOICES:
        if label == region or label.startswith(f"{region}_"):
            return region
    for room, region in ROOM_REGIONS.items():
        if label == room or label.startswith(f"{room}_"):
            return region
    return "veridia"


ROOM_REGIONS: dict[str, str] = {
    "greenhold": "veridia",
    "elderwatch": "veridia",
    "riverbend": "veridia",
    "sunmeadow": "veridia",
    "the_sunken_barrow": "veridia",
    "ravenwatch": "duskwood_vale",
    "moonshade": "duskwood_vale",
    "twilight_grove": "duskwood_vale",
    "the_black_hollow": "duskwood_vale",
    "caeloria_city": "caeloria",
    "brightwater": "caeloria",
    "silverwatch": "caeloria",
    "westgate": "caeloria",
    "starfall_temple": "caeloria",
    "eldryn_city": "eldryn_forest",
    "wildgrowth": "eldryn_forest",
    "greenmist": "eldryn_forest",
    "the_great_tree": "eldryn_forest",
    "rotwood_deep": "eldryn_forest",
    "frosthold": "frostspire_peaks",
    "winters_grasp": "frostspire_peaks",
    "ironwall_pass": "frostspire_peaks",
    "glacial_bastion": "frostspire_peaks",
    "sunscar_city": "zhaar_desert",
    "red_dunes": "zhaar_desert",
    "sandspire_ruins": "zhaar_desert",
    "the_obsidian_pit": "zhaar_desert",
    "scorchstone_keep": "zhaar_desert",
    "zulkarak": "xilnath_jungle",
    "mistvale": "xilnath_jungle",
    "shifting_canopy": "xilnath_jungle",
    "heart_of_xilnath": "xilnath_jungle",
    "stonefang_keep": "thalorin",
    "boulderfall": "thalorin",
    "khazgor_peaks": "thalorin",
    "dreadmaw_hold": "thalorin",
    "irondeep_mines": "thalorin",
    "moltenhold": "ashen_wastes",
    "cragfire": "ashen_wastes",
    "ashen_monoliths": "ashen_wastes",
    "the_flamewrought_forge": "ashen_wastes",
    "the_scorched_gate": "ashen_wastes",
    "stonehelm": "korvash_highlands",
    "highreach": "korvash_highlands",
    "thunderhold": "korvash_highlands",
    "shunderhold": "korvash_highlands",
    "ancient_overlook": "korvash_highlands",
    "korvash_crater": "korvash_highlands",
    "stormreach": "shattered_isles",
    "saltwind_harbor": "shattered_isles",
    "blackreef_citadel": "shattered_isles",
    "the_maelstrom_rise": "shattered_isles",
    "aurelian_city": "skyward_spires",
    "celestial_observatory": "skyward_spires",
    "the_spire_nexus": "skyward_spires",
    "deepforge_city": "the_deepreach",
    "lumengrotto": "the_deepreach",
    "shadowfissure": "the_deepreach",
    "the_crystal_labyrinth": "the_deepreach",
    "voidspire": "the_voidscar",
    "dark_expanse": "the_voidscar",
    "netharions_throne": "the_voidscar",
    "the_rifted_abyss": "the_voidscar",
}


def _stable_index(label: str, size: int) -> int:
    return sum((idx + 1) * ord(char) for idx, char in enumerate(label)) % size


def author_room_descriptions(rooms: dict[str, dict[str, Any]]) -> None:
    """Replace factory room copy with authored regional and landmark prose in place."""
    for label, room in rooms.items():
        region = _region_for_room(label)
        voice = REGION_VOICES[region]
        if label in ROOM_PROSE:
            room["desc"] = ROOM_PROSE[label]
            continue
        if "_delve_vault" in label:
            room["desc"] = (
                f"The optional vault below {voice['name']} is a pocket of old wealth and older caution. "
                f"{voice['history']} The guardian here was placed to protect a choice, not merely a chest."
            )
            continue
        if "_delve_" in label:
            room["desc"] = (
                f"The descent beneath {voice['name']} narrows around you. {voice['history']} "
                f"{voice['pressure']} The stone carries sound farther than it should, and the way back "
                f"is marked by the memory of your own footsteps."
            )
            continue
        if "_caves_" in label or "_underworks_" in label:
            room["desc"] = (
                f"Below {voice['name']}, the dark has its own weather. {voice['history']} "
                f"{voice['pressure']} Water, root, or old conduit gives the passage its direction; "
                "the surface is close enough to promise and far enough to lie."
            )
            continue
        if label.startswith("field_"):
            room["desc"] = (
                f"{voice['terrain']} {voice['weather']} {voice['pressure']} "
                f"{voice['route']} {voice['history']}"
            )
            continue
        # Town interiors and generated service rooms inherit the local voice but name the function in
        # their label, so a store, inn, archive, or forge reads as a place people actually use.
        function = label.rsplit("_", 1)[-1].replace("_", " ")
        room["desc"] = (
            f"This {function} belongs to {voice['name']}, and its walls show the work that keeps the "
            f"region alive. {voice['weather']} {voice['resident_line']}"
        )


def author_enemy_prose(npcs: dict[str, dict[str, Any]]) -> None:
    """Give every materialized enemy and resident a regional identity and authored voice."""
    for label, npc in npcs.items():
        region = _region_for_room(str(npc.get("location", "")))
        voice = REGION_VOICES[region]
        if label.endswith("_warden"):
            npc["name"] = voice["warden"]
            npc["dialogue"] = [voice["resident_line"], voice["history"]]
        elif npc.get("tier") == "boss" or "_deep_boss" in label:
            npc["name"] = voice["boss"]
            npc["dialogue"] = [voice["foe_line"]]
        elif "_guardian" in label or "_vault_guard" in label:
            npc["name"] = f"{voice['name']} threshold keeper"
            npc["dialogue"] = [voice["foe_line"]]
        elif npc.get("aggressive") or npc.get("hp", 0) > 0:
            wildlife = voice["wildlife"]
            npc["name"] = wildlife[_stable_index(label, len(wildlife))]
            npc["dialogue"] = [voice["wild_line"]]
        else:
            npc["dialogue"] = [voice["resident_line"]]


def author_world(rooms: dict[str, dict[str, Any]], npcs: dict[str, dict[str, Any]]) -> None:
    """Apply the complete authored prose pass to a materialized world."""
    author_room_descriptions(rooms)
    author_enemy_prose(npcs)

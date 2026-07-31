"""Security test twin: the seed / world YAML boundary must refuse code-execution deserialization.

The whole world is loaded from YAML on disk (seeds, canon, authored towns, caves, the world-graph,
the generation contract, survey data). That is the world-input TRUST BOUNDARY, and a hand-edited or
maliciously crafted seed is untrusted input. Every world loader funnels through one shared loader,
`parts.world.seed._UniqueKeyLoader`, a SafeLoader/CSafeLoader (SafeConstructor) subclass.

This pins the security invariant BEHAVIOURALLY, not just structurally: the loader builds plain data
and REFUSES the `!!python/...` object-construction tags that a permissive loader (yaml.Loader /
FullLoader / unsafe_load) would turn into live objects or code. So deserializing a world file can
never achieve remote code execution -- and a future refactor to a permissive loader fails loudly
here instead of silently reintroducing an RCE on the world-input boundary.

Framework evidence (implementation + test evidence, NOT a compliance claim; verified against, not
certified to): NIST SP 800-53 SI-10 (information input validation); NIST SSDF PW.5.1 (avoid unsafe
functions); OWASP Top 10:2025 A08 (software & data integrity / insecure deserialization); OWASP
ASVS file-handling / deserialization. See docs/reports/security/security-roadmap.md.
"""

import pytest
import yaml
from yaml.constructor import SafeConstructor

from parts.world.seed import _UniqueKeyLoader

# Payloads a permissive (Full/Unsafe) loader would construct into live objects or execute. A safe
# loader has no constructor for these tags and must raise rather than build them.
_CODE_EXECUTION_PAYLOADS = [
    "!!python/object/apply:os.system ['echo pwned']",
    "!!python/object/new:os.system ['echo pwned']",
    "!!python/object:os.system {}",
    "!!python/name:os.system",
    "!!python/module:os",
]


@pytest.mark.parametrize("payload", _CODE_EXECUTION_PAYLOADS)
def test_the_world_yaml_loader_refuses_code_execution_tags(payload):
    # The core abuse case: a malicious world file cannot execute code through deserialization.
    with pytest.raises(yaml.YAMLError):  # ConstructorError is a YAMLError; a safe loader raises it
        yaml.load(payload, Loader=_UniqueKeyLoader)


def test_the_world_yaml_loader_still_parses_ordinary_seed_data():
    # The control must not break legitimate content: plain mappings, lists, and scalars still load.
    data = yaml.load(
        "forge:\n  name: The Cold Forge\n  exits: {north: courtyard}\n  level: 3\n",
        Loader=_UniqueKeyLoader,
    )
    assert data == {
        "forge": {"name": "The Cold Forge", "exits": {"north": "courtyard"}, "level": 3}
    }


def test_the_shared_world_loader_is_a_safe_constructor():
    # Structural backstop for the behavioural checks: safety rests on a SafeConstructor base (shared
    # by both SafeLoader and libyaml's CSafeLoader). A refactor to yaml.Loader/FullLoader -- which
    # WOULD run the tags above -- fails this assert, backend-independently.
    assert issubclass(_UniqueKeyLoader, SafeConstructor)

"""Real consumers of the Coding Corpus (MOD-05.022) + Smell Engine (MOD-05.023).

Two guarantees, checked in CI:
(a) the Hardware Store shelf stays free of error-swallowing / latent-bug smells (bare except,
    except: pass, mutable default arguments) - a maintainability guard on the reusable core;
(b) every smell the corpus DOCUMENTS is one the engine can actually DETECT - the two parts stay in
    sync, so the corpus never promises a signature the translation matrix cannot find.
"""

from __future__ import annotations

import glob
from pathlib import Path

from kernel.shelf.corpus import load_yaml
from kernel.shelf.smell_engine import analyze, smell_ids

_ROOT = Path(__file__).resolve().parent.parent
_SHELF = str(_ROOT / "parts" / "shelf" / "*.py")
_SEED = _ROOT / "data" / "coding_corpus.yaml"

# smells that hide failures or plant latent bugs - the shelf must never carry these
_HAZARDS = {"SMELL.BARE_EXCEPT", "SMELL.SWALLOWED_EXCEPTION", "SMELL.MUTABLE_DEFAULT_ARG"}


def test_shelf_is_free_of_error_swallowing_smells():
    offenders = []
    for path in sorted(glob.glob(_SHELF)):
        for smell in analyze(Path(path).read_text(encoding="utf-8"), path=path):
            if smell.smell_id in _HAZARDS:
                offenders.append((Path(path).name, smell.smell_id, smell.line))
    assert offenders == [], f"error-swallowing / latent-bug smells in the shelf: {offenders}"


def test_every_documented_smell_is_detectable():
    corpus = load_yaml(_SEED.read_text(encoding="utf-8"))
    documented = {record.id for record in corpus.by_category("smell")}
    missing = documented - smell_ids()
    assert missing == set(), f"corpus documents smells the engine cannot detect: {missing}"


def test_the_seed_corpus_loads_and_is_non_trivial():
    corpus = load_yaml(_SEED.read_text(encoding="utf-8"))
    assert len(corpus.all()) >= 12
    assert corpus.subsumed() and corpus.contested()  # the honesty fields are populated

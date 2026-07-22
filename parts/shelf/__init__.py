"""The Hardware Store layer: reusable, engine-agnostic pattern parts (Layer 3).

Physically separated from the engine (parts/) so the reusable cores are their own package: the
manufacturing platform and the world package both DEPEND on the store, and the store depends on
neither. The dependency arrow points one way (engine -> store), which is what makes these parts
genuinely reusable outside CodeForge.
"""

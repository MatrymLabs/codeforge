"""Build the hand-written C extension (raw CPython API, no helper library).

Deliberately plain setuptools + a single C Extension: the point of this organ is the bare Python/C
API, so there is no pybind11 / Cython / PyO3 in the loop. Build + install with `pip install
./native/textkernel` (the c-kernel CI job does exactly this); the game runs on the Python fallback
when it is not built (ADR-0010).
"""

from setuptools import Extension, setup

setup(
    name="codeforge-textkernel",
    version="0.1.0",
    ext_modules=[
        Extension(
            "codeforge_textkernel",
            sources=["src/textkernel.c"],
            extra_compile_args=["-O2", "-std=c11"],
        )
    ],
)

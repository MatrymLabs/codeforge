"""Build the hand-written C extension (raw CPython API, no helper library).

Deliberately plain setuptools + a single C Extension: the point of this organ is the bare Python/C
API, so there is no pybind11 / Cython / PyO3 in the loop. Build + install with `pip install
./native/textkernel` (the c-kernel CI job does exactly this); the game runs on the Python fallback
when it is not built (ADR-0010).
"""

from setuptools import Extension, setup

# Stable ABI (abi3): build against the Limited API with a 3.10 floor so ONE wheel per platform
# loads on every CPython >= 3.10 (the version axis collapses; the platform axis does not). The
# kernel uses only stable-ABI functions; abi3audit gates that in CI. See ADR-0010 + the R&D
# Technology Admission adoption (T-AP-07).
ABI3_FLOOR = 0x030A0000  # cp310

setup(
    name="codeforge-textkernel",
    version="0.1.0",
    ext_modules=[
        Extension(
            "codeforge_textkernel",
            sources=["src/textkernel.c"],
            extra_compile_args=["-O2", "-std=c11"],
            define_macros=[("Py_LIMITED_API", str(ABI3_FLOOR))],
            py_limited_api=True,
        )
    ],
    options={"bdist_wheel": {"py_limited_api": "cp310"}},
)

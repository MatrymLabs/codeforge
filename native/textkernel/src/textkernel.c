/*
 * codeforge_textkernel: a hand-written CPython extension (raw Python/C API, no PyO3/pybind11).
 *
 * One hot primitive: Levenshtein edit distance between two strings. The O(m*n) dynamic program is
 * cheap in C but expensive in a Python loop, and there is no stdlib shortcut for it -- exactly the
 * shape where hand-written C earns its place. It powers fuzzy matching ("command not found -- did
 * you mean ...?"), proven equal to the pure-Python fallback in parts/shelf/textmatch.py.
 *
 * This is the lowest-level polyglot organ: PyObject arguments parsed by hand, a scratch row managed
 * with PyMem, code points read with the Unicode API, and an int built back for Python. It is OPTIONAL
 * (ADR-0010): when this module is not built, textmatch falls back to the identical Python version.
 *
 * Stable ABI (abi3): built against the Limited API with a 3.10 floor (Py_LIMITED_API, set in
 * setup.py), so ONE wheel per platform loads on every CPython >= 3.10. That means only stable-ABI
 * functions here -- the fast internal macros PyUnicode_GET_LENGTH / PyUnicode_READ_CHAR are NOT in
 * the Limited API, so we use PyUnicode_GetLength / PyUnicode_ReadChar and read each string's code
 * points into a buffer ONCE (O(n)) rather than per DP cell -- abi3-safe AND faster.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

/* levenshtein(a, b) -> int : the edit distance (insert/delete/substitute) between two str. */
static PyObject *textkernel_levenshtein(PyObject *self, PyObject *args) {
    (void)self;
    PyObject *a, *b;
    if (!PyArg_ParseTuple(args, "UU", &a, &b)) {
        return NULL; /* not two str -> a clear TypeError, raised by the parser */
    }

    Py_ssize_t la = PyUnicode_GetLength(a); /* stable-ABI function form (not the internal macro) */
    Py_ssize_t lb = PyUnicode_GetLength(b);
    if (la < 0 || lb < 0) {
        return NULL; /* propagate a unicode error */
    }

    /* Keep the scratch row the size of the shorter string: work over columns of the longer one. */
    if (la > lb) {
        PyObject *t = a; a = b; b = t;
        Py_ssize_t tl = la; la = lb; lb = tl;
    }
    if (la == 0) {
        return PyLong_FromSsize_t(lb); /* everything in b must be inserted */
    }

    /* Read both strings' code points once via the stable-ABI PyUnicode_ReadChar, then run the DP
     * over plain buffers: no Python API call per cell (abi3-safe and faster than the old macro). */
    Py_UCS4 *ca = PyMem_New(Py_UCS4, la);
    Py_UCS4 *cb = PyMem_New(Py_UCS4, lb);
    Py_ssize_t *row = PyMem_New(Py_ssize_t, la + 1);
    if (ca == NULL || cb == NULL || row == NULL) {
        PyMem_Free(ca);
        PyMem_Free(cb);
        PyMem_Free(row);
        return PyErr_NoMemory();
    }
    for (Py_ssize_t i = 0; i < la; ++i) {
        ca[i] = PyUnicode_ReadChar(a, i);
    }
    for (Py_ssize_t j = 0; j < lb; ++j) {
        cb[j] = PyUnicode_ReadChar(b, j);
    }
    for (Py_ssize_t i = 0; i <= la; ++i) {
        row[i] = i;
    }

    for (Py_ssize_t j = 1; j <= lb; ++j) {
        Py_ssize_t diagonal = row[0]; /* cost of (i-1, j-1) before this column overwrites it */
        row[0] = j;
        Py_UCS4 bj = cb[j - 1];
        for (Py_ssize_t i = 1; i <= la; ++i) {
            Py_ssize_t above = row[i]; /* cost of (i, j-1), becomes the diagonal for i+1 */
            Py_ssize_t substitute = diagonal + (ca[i - 1] == bj ? 0 : 1);
            Py_ssize_t delete_ = row[i] + 1;
            Py_ssize_t insert_ = row[i - 1] + 1;
            Py_ssize_t best = substitute < delete_ ? substitute : delete_;
            if (insert_ < best) {
                best = insert_;
            }
            row[i] = best;
            diagonal = above;
        }
    }

    Py_ssize_t distance = row[la];
    PyMem_Free(ca);
    PyMem_Free(cb);
    PyMem_Free(row);
    return PyLong_FromSsize_t(distance);
}

static PyMethodDef textkernel_methods[] = {
    {"levenshtein", textkernel_levenshtein, METH_VARARGS,
     "levenshtein(a, b) -> int: the Levenshtein edit distance between two strings."},
    {NULL, NULL, 0, NULL}, /* sentinel */
};

static struct PyModuleDef textkernel_module = {
    PyModuleDef_HEAD_INIT,
    "codeforge_textkernel",
    "Hand-written CPython text kernel: Levenshtein edit distance (ADR-0010 accelerator).",
    -1,
    textkernel_methods,
    NULL, NULL, NULL, NULL,
};

PyMODINIT_FUNC PyInit_codeforge_textkernel(void) {
    return PyModule_Create(&textkernel_module);
}

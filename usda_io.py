"""
usda_io.py

Thin read/write layer around pxr.Sdf for the sublayer-only .usda files this
tool produces (composition arcs, no actual scene data).

V1 of this tool built and parsed these files as plain text (f-strings /
regex on "@path@" tokens). That worked because the files are simple, but it
meant re-implementing a slice of USD's own composition syntax by hand. V2
uses Sdf.Layer directly instead: same file layout on disk, but authored and
read through the real USD API.
"""

from pxr import Sdf


def write_sublayer_usda(path, sublayer_paths):
    """
    Write a .usda file whose only content is a subLayers list.
    Overwrites any existing file at `path`.
    """
    layer = Sdf.Layer.CreateAnonymous(".usda")
    layer.subLayerPaths.clear()
    for p in sublayer_paths:
        layer.subLayerPaths.append(p)
    layer.Export(str(path))


def read_sublayer_paths(path):
    """
    Return the list of subLayer paths declared in the .usda file at `path`,
    or [] if the file doesn't exist or can't be opened as a USD layer.
    """
    layer = Sdf.Layer.FindOrOpen(str(path))
    if layer is None:
        return []
    return list(layer.subLayerPaths)

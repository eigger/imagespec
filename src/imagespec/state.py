"""Mutable per-render state passed to every element handler."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .context import RenderContext


@dataclass
class RenderState:
    """State threaded through the render loop.

    Handlers mutate this in place:

    * ``img`` is drawn on in place (rotated text and ``dlimg`` blit their tile into
      it), but the dispatcher swaps in a fresh layer for per-element ``dither`` and a
      handler may assign a new image, so always read/write ``state.img`` rather
      than capturing a local reference.
    * ``pos_y`` tracks the running vertical cursor used by elements that flow
      (``line``/``text``/``multiline`` without an explicit ``y``).

    ``canvas_width`` / ``canvas_height`` are the actual pixel dimensions of the
    image being drawn on (after any rotation-driven swap).
    """

    img: Image.Image
    canvas_width: int
    canvas_height: int
    context: RenderContext
    pos_y: float = 0
    # Pixels quantized under an element-level dither override; the final
    # whole-canvas pass must leave these pixels unchanged.
    dither_protected: Image.Image | None = None

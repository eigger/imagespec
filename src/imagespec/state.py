"""Mutable per-render state passed to every element handler."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .context import RenderContext


@dataclass
class RenderState:
    """State threaded through the render loop.

    Handlers mutate this in place:

    * ``img`` may be *reassigned* (e.g. rotated text / ``dlimg`` composite into a
      new image via ``Image.alpha_composite``), so always read/write
      ``state.img`` rather than capturing a local reference.
    * ``pos_y`` tracks the running vertical cursor used by elements that flow
      (``line``/``text``/``multiline`` without an explicit ``y``).

    ``canvas_width`` / ``canvas_height`` are the actual pixel dimensions of the
    image being drawn on (after any rotation-driven swap).
    """

    img: Image.Image
    canvas_width: int
    canvas_height: int
    context: RenderContext
    pos_y: int = 0

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Union

from .multiline_with_links import MultilineWithLinks


class MultilineLog(MultilineWithLinks):
    _log_colors = dict(CRITICAL='tomato1', ERROR='tomato1', WARNING='tan1')

    def finalize(self) -> None:
        # Pre-define color log tags
        for color in self._log_colors.values():
            tag = f'Multiline(None,{color},None)'
            self.tags.add(tag)
            self.widget.tag_configure(tag, background=color)

        # Keep selection tag priority on top of color tags
        self.widget.tag_raise('sel')

        # Forbid user to edit output console,
        # block any keys except Ctrl+C, ←, ↑, →, ↓,
        # Tab, Shift-Tab
        def log_key_handler(e: tk.Event[Any]) -> str | None:
            if e.keysym == 'ISO_Left_Tab' or (e.state == 1 and e.keysym == 'Tab'):
                e.widget.tk_focusPrev().focus()  # Focus previous
                return 'break'

            if e.keysym == 'Tab':
                e.widget.tk_focusNext().focus()  # Focus next
                return 'break'

            if e.char == '\x03' or e.keysym in ('Left', 'Up', 'Right', 'Down'):
                return None

            return 'break'

        self.widget.bind('<Key>', log_key_handler)

        self._finalized = True

    def attach_logger(self, logger: logging.Logger,
                      fmt: str | None = None, datefmt: str | None = None) -> None:
        """Attach logger to the element."""
        if fmt is None:
            fmt = '%(asctime)s | %(message)s'

        if datefmt is None:
            datefmt = '%H:%M:%S'

        formatter = logging.Formatter(fmt, datefmt)
        self._log_handler = MultilineLogHandler(self)
        self._log_handler.setFormatter(formatter)

        logger.addHandler(self._log_handler)

    def update(self, value: Any = None, disabled: bool | None = None, append: bool = False,
               font:  Union[str, tuple[str, int], tuple[str, int, str]] | None = None,
               text_color: str | None = None, background_color: str | None = None,
               text_color_for_value: str | None = None,
               background_color_for_value: str | None = None, visible: bool | None = None,
               autoscroll: bool | None = None, justification: str | None = None,
               font_for_value: Union[str, tuple[str, int]] | None = None) -> None:
        if not getattr(self, '_finalized', False):
            self.finalize()

        super().update(value, disabled, append, font, text_color, background_color, text_color_for_value,
                       background_color_for_value, visible, autoscroll, justification, font_for_value)

    def log(self, message: str, /, level: str = 'INFO') -> None:
        """Log to the element."""
        self.update(
            message, append=True,
            background_color_for_value=self._log_colors.get(level, None)
        )


class MultilineLogHandler(logging.Handler):
    """Logging handler for GUI logger."""
    def __init__(self, multiiline_log: MultilineLog) -> None:
        super().__init__()
        self._multiline_log = multiiline_log

    def emit(self, record: logging.LogRecord) -> None:
        level = record.levelname
        message = self.format(record) + os.linesep
        self._multiline_log.log(message, level)

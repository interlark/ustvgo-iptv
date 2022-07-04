from __future__ import annotations

import re
import tkinter as tk
import webbrowser
from typing import Any, Callable, Union

import PySimpleGUI as sg


class MultilineWithLinks(sg.Multiline):  # type: ignore
    """Multiline with links support."""
    def update(self, value: Any = None, disabled: bool | None = None, append: bool = False,
               font:  Union[str, tuple[str, int], tuple[str, int, str]] | None = None,
               text_color: str | None = None, background_color: str | None = None,
               text_color_for_value: str | None = None,
               background_color_for_value: str | None = None, visible: bool | None = None,
               autoscroll: bool | None = None, justification: str | None = None,
               font_for_value: Union[str, tuple[str, int]] | None = None) -> None:
        if 'hyperlink' not in self.tags:
            # Add URL tag for common link styling
            self.tags.add('hyperlink')
            self.widget.tag_configure('hyperlink', foreground='blue', underline=True)

            self.widget.tag_bind('hyperlink', '<Enter>', lambda e: self.widget.config(cursor='hand2'))
            self.widget.tag_bind('hyperlink', '<Leave>', lambda e: self.widget.config(cursor=''))

        if value:
            for i, text_chunk in enumerate(re.split(r'(https?://\S+)', value)):
                if i % 2 == 0:
                    # Add regular text
                    super().update(text_chunk, disabled, append, font, text_color, background_color,
                                   text_color_for_value, background_color_for_value, visible,
                                   autoscroll, justification, font_for_value)
                else:
                    # Add hyperlink
                    url = text_chunk
                    if url not in self.tags:
                        self.tags.add(url)
                        rclick_event_name = '<Button-2>' if sg.running_mac() else '<Button-3>'
                        self.widget.tag_bind(url, rclick_event_name, self.context_menu_factory(url))
                        self.widget.tag_bind(url, '<Button-1>', lambda e: webbrowser.open(url))

                        # Change links hover color
                        # self.widget.tag_bind(url, '<Enter>',
                        #                      lambda e: self.widget.tag_configure(
                        #                          url, foreground='red', underline=True))
                        # self.widget.tag_bind(url, '<Leave>',
                        #                      lambda e: self.widget.tag_configure(
                        #                          url, foreground='blue', underline=True))

                    tags = ['hyperlink', url]
                    if background_color_for_value:
                        bg_color_tag = f'bg_color_{background_color_for_value}'
                        if bg_color_tag not in self.tags:
                            self.tags.add(bg_color_tag)
                            self.widget.tag_configure(bg_color_tag, background=background_color_for_value)

                            # Keep selection and hyperlink tags priority on the top
                            self.widget.tag_raise('sel')
                            self.widget.tag_raise('hyperlink')

                        tags.append(bg_color_tag)

                    self.widget.insert(tk.END, url, tags)
        else:
            super().update(value, disabled, append, font, text_color, background_color, text_color_for_value,
                           background_color_for_value, visible, autoscroll, justification, font_for_value)

    def context_menu_factory(self, url: str) -> Callable[[tk.Event[Any]], Any]:
        """Context menu factory method."""
        menu = tk.Menu(self.widget.winfo_toplevel(), tearoff=False)

        def copy_link(url: str) -> None:
            self.widget.clipboard_clear()
            self.widget.clipboard_append(url)
            self.widget.update()

        menu.add_command(label='Open', command=lambda: webbrowser.open(url))
        menu.add_command(label='Copy link', command=lambda: copy_link(url))

        # Hide menu
        menu.bind('<FocusOut>', lambda e: menu.unpost())

        def show_menu_handler(event: tk.Event[Any]) -> None:
            """Link menu handler."""
            menu.post(event.x_root, event.y_root)
            menu.focus_set()

            # Set flag to prevent text menu to appear
            self.widget.skip_menu_handler = True

        return show_menu_handler

from __future__ import annotations

import os
import tkinter as tk
import webbrowser
from functools import partialmethod
from typing import TYPE_CHECKING, Any, Callable

import PySimpleGUI as sg


if TYPE_CHECKING:
    from tqdm import tqdm as std_tqdm


def generate_event_handler(func: Callable[[], Any],
                           with_break: bool = False) \
                               -> Callable[[tk.Event[Any]], str | None]:
    """Generate event handler out of function.
    Args:
        func: Function to be wrapped in event handler.
        with_break: Whether to stop event propagation.
    Returns:
        Event handler.
    """
    def wrapper(event: tk.Event[Any]) -> str | None:
        func()
        return 'break' if with_break else None

    return wrapper


def setup_text_widget(widget: tk.Text | tk.Entry, root: tk.Toplevel, *,
                      menu_copy: bool = True, menu_paste: bool = False,
                      menu_cut: bool = False, menu_clear: bool = False,
                      menu_github: bool = False, set_focus: bool = False) -> None:
    """Setup text widgets, add context menu and other functionality.
    Args:
        widget: tk.Text or tk.Entry widget.
        root: Parent window.
        menu_copy: Whether text of the `widget` could be copied with context menu.
        menu_paste: Whether text of the `widget` could be pasted with context menu.
        menu_cut: Whether text of the `widget` could be cut with context menu.
        menu_clear: Whether text of the `widget` could be cleared with context menu.
        set_focus: Whether to set focus on the `widget`.
    """
    # def get_text() -> str:
    #     if isinstance(widget, tk.Entry):
    #         return widget.get()
    #     elif isinstance(widget, tk.Text):
    #         return widget.get('1.0','end')
    #     return ''

    def get_clipboard() -> str | None:
        try:
            return widget.clipboard_get()
        except tk.TclError:
            # Nothing in clipboard
            return None

    def get_selection() -> str | None:
        if isinstance(widget, tk.Entry):
            if widget.selection_present():
                return widget.selection_get()  # type: ignore
            else:
                return None
        elif isinstance(widget, tk.Text):
            try:
                return widget.get('sel.first', 'sel.last')
            except tk.TclError:
                # Nothing was selected
                return None

    def delete_selection() -> None:
        try:
            widget.delete('sel.first', 'sel.last')  # Works for tk.Entry and tk.Text
        except tk.TclError:
            # Nothing was selected
            pass

    def copy_text() -> None:
        selection = get_selection()
        if selection:
            widget.clipboard_clear()
            widget.clipboard_append(selection)
            widget.update()

    def paste_text() -> None:
        delete_selection()

        clipboard = get_clipboard()
        if clipboard:
            widget.insert('insert', clipboard)

    def cut_text() -> None:
        copy_text()
        delete_selection()

    def clear_text() -> None:
        if isinstance(widget, tk.Text):
            widget.delete('1.0', 'end')
        elif isinstance(widget, tk.Entry):
            widget.delete('0', 'end')

    def select_all() -> None:
        if isinstance(widget, tk.Entry):
            widget.select_range(0, 'end')
            widget.icursor('end')
        elif isinstance(widget, tk.Text):
            widget.tag_add('sel', '1.0', 'end')

    def ctrl_key_press(event) -> None:
        """Generate CTRL + X, V, C, A events for non-english layouts."""
        if event.keycode == 88 and event.keysym.lower() != 'x':
            event.widget.event_generate('<<Cut>>')
        elif event.keycode == 86 and event.keysym.lower() != 'v':
            event.widget.event_generate('<<Paste>>')
        elif event.keycode == 67 and event.keysym.lower() != 'c':
            event.widget.event_generate('<<Copy>>')
        elif event.keycode == 65 and event.keysym.lower() != 'a':
            event.widget.event_generate('<<SelectAll>>')

    # Generate extra events for non-english layouts
    widget.bind('<Control-KeyPress>', ctrl_key_press)

    # Create menu
    menu = tk.Menu(root, tearoff=False)

    if menu_copy:
        menu.add_command(label='Copy', command=copy_text)
    if menu_cut:
        menu.add_command(label='Cut', command=cut_text)
    if menu_paste:
        menu.add_command(label='Paste', command=paste_text)
        # Fix paste bahaviour
        widget.bind('<<Paste>>', generate_event_handler(paste_text, with_break=True))

    # Select all bahaviour
    widget.bind('<Control-a>', generate_event_handler(select_all, with_break=True))
    menu.add_command(label='Select all', command=select_all)

    # Clear widget
    if menu_clear:
        menu.add_command(label='Clear', command=clear_text)

    # Repo page
    if menu_github:
        menu.add_command(
            label='Visit Github',
            command=lambda: webbrowser.open('https://github.com/interlark/ustvgo-iptv')
        )

    # Show menu
    def show_menu_handler(event: tk.Event[Any]) -> None:
        """Config menu."""
        # Skip handling if appropriate flag is set
        if getattr(event.widget, 'skip_menu_handler', False):
            event.widget.skip_menu_handler = False
            return None

        # Config menu items state
        is_readonly = widget.cget('state') == 'readonly'

        if menu_copy:
            copy_state = 'normal' if get_selection() else 'disabled'
            menu.entryconfig('Copy', state=copy_state)
        if menu_paste:
            paste_state = 'normal' if not is_readonly and get_clipboard() else 'disabled'
            menu.entryconfig('Paste', state=paste_state)
        if menu_cut:
            cut_state = 'normal' if not is_readonly and get_selection() else 'disabled'
            menu.entryconfig('Cut', state=cut_state)
        if menu_clear:
            clear_state = 'normal' if not is_readonly else 'disabled'
            menu.entryconfig('Clear', state=clear_state)

        menu.post(event.x_root, event.y_root)
        menu.focus_set()

    rclick_event_name = '<Button-2>' if sg.running_mac() else '<Button-3>'
    widget.bind(rclick_event_name, show_menu_handler)

    # Hide menu
    menu.bind('<FocusOut>', generate_event_handler(menu.unpost))

    # Focus
    if set_focus:
        widget.focus_set()


def patch_tqdm(tqdm: std_tqdm, window: sg.Window,
               event_key: str = '@PROGRESS_UPDATE') -> None:
    """Make tqdm send its progress to GUI window.
    Args:
        tqdm (tqdm.tqdm): tqdm class to be patched.
        window (sg.Window): PySimpleGUI window.
        event_key: Event name for progress updated.
    """
    original_update = tqdm.update
    original_close = tqdm.close

    def new_update(tqdm_self: std_tqdm, *args: Any, **kwargs: Any) -> None:
        original_update(tqdm_self, *args, **kwargs)
        window.write_event_value(event_key, (tqdm_self.n, tqdm_self.total))

    def new_close(tqdm_self: std_tqdm, *args: Any, **kwargs: Any) -> None:
        window.write_event_value(event_key, (tqdm_self.n, tqdm_self.total))
        original_close(tqdm_self, *args, **kwargs)

    tqdm.update = new_update
    tqdm.close = new_close

    # Suppress console output
    devnull = open(os.devnull, 'w')
    tqdm.__init__ = partialmethod(tqdm.__init__, file=devnull)

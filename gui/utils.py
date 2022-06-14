import logging
import os
import tkinter as tk
import webbrowser
from functools import partialmethod

import PySimpleGUI as sg
from ustvgo_iptv import logger


def generate_event_handler(func, with_break: bool = False):
    """Generate event handler out of function.
    Args:
        func: Function to be wrapped in event handler.
        with_break: Whether to stop event propagation.
    Returns:
        Event handler.
    """
    def wrapper(event: tk.Event):
        func()
        return 'break' if with_break else None

    return wrapper


def setup_text_widget(widget, root, *,
                      menu_copy=True, menu_paste=False,
                      menu_cut=False, menu_clear=False,
                      menu_github=False, set_focus=False):
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

    def get_clipboard():
        try:
            return widget.clipboard_get()
        except tk.TclError:
            # Nothing in clipboard
            return None

    def get_selection():
        if isinstance(widget, tk.Entry):
            if widget.selection_present():
                return widget.selection_get()
            else:
                return None
        elif isinstance(widget, tk.Text):
            try:
                return widget.get('sel.first', 'sel.last')
            except tk.TclError:
                # Nothing was selected
                return None

    def delete_selection():
        try:
            widget.delete('sel.first', 'sel.last')  # Works for tk.Entry and tk.Text
        except tk.TclError:
            # Nothing was selected
            pass

    def copy_text():
        selection = get_selection()
        if selection:
            widget.clipboard_clear()
            widget.clipboard_append(selection)
            widget.update()

    def paste_text():
        delete_selection()

        clipboard = get_clipboard()
        if clipboard:
            widget.insert('insert', clipboard)

    def cut_text():
        copy_text()
        delete_selection()

    def clear_text():
        if isinstance(widget, tk.Text):
            widget.delete('1.0', 'end')
        elif isinstance(widget, tk.Entry):
            widget.delete('0', 'end')

    def select_all():
        if isinstance(widget, tk.Entry):
            widget.select_range(0, 'end')
            widget.icursor('end')
        elif isinstance(widget, tk.Text):
            widget.tag_add('sel', '1.0', 'end')

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
    def show_menu_handler(event: tk.Event):
        """Config menu."""
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


class QueueHandler(logging.Handler):
    """Queue handler for GUI logger."""
    def __init__(self, log_queue):
        super().__init__()
        self._log_queue = log_queue

    def emit(self, record):
        log_message = (record.levelname, self.format(record) + os.linesep)
        self._log_queue.put(log_message)


def setup_gui_logger(log_queue):
    """Add queue handler to existing logger so it would
    emmit logs to the specified queue.

    Args:
        log_queue: Queue to put logging messages into.
    """
    formatter = logging.Formatter('%(asctime)s | %(message)s', '%H:%M:%S')
    queue_handler = QueueHandler(log_queue)
    queue_handler.setFormatter(formatter)
    logger.addHandler(queue_handler)

    # Also add handler to access logs
    access_logger = logging.getLogger('aiohttp.access')
    access_logger.addHandler(queue_handler)


def patch_tqdm(tqdm, window, event_key='@PROGRESS_UPDATE'):
    """Make tqdm send its progress to GUI window.
    Args:
        tqdm (tqdm.tqdm): tqdm class to be patched.
        window (sg.Window): PySimpleGUI window.
        event_key: Event name for progress updated.
    """
    original_update = tqdm.update
    original_close = tqdm.close

    def new_update(tqdm_self, *args, **kwargs):
        original_update(tqdm_self, *args, **kwargs)
        window.write_event_value(event_key, (tqdm_self.n, tqdm_self.total))

    def new_close(tqdm_self, *args, **kwargs):
        window.write_event_value(event_key, (tqdm_self.n, tqdm_self.total))
        original_close(tqdm_self, *args, **kwargs)

    tqdm.update = new_update
    tqdm.close = new_close

    # Suppress console output
    devnull = open(os.devnull, 'w')
    tqdm.__init__ = partialmethod(tqdm.__init__, file=devnull)

from __future__ import annotations

import asyncio
import logging
import tkinter as tk
from typing import Any, Awaitable

import PySimpleGUI as sg
import ustvgo_iptv

from .error_popup import error_popup
from .paths import image_data
from .settings import load_settings, save_settings, GUI_SETTINGS
from .utils import patch_tqdm, setup_text_widget
from .widgets import MultilineLog

logger = logging.getLogger('ustvgo_iptv')


async def app() -> None:
    # Load settings
    settings = load_settings()

    # App color theme
    sg.theme('BrownBlue')

    # Set icon
    sg.set_global_icon(image_data('icon.png'))

    # Window layout
    layout = [
        [
            sg.Frame('Options', expand_x=True, expand_y=True, layout=[
                [
                    sg.Column([[
                        sg.Column([[
                            sg.Checkbox(text='Icons for light background',
                                        default=settings['icons_for_light_bg'],
                                        key='-CHECK_ICONS_FOR_LIGHT_BG-',
                                        tooltip='Switch to dark iconset for players with light UI'),
                        ]], p=0, expand_x=True),
                        sg.Column([[
                            sg.Checkbox(text='Access logs',
                                        default=settings['access_logs'],
                                        key='-CHECK_ACCESS_LOGS-',
                                        tooltip='Enable access logs for tracking requests activity'),
                        ]], p=0, expand_x=True),
                        sg.Column([[
                            sg.Text('Port', key='-LBL_PORT-', tooltip='Server port'),
                            sg.Spin(list(range(1, 65535 + 1)),
                                    initial_value=settings['port'],
                                    key='-IN_PORT-', size=(8, 1))
                        ]], expand_x=True, element_justification='right')
                    ]], p=0, expand_x=True),
                ],
                [
                    sg.Column([[
                        sg.Column([[
                            sg.Checkbox(text='Uncompressed TV Guide',
                                        default=settings['use_uncompressed_tvguide'],
                                        key='-CHECK_UNCOMPRESSED_TVGUIDE-',
                                        tooltip='Use uncompressed TV Guide in master playlist'),
                        ]], p=0, expand_x=True),
                        sg.Column([[
                            sg.Checkbox(text='Autostart',
                                        default=settings['autostart'],
                                        key='-CHECK_AUTOSTART-',
                                        tooltip='Autostart USTVGO-IPTV'),
                        ]], p=((0 if sg.running_windows() else 16, 0), 0), expand_x=True),
                        sg.Column([[
                            sg.Text('Parallel', key='-LBL_PARALLEL-',
                                    tooltip='Number of parallel parsing requests'),
                            sg.Spin(list(range(1, 15 + 1)),
                                    initial_value=settings['parallel'],
                                    key='-IN_PARALLEL-', size=(8, 1))
                        ]], expand_x=True, element_justification='right')
                    ]], p=0, expand_x=True),
                ],
                [
                    sg.Column([[
                        sg.Column([[
                            sg.Text('Password', key='-LBL_PASSWORD-',
                                    tooltip='Add URL path protection with a password'),
                            sg.Input(settings['password'], key='-IN_PASSWORD-', expand_x=True)
                        ]], p=0, expand_x=True),
                    ]], p=((1 if sg.running_windows() else 8, 5), (3, 8)), expand_x=True),
                ],
            ]),
        ],
        [
            sg.Frame('Log', expand_x=True, expand_y=True, layout=[
                [
                    MultilineLog(key='-LOG-', size=(61, 15), expand_x=True, autoscroll=True,
                                 reroute_stdout=True, reroute_stderr=True, echo_stdout_stderr=True),
                ],
            ]),
        ],
        [
            sg.ProgressBar(0, orientation='h', size=(1, 22),
                           expand_x=True, key='-PROGRESSBAR-', p=(5, 10))
        ],
        [
            sg.Column([[
                sg.Column([
                    [
                        sg.Button('Start', size=(10, 1), key='-BTN_START-', p=0),
                        sg.Button('Stop', size=(10, 1), key='-BTN_STOP-',
                                  button_color=('white', 'orange3'), p=0, visible=False),
                    ]
                ], element_justification='left', p=0),
                sg.Column([
                    [
                        sg.Button('Exit', size=(10, 1), key='-BTN_EXIT-',
                                  button_color=('white', 'firebrick3'), p=0),
                    ]
                ], expand_x=True, element_justification='right', p=0),
            ]], expand_x=True, p=(5, (3, 8))),
        ],
    ]

    # Main window
    window = sg.Window(f'USTVGO IPTV v{ustvgo_iptv.VERSION}', layout, auto_size_text=True,
                       finalize=True, font='Any 12', use_default_focus=False)

    # Setup text widgets
    setup_text_widget(window['-LOG-'].widget, window.TKroot,
                      menu_clear=True, menu_copy=True, menu_github=True)
    setup_text_widget(window['-IN_PORT-'].widget, window.TKroot,
                      menu_paste=True, menu_cut=True, menu_copy=True)
    setup_text_widget(window['-IN_PARALLEL-'].widget, window.TKroot,
                      menu_paste=True, menu_cut=True, menu_copy=True)
    setup_text_widget(window['-IN_PASSWORD-'].widget, window.TKroot,
                      menu_paste=True, menu_cut=True, menu_copy=True)

    # Set disabled color
    for key in ('-CHECK_ICONS_FOR_LIGHT_BG-',
                '-CHECK_ACCESS_LOGS-', '-CHECK_AUTOSTART-',
                '-CHECK_UNCOMPRESSED_TVGUIDE-', '-LBL_PORT-',
                '-LBL_PARALLEL-', '-LBL_PASSWORD-'):
        window[key].widget.config(disabledforeground='snow3')

    # Attach app loggers
    window['-LOG-'].attach_logger(logger)
    window['-LOG-'].attach_logger(logging.getLogger('aiohttp.access'))

    # Patch tqdm to show progress on GUI
    patch_tqdm(ustvgo_iptv.ustvgo_iptv.tqdm, window)

    # Sync params between window controls and settings
    def sync_settings(verbose: bool = True) -> bool:
        for arg_name in ('port', 'parallel'):
            try:
                value_str = window[f'-IN_{arg_name.upper()}-'].get()
                value = int(value_str)
                if value <= 0:
                    raise ValueError
                settings[arg_name] = value
            except ValueError:
                if verbose:
                    error_popup(f'Incorrect integer value "{value_str}" for "{arg_name}"')
                return False

        settings['use_uncompressed_tvguide'] = window['-CHECK_UNCOMPRESSED_TVGUIDE-'].get()
        settings['icons_for_light_bg'] = window['-CHECK_ICONS_FOR_LIGHT_BG-'].get()
        settings['access_logs'] = window['-CHECK_ACCESS_LOGS-'].get()
        settings['autostart'] = window['-CHECK_AUTOSTART-'].get()
        settings['password'] = window['-IN_PASSWORD-'].get()
        return True

    # Controls locking during background tasks running
    def lock_controls(state: bool = True) -> None:
        try:
            for key in ('-LBL_PORT-', '-LBL_PARALLEL-', '-LBL_PASSWORD-'):
                window[key].widget.config(state='disabled' if state else 'normal')

            for key in ('-IN_PORT-', '-IN_PARALLEL-', '-IN_PASSWORD-',
                        '-CHECK_ICONS_FOR_LIGHT_BG-', '-CHECK_UNCOMPRESSED_TVGUIDE-',
                        '-CHECK_ACCESS_LOGS-', '-CHECK_AUTOSTART-'):
                window[key].update(disabled=state)

            # Change foregorund for tk.Entry widget
            if state:
                window['-IN_PASSWORD-'].widget.config(fg='gray')
            else:
                window['-IN_PASSWORD-'].widget.config(fg='black')

            window['-BTN_STOP-'].update(visible=state)
            window['-BTN_START-'].update(visible=not state)

            # Switch focus between start\stop buttons
            focused_widget = window.TKroot.focus_get()
            if focused_widget is window['-BTN_START-'].Widget and state:
                window['-BTN_STOP-'].set_focus()
            elif focused_widget is window['-BTN_STOP-'].Widget and not state:
                window['-BTN_START-'].set_focus()

        except tk.TclError:
            pass  # Main window could be already destroyed by sg

    # Background tasks wrapper for restoring state
    async def background_task_finished(coro: Awaitable[Any]) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(e, exc_info=True)

        lock_controls(state=False)

    # Running background task
    background_task: asyncio.Future[Any] | None = None

    # coro wrapper for window events reading
    async def read_window() -> Any:
        return window.read(timeout=50)

    # Finalize custom log element and set focus on it
    window['-LOG-'].finalize()
    window['-LOG-'].set_focus(force=True)

    def start_server() -> None:
        nonlocal background_task

        # Sync settings
        if sync_settings():
            # Lock user inputs
            lock_controls()

            cli_settings = {k: v for k, v in settings.items() if k not in GUI_SETTINGS}
            loop = asyncio.get_running_loop()
            background_task = loop.create_task(
                background_task_finished(
                    ustvgo_iptv.playlist_server(**cli_settings)
                )
            )

    def stop_server() -> None:
        if background_task:
            background_task.cancel()

    if settings['autostart']:
        start_server()

    # Main loop
    while True:
        event, values = await asyncio.ensure_future(read_window())

        # App exit
        if event in (None, '-BTN_EXIT-'):
            # Sync settings
            if sync_settings(verbose=False):
                # Save settings
                save_settings(settings)

            # Stop and await running server
            if background_task and not background_task.done():
                background_task.cancel()
                await background_task
            break

        # Click "Start"
        elif event == '-BTN_START-':
            # Start USTVGO server
            start_server()

        # Click "Cancel"
        elif event == '-BTN_STOP-':
            # Stop USTVGO server
            stop_server()

        # Update progress bar
        elif event == '@PROGRESS_UPDATE':
            n, total = values['@PROGRESS_UPDATE']
            window['-PROGRESSBAR-'].update(current_count=n, max=total)

    window.close()
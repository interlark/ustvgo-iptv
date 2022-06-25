import asyncio
import queue

import PySimpleGUI as sg
from ustvgo_iptv import VERSION, logger, playlist_server, tqdm

from .error_popup import error_popup
from .paths import image_data
from .settings import load_settings, save_settings
from .utils import patch_tqdm, setup_gui_logger, setup_text_widget


async def app():
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
                    sg.Checkbox(text='Icons for light background', default=settings['icons_for_light_bg'],
                                key='-CHECK_ICONS_FOR_LIGHT_BG-', expand_x=True),
                    sg.Checkbox(text='Access logs', default=settings['access_logs'],
                                key='-CHECK_ACCESS_LOGS-', expand_x=True),
                    sg.Column([[
                        sg.Text('Port', key='-LBL_PORT-'),
                        sg.Input(settings['port'], key='-IN_PORT-', size=(8, 1))
                    ]], expand_x=True)
                ],
            ]),
        ],
        [
            sg.Frame('Log', expand_x=True, expand_y=True, layout=[
                [
                    sg.Multiline(key='-LOG-', size=(61, 15), expand_x=True, autoscroll=True,
                                 reroute_stdout=True, reroute_stderr=True, echo_stdout_stderr=True),
                ],
            ]),
        ],
        [
            sg.ProgressBar(0, orientation='h', size=(1, 22),
                           expand_x=True, key='-PROGRESSBAR-', pad=(5, 10))
        ],
        [
            sg.Column([
                [
                    sg.Button('Start', size=(10, 1), key='-BTN_START-', pad=((5, 5), (2, 8))),
                    sg.Button('Stop', size=(10, 1), key='-BTN_STOP-', visible=False,
                              button_color=('white', 'orange3'), pad=((3, 5), (2, 8))),
                ]
            ], element_justification='left', pad=0),
            sg.Column([
                [
                    sg.Button('Exit', size=(10, 1), button_color=('white', 'firebrick3'),
                              key='-BTN_EXIT-', pad=((5, 3), (2, 8))),
                ]
            ], expand_x=True, element_justification='right', pad=0)
        ],
    ]

    # Main window
    window = sg.Window(f'USTVGO IPTV v{VERSION}', layout, auto_size_text=True,
                       finalize=True, font='Any 12')

    # Setup text widgets
    setup_text_widget(window['-LOG-'].widget, window.TKroot,
                      menu_clear=True, menu_copy=True, menu_github=True, set_focus=True)
    setup_text_widget(window['-IN_PORT-'].widget, window.TKroot,
                      menu_paste=True, menu_cut=True, menu_copy=True, menu_clear=False)

    # Set disabled color
    for key in ('-CHECK_ICONS_FOR_LIGHT_BG-', '-CHECK_ACCESS_LOGS-', '-LBL_PORT-'):
        window[key].widget.config(disabledforeground='snow3')

    # Forbid user to edit output console,
    # block any keys except ctl+c, ←, ↑, →, ↓
    def log_key_handler(e):
        if e.char == '\x03' or e.keysym in ('Left', 'Up', 'Right', 'Down'):
            return None

        return 'break'

    window['-LOG-'].widget.bind('<Key>', log_key_handler)

    # Enable logging queue to be able to handle logs in the mainloop
    log_queue = queue.Queue()  # Queue of log messages (log_level, log_message)
    setup_gui_logger(log_queue)

    # Set log background colors by level
    log_colors = dict(CRITICAL='tomato1', ERROR='tomato1', WARNING='tan1')

    # Pre-define log tags
    for color in log_colors.values():
        tag = f'Multiline(None,{color},None)'
        window['-LOG-'].tags.add(tag)
        window['-LOG-'].widget.tag_configure(tag, background=color)

    # Keep selection tag priority on top
    window['-LOG-'].widget.tag_raise('sel')

    # Patch tqdm to show progress on GUI
    patch_tqdm(tqdm, window)

    # Sync params between window controls and settings
    def sync_settings(verbose=True):
        try:
            settings['port'] = int(window['-IN_PORT-'].get())
        except ValueError:
            if verbose:
                error_popup('Incorrect port value')
            return False

        settings['icons_for_light_bg'] = window['-CHECK_ICONS_FOR_LIGHT_BG-'].get()
        settings['access_logs'] = window['-CHECK_ACCESS_LOGS-'].get()
        return True

    # Controls locking during background tasks running
    def lock_controls(state=True):
        try:
            window['-LBL_PORT-'].widget.configure(state='disabled' if state else 'normal')

            for key in ('-IN_PORT-', '-CHECK_ICONS_FOR_LIGHT_BG-', '-CHECK_ACCESS_LOGS-'):
                window[key].update(disabled=state)

            window['-BTN_STOP-'].update(visible=state)
            window['-BTN_START-'].update(visible=not state)
        except sg.tk.TclError:
            pass  # Main window could be already destroyed by sg

    # Background tasks wrapper for restoring state
    async def background_task_finished(coro):
        try:
            await coro
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(e, exc_info=True)

        lock_controls(state=False)

    # Running background task
    background_task = None

    # coro wrapper for window events reading
    async def read_window():
        return window.read(timeout=50)

    # Main loop
    while True:
        event, values = await asyncio.ensure_future(read_window())

        # App exit
        if event in (None, '-BTN_EXIT-'):
            if background_task and not background_task.done():
                background_task.cancel()
                await background_task
            break

        # Click Start
        elif event == '-BTN_START-':
            if not sync_settings():
                continue

            lock_controls()

            loop = asyncio.get_running_loop()
            background_task = loop.create_task(
                background_task_finished(
                    playlist_server(**settings)
                )
            )

        # Click Cancel
        elif event == '-BTN_STOP-':
            if background_task:
                background_task.cancel()

        # Update progress bar
        elif event == '@PROGRESS_UPDATE':
            n, total = values['@PROGRESS_UPDATE']
            window['-PROGRESSBAR-'].update(current_count=n, max=total)

        # Poll log queue
        while True:
            try:
                log_level, log_msg = log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                # Print message to log
                window['-LOG-'].update(
                    log_msg, append=True,
                    background_color_for_value=log_colors.get(log_level, None)
                )

    # Save settings before exit
    sync_settings(verbose=False)
    save_settings(settings)

    window.close()


def main() -> None:
    """Entry point."""
    asyncio.run(app())

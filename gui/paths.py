import base64
import os
import pathlib

import PySimpleGUI as sg


def config_path() -> pathlib.Path:
    """Get user path depending on running OS.
    Note:
        Possible path location depending on running OS:
        * Unix: ~/.config/ustvgo-iptv
        * Mac: ~/Library/Application Support/ustvgo-iptv
        * Win: C:\\Users\\%USERPROFILE%\\AppData\\Local\\ustvgo-iptv
    """
    if sg.running_windows():
        import ctypes

        CSIDL_LOCAL_APPDATA = 28
        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_LOCAL_APPDATA, None, 0, buf)  # type: ignore
        path = buf.value
    elif sg.running_mac():
        path = os.path.expanduser('~/Library/Application Support')
    else:
        path = os.getenv('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))

    path = os.path.join(path, 'ustvgo-iptv')
    return pathlib.Path(path)


def image_data(filename: str) -> bytes:
    """Get image data `basename`.`ext`."""
    images_path = pathlib.Path(__file__).parent / 'icons'
    for file_path in images_path.iterdir():
        if file_path.name == filename:
            return base64.b64encode(file_path.read_bytes())

    raise FileNotFoundError(f'Image {filename} not found')

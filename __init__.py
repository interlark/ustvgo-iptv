"""
USTVGO Free IPTV.
"""

from .ustvgo_iptv import main, args_parser, playlist_server, VERSION

__version__ = VERSION
__all__ = ['main', 'args_parser', 'playlist_server', '__version__']

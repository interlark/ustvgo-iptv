#!/usr/bin/env python3

import argparse
import asyncio
import io
import json
import logging
import pathlib
import re
import sys
import time
from functools import partial

import aiohttp
import netifaces
from aiohttp import web
from furl import furl
from tqdm.asyncio import tqdm

# Usage:
# ./ustvgo_iptv.py
# vlc http://127.0.0.1:6363/ustvgo.m3u8


VERSION = '0.1.1'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/102.0.5005.63 Safari/537.36')
USTVGO_HEADERS = {'Referer': 'https://ustvgo.tv', 'User-Agent': USER_AGENT}

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s :: %(levelname)s :: %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


def root_dir():
    """Root directory."""
    return pathlib.Path(__file__).parent


def load_dict(filename):
    """Load root dictionary."""
    filepath = root_dir() / filename
    with open(filepath, encoding='utf-8') as f:
        return json.load(f)


def local_ip_addresses():
    """Finding all local IP addresses."""
    ip_addresses = []
    interfaces = netifaces.interfaces()
    for i in interfaces:
        iface = netifaces.ifaddresses(i).get(netifaces.AF_INET, [])
        ip_addresses.extend(x['addr'] for x in iface)

    return ip_addresses


async def gather_with_concurrency(n, *tasks, show_progress=True, progress_title=None):
    """Gather tasks with concurrency."""
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task

    gather = partial(tqdm.gather, desc=progress_title) if show_progress \
        else asyncio.gather
    return await gather(*[sem_task(x) for x in tasks])


async def retrieve_stream_url(channel, max_retries=5):
    """Retrieve stream URL from web player with retries."""
    url = 'https://ustvgo.tv/player.php?stream=' + channel['stream_id']
    timeout, max_timeout = 2, 10
    exceptions = (asyncio.TimeoutError, aiohttp.ClientConnectionError,
                  aiohttp.ClientResponseError, aiohttp.ServerDisconnectedError)

    while True:
        try:
            async with aiohttp.ClientSession(headers=USTVGO_HEADERS, raise_for_status=True) as session:
                async with session.get(url=url, timeout=timeout) as response:
                    resp_html = await response.text()
                    match = re.search(r'hls_src=["\'](?P<stream_url>[^"\']+)', resp_html)
                    if match:
                        channel['stream_url'] = furl(match.group('stream_url'))
                        return channel
                    return None
        except Exception as e:
            is_exc_valid = any([isinstance(e, exc) for exc in exceptions])
            if not is_exc_valid:
                raise

            timeout = min(timeout + 1, max_timeout)
            max_retries -= 1
            if max_retries <= 0:
                logger.error('Failed to get url %s', url)
                return None


def render_playlist(channels, host, tvguide_base_url, icons_for_light_bg):
    """Render master playlist."""
    with io.StringIO() as f:
        color_scheme = 'for-light-bg' if icons_for_light_bg else 'for-dark-bg'
        tvg_url = furl(tvguide_base_url) / f'ustvgo.{color_scheme}.xml.gz'
        f.write('#EXTM3U url-tvg="%s" refresh="1800"\n\n' % tvg_url)
        for channel in channels:
            if channel.get('stream_url'):
                tvg_logo = furl(tvguide_base_url) / 'images' / 'icons' / 'channels' / \
                    color_scheme / (channel['stream_id'] + '.png')
                stream_url = (furl(channel['stream_url'])
                              .set(netloc=host, scheme='http')
                              # No need to expose auth key to the master playlist
                              .remove(args=['wmsAuthSign'])
                              .tostr(query_dont_quote='='))

                f.write(('#EXTINF:-1 tvg-id="{0[stream_id]}" tvg-logo="{1}" '
                         'group-title="{0[category]}",{0[name]}\n'.format(channel, tvg_logo)))
                f.write(f'{stream_url}\n\n')

        return f.getvalue()


async def collect_urls(channels, parallel):
    """Collect channel stream URLs from ustvgo.tv web players."""
    logger.info('Extracting stream URLs from USTVGO. Parallel requests: %d.', parallel)
    retrieve_tasks = [retrieve_stream_url(channel) for channel in channels]
    channels = await gather_with_concurrency(parallel, *retrieve_tasks,
                                             progress_title='Collect URLs')

    channels_ok = [x for x in channels if x]
    report_msg = 'Extracted %d channels out of %d.'
    if len(channels_ok) < len(channels):
        report_msg += ' You can extract more using VPN.'
    logger.info(report_msg, len(channels_ok), len(channels))

    return channels_ok


async def update_auth_key(channels):
    """Update auth key."""
    logger.info('Fetching new auth key from USTVGO.')
    for channel in channels:
        if await retrieve_stream_url(channel):
            auth_key = channel['stream_url'].args.get('wmsAuthSign')
            logger.info('Got new auth key "%s"', auth_key)
            return auth_key

    logger.error('Update auth key failed')


async def playlist_server(port, parallel, tvguide_base_url, access_logs, icons_for_light_bg):
    """Run proxying server with key rotation."""
    async def master_handler(request):
        async with auth_key_lock:
            return web.Response(
                text=render_playlist(channels, request.host, tvguide_base_url, icons_for_light_bg),
                status=200
            )

    async def stream_handler(request):
        nonlocal auth_key, auth_key_retrieved_time
        stream_id = request.match_info.get('stream_id')

        if stream_id not in channel_origins:
            return web.Response(status=404)

        headers = {key: value for key, value in request.headers.items()
                   if key.lower() not in ('host', 'user-agent')}
        headers = {**USTVGO_HEADERS, **headers}

        data = await request.read()
        max_retries = 2  # Second retry for 403-forbidden recovery or response payload error

        for retry in range(1, max_retries + 1):
            url = furl(request.path_qs).set(
                origin=channel_origins[stream_id], args={'wmsAuthSign': auth_key}
            ).tostr(query_dont_quote='=')

            try:
                async with aiohttp.request(
                    request.method, url, params=request.query, data=data,
                    headers=headers, raise_for_status=True
                ) as response:

                    content = await response.read()
                    headers = {name: value for name, value in response.headers.items()
                               if name.lower() not in
                               ('content-encoding', 'content-length',
                                'transfer-encoding', 'connection')}

                    return web.Response(
                        body=content, status=response.status,
                        headers=headers
                    )
            except aiohttp.ClientResponseError as e:
                if retry >= max_retries:
                    return web.Response(text=e.message, status=e.status)

                if request.path.endswith('.m3u8') and e.status == 404:
                    notfound_segment_url = furl(tvguide_base_url) / 'assets' / '404.ts'
                    return web.Response(text=(
                        '#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n'
                        f'#EXTINF:10.000\n{notfound_segment_url}\n#EXT-X-ENDLIST'
                    ))

                async with auth_key_lock:
                    if e.status == 403 and time.time() - auth_key_retrieved_time > 5:
                        new_auth_key = await update_auth_key(channels)
                        if new_auth_key:
                            auth_key = new_auth_key
                            auth_key_retrieved_time = time.time()
                        else:
                            logger.error('[Retry %d] Failed to get new auth key', retry)

            except aiohttp.ClientPayloadError as e:
                if retry >= max_retries:
                    return web.Response(text=e.message, status=500)

            except aiohttp.ClientError as e:
                logger.error('[Retry %d] Error occured during handling request: %s',
                             retry, e, exc_info=True)

    # Load channels info
    channels = load_dict('channels.json')

    # Retrieve available channels with their stream urls
    channels = await collect_urls(channels, parallel)

    if not channels:
        logger.error('No channels were retrieved!')
        return

    # Get initial auth key
    auth_key_lock = asyncio.Lock()
    auth_key = channels[0]['stream_url'].args.get('wmsAuthSign')
    auth_key_retrieved_time = 0
    logger.info('Got auth key "%s"', auth_key)

    if not auth_key:
        logger.info('Auth key is empty!', auth_key)
        return

    # Upstream origins
    channel_origins = {x['stream_id']: x['stream_url'].origin for x in channels}

    # Setup access logging
    access_logger = logging.getLogger('aiohttp.access')
    if access_logs:
        access_logger.setLevel('INFO')
    else:
        access_logger.setLevel('ERROR')

    # Run server
    for ip_address in local_ip_addresses():
        logger.info(f'Serving http://{ip_address}:{port}/ustvgo.m3u8')

    app = web.Application()
    app.router.add_get('/', master_handler)  # master
    app.router.add_get('/ustvgo.m3u8', master_handler)  # master
    app.router.add_route('*', '/{stream_id}{tail:/.*}', stream_handler)  # proxy

    runner = web.AppRunner(app)
    try:
        await runner.setup()
        site = web.TCPSite(runner, port=port)
        await site.start()

        # Sleep forever by 1 hour intervals,
        # on Windows before Python 3.8 wake up every 1 second to handle
        # Ctrl+C smoothly.
        if sys.platform == 'win32' and sys.version_info < (3, 8):
            delay = 1
        else:
            delay = 3600

        while True:
            await asyncio.sleep(delay)
    finally:
        await runner.cleanup()  # cleanup used resources, release port


def args_parser():
    """Command line arguments parser."""
    def int_range(min_value=-sys.maxsize - 1, max_value=sys.maxsize):
        def constrained_int(arg):
            value = int(arg)
            if not min_value <= value <= max_value:
                raise argparse.ArgumentTypeError(
                    f'{min_value} <= {arg} <= {max_value}'
                )
            return value

        return constrained_int

    parser = argparse.ArgumentParser('ustvgo-iptv')
    parser.add_argument(
        '--port', '-p', metavar='PORT',
        type=int_range(min_value=1, max_value=65535), default=6363,
        help='Serving port (default: %(default)s)'
    )
    parser.add_argument(
        '--parallel', '-t', metavar='N',
        type=int_range(min_value=1), default=10,
        help='Number of parallel fetcher requests (default: %(default)s)'
    )
    parser.add_argument(
        '--icons-for-light-bg', action='store_true',
        help='Put channel icons adapted for apps with light background'
    )
    parser.add_argument(
        '--access-logs',
        action='store_true',
        help='Enable access logging'
    )
    parser.add_argument(
        '--tvguide-base-url', metavar='URL',
        default='https://raw.githubusercontent.com/interlark/ustvgo-iptv/tvguide',
        help='Base TVGuide URL'
    )
    parser.add_argument(
        '--version', '-v', action='version', version=f'%(prog)s {VERSION}'
    )

    return parser


def main():
    """Entry point."""
    parser = args_parser()
    args = parser.parse_args()

    asyncio.run(playlist_server(**vars(args)))


if __name__ == '__main__':
    main()

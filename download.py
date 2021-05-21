#!/usr/bin/env python3

import os
import re
import sys
import tarfile
import zipfile
from argparse import ArgumentParser
from time import sleep

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

IFRAME_CSS_SELECTOR = '.iframe-container>iframe'

def check_gecko_driver():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(script_dir, 'bin') 

    if sys.platform.startswith('linux'):
        platform = 'linux'
        url = 'https://github.com/mozilla/geckodriver/releases/download/v0.26.0/geckodriver-v0.26.0-linux64.tar.gz'
        local_platform_path = os.path.join(bin_dir, platform)
        local_driver_path = os.path.join(local_platform_path, 'geckodriver')
        var_separator = ':'
    elif sys.platform == 'darwin':
        platform = 'mac'
        url = 'https://github.com/mozilla/geckodriver/releases/download/v0.26.0/geckodriver-v0.26.0-macos.tar.gz'
        local_platform_path = os.path.join(bin_dir, platform)
        local_driver_path = os.path.join(local_platform_path, 'geckodriver')
        var_separator = ':'
    elif sys.platform.startswith('win'):
        platform = 'win'
        url = 'https://github.com/mozilla/geckodriver/releases/download/v0.26.0/geckodriver-v0.26.0-win64.zip'
        local_platform_path = os.path.join(bin_dir, platform)
        local_driver_path = os.path.join(local_platform_path, 'geckodriver.exe')
        var_separator = ';'
    else:
        raise RuntimeError('Could not determine your OS')

    if not os.path.isdir(bin_dir):
        os.mkdir(bin_dir)

    if not os.path.isdir(local_platform_path):
        os.mkdir(local_platform_path)

    if not os.path.isfile(local_driver_path):
        print('Downloading gecko driver...', file=sys.stderr)
        data_resp = requests.get(url, stream=True)
        file_name = url.split('/')[-1]
        tgt_file = os.path.join(local_platform_path, file_name)
        with open(tgt_file, 'wb') as f:
            for chunk in data_resp.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        if file_name.endswith('.zip'):
            with zipfile.ZipFile(tgt_file, 'r') as f_zip:
                f_zip.extractall(local_platform_path)
        else:
            with tarfile.open(tgt_file, 'r') as f_gz:
                f_gz.extractall(local_platform_path)

        if not os.access(local_driver_path, os.X_OK):
            os.chmod(local_driver_path, 0o744)

        os.remove(tgt_file)
    
    if 'PATH' not in os.environ:
        os.environ['PATH'] = local_platform_path
    elif local_driver_path not in os.environ['PATH']:
        os.environ['PATH'] = local_platform_path + var_separator + os.environ['PATH']

if __name__ == '__main__':
    args_parser = ArgumentParser()
    args_parser.add_argument('-n', '--no-headless', action='store_true', help='Run script in no-headless mode (debug)')
    args_parser.add_argument('-t', '--timeout', type=int, default=10, help='Maximum number of seconds to wait for the response')
    args_parser.add_argument('-m', '--max-retries', type=int, default=3, help='Maximum number of attempts to collect data')
    args_parser.add_argument('-p', '--proxy', type=str, default=None, help='Use proxy')
    args = args_parser.parse_args()
    args.no_headless = True
    if args.max_retries <= 0 or args.timeout <= 0:
        print('Invalid arguments', file=sys.stderr)
        exit(1)

    check_gecko_driver()

    ff_options = FirefoxOptions()
    if not args.no_headless:
        ff_options.add_argument('--headless')

    print('Downloading the playlist, please wait...', file=sys.stderr)

    firefox_profile = webdriver.FirefoxProfile()
    firefox_profile.set_preference('permissions.default.image', 2)
    firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
    firefox_profile.set_preference('dom.disable_beforeunload', True)
    firefox_profile.set_preference('browser.tabs.warnOnClose', False)
    firefox_profile.set_preference('media.volume_scale', '0.0')

    set_seleniumwire_options = {
        'connection_timeout': None,
        'verify_ssl': False,
        'suppress_connection_errors': False 
    }

    if args.proxy:
        set_seleniumwire_options['proxy'] = {
            'http': f'http://{args.proxy}',
            'https': f'https://{args.proxy}'
        }

    # pylint: disable=unexpected-keyword-arg
    driver = webdriver.Firefox(seleniumwire_options=set_seleniumwire_options, options=ff_options, firefox_profile=firefox_profile)
    driver.get('https://ustvgo.tv/')
    sleep(0.5)

    soup = BeautifulSoup(driver.page_source, features='lxml')
    root_div = soup.select_one('div.article-container')
    page_links = []
    for link in root_div.select('li>strong>a[href]'):
        page_links.append(link.get('href'))
    for link in root_div.select('li>a[href]'):
        page_links.append(link.get('href'))

    channel_list = [
        re.sub(r'^https://ustvgo.tv/|/$', '', i)
        .replace('-live', '')
        .replace('-channel', '')
        .replace('-free', '')
        .replace('-streaming', '')
        .replace('-', ' ')
        .upper() for i in page_links
    ]
    video_links = []

    for item_n, link in enumerate(page_links):
        retry = 1
        while True:
            try:
                driver.get(link)

                # Get iframe
                iframe = None
                try:
                    iframe = driver.find_element_by_css_selector(IFRAME_CSS_SELECTOR)
                except NoSuchElementException:
                    print('[%d/%d] Video frame is not found for channel %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                    break

                # Detect VPN-required channels
                try:
                    driver.switch_to.frame(iframe)
                    driver.find_element_by_xpath("//*[text()='Please use our VPN to watch this channel!']")
                    need_vpn = True
                except NoSuchElementException:
                    need_vpn = False
                finally:
                    driver.switch_to.default_content()

                if need_vpn:
                    print('[%d/%d] Channel %s needs VPN to be grabbed, skipping' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                    break

                # Autoplay
                iframe.click()

                try:
                    playlist = driver.wait_for_request('/playlist.m3u8', timeout=args.timeout)
                except TimeoutException:
                    playlist = None
                
                if playlist:
                    video_link = playlist.path
                    video_links.append((channel_list[item_n], video_link))
                    print('[%d/%d] Successfully collected link for %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                else:
                    video_link = ''
                    sleep(1.5)

                sleep(3)
                del driver.requests
                if not video_link:
                    raise NoSuchElementException()
                break
            except KeyboardInterrupt:
                exit(1)
            except:
                print('[%d] Retry link for %s' % (retry, channel_list[item_n]), file=sys.stderr)
                retry += 1
                if retry > args.max_retries:
                    print('[%d/%d] Failed to collect link for %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                    break

    print('Generating ustvgo.m3u8 playlist...', file=sys.stderr)
    with open('ustvgo.m3u8', 'w') as file:
        file.write('#EXTM3U\n\n')
        for name, url in video_links:
            file.write('#EXTINF:-1,' + name + '\n')
            file.write("#EXTVLCOPT:http-user-agent=\"Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:71.0) Gecko/20100101 Firefox/71.0\"\n")
            file.write("#EXTVLCOPT:http-referrer=\"https://ustvgo.tv\"\n")
            file.write(url + '\n\n')

    driver.close()
    driver.quit()

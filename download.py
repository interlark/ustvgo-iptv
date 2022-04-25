#!/usr/bin/env python3

from operator import contains
from optparse import Option
import os
import re
from ssl import Options
import sys
import tarfile
import zipfile
import json
from argparse import ArgumentParser
from time import sleep

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver
from os import path

IFRAME_CSS_SELECTOR = '.iframe-container>iframe'
POPUP_ACCEPT_XPATH_SELECTOR = '//button[contains(text(),"AGREE")]'
# Opening JSON file
if path.exists("channel_categories.json"):
    with open('channel_categories.json') as json_file:
        channel_categories = json.load(json_file)
if path.exists('channel_id_override.json'):
    with open('channel_id_override.json') as json_file:
        channel_id_override = json.load(json_file)

def check_gecko_driver():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(script_dir, 'bin') 

    if sys.platform.startswith('linux'):
        platform = 'linux'
        url = 'https://github.com/mozilla/geckodriver/releases/download/v0.31.0/geckodriver-v0.31.0-linux32.tar.gz'
        local_platform_path = os.path.join(bin_dir, platform)
        local_driver_path = os.path.join(local_platform_path, 'geckodriver')
        var_separator = ':'
    elif sys.platform == 'darwin':
        platform = 'mac'
        url = 'https://github.com/mozilla/geckodriver/releases/download/v0.31.0/geckodriver-v0.31.0-macos.tar.gz'
        local_platform_path = os.path.join(bin_dir, platform)
        local_driver_path = os.path.join(local_platform_path, 'geckodriver')
        var_separator = ':'
    elif sys.platform.startswith('win'):
        platform = 'win'
        url = 'https://github.com/mozilla/geckodriver/releases/download/v0.31.0/geckodriver-v0.31.0-win64.zip'
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

    ff_options = Options()
    if not args.no_headless:
        ff_options.add_argument('--headless')

    print('Downloading the playlist, please wait...', file=sys.stderr)
    firefox_profile = ff_options
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
    with webdriver.Firefox(seleniumwire_options=set_seleniumwire_options, options=ff_options, firefox_profile=firefox_profile.profile) as driver:
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
                        iframe = driver.find_element(by=By.CSS_SELECTOR, value=IFRAME_CSS_SELECTOR)
                    except NoSuchElementException:
                        print('[%d/%d] Video frame is not found for channel %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                        break

                    # Detect VPN-required channels
                    try:
                        driver.switch_to.frame(iframe)
                        driver.find_element(by=By.XPATH, value="//*[text()='Please use the VPN in the link above to access this channel.']")
                        need_vpn = True
                    except NoSuchElementException:
                        need_vpn = False
                    finally:
                        driver.switch_to.default_content()

                    if need_vpn:
                        print('[%d/%d] Channel %s needs VPN to be grabbed, skipping' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                        break

                    # close popup if it shows up
                    try:
                        driver.find_element(by=By.XPATH, value=POPUP_ACCEPT_XPATH_SELECTOR).click()
                    except NoSuchElementException:
                        pass

                    # Autoplay
                    iframe.click()

                    try:
                        driver.switch_to.frame(iframe)
                        scriptList = driver.find_elements(By.XPATH, "//body/script")
                        for script in scriptList:
                            innerText = script.get_attribute("innerHTML")
                            if "hls_src" in innerText:
                                playlist = innerText
                                temp = re.search(r"https:[^']*", playlist)
                                playlist = temp.group(0)
                                driver.switch_to.default_content()
                    except TimeoutException:
                        playlist = None
                    
                    if playlist:
                        video_link = playlist
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
                if path.exists("channel_id_override.json"):
                    tvg_id = (channel_id_override.get(name, name))
                else:
                    tvg_id = name
                if path.exists("channel_categories.json"):
                    group_title = (channel_categories.get(name, "Uncategorized"))
                else:
                    group_title = "Uncategorized"
                file.write('#EXTINF:-1 tvg-id="%s" group-title="%s", %s \n' % (tvg_id, group_title, name))
                file.write("#EXTVLCOPT:http-user-agent=\"Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:71.0) Gecko/20100101 Firefox/71.0\"\n")
                file.write("#EXTVLCOPT:http-referrer=\"https://ustvgo.tv\"\n")
                file.write(url + '\n\n')

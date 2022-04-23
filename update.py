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
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException,
                                        TimeoutException)
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

IFRAME_CSS_SELECTOR = '.iframe-container>iframe'
POPUP_ACCEPT_XPATH_SELECTOR = '//button[contains(text(),"AGREE")]'
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
    args = args_parser.parse_args()

    if args.max_retries <= 0 or args.timeout <= 0:
        print('Invalid arguments', file=sys.stderr)
        exit(1)

    if not os.path.isfile('ustvgo.m3u8'):
        print('playlist ustvgo.m3u8 not found', file=sys.stderr)
        exit(1)

    check_gecko_driver()

    print('Updating authentication key, please wait...')

    ff_options = FirefoxOptions()
    if not args.no_headless:
        ff_options.add_argument('--headless')

    firefox_profile = webdriver.FirefoxProfile()
    firefox_profile.set_preference('permissions.default.image', 2)
    firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
    firefox_profile.set_preference('dom.disable_beforeunload', True)
    firefox_profile.set_preference('browser.tabs.warnOnClose', False)
    firefox_profile.set_preference('media.volume_scale', '0.0')

    with webdriver.Firefox(options=ff_options, firefox_profile=firefox_profile) as driver:
        driver.get('https://ustvgo.tv/')
        sleep(0.5)

        soup = BeautifulSoup(driver.page_source, features='lxml')
        root_div = soup.select_one('div.article-container')
        page_links = []
        for link in root_div.select('li>strong>a[href]'):
            page_links.append(link.get('href'))

        page_links = set(page_links)
        video_links = []
        captured_key = None

        for item_n, link in enumerate(page_links):
            if captured_key:
                break
            retry = 1
            while True:
                try:
                    driver.get(link)
                    
                    # Get iframe
                    iframe = None
                    try:
                        iframe = driver.find_element_by_css_selector(IFRAME_CSS_SELECTOR)
                    except NoSuchElementException:
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
                        break
                    
                    # close popup if it shows up
                    try:
                        driver.find_element_by_xpath(POPUP_ACCEPT_XPATH_SELECTOR).click()
                    except NoSuchElementException:
                        pass
                    
                    # Autoplay
                    iframe.click()
                    
                    try:
                        playlist = driver.wait_for_request('/playlist.m3u8', timeout=args.timeout)
                    except TimeoutException:
                        playlist = None

                    if playlist:
                        video_link = playlist.path
                        m_key = re.search('(?<=wmsAuthSign=).*$',video_link)
                        if m_key:
                            captured_key = m_key.group()
                            print('Recieved key: %s' % captured_key, file=sys.stderr)
                            break
                    else:
                        raise Exception()

                except KeyboardInterrupt:
                    exit(1)
                except Exception as e:
                    print('Failed to get key, retry(%d) ...' % retry, file=sys.stderr)
                    retry += 1
                    if retry > args.max_retries:
                        break

        if not captured_key:
            print('No key found. Exiting...', file=sys.stderr)
            exit(1)

        print('Updating ustvgo.m3u8 playlist...', file=sys.stderr)

        playlist_text = open('ustvgo.m3u8', 'r').read()
        playlist_text = re.sub('(?<=wmsAuthSign=).*(?=\n)', captured_key, playlist_text)

        with open('ustvgo.m3u8', 'w') as file:
            file.write(playlist_text)

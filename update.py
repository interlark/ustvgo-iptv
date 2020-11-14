#!/usr/bin/env python3

import re
import os
import sys
from time import sleep

from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from argparse import ArgumentParser

IFRAME_CSS_SELECTOR = '.iframe-container>iframe'

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

    driver = webdriver.Firefox(options=ff_options, firefox_profile=firefox_profile)
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

    driver.close()
    driver.quit()

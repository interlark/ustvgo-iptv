#!/usr/bin/env python3

import re
import sys
from time import sleep

from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options as FirefoxOptions

PROXY = None  # 'host:port' or None
TIMEOUT = 10
MAX_RETRIES = 3

if __name__ == '__main__':
    ff_options = FirefoxOptions()
    ff_options.add_argument('--headless')

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

    if PROXY:
        set_seleniumwire_options['proxy'] = {
            'http': f'http://{PROXY}',
            'https': f'https://{PROXY}'
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

                try:
                    driver.find_element_by_xpath("//h5[text()='This channel requires our VPN to watch!']")
                    need_vpn = True
                except NoSuchElementException:
                    need_vpn = False

                if need_vpn:
                    print('[%d/%d] Channel %s needs VPN to be grabbed, skipping' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                    break

                try:
                    playlist = driver.wait_for_request('/playlist.m3u8?wmsAuthSign', timeout=TIMEOUT)
                except TimeoutException:
                    playlist = None
                
                if playlist:
                    video_link = playlist.path
                    video_links.append((channel_list[item_n], video_link))
                    print('[%d/%d] Successfully collected link for %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                else:
                    video_link = ''
                    print('[%d/%d] Failed to collect link for %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                    sleep(1.5)

                sleep(3)
                del driver.requests
                if not video_link:
                    raise Exception()
                break
            except:
                print('[%d] Retry link for %s' % (retry, channel_list[item_n]), file=sys.stderr)
                retry += 1
                if retry > MAX_RETRIES:
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

#!/usr/bin/env python3

import re
import os
import sys
from time import sleep

from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options as FirefoxOptions

if __name__ == '__main__':
    if not os.path.isfile('ustvgo.m3u'):
        print('playlist ustvgo.m3u not found', file=sys.stderr)
        exit(1)

    ff_options = FirefoxOptions()
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

    MAX_RETRIES = 3

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

                sleep(0.5)
                player_frame = driver.find_element_by_class_name('iframe-container')
                if player_frame:
                    player_frame.click()
                    sleep(0.5)
                else:
                    print('Warning, player frame isn\'t found', file=sys.stderr)
                
                playlists = [x for x in driver.requests if '/playlist.m3u8?wmsAuthSign' in x.path]
                if playlists:
                    video_link = playlists[0].path
                    m_key = re.search('(?<=wmsAuthSign=).*$',video_link)
                    if m_key:
                        captured_key = m_key.group()
                        print('Recieved key: %s' % captured_key, file=sys.stderr)
                        break
                else:
                    raise Exception()

            except:
                print('Failed to get key, retry(%d) ...' % retry, file=sys.stderr)
                retry += 1
                if retry > MAX_RETRIES:
                    break

    if not captured_key:
        print('Exiting...')
        exit(1)

    print('Updating ustvgo.m3u playlist...', file=sys.stderr)

    playlist_text = open('ustvgo.m3u', 'r').read()
    playlist_text = re.sub('(?<=wmsAuthSign=).*(?=\n)', captured_key, playlist_text)

    with open('ustvgo.m3u', 'w') as file:
        file.write(playlist_text)

    driver.close()
    driver.quit()

#!/usr/bin/env python3

import re
import os
import sys
from time import sleep

from bs4 import BeautifulSoup
from selenium import webdriver
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

    driver = webdriver.Firefox(options=ff_options, firefox_profile=firefox_profile)
    driver.get('https://ustvgo.tv/')


    MAX_RETRIES = 3

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.pis-title-link')))
    sleep(0.5)

    soup = BeautifulSoup(driver.page_source, features='lxml')

    page_links = []
    for link in soup.findAll('a', attrs={'class': 'pis-title-link','href': re.compile('^https://ustvgo.tv.+?')}):
        page_links.append(link.get('href'))

    page_links = set(page_links)
    channel_list = [re.split(r'.tv/|-channel|-live', i)[1].upper().replace('-', ' ').rstrip('/') for i in page_links]
    video_links = []
    captured_key = None

    for item_n, link in enumerate(page_links):
        if captured_key:
            break
        retry = 1
        while True:
            try:
                driver.get(link)
                iframe = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.iframe-container>iframe')))
                driver.switch_to.frame(iframe)
                html_source = driver.page_source
                try:
                    video_link = re.findall('(http.*m3u8.*)', html_source)[0]
                    m_key = re.search('(?<=wmsAuthSign=).*$',video_link)
                    if m_key:
                        captured_key = m_key.group()
                        print('Recieved key: %s' % captured_key, file=sys.stderr)
                        break
                    else:
                        print('Warning, no wmsAuthKey found in response!', file=sys.stderr)
                except:
                    video_link = ''
                video_links.append(video_link)
                sleep(0.5)
                break
            except TimeoutException:
                print('Timeout, retry...')
                retry += 1
                if retry > MAX_RETRIES:
                    break

    print('Updating ustvgo.m3u playlist...', file=sys.stderr)

    playlist_text = open('ustvgo.m3u', 'r').read()
    playlist_text = re.sub('(?<=wmsAuthSign=).*(?=\n)', captured_key, playlist_text)

    with open('ustvgo.m3u', 'w') as file:
        file.write(playlist_text)

    driver.close()
    driver.quit()

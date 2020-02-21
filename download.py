#!/usr/bin/env python3

import re
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
    ff_options = FirefoxOptions()
    ff_options.add_argument('--headless')

    firefox_profile = webdriver.FirefoxProfile()
    firefox_profile.set_preference('permissions.default.image', 2)
    firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
    firefox_profile.set_preference("dom.disable_beforeunload", True)
    firefox_profile.set_preference("browser.tabs.warnOnClose", False)

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

    for item_n, link in enumerate(page_links):
        retry = 1
        while True:
            try:
                driver.get(link)
                iframe = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.iframe-container>iframe')))
                driver.switch_to.frame(iframe)
                html_source = driver.page_source
                try:
                    video_link = re.findall('(http.*m3u8.*)', html_source)[0]
                    print('[%d/%d] Successfully collected link for %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                except:
                    video_link = ''
                    print('[%d/%d] Failed to collect link for %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                video_links.append(video_link)
                sleep(0.5)
                break
            except TimeoutException:
                print('Timeout, retry...')
                retry += 1
                if retry > MAX_RETRIES:
                    print('[%d/%d] Failed to collect link for %s' % (item_n + 1, len(page_links), channel_list[item_n]), file=sys.stderr)
                    break

    print('Generating ustvgo.m3u playlist...', file=sys.stderr)

    zip_pair = sorted(zip(channel_list, video_links))
    zip_pair = list(filter(lambda t: '' not in t, zip_pair))

    with open('ustvgo.m3u', 'w') as file:
        file.write('#EXTM3U\n\n')
        for name, url in zip_pair:
            file.write('#EXTINF:-1,' + name + '\n')
            file.write("#EXTVLCOPT:http-user-agent=\"Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:71.0) Gecko/20100101 Firefox/71.0\"\n")
            file.write(url + '\n\n')

    driver.close()
    driver.quit()

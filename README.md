# Playlist downloader for ustvgo.tv

## Installation

Script uses Selenium & Firefox (Gecko driver), so make sure you've installed all of them on your machine:

```bash
sudo apt install firefox
wget https://github.com/mozilla/geckodriver/releases/download/v0.26.0/geckodriver-v0.26.0-linux64.tar.gz
sudo sh -c 'tar -x geckodriver -zf geckodriver-v0.26.0-linux64.tar.gz -O > /usr/bin/geckodriver'
sudo chmod +x /usr/bin/geckodriver
rm geckodriver-v0.26.0-linux64.tar.gz
```

Then,

```bash
pip3 install -r requirements.txt
```

## Usage

* Use [download.py](download.py) to download playlist [ustvgo.m3u8](ustvgo.m3u8) from [ustvgo.tv](http://ustvgo.tv/) if you need it:

```bash
python3 download.py
```

```text 
[1/81] Successfully collected link for GSN
[2/81] Successfully collected link for LIFETIME MOVIES
[3/81] Successfully collected link for ANIMAL PLANET
[4/81] Successfully collected link for NBC SPORTS
...
```

* Use [update.py](update.py) to update authentication key:
```bash
python3 update.py
```

```text
Recieved key: c2VakmPyX...aW52dRVzoTI1MA==
Updating ustvgo.m3u8 playlist...
```

* Play collected playlist:
```bash
vlc ustvgo.m3u8 --adaptive-use-access
```

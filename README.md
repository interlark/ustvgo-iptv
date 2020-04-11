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

Use download.py to download playlist from [ustvgo](http://ustvgo.tv/)

Use update.py to update authentication key

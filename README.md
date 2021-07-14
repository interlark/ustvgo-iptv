# Playlist downloader for ustvgo.tv

## Installation

Script uses **Selenium & Firefox (Gecko driver)**, so make sure you've installed **Firefox browser** on your computer, all the rest get installed automatically.

```bash
git clone https://github.com/interlark/ustvgo_downloader
cd ustvgo_downloader
pip3 install -r requirements.txt
```

## Usage

* Use [download.py](download.py) to **download** playlist [ustvgo.m3u8](ustvgo.m3u8) from [ustvgo.tv](http://ustvgo.tv/) if you need it:
> It's not required, since you can use the already [existing](ustvgo.m3u8) playlist

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

* Use [update.py](update.py) to **update** authentication key:

> Every key is valid for 4 hours
```bash
python3 update.py
```

```text
Recieved key: c2VakmPyX...aW52dRVzoTI1MA==
Updating ustvgo.m3u8 playlist...
```

* **Play** collected playlist:
```bash
vlc ustvgo.m3u8 --adaptive-use-access
```

## Troubleshooting
* If you run script on dedicated headless server and bump into erros like **Failed to collect link** - seems like you don't have **AVC codecs** installed on your server, try install them with
```bash
sudo apt-get install ubuntu-restricted-extras
```
if you have ubuntu server installed or commonly
```bash
sudo apt-get install libavcodec58 libav-tools
```
* If you get errors and now guessing what's going wrong, try to run script with **--no-headless** argument to see what's going on in the browser
```bash
python3 download.py --no-headless
```
or 

```bash
python3 update.py --no-headless
```

## Tips
* In case if you're not a native speaker and use TV, Cartoons, Movies and Shows to **learn the language** - on some channels you can **turn on subtitles** that make it easier pretty much.

![Subtitles screenshot](https://raw.githubusercontent.com/interlark/ustvgo_downloader/master/assets/subtitles-screenshot.png)

#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
vlc ${DIR}/ustvgo.m3u --adaptive-use-access

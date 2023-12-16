#!/bin/bash
echo Updating scoreboard
/etc/init.d/rgb_scoreboard.sh stop

git reset --hard
git fetch origin --prune
git pull

cp ./scoreboard.py /usr/local/bin/scoreboard.py
chmod +x /usr/local/bin/scoreboard.py
/etc/init.d/rgb_scoreboard.sh start
exit
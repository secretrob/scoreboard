#!/bin/bash
echo Installing scoreboard

#apt
apt install python3-pip python3-pillow -y
python3 -m pip install -r setup/requirements.txt

#install rgbmatrix
git submodule update --init --recursive
git config submodule.matrix.ignore all

echo Running RGBMatrix Install

cd submodules/matrix/bindings/python/rgbmatrix/ || exit

python3 -m pip install --no-cache-dir cython
python3 -m cython -2 --cplus *.pyx

cd ../../../ || exit

make build-python PYTHON="$(command -v python3)"
sudo make install-python PYTHON="$(command -v python3)"

cd ../../ || exit

git reset --hard
git fetch origin --prune
git pull

make
echo If no errors than the RGB install is complete

#install scoreboard
cp ./setup/scoreboard.conf /etc/rgb_scoreboard.conf
cp ./setup/rgb_scoreboard.sh /etc/init.d/rgb_scoreboard.sh
cp ./setup/rgb_scoreboard_update.sh /usr/local/bin/rgb_scoreboard_update.sh
cp ./scoreboard.py /usr/local/bin/scoreboard.py
chmod +x /etc/init.d/rgb_scoreboard.sh
chmod +x /usr/local/bin/scoreboard.py
chmod +x /usr/local/bin/rgb_scoreboard_update.sh

mkdir /usr/local/scoreboard
mkdir /usr/local/scoreboard/cache
touch /usr/local/scoreboard/cache/teams.json
touch /usr/local/scoreboard/cache/games.json
chmod -R 777 /usr/local/scoreboard/cache
cp -R assets /usr/local/scoreboard/
cp -R submodules /usr/local/scoreboard/

echo Starting Scoreboard...
/etc/init.d/rgb_scoreboard.sh start
exit
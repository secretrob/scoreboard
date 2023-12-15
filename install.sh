#!/bash/sh
echo Installing scoreboard
apt install python3-pip -y
python3 -m pip install -r setup/requirements.txt
cp ./setup/scoreboard.conf /etc/scoreboard.conf
cp ./setup/rgb_scoreboard.sh /etc/init.d/rgb_scoreboard.sh
chmod +x /etc/init.d/rgb_scoreboard.sh
cp ./scoreboard.py /usr/local/bin/scoreboard.py
chmod +x /usr/local/bin/scoreboard.py
echo Starting Scoreboard...
/etc/init.d/rgb_scoreboard.sh start
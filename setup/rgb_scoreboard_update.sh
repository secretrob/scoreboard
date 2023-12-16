#!/bin/bash

dir=${1?param missing - downloaded scoreboard dir. Default is ~/scoreboard }
cd dir
chmod +x update.sh
./update.sh

echo "Update Complete"
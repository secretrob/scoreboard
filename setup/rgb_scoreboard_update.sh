#!/bin/bash

dir=${1?param missing - downloaded scoreboard dir. Default is ~/scoreboard }
TRIMMED=$(echo "$dir" | sed 's:/*$::')
cd $TRIMMED
chmod +x update.sh
./update.sh

echo "Update Complete"
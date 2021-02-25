#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

source "${DIR}/scripts/start_py36ev.sh"
nohup python "${DIR}/mini_spiders.py" > "${DIR}/nohup.out" &

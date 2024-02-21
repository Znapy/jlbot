#!/usr/bin/env bash
# Launch the development environment: pylsp in jlbot venv and spyder in spyder venv.

ss -tulpn | grep 2087
set -e

export OLD_PROJECTPATH="$PROJECTPATH"
export PROJECTPATH="$( dirname -- "$( readlink -f -- "$0"; )"; )"

bash -c "source $PROJECTPATH/.venv/bin/activate && pylsp --tcp" &
bash -c "source ~/env-py/spyder/bin/activate && spyder --new-instance --project '$PROJECTPATH' --conf-dir '$PROJECTPATH/.spyproject/spyder-py3'"

export PROJECTPATH="$OLD_PROJECTPATH"

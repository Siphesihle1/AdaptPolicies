#!/bin/bash

PREFIX=$1

# ----- installs pyenv -----

# 1. Check if pyenv already exists
if command -v pyenv >/dev/null 2>&1
then
  echo "pyenv is already installed"
  exit 0
fi

# 2. Install pyenv if it doesn't exist
PYENV_ROOT="${HOME}/.pyenv"
PATH=$PYENV_ROOT/bin:$PATH

cd $PREFIX

curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ${HOME}/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ${HOME}/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ${HOME}/.profile
echo 'eval "$(pyenv init - bash)"' >> ${HOME}/.profile
. ${HOME}/.profile

# 3. Installing additional dependencies for pyenv
echo "Installing pyenv dependencies..."
sudo apt-get install -y \
  make \
  libxml2-dev \
  libxmlsec1-dev \
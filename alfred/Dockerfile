FROM nvidia/cuda:13.0.0-cudnn-devel-ubuntu24.04

ARG USER_NAME

SHELL [ "/bin/bash", "-l", "-c" ]

RUN apt update -y
RUN useradd -ms /bin/bash $USER_NAME
RUN usermod -aG sudo $USER_NAME

RUN apt install -y \
   build-essential \
   libssl-dev \
   zlib1g-dev \
   libbz2-dev \
   libreadline-dev \
   libsqlite3-dev \
   wget \
   curl \
   llvm \
   libncursesw5-dev \
   xz-utils \
   tk-dev \
   libffi-dev \
   liblzma-dev \
   git

WORKDIR /home/$USER_NAME

# --- Pyenv setup ---
ENV PYENV_ROOT="/home/$USER_NAME/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"

RUN curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
RUN echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
RUN echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
RUN echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.profile
RUN echo 'eval "$(pyenv init - bash)"' >> ~/.profile
RUN source ${HOME}/.bashrc

# install system dependencies
COPY ./scripts/install_deps.sh /tmp/install_deps.sh
RUN yes "Y" | /tmp/install_deps.sh

# setup python environment
RUN cd $WORKDIR
RUN apt install make build-essential libssl-dev zlib1g-dev \
   libbz2-dev libreadline-dev libsqlite3-dev curl git \
   libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev -y
RUN pyenv install 3.7
# RUN pyenv versions
RUN pyenv global 3.7
ENV VIRTUAL_ENV=/home/$USER_NAME/alfred_env
RUN pip install virtualenv
RUN python -m virtualenv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# install python requirements
RUN pip install --upgrade pip==19.3.1
RUN pip install -U setuptools
# RUN apt install python3-setuptools -y
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# install GLX-Gears (for debugging)
RUN apt-get install -y \
   mesa-utils && \
   rm -rf /var/lib/apt/lists/*

# change ownership of everything to our user
RUN mkdir /home/$USER_NAME/alfred
RUN cd /home/$USER_NAME && echo $(pwd) && chown $USER_NAME:$USER_NAME -R .

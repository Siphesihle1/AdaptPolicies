FROM alfred:latest

ARG USER_NAME

# Modify user permissions
RUN usermod -aG tty $USER_NAME

# Setup
RUN apt install tmux -y

USER $USER_NAME

RUN ls -l /dev/tty2

WORKDIR /home/$USER_NAME

# Setup python environment
RUN cd $WORKDIR
RUN pyenv global 3.7
CMD [ "/bin/bash", "-l", "-c", "source", "~/alfred_env/bin/activate" ]
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ENV ALFRED_ROOT=~/alfred
ENV ALFRED_DATA=/data

ENV DISPLAY=:0
RUN mkdir agent
COPY example_agent.py ./agent
COPY startx.py .

# Start x server
RUN tmux new -s startx
RUN ls /usr/local/lib
RUN python ./startx.py 0

# Run agent
RUN python ./agent/example_agent.py

# CMD [ "lspci", "-vmm" ]
# ENTRYPOINT [ "/bin/bash", "-l", "-c" ]
# CMD [ "ls", "/usr/local/lib" ]
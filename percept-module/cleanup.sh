#!/bin/bash
docker compose down
docker container rm percept_module
docker image rm percept_module:latest
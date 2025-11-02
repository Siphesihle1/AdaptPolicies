#!/usr/bin/env python

#########
# Credit: https://github.com/RobotLocomotion/pytorch-dense-correspondence/blob/master/docker/docker_build.py
#########

from __future__ import print_function

import argparse
import os
import getpass

if __name__=="__main__":

    print("building docker container . . . ")
    user_name = getpass.getuser()
    default_image_name = 'alfred:latest'


    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--image", type=str,
                        help="name for the newly created docker image", default=default_image_name)

    parser.add_argument("-dr", "--dry_run", action='store_true', help="(optional) perform a dry_run, print the command that would have been executed but don't execute it.")

    parser.add_argument('-p', "--passthrough", type=str, help="(optional) passthrough arguments to add to the docker build")

    args = parser.parse_args()
    print("building docker image named ", args.image)
    cmd = "docker build --build-arg USER_NAME=%(user_name)s" %{'user_name': user_name,}

    if args.passthrough:
        cmd += " " + args.passthrough

    cmd += " -t %s -f Dockerfile ." % args.image


    print("command = \n \n", cmd)
    print("")

    # build the docker image
    if not args.dry_run:
        print("executing shell command")
        os.system(cmd)
    else:
        print("dry run, not executing command")

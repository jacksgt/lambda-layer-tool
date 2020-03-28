#!/usr/bin/env python3

import yaml
import subprocess
import venv
import os
import sys
import shutil
import random
import argparse


def main():

    parser = argparse.ArgumentParser(prog=__name__,
                                     description='Builds and publishes Lambda layers defined in layers.yaml')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--build',
                       nargs='*',
                       metavar='LAYER',
                       default=None,
                       help='Publish the specified layers, or all if none given.')
    group.add_argument('--publish',
                       nargs='*',
                       metavar='LAYER',
                       default=None,
                       help='Publish the specified layers, or all if none given.')
    group.add_argument('--list',
                       action='store_true',
                       help='List available layers.')

    args = parser.parse_args()

    with open('layers.yaml', 'r') as stream:
        try:
            data = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            print(e)
            sys.exit(1)

        if data['version'].strip() != '0.2':
            print("Unsupport file version: ", data['version'])
            sys.exit(1)

        for key, value in data['layers'].items():
            if args.list:
                print(key)

            if args.build != None and (args.build == [] or key in args.build):
                if build_layer(key, value):
                    print("Failed to build layer ", key, ", aborting.")
                    sys.exit(1)

            if args.publish != None and (args.publish == [] or key in args.publish):
                if publish_layer(key, value):
                    print("Failed to publish layer ", key, ", aborting.")
                    sys.exit(1)


def publish_layer(layername, options):
    description = options['description']
    runtimes = options['runtimes']

    aws_publish_layer_cmd = ['aws', 'lambda', 'publish-layer-version',
                             '--layer-name', layername,
                             '--description', description,
                             '--zip-file', 'fileb://' + layername + '.zip',
                             '--compatible-runtimes' ] + runtimes

    try:
        proc = subprocess.run(aws_publish_layer_cmd)
        proc.check_returncode()
    except subprocess.CalledProcessError as e:
        print(e)
        return 1


def build_layer(layername, options):
    requirements = options['requirements']
    excludes = options['excludes']
    runtime = options['runtimes'][0]

    if not check_runtime(runtime):
        return 1

    # TODO: Use tempfile and os.path.join
    # generate random id
    rid = "".join([random.choice("0123456789") for x in range(10)])

    # set paths
    tmp_dir = "/tmp/layer-tool/{}/".format(rid)
    venv_dir = tmp_dir + "venv/"
    pip_bin = venv_dir + "bin/pip"
    lambda_dir = tmp_dir + "python/"
    outfile = layername + ".zip"

    # activate virtualenv
    venv.create(tmp_dir + "venv", with_pip=True)

    # install requirements with pip in venv
    for r in requirements:
        try:
            proc = subprocess.run([pip_bin, "install", r])
            proc.check_returncode()
        except subprocess.CalledProcessError as e:
            print(e)
            return 1

    # create a new directory
    # which only contains files relevant to the lambda layer
    # and change to it
    os.mkdir(lambda_dir)
    os.rename(venv_dir + "lib/", lambda_dir + "lib/")
    work_dir = os.getcwd()
    os.chdir(tmp_dir)

    # put current configuration into the folder
    with open('python/layer.yaml', 'w') as outstream:
        yaml.safe_dump({layername: options}, outstream, default_flow_style=False)

    # strip libraries
    # this command will fail when find returns no matching files
    try:
        proc = subprocess.run(["find", ".", "-name", "*.so", "-exec", "strip", "{}", "+"])
        proc.check_returncode()
    except subprocess.CalledProcessError as e:
        print(e)
        return 1

    # package to zip archive and exclude unnecessary files
    zip_cmd = ['zip', '-r', '-9', work_dir + "/" + outfile, "python/"]
    for e in excludes:
        zip_cmd.append('-x')
        zip_cmd.append(e)

    try:
        proc = subprocess.run(zip_cmd)
        proc.check_returncode()
    except subprocess.CalledProcessError as e:
        print(e)
        return 1

    os.chdir(work_dir)

    # delete temp directory
    shutil.rmtree(tmp_dir)

    # notify user
    statinfo = os.stat(outfile)
    print("Successfully created {}, size {} B".format(outfile, statinfo.st_size))
    return 0


def check_runtime(expected_runtime):
    actual_runtime = "python{}.{}".format(sys.version_info[0], sys.version_info[1])
    if actual_runtime != expected_runtime:
        print("Error: specified runtime {} does not match: {}".format(expected_runtime, actual_runtime))
        return False

    return True


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile
import venv
import yaml


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

        if data['version'].strip() != '0.3':
            print("Unsupport file version: ", data['version'])
            sys.exit(1)

        for key, value in data['layers'].items():
            if args.list:
                print(key)

            if args.build is not None and (args.build == [] or key in args.build):
                if build_layer(key, value):
                    print("Failed to build layer ", key, ", aborting.")
                    sys.exit(1)

            if args.publish is not None and (args.publish == [] or key in args.publish):
                if publish_layer(key, value):
                    print("Failed to publish layer ", key, ", aborting.")
                    sys.exit(1)


def publish_layer(layername, options):
    description = options['description']
    runtime = options['runtimes']

    aws_publish_layer_cmd = ['aws', 'lambda', 'publish-layer-version',
                             '--layer-name', layername,
                             '--description', description,
                             '--zip-file', 'fileb://' + layername + '.zip',
                             '--compatible-runtimes', runtime]

    try:
        proc = subprocess.run(aws_publish_layer_cmd)
        proc.check_returncode()
    except subprocess.CalledProcessError as e:
        print(e)
        return 1

    return 0


def build_layer(layername, options):
    requirements = options['requirements']
    excludes = options['excludes']
    runtime = options['runtimes']

    if not check_runtime(runtime):
        return 1

    # create temporary directory
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_dir_path = tmp_dir.name
    print('created temporary directory', tmp_dir_path)

    # set_paths
    venv_dir = os.path.join(tmp_dir_path, "venv/")
    pip_bin = os.path.join(venv_dir, "bin/pip")
    lambda_dir = os.path.join(tmp_dir_path, "python/")
    outfile = layername + ".zip"

    # activate virtualenv
    venv.create(venv_dir, with_pip=True)

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
    os.rename(os.path.join(venv_dir, "lib/"), os.path.join(lambda_dir, "lib/"))
    work_dir = os.getcwd()
    os.chdir(tmp_dir_path)

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
    zip_cmd = ['zip', '-r', '-9', os.path.join(work_dir, outfile), "python/"]
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
    tmp_dir.cleanup()

    # notify user
    statinfo = os.stat(outfile)
    print("Successfully created {}, size {} kB".format(outfile, statinfo.st_size/1000))
    return 0


def check_runtime(expected_runtime):
    actual_runtime = "python{}.{}".format(sys.version_info[0], sys.version_info[1])
    if actual_runtime != expected_runtime:
        print("Error: specified runtime {} does not match: {}".format(expected_runtime, actual_runtime))
        return False

    return True


if __name__ == "__main__":
    main()

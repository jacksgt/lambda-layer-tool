#!/usr/bin/env python3

import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile
from typing import List
import venv # type: ignore
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
            data: dict = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            print(e)
            return 1

        file_version: str = data.get('version', '').strip()
        if not file_version:
            print("Warning: no version specified in file!")
        elif file_version != '0.3':
            print("Unsupport file version: ", file_version)
            return 1

        # basic sanity check for YAML file structure
        layers: dict = data.get('layers', {})
        if not layers:
            print("No layers found in configuration file")
            return 1

        default_excludes: List[str] = data.get('default_excludes', [])

        for key, value in layers.items():
            if args.list:
                # just print out the layer name
                print(key)

            if args.build is not None and (args.build == [] or key in args.build):
                # merge the default and local exclude arrays
                excludes: List[str] = value.get('excludes', [])
                value['excludes'] = excludes + default_excludes
                if build_layer(key, value):
                    print("Failed to build layer ", key, ", aborting.")
                    return 1

            if args.publish is not None and (args.publish == [] or key in args.publish):
                if publish_layer(key, value):
                    print("Failed to publish layer ", key, ", aborting.")
                    return 1


def publish_layer(layername: str, options: dict) -> int:
    description: str = options.get('description', ' ')
    runtime: str = options.get('runtimes', '[]')

    aws_publish_layer_cmd: List[str] = ['aws', 'lambda', 'publish-layer-version',
                                        '--layer-name', layername,
                                        '--description', description,
                                        '--zip-file', 'fileb://' + layername + '.zip',
                                        '--compatible-runtimes', runtime]

    try:
        proc: subprocess.CompletedProcess = subprocess.run(aws_publish_layer_cmd)
        proc.check_returncode()
    except subprocess.CalledProcessError as e:
        print(e)
        return 1

    return 0


def build_layer(layername: str, options: dict) -> int:
    requirements: List[str] = options.get('requirements', [])
    if not requirements:
        print("No requirements found for layer " + layername)
        return 1

    excludes: List[str] = options.get('excludes', [])
    runtime: str = options.get('runtimes', '')
    if not runtime:
        print("No runtime specified for layer " + layername)
        return 1
    if not check_runtime(runtime):
        return 1

    pre_install_cmds: List[str] = options.get('pre_installs', [])

    # create temporary directory and change to it (also save old path)
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_dir_path: str = tmp_dir.name
    print('created temporary directory', tmp_dir_path)
    work_dir: str = os.getcwd()
    os.chdir(tmp_dir_path)

    # set_paths
    venv_dir: str = os.path.join(tmp_dir_path, "venv/")
    pip_bin: str = os.path.join(venv_dir, "bin/pip")
    lambda_dir: str = os.path.join(tmp_dir_path, "python/")
    outfile: str = layername + ".zip"

    # create a new directory
    # which only contains files relevant to the lambda layer
    os.mkdir(lambda_dir)

    # activate virtualenv
    venv.create(venv_dir, with_pip=True)

    # run pre-install steps
    for cmd in pre_install_cmds:
        try:
            proc: subprocess.CompletedProcess = subprocess.run(cmd, shell=True)
            proc.check_returncode()
        except subprocess.CalledProcessError as e:
            print(e)
            return 1

    # install requirements with pip in venv
    for r in requirements:
        try:
            proc = subprocess.run([pip_bin, "install", r])
            proc.check_returncode()
        except subprocess.CalledProcessError as e:
            print(e)
            return 1

    # move (copy) the installed requirements into the layer path
    os.rename(os.path.join(venv_dir, "lib/"), os.path.join(lambda_dir, "lib/"))

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
    zip_cmd: List[str] = ['zip', '-r', '-9', os.path.join(work_dir, outfile), "python/"]
    for exclude in excludes:
        zip_cmd.append('-x')
        zip_cmd.append(exclude)

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
    statinfo: os.stat_result = os.stat(outfile)
    print("Successfully created {}, size {} kB".format(outfile, statinfo.st_size/1000))
    return 0


def check_runtime(expected_runtime: str) -> bool:
    actual_runtime: str = "python{}.{}".format(sys.version_info[0], sys.version_info[1])
    if actual_runtime != expected_runtime:
        print("Error: specified runtime {} does not match: {}".format(expected_runtime, actual_runtime))
        return False

    return True


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import tempfile
from typing import List, Dict, Any
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
            data: Dict[str, Any] = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            print(e)
            return 1

    file_version: str = data.get('version', '').strip()
    if not file_version:
        print("Warning: no version specified in file!")
    elif file_version != '0.3':
        print("Unsupported file version: ", file_version)
        return 1

    # basic sanity check for YAML file structure
    layers: Dict[str, Any] = data.get('layers', {})
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

    return 0


def publish_layer(layername: str, options: Dict[str, Any]) -> int:
    description: str = options.get('description', ' ')
    runtime: str = options.get('runtimes', '[]')

    aws_publish_layer_cmd: List[str] = ['aws', 'lambda', 'publish-layer-version',
                                        '--layer-name', layername,
                                        '--description', description,
                                        '--zip-file', 'fileb://' + layername + '.zip',
                                        '--compatible-runtimes', runtime]

    try:
        subprocess.run(aws_publish_layer_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(e)
        return 1

    return 0


def build_layer(layername: str, options: Dict[str, Any]) -> int:
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
    node_modules_dir: str = os.path.join(tmp_dir_path, "node_modules/")
    pip_bin: str = os.path.join(venv_dir, "bin/pip")
    outfile: str = layername + ".zip"

    lambda_dir: str
    if runtime.startswith("python"):
        lambda_dir = os.path.join(tmp_dir_path, "python")
    elif runtime.startswith("node"):
        lambda_dir = os.path.join(tmp_dir_path, "nodejs")

    # create a new directory
    # which only contains files relevant to the lambda layer
    os.mkdir(lambda_dir)

    if runtime.startswith('python'):
        # activate virtualenv
        venv.create(venv_dir, with_pip=True)

        # run pre-install steps
        for cmd in pre_install_cmds:
            try:
                subprocess.run(cmd, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return 1

        # install requirements with pip in venv
        for r in requirements:
            try:
                subprocess.run([pip_bin, "install", r], check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return 1

        # save venv packages
        with open(os.path.join(lambda_dir, 'pip-freeze.txt'), 'w') as outstream:
            try:
                subprocess.run([pip_bin, "freeze"], stdout=outstream, check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return 1

        # move (copy) the installed requirements into the layer path
        os.rename(os.path.join(venv_dir, "lib/"), os.path.join(lambda_dir, "lib/"))

    elif runtime.startswith('node'):
        # this ensures pre-install commands work properly
        os.mkdir(node_modules_dir)

        # run pre-install steps
        for cmd in pre_install_cmds:
            try:
                subprocess.run(cmd, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return 1

        # install packages with npm
        for r in requirements:
            try:
                subprocess.run(["npm", "install", r], check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return 1

        # save installed packages
        with open(os.path.join(lambda_dir, 'npm-list.txt'), 'w') as outstream:
            try:
                subprocess.run(["npm", "list"], stdout=outstream, check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return 1

        # move the installed dependencies into the layer path
        os.rename(node_modules_dir, os.path.join(lambda_dir, "node_modules/"))
        os.rename(os.path.join(tmp_dir_path, "package-lock.json"), os.path.join(lambda_dir, "package-lock.json"))

    # put current layer configuration into the folder
    with open(os.path.join(lambda_dir, 'layer.yaml'), 'w') as outstream:
        yaml.safe_dump({layername: options}, outstream, default_flow_style=False)

    # strip libraries
    # this command will fail when find returns no matching files
    try:
        subprocess.run(["find", ".", "-name", "*.so", "-exec", "strip", "{}", "+"], check=False)
    except subprocess.CalledProcessError as e:
        print(e)
        return 1

    # package to zip archive and exclude unnecessary files
    zip_cmd: List[str] = ['zip', '--filesync', '-r', '-9', os.path.join(work_dir, outfile), os.path.basename(lambda_dir)]
    for exclude in excludes:
        zip_cmd.append('-x')
        zip_cmd.append(exclude)

    try:
        subprocess.run(zip_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(e)
        return 1

    # change back to the old working directory
    os.chdir(work_dir)

    # delete temp directory
    tmp_dir.cleanup()

    # notify user
    statinfo: os.stat_result = os.stat(outfile)
    print("Successfully created {}, size {} kB".format(outfile, statinfo.st_size/1000))
    return 0


def check_runtime(expected_runtime: str) -> bool:
    actual_runtime: str
    if expected_runtime.startswith("python"):
        actual_runtime = "python{}.{}".format(sys.version_info[0], sys.version_info[1])
    elif expected_runtime.startswith("node"):
        node_major_version: str = subprocess.check_output(["node", "--version"]).decode("ascii")
        node_major_version = node_major_version[1:].split('.')[0]
        actual_runtime = "node{}.x".format(node_major_version)
    else:
        print("Error: unsupported runtime {}".format(expected_runtime))
        return False

    if actual_runtime != expected_runtime:
        print("Error: specified runtime {} does not match: {}".format(expected_runtime, actual_runtime))
        return False

    return True


if __name__ == "__main__":
    main()

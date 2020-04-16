# Lambda Layer Tool

![Build status](https://github.com/jacksgt/lambda-layer-tool/workflows/Python%20application/badge.svg?branch=master)

A tool to programmatically build and publish Layers for AWS Lambda.

Instead of manually copy & pasting build instructions for a Lambda Layer into your shell or trying to script your way around, use this tool to automate the process.
Given a simple YAML file, it will:
* create a new, clean directory for the lambda layer,
* run specified pre-installation commands,
* install python requirements with Pip in a virtual environment,
* strip any binaries and libraries in the lambda directory,
* apply global and layer-specific exclusion patterns,
* bundle the remainder up into a ZIP archive.

Then, you can use the tool to publish the new layer (version) on AWS.

For a full introduction, read the [introductory blog post](https://blog.cubieserver.de/2020/lambda-layer-tool/).

Here is a simple example:
```yaml
---
version: '0.3'
default_excludes:
  - '*.dist-info/*'
  - '*.egg-info/*'
  - '*/__pycache__/*'
  - '*.pyc'
layers:
  awesome-numpy:
    description: 'Minimal numpy 1.18'
    runtimes: 'python3.6'
    pre_installs:
      - 'yum install gcc-gfortran'
    requirements:
      - 'numpy==1.18.2'
    excludes:
      - '*/numpy/tests/*'
```

Then just run:
```
$ ./layer-tool.py --build awesome-numpy
[...]

$ du -h awesome-numpy.zip
13M

$ ./layer-tool.py --publish awesome-numpy
{
    "Content": {
        "Location": "https://example.com/aws",
        "CodeSha256": "xxQC6FDxg63M5m2UL2cXmChD+dFX7fp61LRrrqmVjGY=",
        "CodeSize": 13590501
    },
    "LayerArn": "arn:aws:lambda:$AWS_REGION:$AWS_ID:layer:awesome-numpy",
    "LayerVersionArn": "arn:aws:lambda:$AWS_REGION:$AWS_ID:layer:awesome-numpy:1",
    "Description": "Minimal numpy 1.18 for python3.7",
    "CreatedDate": "2020-03-28T07:40:49.714+0000",
    "Version": 1,
    "CompatibleRuntimes": [
        "python3.7"
    ]
}
```

To learn how to use this tool to reduce the size of your layers, read the [post about creating a minimal boto3 layer](https://blog.cubieserver.de/2020/building-a-minimal-boto3-lambda-layer/).

## Lambda Environment

To match the environment of AWS Lambda functions as closely as possible (especially when you use this tool on non-Linux systems), the tool should be run inside a Docker container.
The [lambci/lambda Docker image](https://github.com/lambci/docker-lambda) closely resembles the real Lambda environment and is well-suited for this task.
Example:

```
docker run --rm -v "$PWD:/var/task" lambci/lambda:build-python3.7 ./layer-tool.py --build awesome-numpy
```

## Publishing

Publishing assumes you have previously configured the aws-cli to connect to your AWS account.

**Note**: Publishing *always* creates a new version of your layer. For more information see https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html .

## Dependencies

In addition to the Python dependencies (`requirements.txt`), this tool currently needs the following command line tools:

* aws-cli (aws)
* find
* zip

## Limitations

Currently, this tool only supports building Python layers with Pip.
However, it should be fairly straightforward to extend the functionality to other runtimes, e.g. JavaScript.

## License

This software is license under the [MIT License](https://spdx.org/licenses/MIT.html).
See `LICENSE`.

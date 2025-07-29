#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='common',
    version='0.0.1',
    description='backstage-aws-resource-collector common code',
    author='ServerlessOps',
    license='Apache License 2.0',
    packages=find_packages(exclude=['tests.*', 'tests']),
    keywords="backstage-aws-resource-collector service",
    python_requires='>=3.13',
    include_package_data=True,
    install_requires=[
        'aws_lambda_powertools',
        'boto3',
        'boto3-stubs[organizations]',
        'dataclasses-json',
    ],
    extras_require={
        'dev': [
            'pytest',
            'pytest-mock',
            'moto',
            'boto3-stubs[ec2]',
            'boto3-stubs[sts]',
        ]
    },
    classifiers=[
        'Environment :: Console',
        'Environment :: Other Environment',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.13',
    ]
)


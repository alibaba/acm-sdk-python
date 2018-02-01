from setuptools import setup, find_packages
import acm

setup(
    name='acm-sdk-python',
    version=acm.__version__,
    packages=find_packages(exclude=["test"]),
    url='',
    license='',
    author='acm',
    author_email='755063194@qq.com',
    description='Python client for ACM.',
    install_requires=[],
)

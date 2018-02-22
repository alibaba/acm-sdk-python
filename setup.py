from setuptools import setup, find_packages
import acm

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = open('README.md').read()

setup(
    name="acm-sdk-python",
    version=acm.__version__,
    packages=find_packages(exclude=["test"]),
    url="https://github.com/alibaba/acm-sdk-python",
    license="Apache License 2.0",
    author="acm",
    author_email="755063194@qq.com",
    description="Python client for ACM.",
    long_description=long_description,
    install_requires=[],
    entry_points={
      "console_scripts": ["acm=acm.command:main"],
    },
)

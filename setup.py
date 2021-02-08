import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ibparser",
    version="0.0.1",
    author="belugame",
    author_email="mb@altmuehl.net",
    description="Transaction and portfolio analysis for your InteractiveBroker CSV files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/belugame/ibparser",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: Unix",
    ],
    python_requires=">=3.8",
    install_requires=[
        "forex-python",
        "matplotlib",
        "pandas",
        "peewee",
        "yahoo-historical",
    ],
    entry_points={
        "console_scripts": ["ibp=ibp.__main__:main"],
    },
    include_package_data=True,
)

from setuptools import setup, find_packages

setup(
    name="ant",                     # The name of the package
    version="1.3.0",                # Version number
    description="Ant Generative Visual Library",      # Short description
    author="EPFL+ECAL Lab",         # Author name
    packages=find_packages(where="src"),  # Finds all Python packages inside the 'src/' folder
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    package_dir={"": "src"},        # Tells setuptools where your code is
    install_requires=[              # Dependencies
        "requests>=2.0",
    ],
)
from setuptools import setup, find_packages

setup(
    name="solar-monitoring-system",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "Flask==2.3.3",
        "requests==2.31.0",
        "gunicorn==21.2.0",
    ],
)

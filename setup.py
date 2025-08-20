from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='ChessTournamentManager',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'run-tournament=app:main',
        ],
    },
    author='Your Name',
    author_email='your.email@example.com',
    description='A web application for managing chess tournaments using the Swiss system',
    keywords='chess tournament swiss-system flask',
    url='https://github.com/yourusername/ChessPairings',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)

from setuptools import setup

def get_extras(rel_path):
	with open(rel_path) as f:
		extras = [line for line in f.read().splitlines() if not line.startswith('#')]
	return extras

def get_version(rel_path):
	with open(rel_path) as f:
		for line in f.read().splitlines():
			if line.startswith('__version__'):
				delim = '"' if '"' in line else "'"
				return line.split(delim)[1]
	raise RuntimeError('Unable to find version string')

setup(
	name='sushasan',
	version=get_version('sushasan.py'),
	author='Marcin Ulikowski',
	author_email='marcin@ulikowski.pl',
	description='Domain name permutation engine for detecting homograph phishing attacks, typo squatting, and brand impersonation',
	long_description='Project website: https://github.com/elceef/sushasan',
	url='https://github.com/elceef/sushasan',
	license='ASL 2.0',
	py_modules=['sushasan'],
	entry_points={
		'console_scripts': ['sushasan=sushasan:run']
	},
	install_requires=[],
	extras_require={
		'full': get_extras('requirements.txt'),
	},
	classifiers=[
		'Programming Language :: Python :: 3',
		'License :: OSI Approved :: Apache Software License',
		'Operating System :: OS Independent',
	],
)

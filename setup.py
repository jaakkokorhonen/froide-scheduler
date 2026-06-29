from setuptools import setup, find_packages

setup(
    name='froide-scheduler',
    version='0.1.0',
    description='Cloud SQL automaattinen sammutus/herätys Froide-asennuksille',
    packages=find_packages(),
    python_requires='>=3.10',
    install_requires=[
        'Django>=4.2',
        'google-auth>=2.0',
        'google-api-python-client>=2.0',
    ],
)

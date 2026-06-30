from setuptools import setup, find_packages

setup(
    name='froide-scheduler',
    version='0.2.0',
    description='Cloud SQL automaattinen sammutus/herätys ja Google ja GitHub SSO Froide-asennuksille',
    packages=find_packages(),
    python_requires='>=3.10',
    install_requires=[
        'Django>=4.2',
        'google-auth>=2.0',
        'google-api-python-client>=2.0',
        'django-allauth>=0.63',
    ],
    extras_require={
        'sso': ['django-allauth>=0.63'],
    },
)

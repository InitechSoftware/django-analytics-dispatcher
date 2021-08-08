import os
from setuptools import setup

f = open(os.path.join(os.path.dirname(__file__), 'README.md'))
readme = f.read()
f.close()

setup(
    name='django-analytics-dispatcher',
    version='0.9',
    description='Common way to send event to Amplitude, Intercom, User.com',
    long_description=readme,
    author="Andrey Chichak",
    author_email='andrey.chichak@initech.co.il',
    url='https://github.com/InitechSoftware/django-analytics-dispatcher',
    packages=['analytics_dispatcher'],
    include_package_data=True,
    install_requires=['django>=3.2', 'requests', 'django-ipware', 'ua-parser',
                      'django-admin-list-filter-dropdown', 'mixpanel'],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        # 'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)

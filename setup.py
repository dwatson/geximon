#!/usr/bin/python
import distutils.core

VERSION = '0.7.7'
long_description = \
"""Geximon is a monitor for the exim mail server. It has all the features
of the original program, eximon, plus some more, and looks nicer."""

distutils.core.setup(
        name='geximon',
        version=VERSION,
        description="exim MTA monitor",
        long_description=long_description,
        url='http://geximon.planetwatson.co.uk/',
        scripts=['scripts/geximon'],
        data_files=[('share/doc/geximon', ['README', 'doc/geximon.html']),
                    ('share/doc/geximon/docbook', ['doc/geximon-C.xml']),
                    ('share/man/man8', ['doc/geximon.8']),
                    ('share/omf/geximon', ['doc/geximon-C.omf']),
                    ('share/pixmaps', ['pixmaps/geximon-16x16.xpm',
                                       'pixmaps/geximon-32x32.xpm']),
                    # XXX lithuanian translation
                    ('share/locale/lt/LC_MESSAGES', ['translation/geximon.mo'])],
        packages = ['geximon'],
        author="Gintautas Miliauskas",
        author_email="gintas@pov.lt",
        maintainer="David Watson",
        maintainer_email="david@planetwatson.co.uk",
        license='GPL',
        platforms='POSIX',
        classifiers = [
            'Development Status :: 5 - Production/Stable',
            'Environment :: X11 Applications :: Gnome',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Operating System :: POSIX',
            'Programming Language :: Python',
            'Topic :: System :: Networking :: Monitoring',
            ]
        )

# run scrollkeeper-update after installation
# XXX this runs while building the Debian package but does no harm
import sys, os
if 'install' in sys.argv:
    os.system('scrollkeeper-update -q')

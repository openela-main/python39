# ==================
# Top-level metadata
# ==================

%global pybasever 3.9

# pybasever without the dot:
%global pyshortver 39

Name: python%{pyshortver}
Summary: Version %{pybasever} of the Python interpreter
URL: https://www.python.org/

#  WARNING  When rebasing to a new Python version,
#           remember to update the python3-docs package as well
%global general_version %{pybasever}.16
#global prerel ...
%global upstream_version %{general_version}%{?prerel}
Version: %{general_version}%{?prerel:~%{prerel}}
Release: 1%{?dist}.2
License: Python

# Exclude i686 arch. Due to a modularity issue it's being added to the
# x86_64 compose of CRB, but we don't want to ship it at all.
# See: https://projects.engineering.redhat.com/browse/RCM-72605
ExcludeArch: i686

# ==================================
# Conditionals controlling the build
# ==================================

# Note that the bcond macros are named for the CLI option they create.
# "%%bcond_without" means "ENABLE by default and create a --without option"

# Main Python, i.e. whether this is the main Python version in the distribution
# that owns /usr/bin/python3 and other unique paths
# This also means the built subpackages are called python3 rather than python3X
# WARNING: This also influences the flatpackage bcond below.
# By default, this is determined by the %%__default_python3_pkgversion value
# RHEL: Disabled by default
%bcond_with main_python

# Flat package, i.e. no separate subpackages
# Default (in Fedora): if this is a main Python, it is not a flatpackage
# Not supported: Combination of flatpackage enabled and main_python enabled
# RHEL: Disabled by default
%bcond_with flatpackage

# When bootstrapping python3, we need to build setuptools.
# but setuptools BR python3-devel and that brings in python3-rpm-generators;
# python3-rpm-generators needs python3-setuptools, so we cannot have it yet.
#
# We also use the previous build of Python in "make regen-all"
# and in "distutils.tests.test_bdist_rpm".
#
# Procedure: https://fedoraproject.org/wiki/SIGs/Python/UpgradingPython
#
#   IMPORTANT: When bootstrapping, it's very likely the wheels for pip and
#   setuptools are not available. Turn off the rpmwheels bcond until
#   the two packages are built with wheels to get around the issue.
%bcond_with bootstrap

# Whether to use RPM build wheels from the python-{pip,setuptools}-wheel package
# Uses upstream bundled prebuilt wheels otherwise
%bcond_without rpmwheels

# Expensive optimizations (mainly, profile-guided optimizations)
%bcond_without optimizations

# https://fedoraproject.org/wiki/Changes/PythonNoSemanticInterpositionSpeedup
%bcond_without no_semantic_interposition

# Run the test suite in %%check
%bcond_without tests

# Extra build for debugging the interpreter or C-API extensions
# (the -debug subpackages)
%if %{with flatpackage}
%bcond_with debug_build
%else
%bcond_without debug_build
%endif

# Support for the GDB debugger
%bcond_without gdb_hooks

# The dbm.gnu module (key-value database)
%bcond_without gdbm

# Main interpreter loop optimization
%bcond_without computed_gotos

# Support for the Valgrind debugger/profiler
%ifarch %{valgrind_arches}
%bcond_without valgrind
%else
%bcond_with valgrind
%endif

# https://fedoraproject.org/wiki/Changes/Python_Upstream_Architecture_Names
# For a very long time we have converted "upstream architecture names" to "Fedora names".
# This made sense at the time, see https://github.com/pypa/manylinux/issues/687#issuecomment-666362947
# However, with manylinux wheels popularity growth, this is now a problem.
# Wheels built on a Linux that doesn't do this were not compatible with ours and vice versa.
# We now have a compatibility layer to workaround a problem,
# but we also no longer use the legacy arch names in Fedora 34+.
# This bcond controls the behavior. The defaults should be good for anybody.
# RHEL: Disabled by default
%bcond_with legacy_archnames

# In RHEL 9+, we obsolete/provide Platform Python from regular Python
# This is only appropriate for the main Python build
# RHEL: Disabled for python39 module
%bcond_with rhel8_compat_shims


# =====================
# General global macros
# =====================

%if %{with main_python}
%global pkgname python3
%global exename python3
%else
%global pkgname python%{pyshortver}
%global exename python%{pybasever}
%endif

%global pylibdir %{_libdir}/python%{pybasever}
%global dynload_dir %{pylibdir}/lib-dynload

# ABIFLAGS, LDVERSION and SOABI are in the upstream configure.ac
# See PEP 3149 for some background: http://www.python.org/dev/peps/pep-3149/
%global ABIFLAGS_optimized %{nil}
%global ABIFLAGS_debug     d

%global LDVERSION_optimized %{pybasever}%{ABIFLAGS_optimized}
%global LDVERSION_debug     %{pybasever}%{ABIFLAGS_debug}

# When we use the upstream arch triplets, we convert them from the legacy ones
# This is reversed in prep when %%with legacy_archnames, so we keep both macros
%global platform_triplet_legacy %{_arch}-linux%{_gnu}
%global platform_triplet_upstream %{expand:%(echo %{platform_triplet_legacy} | sed -E \\
    -e 's/^arm(eb)?-linux-gnueabi$/arm\\1-linux-gnueabihf/' \\
    -e 's/^mips64(el)?-linux-gnu$/mips64\\1-linux-gnuabi64/' \\
    -e 's/^ppc(64)?(le)?-linux-gnu$/powerpc\\1\\2-linux-gnu/')}
%if %{with legacy_archnames}
%global platform_triplet %{platform_triplet_legacy}
%else
%global platform_triplet %{platform_triplet_upstream}
%endif

%global SOABI_optimized cpython-%{pyshortver}%{ABIFLAGS_optimized}-%{platform_triplet}
%global SOABI_debug     cpython-%{pyshortver}%{ABIFLAGS_debug}-%{platform_triplet}

# All bytecode files are in a __pycache__ subdirectory, with a name
# reflecting the version of the bytecode.
# See PEP 3147: http://www.python.org/dev/peps/pep-3147/
# For example,
#   foo/bar.py
# has bytecode at:
#   foo/__pycache__/bar.cpython-%%{pyshortver}.pyc
#   foo/__pycache__/bar.cpython-%%{pyshortver}.opt-1.pyc
#   foo/__pycache__/bar.cpython-%%{pyshortver}.opt-2.pyc
%global bytecode_suffixes .cpython-%{pyshortver}*.pyc

# libmpdec (mpdecimal package in Fedora) is tightly coupled with the
# decimal module. We keep it bundled as to avoid incompatibilities
# with the packaged version.
# The version information can be found at Modules/_decimal/libmpdec/mpdecimal.h
# defined as MPD_VERSION.
%global libmpdec_version 2.5.0

# Python's configure script defines SOVERSION, and this is used in the Makefile
# to determine INSTSONAME, the name of the libpython DSO:
#   LDLIBRARY='libpython$(VERSION).so'
#   INSTSONAME="$LDLIBRARY".$SOVERSION
# We mirror this here in order to make it easier to add the -gdb.py hooks.
# (if these get out of sync, the payload of the libs subpackage will fail
# and halt the build)
%global py_SOVERSION 1.0
%global py_INSTSONAME_optimized libpython%{LDVERSION_optimized}.so.%{py_SOVERSION}
%global py_INSTSONAME_debug     libpython%{LDVERSION_debug}.so.%{py_SOVERSION}

# Disable automatic bytecompilation. The python3 binary is not yet be
# available in /usr/bin when Python is built. Also, the bytecompilation fails
# on files that test invalid syntax.
%undefine py_auto_byte_compile

# When a main_python build is attempted despite the %%__default_python3_pkgversion value
# We undefine magic macros so the python3-... package does not provide wrong python3X-...
# RHEL: DISABLED, __default_python3_pkgversion is not implemented
# %%if %%{with main_python} && ("%%{?__default_python3_pkgversion}" != "%%{pybasever}")
# %%undefine __pythonname_provides
# %%{warn:Doing a main_python build with wrong %%%%__default_python3_pkgversion (0%%{?__default_python3_pkgversion}, but this is %%pyshortver)}
# %%endif

# RHEL: An example egg file is included among the python39-test files and due
# to a bug in python3-rpm-generator, mistaken Provides are generated. So we
# exclude them until the issue is properly addressed.
# See BZ: https://bugzilla.redhat.com/show_bug.cgi?id=1916172
%global __provides_exclude_from ^%{pylibdir}/test/test_importlib/data/example-.*\.egg$

# =======================
# Build-time requirements
# =======================

# (keep this list alphabetized)

BuildRequires: autoconf
BuildRequires: bluez-libs-devel
BuildRequires: bzip2
BuildRequires: bzip2-devel
BuildRequires: desktop-file-utils
BuildRequires: expat-devel

BuildRequires: findutils
BuildRequires: gcc-c++
%if %{with gdbm}
BuildRequires: gdbm-devel
%endif
BuildRequires: git-core
BuildRequires: glibc-all-langpacks
BuildRequires: glibc-devel
BuildRequires: gmp-devel
BuildRequires: gnupg2
BuildRequires: libappstream-glib
BuildRequires: libffi-devel
BuildRequires: libnsl2-devel
BuildRequires: libtirpc-devel
BuildRequires: libGL-devel
BuildRequires: libuuid-devel
BuildRequires: libX11-devel
BuildRequires: make
BuildRequires: ncurses-devel

BuildRequires: openssl-devel
BuildRequires: pkgconfig
BuildRequires: readline-devel
BuildRequires: redhat-rpm-config
BuildRequires: sqlite-devel
BuildRequires: gdb

BuildRequires: tar
BuildRequires: tcl-devel
BuildRequires: tix-devel
BuildRequires: tk-devel
BuildRequires: tzdata

%if %{with valgrind}
BuildRequires: valgrind-devel
%endif

BuildRequires: xz-devel
BuildRequires: zlib-devel

BuildRequires: /usr/bin/dtrace

# workaround http://bugs.python.org/issue19804 (test_uuid requires ifconfig)
BuildRequires: /usr/sbin/ifconfig

%if %{with rpmwheels}
BuildRequires: python%{python3_pkgversion}-setuptools-wheel
BuildRequires: python%{python3_pkgversion}-pip-wheel
%endif

%if %{without bootstrap}
# for make regen-all and distutils.tests.test_bdist_rpm
BuildRequires: python%{pyshortver}
%endif

# Generators run on Python 3.6 so we can take this dependency out of the bootstrap loop
BuildRequires: python3-rpm-generators

# =======================
# Source code and patches
# =======================

Source0: %{url}ftp/python/%{general_version}/Python-%{upstream_version}.tar.xz
Source1: %{url}ftp/python/%{general_version}/Python-%{upstream_version}.tar.xz.asc
Source2: %{url}static/files/pubkeys.txt
Source3: macros.python39

# A simple script to check timestamps of bytecode files
# Run in check section with Python that is currently being built
# Originally written by bkabrda
Source8: check-pyc-timestamps.py

# Desktop menu entry for idle3
Source10: idle3.desktop

# AppData file for idle3
Source11: idle3.appdata.xml

# (Patches taken from github.com/fedora-python/cpython)

# 00001 # d06a8853cf4bae9e115f45e1d531d2dc152c5cc8
# Fixup distutils/unixccompiler.py to remove standard library path from rpath
# Was Patch0 in ivazquez' python3000 specfile
Patch1: 00001-rpath.patch

# 00111 # 93b40d73360053ca68b0aeec33b6a8ca167e33e2
# Don't try to build a libpythonMAJOR.MINOR.a
#
# Downstream only: not appropriate for upstream.
#
# See https://bugzilla.redhat.com/show_bug.cgi?id=556092
Patch111: 00111-no-static-lib.patch

# 00189 # 4242864a6a12f1f4cf9fd63a6699a73f35261aa3
# Instead of bundled wheels, use our RPM packaged wheels
#
# We keep them in /usr/share/python-wheels
#
# Downstream only: upstream bundles
# We might eventually pursuit upstream support, but it's low prio
Patch189: 00189-use-rpm-wheels.patch
# The following versions of setuptools/pip are bundled when this patch is not applied.
# The versions are written in Lib/ensurepip/__init__.py, this patch removes them.
# When the bundled setuptools/pip wheel is updated, the patch no longer applies cleanly.
# In such cases, the patch needs to be amended and the versions updated here:
%global pip_version 21.2.3
%global setuptools_version 57.4.0

# 00251 # 2eabd04356402d488060bc8fe316ad13fc8a3356
# Change user install location
#
# Set values of prefix and exec_prefix in distutils install command
# to /usr/local if executable is /usr/bin/python* and RPM build
# is not detected to make pip and distutils install into separate location.
#
# Fedora Change: https://fedoraproject.org/wiki/Changes/Making_sudo_pip_safe
# Downstream only: Awaiting resources to work on upstream PEP
Patch251: 00251-change-user-install-location.patch

# 00328 # 367fdcb5a075f083aea83ac174999272a8faf75c
# Restore pyc to TIMESTAMP invalidation mode as default in rpmbuild
#
# Since Fedora 31, the $SOURCE_DATE_EPOCH is set in rpmbuild to the latest
# %%changelog date. This makes Python default to the CHECKED_HASH pyc
# invalidation mode, bringing more reproducible builds traded for an import
# performance decrease. To avoid that, we don't default to CHECKED_HASH
# when $RPM_BUILD_ROOT is set (i.e. when we are building RPM packages).
#
# See https://src.fedoraproject.org/rpms/redhat-rpm-config/pull-request/57#comment-27426
# Downstream only: only used when building RPM packages
# Ideally, we should talk to upstream and explain why we don't want this
Patch328: 00328-pyc-timestamp-invalidation-mode.patch

# 00329 #
# Support OpenSSL FIPS mode
# - In FIPS mode, OpenSSL wrappers are always used in hashlib
# - The "usedforsecurity" keyword argument can be used to the various digest
#   algorithms in hashlib so that you can whitelist a callsite with
#   "usedforsecurity=False"
# - OpenSSL wrappers for the hashes blake2{b512,s256},
# - In FIPS mode, the blake2 hashes use OpenSSL wrappers
#   and do not offer extended functionality (keys, tree hashing, custom digest size)
# - In FIPS mode, hmac.HMAC can only be instantiated with an OpenSSL wrapper
#   or an string with OpenSSL hash name as the "digestmod" argument.
#   The argument must be specified (instead of defaulting to ‘md5’).
#
# - Also while in FIPS mode, we utilize OpenSSL's DRBG and disable the
#   os.getrandom() function.
#
Patch329: 00329-fips.patch

# 00353 # ab4cc97b643cfe99f567e3a03e5617b507183771
# Original names for architectures with different names downstream
#
# https://fedoraproject.org/wiki/Changes/Python_Upstream_Architecture_Names
#
# Pythons in RHEL/Fedora used different names for some architectures
# than upstream and other distros (for example ppc64 vs. powerpc64).
# This was patched in patch 274, now it is sedded if %%with legacy_archnames.
#
# That meant that an extension built with the default upstream settings
# (on other distro or as an manylinux wheel) could not been found by Python
# on RHEL/Fedora because it had a different suffix.
# This patch adds the legacy names to importlib so Python is able
# to import extensions with a legacy architecture name in its
# file name.
# It work both ways, so it support both %%with and %%without legacy_archnames.
#
# WARNING: This patch has no effect on Python built with bootstrap
# enabled because Python/importlib_external.h is not regenerated
# and therefore Python during bootstrap contains importlib from
# upstream without this feature. It's possible to include
# Python/importlib_external.h to this patch but it'd make rebasing
# a nightmare because it's basically a binary file.
Patch353: 00353-architecture-names-upstream-downstream.patch

# 00378 #
# Support expat 2.4.5
#
# Curly brackets were never allowed in namespace URIs
# according to RFC 3986, and so-called namespace-validating
# XML parsers have the right to reject them a invalid URIs.
#
# libexpat >=2.4.5 has become strcter in that regard due to
# related security issues; with ET.XML instantiating a
# namespace-aware parser under the hood, this test has no
# future in CPython.
#
# References:
# - https://datatracker.ietf.org/doc/html/rfc3968
# - https://www.w3.org/TR/xml-names/
#
# Also, test_minidom.py: Support Expat >=2.4.5
#
# The patch has diverged from upstream as the python test
# suite was relying on checking the expat version, whereas
# in RHEL fixes get backported instead of rebasing packages.
#
# Upstream: https://bugs.python.org/issue46811
Patch378: 00378-support-expat-2-4-5.patch

# 00399 # c32eff86eb80f6a6bdcbf4b1b6535fbc627b51a2
# CVE-2023-24329
#
# * gh-102153: Start stripping C0 control and space chars in `urlsplit` (GH-102508)
#
# `urllib.parse.urlsplit` has already been respecting the WHATWG spec a bit GH-25595.
#
# This adds more sanitizing to respect the "Remove any leading C0 control or space from input" [rule](https://url.spec.whatwg.org/GH-url-parsing:~:text=Remove%%20any%%20leading%%20and%%20trailing%%20C0%%20control%%20or%%20space%%20from%%20input.) in response to [CVE-2023-24329](https://nvd.nist.gov/vuln/detail/CVE-2023-24329).
#
# ---------
Patch399: 00399-cve-2023-24329.patch

# 00404 #
# CVE-2023-40217
#
# Security fix for CVE-2023-40217: Bypass TLS handshake on closed sockets
# Resolved upstream: https://github.com/python/cpython/issues/108310
# Fixups added on top from:
# https://github.com/python/cpython/issues/108342
#
Patch404: 00404-cve-2023-40217.patch

# (New patches go here ^^^)
#
# When adding new patches to "python" and "python3" in Fedora, EL, etc.,
# please try to keep the patch numbers in-sync between all specfiles.
#
# More information, and a patch number catalog, is at:
#
#     https://fedoraproject.org/wiki/SIGs/Python/PythonPatches
#
# The patches are stored and rebased at:
#
#     https://github.com/fedora-python/cpython


# ==========================================
# Descriptions, and metadata for subpackages
# ==========================================

# Require alternatives version that implements the --keep-foreign flag
Requires:         alternatives >= 1.19.1-1
Requires(post):   alternatives >= 1.19.1-1
Requires(postun): alternatives >= 1.19.1-1

# When the user tries to `yum install python`, yum will list this package among
# the possible alternatives
Provides: alternative-for(python)

# this if branch is ~300 lines long and contains subpackages' definitions
%if %{without flatpackage}
%if %{with main_python}
# Description for the python3X SRPM only:
%description
Python %{pybasever} is an accessible, high-level, dynamically typed, interpreted
programming language, designed with an emphasis on code readability.
It includes an extensive standard library, and has a vast ecosystem of
third-party libraries.

%package -n %{pkgname}
Summary: Python %{pybasever} interpreter

# In order to support multiple Python interpreters for development purposes,
# packages with the naming scheme flatpackage (e.g. python3.5) exist for
# non-default versions of Python 3.
# For consistency, we provide python3.X from python3 as well.
Provides: python%{pybasever} = %{version}-%{release}
Provides: python%{pybasever}%{?_isa} = %{version}-%{release}
# To keep the upgrade path clean, we Obsolete python3.X.
# Note that using Obsoletes without package version is not standard practice.
# Here we assert that *any* version of the system's default interpreter is
# preferable to an "extra" interpreter. For example, python3-3.6.1 will
# replace python3.6-3.6.2.
Obsoletes: python%{pybasever}

# https://fedoraproject.org/wiki/Changes/Move_usr_bin_python_into_separate_package
# https://fedoraproject.org/wiki/Changes/Python_means_Python3
# We recommend /usr/bin/python so users get it by default
# Versioned recommends are problematic, and we know that the package requires
# python3 back with fixed version, so we just use the path here:
Recommends: %{_bindir}/python
%endif

%if %{with rhel8_compat_shims}
Provides:  platform-python = %{version}-%{release}
Provides:  platform-python%{?_isa} = %{version}-%{release}
Obsoletes: platform-python < %{pybasever}
%endif

# Python interpreter packages used to be named (or provide) name pythonXY (e.g.
# python39). However, to align it with the executable names and to prepare for
# Python 3.10, they were renamed to pythonX.Y (e.g. python3.9, python3.10). We
# provide and obsolete the previous names.
# - Here are the tags for the nonflat package, regardless if main_python (e.g.
#   python3) or not (e.g. python39). For the flat package, the provide is
#   repeated many lines later.
Provides: python%{pyshortver} = %{version}-%{release}
Obsoletes: python%{pyshortver} < %{version}-%{release}
# RHEL: The python39 rpm is named without the dot unlike in Fedora, so we need
# to also provide the name *with* the dot
Provides: python%{pybasever} = %{version}-%{release}
Provides: python%{pybasever}%{?_isa} = %{version}-%{release}
Obsoletes: python%{pybasever} < %{version}-%{release}

# Packages with Python modules in standard locations automatically
# depend on python(abi). Provide that here.
Provides: python(abi) = %{pybasever}

Requires: %{pkgname}-libs%{?_isa} = %{version}-%{release}

# Previously, this was required for our rewheel patch to work.
# This is technically no longer needed, but we keep it recommended
# for the developer experience.
Recommends: %{pkgname}-setuptools
Recommends: %{pkgname}-pip

# This prevents ALL subpackages built from this spec to require
# /usr/bin/python3* or python(abi). Granularity per subpackage is impossible.
# It's intended for the libs package not to drag in the interpreter, see
# https://bugzilla.redhat.com/show_bug.cgi?id=1547131
# https://bugzilla.redhat.com/show_bug.cgi?id=1862082
# All other packages require %%{pkgname} explicitly.
%global __requires_exclude ^(/usr/bin/python3|python\\(abi\\))

%description -n %{pkgname}
Python %{pybasever} is an accessible, high-level, dynamically typed, interpreted
programming language, designed with an emphasis on code readability.
It includes an extensive standard library, and has a vast ecosystem of
third-party libraries.

The %{pkgname} package provides the "%{exename}" executable: the reference
interpreter for the Python language, version 3.
The majority of its standard library is provided in the %{pkgname}-libs package,
which should be installed automatically along with %{pkgname}.
The remaining parts of the Python standard library are broken out into the
%{pkgname}-tkinter and %{pkgname}-test packages, which may need to be installed
separately.

Documentation for Python is provided in the %{pkgname}-docs package.

Packages containing additional libraries for Python are generally named with
the "%{pkgname}-" prefix.

For the unversioned "python" executable, see manual page "unversioned-python".


%if %{with main_python}
# https://fedoraproject.org/wiki/Changes/Move_usr_bin_python_into_separate_package
# https://fedoraproject.org/wiki/Changes/Python_means_Python3
%package -n python-unversioned-command
Summary: The "python" command that runs Python 3
BuildArch: noarch

# In theory this could require any python3 version
Requires: python3 == %{version}-%{release}
# But since we want to provide versioned python, we require exact version
Provides: python = %{version}-%{release}
# This also save us an explicit conflict for older python3 builds

# Also provide the name of the Ubuntu package with the same function,
# to be nice to people who temporarily forgot which distro they're on.
# C.f. https://packages.ubuntu.com/hirsute/all/python-is-python3/filelist
Provides: python-is-python3 = %{version}-%{release}

%description -n python-unversioned-command
This package contains /usr/bin/python - the "python" command that runs Python 3.

%endif # with main_python


%package -n %{pkgname}-libs
Summary:        Python runtime libraries

%if %{with rpmwheels}
Requires: python%{python3_pkgversion}-setuptools-wheel
Requires: python%{python3_pkgversion}-pip-wheel
%else
Provides: bundled(python3dist(pip)) = %{pip_version}
Provides: bundled(python3dist(setuptools)) = %{setuptools_version}
%endif

# Provides for the bundled libmpdec
Provides: bundled(mpdecimal) = %{libmpdec_version}
Provides: bundled(libmpdec) = %{libmpdec_version}

# There are files in the standard library that have python shebang.
# We've filtered the automatic requirement out so libs are installable without
# the main package. This however makes it pulled in by default.
# See https://bugzilla.redhat.com/show_bug.cgi?id=1547131
Recommends: %{pkgname}%{?_isa} = %{version}-%{release}

# tkinter is part of the standard library,
# but it is torn out to save an unwanted dependency on tk and X11.
# we recommend it when tk is already installed (for better UX)
Recommends: (%{pkgname}-tkinter%{?_isa} = %{version}-%{release} if tk%{?_isa})

# The zoneinfo module needs tzdata
Requires: tzdata


%description -n %{pkgname}-libs
This package contains runtime libraries for use by Python:
- the majority of the Python standard library
- a dynamically linked library for use by applications that embed Python as
  a scripting language, and by the main "%{exename}" executable


%package -n %{pkgname}-devel
Summary: Libraries and header files needed for Python development
Requires: %{pkgname} = %{version}-%{release}
Requires: %{pkgname}-libs%{?_isa} = %{version}-%{release}
# The RPM related dependencies bring nothing to a non-RPM Python developer
# But we want them when packages BuildRequire python3-devel
Requires: (python-rpm-macros if rpm-build)
Requires: (python3-rpm-macros if rpm-build)

# Require alternatives version that implements the --keep-foreign flag
Requires(postun): alternatives >= 1.19.1-1
# python39 installs the alternatives master symlink to which we attach a slave
Requires(post): %{pkgname}
Requires(postun): %{pkgname}

%if %{without bootstrap}
# This is not "API" (packages that need setuptools should still BuildRequire it)
# However some packages apparently can build both with and without setuptools
# producing egg-info as file or directory (depending on setuptools presence).
# Directory-to-file updates are problematic in RPM, so we ensure setuptools is
# installed when -devel is required.
# See https://bugzilla.redhat.com/show_bug.cgi?id=1623914
# See https://fedoraproject.org/wiki/Packaging:Directory_Replacement
Requires: (%{pkgname}-setuptools if rpm-build)
%endif

# Generators run on Python 3.6 so we can take this dependency out of the bootstrap loop
Requires: (python3-rpm-generators if rpm-build)

Provides: %{pkgname}-2to3 = %{version}-%{release}

Conflicts: %{pkgname} < %{version}-%{release}

%if %{with rhel8_compat_shims}
Provides:  platform-python-devel = %{version}-%{release}
Provides:  platform-python-devel%{?_isa} = %{version}-%{release}
Obsoletes: platform-python-devel < %{pybasever}
%endif

%description -n %{pkgname}-devel
This package contains the header files and configuration needed to compile
Python extension modules (typically written in C or C++), to embed Python
into other programs, and to make binary distributions for Python libraries.

It also contains the necessary macros to build RPM packages with Python modules
and 2to3 tool, an automatic source converter from Python 2.X.

If you want to build an RPM against the python39 module, you also need to
install the python39-rpm-macros package.

%package -n %{pkgname}-idle
Summary: A basic graphical development environment for Python
Requires: %{pkgname} = %{version}-%{release}
Requires: %{pkgname}-tkinter = %{version}-%{release}

Provides: %{pkgname}-tools = %{version}-%{release}
Provides: %{pkgname}-tools%{?_isa} = %{version}-%{release}
Obsoletes: %{pkgname}-tools < %{version}-%{release}

# Require alternatives version that implements the --keep-foreign flag
Requires(postun): alternatives >= 1.19.1-1
# python39 installs the alternatives master symlink to which we attach a slave
Requires(post): %{pkgname}
Requires(postun): %{pkgname}

%description -n %{pkgname}-idle
IDLE is Python’s Integrated Development and Learning Environment.

IDLE has the following features: Python shell window (interactive
interpreter) with colorizing of code input, output, and error messages;
multi-window text editor with multiple undo, Python colorizing,
smart indent, call tips, auto completion, and other features;
search within any window, replace within editor windows, and
search through multiple files (grep); debugger with persistent
breakpoints, stepping, and viewing of global and local namespaces;
configuration, browsers, and other dialogs.


%package -n %{pkgname}-tkinter
Summary: A GUI toolkit for Python
Requires: %{pkgname} = %{version}-%{release}

%description -n %{pkgname}-tkinter
The Tkinter (Tk interface) library is a graphical user interface toolkit for
the Python programming language.


%package -n %{pkgname}-test
Summary: The self-test suite for the main python3 package
Requires: %{pkgname} = %{version}-%{release}
Requires: %{pkgname}-libs%{?_isa} = %{version}-%{release}

%description -n %{pkgname}-test
The self-test suite for the Python interpreter.

This is only useful to test Python itself. For testing general Python code,
you should use the unittest module from %{pkgname}-libs, or a library such as
%{pkgname}-pytest.


%if %{with debug_build}
%package -n %{pkgname}-debug
Summary: Debug version of the Python runtime

# The debug build is an all-in-one package version of the regular build, and
# shares the same .py/.pyc files and directories as the regular build. Hence
# we depend on all of the subpackages of the regular build:
Requires: %{pkgname}%{?_isa} = %{version}-%{release}
Requires: %{pkgname}-libs%{?_isa} = %{version}-%{release}
Requires: %{pkgname}-devel%{?_isa} = %{version}-%{release}
Requires: %{pkgname}-test%{?_isa} = %{version}-%{release}
Requires: %{pkgname}-tkinter%{?_isa} = %{version}-%{release}
Requires: %{pkgname}-idle%{?_isa} = %{version}-%{release}

%if %{with rhel8_compat_shims}
Provides:  platform-python-debug = %{version}-%{release}
Provides:  platform-python-debug%{?_isa} = %{version}-%{release}
Obsoletes: platform-python-debug < %{pybasever}
%endif

# Require alternatives version that implements the --keep-foreign flag
Requires(postun): alternatives >= 1.19.1-1
# python39 installs the alternatives master symlink to which we attach a slave
Requires(post): %{pkgname}
Requires(postun): %{pkgname}

%description -n %{pkgname}-debug
python3-debug provides a version of the Python runtime with numerous debugging
features enabled, aimed at advanced Python users such as developers of Python
extension modules.

This version uses more memory and will be slower than the regular Python build,
but is useful for tracking down reference-counting issues and other bugs.

The debug build shares installation directories with the standard Python
runtime. Python modules -- source (.py), bytecode (.pyc), and C-API extensions
(.cpython*.so) -- are compatible between this and the standard version
of Python.

The debug runtime additionally supports debug builds of C-API extensions
(with the "d" ABI flag) for debugging issues in those extensions.
%endif # with debug_build

%else  # with flatpackage

# We'll not provide this, on purpose
# No package in Fedora shall ever depend on flatpackage via this
%global __requires_exclude ^python\\(abi\\) = 3\\..$
%global __provides_exclude ^python\\(abi\\) = 3\\..$

# Python interpreter packages used to be named (or provide) name pythonXY (e.g.
# python39). However, to align it with the executable names and to prepare for
# Python 3.10, they were renamed to pythonX.Y (e.g. python3.9, python3.10). We
# provide and obsolete the previous names.
# - Here are the tags for the flat package. For the nonflat package, the
#   provide is repeated many lines above.
Provides: python%{pyshortver} = %{version}-%{release}
Obsoletes: python%{pyshortver} < %{version}-%{release}

%if %{with rpmwheels}
Requires: python%{python3_pkgversion}-setuptools-wheel
Requires: python%{python3_pkgversion}-pip-wheel
%else
Provides: bundled(python3dist(pip)) = %{pip_version}
Provides: bundled(python3dist(setuptools)) = %{setuptools_version}
%endif

# Provides for the bundled libmpdec
Provides: bundled(mpdecimal) = %{libmpdec_version}
Provides: bundled(libmpdec) = %{libmpdec_version}

# The zoneinfo module needs tzdata
Requires: tzdata

# The description for the flat package (SRPM and built)
%description
Python %{pybasever} package for developers.

This package exists to allow developers to test their code against a newer
version of Python. This is not a full Python stack and if you wish to run
your applications with Python %{pybasever}, update your Fedora to a newer
version once Python %{pybasever} is stable.

%endif # with flatpackage


%package -n %{pkgname}-rpm-macros
Summary:    RPM macros for building RPMs with Python %{pybasever}
License:    MIT
Provides:   %{pkgname}-modular-devel = %{version}-%{release}
Provides:   python-modular-rpm-macros == %{pybasever}
Conflicts:  python-modular-rpm-macros > %{pybasever}
Requires:   python3-rpm-macros
BuildArch:  noarch

%description -n %{pkgname}-rpm-macros
RPM macros for building RPMs with Python %{pybasever} from the python%{pyshortver} module.
If you want to build an RPM against the python%{pyshortver} module, you need to add:

    BuildRequire: %{pkgname}-rpm-macros.

# ======================================================
# The prep phase of the build:
# ======================================================

%prep
%autosetup -S git_am -N -n Python-%{upstream_version}

# Temporary workaround for https://bugzilla.redhat.com/show_bug.cgi?id=1954999
%{?!apply_patch:%define apply_patch(qp:m:) {%__apply_patch %**}}

# Apply patches up to 188
%apply_patch -q %{PATCH1}
%apply_patch -q %{PATCH111}

%if %{with rpmwheels}
%apply_patch -q %{PATCH189}
rm Lib/ensurepip/_bundled/*.whl
%endif

# Apply the remaining patches
%apply_patch -q %{PATCH251}
%apply_patch -q %{PATCH328}
%apply_patch -q %{PATCH329}
%apply_patch -q %{PATCH353}
%apply_patch -q %{PATCH378}
%apply_patch -q %{PATCH399}
%apply_patch -q %{PATCH404}

# Remove all exe files to ensure we are not shipping prebuilt binaries
# note that those are only used to create Microsoft Windows installers
# and that functionality is broken on Linux anyway
find -name '*.exe' -print -delete

# Remove bundled libraries to ensure that we're using the system copy.
rm -r Modules/expat

# Remove files that should be generated by the build
# (This is after patching, so that we can use patches directly from upstream)
rm configure pyconfig.h.in

# When we use the legacy arch names, we need to change them in configure.ac
%if %{with legacy_archnames}
sed -i configure.ac \
    -e 's/\b%{platform_triplet_upstream}\b/%{platform_triplet_legacy}/'
%endif


# ======================================================
# Configuring and building the code:
# ======================================================

%build

# The build process embeds version info extracted from the Git repository
# into the Py_GetBuildInfo and sys.version strings.
# Our Git repository is artificial, so we don't want that.
# Tell configure to not use git.
export HAS_GIT=not-found

# Regenerate the configure script and pyconfig.h.in
autoconf
autoheader

# Remember the current directory (which has sources and the configure script),
# so we can refer to it after we "cd" elsewhere.
topdir=$(pwd)

# Get proper option names from bconds
%if %{with computed_gotos}
%global computed_gotos_flag yes
%else
%global computed_gotos_flag no
%endif

%if %{with optimizations}
%global optimizations_flag "--enable-optimizations"
%else
%global optimizations_flag "--disable-optimizations"
%endif

# Set common compiler/linker flags
# We utilize the %%extension_...flags macros here so users building C/C++
# extensions with our python won't get all the compiler/linker flags used
# in Fedora RPMs.
# Standard library built here will still use the %%build_...flags,
# Fedora packages utilizing %%py3_build will use them as well
# https://fedoraproject.org/wiki/Changes/Python_Extension_Flags
export CFLAGS="%{extension_cflags} -D_GNU_SOURCE -fPIC -fwrapv"
export CFLAGS_NODIST="%{build_cflags} -D_GNU_SOURCE -fPIC -fwrapv%{?with_no_semantic_interposition: -fno-semantic-interposition}"
export CXXFLAGS="%{extension_cxxflags} -D_GNU_SOURCE -fPIC -fwrapv"
export CPPFLAGS="$(pkg-config --cflags-only-I libffi)"
export OPT="%{extension_cflags} -D_GNU_SOURCE -fPIC -fwrapv"
export LINKCC="gcc"
export CFLAGS="$CFLAGS $(pkg-config --cflags openssl)"
export LDFLAGS="%{extension_ldflags} -g $(pkg-config --libs-only-L openssl)"
export LDFLAGS_NODIST="%{build_ldflags}%{?with_no_semantic_interposition: -fno-semantic-interposition} -g $(pkg-config --libs-only-L openssl)"

# We can build several different configurations of Python: regular and debug.
# Define a common function that does one build:
BuildPython() {
  ConfName=$1
  ExtraConfigArgs=$2
  MoreCFlags=$3

  # Each build is done in its own directory
  ConfDir=build/$ConfName
  echo STARTING: BUILD OF PYTHON FOR CONFIGURATION: $ConfName
  mkdir -p $ConfDir
  pushd $ConfDir

  # Normally, %%configure looks for the "configure" script in the current
  # directory.
  # Since we changed directories, we need to tell %%configure where to look.
  %global _configure $topdir/configure

  # A workaround for https://bugs.python.org/issue39761
  export DFLAGS=" "

%configure \
  --with-platlibdir=%{_lib} \
  --enable-ipv6 \
  --enable-shared \
  --with-computed-gotos=%{computed_gotos_flag} \
  --with-dbmliborder=gdbm:ndbm:bdb \
  --with-system-expat \
  --with-system-ffi \
  --enable-loadable-sqlite-extensions \
  --with-dtrace \
  --with-lto \
  --with-ssl-default-suites=openssl \
  --with-builtin-hashlib-hashes=blake2 \
%if %{with valgrind}
  --with-valgrind \
%endif
  $ExtraConfigArgs \
  %{nil}

%global flags_override EXTRA_CFLAGS="$MoreCFlags" CFLAGS_NODIST="$CFLAGS_NODIST $MoreCFlags"

%if %{without bootstrap}
  # Regenerate generated files (needs python3)
  %make_build %{flags_override} regen-all PYTHON_FOR_REGEN="python%{pybasever}"
%endif

  # Invoke the build
  %make_build %{flags_override}

  popd
  echo FINISHED: BUILD OF PYTHON FOR CONFIGURATION: $ConfName
}

# Call the above to build each configuration.

%if %{with debug_build}
# The debug build is compiled with the lowest level of optimizations as to not optimize
# out frames. We also suppress the warnings as the default distro value of the FORTIFY_SOURCE
# option produces too many warnings when compiling at the O0 optimization level.
# See also: https://bugzilla.redhat.com/show_bug.cgi?id=1818857
BuildPython debug \
  "--without-ensurepip --with-pydebug" \
  "-O0 -Wno-cpp"
%endif # with debug_build

BuildPython optimized \
  "--without-ensurepip %{optimizations_flag}" \
  ""

# ======================================================
# Installing the built code:
# ======================================================

%install

# As in %%build, remember the current directory
topdir=$(pwd)

# We install a collection of hooks for gdb that make it easier to debug
# executables linked against libpython3* (such as /usr/bin/python3 itself)
#
# These hooks are implemented in Python itself (though they are for the version
# of python that gdb is linked with)
#
# gdb-archer looks for them in the same path as the ELF file or its .debug
# file, with a -gdb.py suffix.
# We put them next to the debug file, because ldconfig would complain if
# it found non-library files directly in /usr/lib/
# (see https://bugzilla.redhat.com/show_bug.cgi?id=562980)
#
# We'll put these files in the debuginfo package by installing them to e.g.:
#  /usr/lib/debug/usr/lib/libpython3.2.so.1.0.debug-gdb.py
# (note that the debug path is /usr/lib/debug for both 32/64 bit)
#
# See https://fedoraproject.org/wiki/Features/EasierPythonDebugging for more
# information

%if %{with gdb_hooks}
DirHoldingGdbPy=%{_usr}/lib/debug/%{_libdir}
mkdir -p %{buildroot}$DirHoldingGdbPy
%endif # with gdb_hooks

# Multilib support for pyconfig.h
# 32- and 64-bit versions of pyconfig.h are different. For multilib support
# (making it possible to install 32- and 64-bit versions simultaneously),
# we need to install them under different filenames, and to make the common
# "pyconfig.h" include the right file based on architecture.
# See https://bugzilla.redhat.com/show_bug.cgi?id=192747
# Filanames are defined here:
%global _pyconfig32_h pyconfig-32.h
%global _pyconfig64_h pyconfig-64.h
%global _pyconfig_h pyconfig-%{__isa_bits}.h

# Use a common function to do an install for all our configurations:
InstallPython() {

  ConfName=$1
  PyInstSoName=$2
  MoreCFlags=$3
  LDVersion=$4

  # Switch to the directory with this configuration's built files
  ConfDir=build/$ConfName
  echo STARTING: INSTALL OF PYTHON FOR CONFIGURATION: $ConfName
  mkdir -p $ConfDir
  pushd $ConfDir

  %make_install EXTRA_CFLAGS="$MoreCFlags"

  popd

%if %{with gdb_hooks}
  # See comment on $DirHoldingGdbPy above
  PathOfGdbPy=$DirHoldingGdbPy/$PyInstSoName-%{version}-%{release}.%{_arch}.debug-gdb.py
  cp Tools/gdb/libpython.py %{buildroot}$PathOfGdbPy
%endif # with gdb_hooks

  # Rename the -devel script that differs on different arches to arch specific name
  mv %{buildroot}%{_bindir}/python${LDVersion}-{,`uname -m`-}config
  echo -e '#!/bin/sh\nexec %{_bindir}/python'${LDVersion}'-`uname -m`-config "$@"' > \
    %{buildroot}%{_bindir}/python${LDVersion}-config
    chmod +x %{buildroot}%{_bindir}/python${LDVersion}-config

  # Make python3-devel multilib-ready
  mv %{buildroot}%{_includedir}/python${LDVersion}/pyconfig.h \
     %{buildroot}%{_includedir}/python${LDVersion}/%{_pyconfig_h}
  cat > %{buildroot}%{_includedir}/python${LDVersion}/pyconfig.h << EOF
#include <bits/wordsize.h>

#if __WORDSIZE == 32
#include "%{_pyconfig32_h}"
#elif __WORDSIZE == 64
#include "%{_pyconfig64_h}"
#else
#error "Unknown word size"
#endif
EOF

  echo FINISHED: INSTALL OF PYTHON FOR CONFIGURATION: $ConfName
}

# Install the "debug" build first; any common files will be overridden with
# later builds
%if %{with debug_build}
InstallPython debug \
  %{py_INSTSONAME_debug} \
  -O0 \
  %{LDVERSION_debug}
%endif # with debug_build

# Now the optimized build:
InstallPython optimized \
  %{py_INSTSONAME_optimized} \
  "" \
  %{LDVERSION_optimized}

# Install directories for additional packages
install -d -m 0755 %{buildroot}%{pylibdir}/site-packages/__pycache__
%if "%{_lib}" == "lib64"
# The 64-bit version needs to create "site-packages" in /usr/lib/ (for
# pure-Python modules) as well as in /usr/lib64/ (for packages with extension
# modules).
# Note that rpmlint will complain about hardcoded library path;
# this is intentional.
install -d -m 0755 %{buildroot}%{_prefix}/lib/python%{pybasever}/site-packages/__pycache__
%endif

%if %{with main_python}
# add idle3 to menu
install -D -m 0644 Lib/idlelib/Icons/idle_16.png %{buildroot}%{_datadir}/icons/hicolor/16x16/apps/idle3.png
install -D -m 0644 Lib/idlelib/Icons/idle_32.png %{buildroot}%{_datadir}/icons/hicolor/32x32/apps/idle3.png
install -D -m 0644 Lib/idlelib/Icons/idle_48.png %{buildroot}%{_datadir}/icons/hicolor/48x48/apps/idle3.png
install -D -m 0644 Lib/idlelib/Icons/idle_256.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/idle3.png
desktop-file-install --dir=%{buildroot}%{_datadir}/applications %{SOURCE10}

# Install and validate appdata file
mkdir -p %{buildroot}%{_metainfodir}
cp -a %{SOURCE11} %{buildroot}%{_metainfodir}
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/idle3.appdata.xml
%endif

# Make sure distutils looks at the right pyconfig.h file
# See https://bugzilla.redhat.com/show_bug.cgi?id=201434
# Similar for sysconfig: sysconfig.get_config_h_filename tries to locate
# pyconfig.h so it can be parsed, and needs to do this at runtime in site.py
# when python starts up (see https://bugzilla.redhat.com/show_bug.cgi?id=653058)
#
# Split this out so it goes directly to the pyconfig-32.h/pyconfig-64.h
# variants:
sed -i -e "s/'pyconfig.h'/'%{_pyconfig_h}'/" \
  %{buildroot}%{pylibdir}/distutils/sysconfig.py \
  %{buildroot}%{pylibdir}/sysconfig.py

# Install pathfix.py to bindir
# See https://github.com/fedora-python/python-rpm-porting/issues/24
cp -p Tools/scripts/pathfix.py %{buildroot}%{_bindir}/pathfix%{pybasever}.py

# Install i18n tools to bindir
# They are also in python2, so we version them
# https://bugzilla.redhat.com/show_bug.cgi?id=1571474
for tool in pygettext msgfmt; do
  cp -p Tools/i18n/${tool}.py %{buildroot}%{_bindir}/${tool}%{pybasever}.py
  ln -s ${tool}%{pybasever}.py %{buildroot}%{_bindir}/${tool}3.py
done

# Switch all shebangs to refer to the specific Python version.
# This currently only covers files matching ^[a-zA-Z0-9_]+\.py$,
# so handle files named using other naming scheme separately.
LD_LIBRARY_PATH=./build/optimized ./build/optimized/python \
  Tools/scripts/pathfix.py \
  -i "%{_bindir}/python%{pybasever}" -pn \
  %{buildroot} \
  %{buildroot}%{_bindir}/*%{pybasever}.py \
  %{?with_gdb_hooks:%{buildroot}$DirHoldingGdbPy/*.py}

# Remove shebang lines from .py files that aren't executable, and
# remove executability from .py files that don't have a shebang line:
find %{buildroot} -name \*.py \
  \( \( \! -perm /u+x,g+x,o+x -exec sed -e '/^#!/Q 0' -e 'Q 1' {} \; \
  -print -exec sed -i '1d' {} \; \) -o \( \
  -perm /u+x,g+x,o+x ! -exec grep -m 1 -q '^#!' {} \; \
  -exec chmod a-x {} \; \) \)

# Get rid of DOS batch files:
find %{buildroot} -name \*.bat -exec rm {} \;

# Get rid of backup files:
find %{buildroot}/ -name "*~" -exec rm -f {} \;
find . -name "*~" -exec rm -f {} \;

# Do bytecompilation with the newly installed interpreter.
# This is similar to the script in macros.pybytecompile
# compile *.pyc
# Python CMD line options:
# -s - don't add user site directory to sys.path
# -B - don't write .pyc files on import
# compileall CMD line options:
# -f - force rebuild even if timestamps are up to date
# -o - optimization levels to run compilation with
# -s - part of path to left-strip from path to source file (buildroot)
# -p - path to add as prefix to path to source file (/ to make it absolute)
# --hardlink-dupes - hardlink different optimization level pycs together if identical (saves space)
LD_LIBRARY_PATH="%{buildroot}%{dynload_dir}/:%{buildroot}%{_libdir}" \
%{buildroot}%{_bindir}/python%{pybasever} -s -B -m compileall \
-f %{_smp_mflags} -o 0 -o 1 -o 2 -s %{buildroot} -p / %{buildroot} --hardlink-dupes || :

# Turn this BRP off, it is done by compileall2 --hardlink-dupes above
%global __brp_python_hardlink %{nil}

# Since we have pathfix.py in bindir, this is created, but we don't want it
rm -rf %{buildroot}%{_bindir}/__pycache__

# Fixup permissions for shared libraries from non-standard 555 to standard 755:
find %{buildroot} -perm 555 -exec chmod 755 {} \;

# Create "/usr/bin/python3-debug", a symlink to the python3 debug binary, to
# avoid the user having to know the precise version and ABI flags.
# See e.g. https://bugzilla.redhat.com/show_bug.cgi?id=676748
%if %{with debug_build} && %{with main_python}
ln -s \
  %{_bindir}/python%{LDVERSION_debug} \
  %{buildroot}%{_bindir}/python3-debug
%endif

# There's 2to3-X.X executable and 2to3 soft link to it.
# No reason to have both, so keep only 2to3 as an executable.
# See https://bugzilla.redhat.com/show_bug.cgi?id=1111275
# RHEL: We keep 2to3-X.X versioned not to conflict with other versions

%if %{without main_python}
# Remove stuff that would conflict with python3 package
rm %{buildroot}%{_bindir}/python3
rm %{buildroot}%{_bindir}/pydoc3
rm %{buildroot}%{_bindir}/pygettext3.py
rm %{buildroot}%{_bindir}/msgfmt3.py
rm %{buildroot}%{_bindir}/idle3
rm %{buildroot}%{_bindir}/python3-*
rm %{buildroot}%{_bindir}/2to3
rm %{buildroot}%{_libdir}/libpython3.so
rm %{buildroot}%{_mandir}/man1/python3.1*
rm %{buildroot}%{_libdir}/pkgconfig/python3.pc
rm %{buildroot}%{_libdir}/pkgconfig/python3-embed.pc
%else
# Link the unversioned stuff
# https://fedoraproject.org/wiki/Changes/Python_means_Python3
ln -s ./python3 %{buildroot}%{_bindir}/python
ln -s ./pydoc3 %{buildroot}%{_bindir}/pydoc
ln -s ./pygettext3.py %{buildroot}%{_bindir}/pygettext.py
ln -s ./msgfmt3.py %{buildroot}%{_bindir}/msgfmt.py
ln -s ./idle3 %{buildroot}%{_bindir}/idle
ln -s ./python3-config %{buildroot}%{_bindir}/python-config
ln -s ./python3.1 %{buildroot}%{_mandir}/man1/python.1
ln -s ./python3.pc %{buildroot}%{_libdir}/pkgconfig/python.pc
ln -s ./pathfix%{pybasever}.py %{buildroot}%{_bindir}/pathfix.py
%if %{with debug_build}
ln -s ./python3-debug %{buildroot}%{_bindir}/python-debug
%endif
%endif

%if %{with rhel8_compat_shims}
# Provide RHEL8 backwards compatible symbolic links in %%_libexecdir
mkdir -p %{buildroot}%{_libexecdir}
ln -s %{_bindir}/python%{pybasever} %{buildroot}%{_libexecdir}/platform-python
ln -s %{_bindir}/python%{pybasever} %{buildroot}%{_libexecdir}/platform-python%{pybasever}
ln -s %{_bindir}/python%{pybasever}-config %{buildroot}%{_libexecdir}/platform-python-config
ln -s %{_bindir}/python%{pybasever}-config %{buildroot}%{_libexecdir}/platform-python%{pybasever}-config
ln -s %{_bindir}/python%{pybasever}-`uname -m`-config %{buildroot}%{_libexecdir}/platform-python%{pybasever}-`uname -m`-config
# There were also executables with %%{LDVERSION_optimized} in RHEL 8,
# but since Python 3.8 %%{LDVERSION_optimized} == %%{pybasever}.
# We list both in the %%files section to assert this.
%if %{with debug_build}
ln -s %{_bindir}/python%{LDVERSION_debug} %{buildroot}%{_libexecdir}/platform-python-debug
ln -s %{_bindir}/python%{LDVERSION_debug} %{buildroot}%{_libexecdir}/platform-python%{LDVERSION_debug}
ln -s %{_bindir}/python%{LDVERSION_debug}-config %{buildroot}%{_libexecdir}/platform-python%{LDVERSION_debug}-config
ln -s %{_bindir}/python%{LDVERSION_debug}-`uname -m`-config %{buildroot}%{_libexecdir}/platform-python%{LDVERSION_debug}-`uname -m`-config
%endif
%endif

# Remove large, autogenerated sources and keep only the non-optimized pycache
for file in %{buildroot}%{pylibdir}/pydoc_data/topics.py $(grep --include='*.py' -lr %{buildroot}%{pylibdir}/encodings -e 'Python Character Mapping Codec .* from .* with gencodec.py'); do
    directory=$(dirname ${file})
    module=$(basename ${file%%.py})
    mv ${directory}/{__pycache__/${module}.cpython-%{pyshortver}.pyc,${module}.pyc}
    rm ${directory}/{__pycache__/${module}.cpython-%{pyshortver}.opt-?.pyc,${module}.py}
done

# Python RPM macros
mkdir -p %{buildroot}%{rpmmacrodir}/
install -m 644 %{SOURCE3} \
    %{buildroot}/%{rpmmacrodir}/

# All ghost files controlled by alternatives need to exist for the files
# section check to succeed
# - Don't list /usr/bin/python as a ghost file so `yum install /usr/bin/python`
#   doesn't install this package
touch %{buildroot}%{_bindir}/unversioned-python
touch %{buildroot}%{_mandir}/man1/python.1.gz
touch %{buildroot}%{_bindir}/python3
touch %{buildroot}%{_mandir}/man1/python3.1.gz
touch %{buildroot}%{_bindir}/pydoc3
touch %{buildroot}%{_bindir}/pydoc-3
touch %{buildroot}%{_bindir}/idle3
touch %{buildroot}%{_bindir}/python3-config
touch %{buildroot}%{_bindir}/python3-debug
touch %{buildroot}%{_bindir}/python3-debug-config


# ======================================================
# Checks for packaging issues
# ======================================================

%check

# first of all, check timestamps of bytecode files
find %{buildroot} -type f -a -name "*.py" -print0 | \
    LD_LIBRARY_PATH="%{buildroot}%{dynload_dir}/:%{buildroot}%{_libdir}" \
    PYTHONPATH="%{buildroot}%{_libdir}/python%{pybasever} %{buildroot}%{_libdir}/python%{pybasever}/site-packages" \
    xargs -0 %{buildroot}%{_bindir}/python%{pybasever} %{SOURCE8}

# Ensure that the curses module was linked against libncursesw.so, rather than
# libncurses.so
# See https://bugzilla.redhat.com/show_bug.cgi?id=539917
ldd %{buildroot}/%{dynload_dir}/_curses*.so \
    | grep curses \
    | grep libncurses.so && (echo "_curses.so linked against libncurses.so" ; exit 1)

# Ensure that the debug modules are linked against the debug libpython, and
# likewise for the optimized modules and libpython:
for Module in %{buildroot}/%{dynload_dir}/*.so ; do
    case $Module in
    *.%{SOABI_debug})
        ldd $Module | grep %{py_INSTSONAME_optimized} &&
            (echo Debug module $Module linked against optimized %{py_INSTSONAME_optimized} ; exit 1)

        ;;
    *.%{SOABI_optimized})
        ldd $Module | grep %{py_INSTSONAME_debug} &&
            (echo Optimized module $Module linked against debug %{py_INSTSONAME_debug} ; exit 1)
        ;;
    esac
done

# Verify that the bundled libmpdec version python was compiled with, is the same version we have virtual
# provides for in the SPEC.
test "$(LD_LIBRARY_PATH=$(pwd)/build/optimized $(pwd)/build/optimized/python -c 'import decimal; print(decimal.__libmpdec_version__)')" = \
     "%{libmpdec_version}"


# ======================================================
# Running the upstream test suite
# ======================================================

topdir=$(pwd)
CheckPython() {
  ConfName=$1
  ConfDir=$(pwd)/build/$ConfName

  echo STARTING: CHECKING OF PYTHON FOR CONFIGURATION: $ConfName

  # Note that we're running the tests using the version of the code in the
  # builddir, not in the buildroot.

  # Show some info, helpful for debugging test failures
  LD_LIBRARY_PATH=$ConfDir $ConfDir/python -m test.pythoninfo

  # Run the upstream test suite
  # --timeout=1800: kill test running for longer than 30 minutes
  # test_distutils
  #   distutils.tests.test_bdist_rpm tests fail when bootstraping the Python
  #   package: rpmbuild requires /usr/bin/pythonX.Y to be installed
  LD_LIBRARY_PATH=$ConfDir $ConfDir/python -m test.regrtest \
    -wW --slowest -j0 --timeout=1800 \
    %if %{with bootstrap}
    -x test_distutils \
    %endif
    %ifarch %{mips64}
    -x test_ctypes \
    %endif

  echo FINISHED: CHECKING OF PYTHON FOR CONFIGURATION: $ConfName

}

%if %{with tests}

# Check each of the configurations:
%if %{with debug_build}
CheckPython debug
%endif # with debug_build
CheckPython optimized

%endif # with tests


# ======================================================
# Scriptlets for alternatives
# ======================================================

%post
# Alternative for /usr/bin/python -> /usr/bin/python3 + man page
alternatives --install %{_bindir}/unversioned-python \
                       python \
                       %{_bindir}/python3 \
                       300 \
             --slave   %{_bindir}/python \
                       unversioned-python \
                       %{_bindir}/python3 \
             --slave   %{_mandir}/man1/python.1.gz \
                       unversioned-python-man \
                       %{_mandir}/man1/python3.1.gz

# Alternative for /usr/bin/python -> /usr/bin/python3.9 + man page
alternatives --install %{_bindir}/unversioned-python \
                       python \
                       %{_bindir}/python3.9 \
                       209 \
             --slave   %{_bindir}/python \
                       unversioned-python \
                       %{_bindir}/python3.9 \
             --slave   %{_mandir}/man1/python.1.gz \
                       unversioned-python-man \
                       %{_mandir}/man1/python3.9.1.gz

# Alternative for /usr/bin/python3 -> /usr/bin/python3.8 + related files
# Create only if it doesn't exist already
EXISTS=`alternatives --display python3 | \
        grep -c "^/usr/bin/python3.9 - priority [0-9]*"`

if [ $EXISTS -eq 0 ]; then
    alternatives --install %{_bindir}/python3 \
                           python3 \
                           %{_bindir}/python3.9 \
                           3900 \
                 --slave   %{_mandir}/man1/python3.1.gz \
                           python3-man \
                           %{_mandir}/man1/python3.9.1.gz \
                 --slave   %{_bindir}/pydoc3 \
                           pydoc3 \
                           %{_bindir}/pydoc3.9 \
                 --slave   %{_bindir}/pydoc-3 \
                           pydoc-3 \
                           %{_bindir}/pydoc3.9
fi

%postun
# Do this only during uninstall process (not during update)
if [ $1 -eq 0 ]; then
    alternatives --keep-foreign --remove python \
                        %{_bindir}/python3.9

    alternatives --keep-foreign --remove python3 \
                        %{_bindir}/python3.9

    # Remove link python → python3 if no other python3.* exists
    if ! alternatives --display python3 > /dev/null; then
        alternatives --keep-foreign --remove python \
                            %{_bindir}/python3
    fi
fi


%post devel
alternatives --add-slave python3 %{_bindir}/python3.9 \
    %{_bindir}/python3-config \
    python3-config \
    %{_bindir}/python3.9-config

%postun devel
# Do this only during uninstall process (not during update)
if [ $1 -eq 0 ]; then
    alternatives --keep-foreign --remove-slave python3 %{_bindir}/python3.9 \
        python3-config
fi


%post debug
alternatives --add-slave python3 %{_bindir}/python3.9 \
    %{_bindir}/python3-debug \
    python3-debug \
    %{_bindir}/python3.9d
alternatives --add-slave python3 %{_bindir}/python3.9 \
    %{_bindir}/python3-debug-config \
    python3-debug-config \
    %{_bindir}/python3.9d-config

%postun debug
# Do this only during uninstall process (not during update)
if [ $1 -eq 0 ]; then
    alternatives --keep-foreign --remove-slave python3 %{_bindir}/python3.9 \
        python3-debug
    alternatives --keep-foreign --remove-slave python3 %{_bindir}/python3.9 \
        python3-debug-config
fi


%post idle
alternatives --add-slave python3 %{_bindir}/python3.9 \
    %{_bindir}/idle3 \
    idle3 \
    %{_bindir}/idle3.9

%postun idle
# Do this only during uninstall process (not during update)
if [ $1 -eq 0 ]; then
    alternatives --keep-foreign --remove-slave python3 %{_bindir}/python3.9 \
       idle3
fi


# ======================================================
# Files for each RPM (sub)package
# ======================================================

%files -n %{pkgname}-rpm-macros
%{rpmmacrodir}/macros.python%{pyshortver}

%files -n %{pkgname}
%doc README.rst

# Alternatives
%ghost %{_bindir}/unversioned-python
%ghost %{_mandir}/man1/python.1.gz
%ghost %{_bindir}/python3
%ghost %{_mandir}/man1/python3.1.gz
%ghost %{_bindir}/pydoc3
%ghost %{_bindir}/pydoc-3

%if %{with main_python}
%{_bindir}/pydoc*
%{_bindir}/python3
%else
%{_bindir}/pydoc%{pybasever}
%endif

%{_bindir}/python%{pybasever}
%{_bindir}/python%{LDVERSION_optimized}
%{_mandir}/*/*3*

%if %{with rhel8_compat_shims}
%{_libexecdir}/platform-python
%{_libexecdir}/platform-python%{pybasever}
%{_libexecdir}/platform-python%{LDVERSION_optimized}
%endif

%if %{with main_python}
%if %{without flatpackage}
%files -n python-unversioned-command
%endif
%{_bindir}/python
%{_mandir}/*/python.1*
%endif

%if %{without flatpackage}
%files -n %{pkgname}-libs
%doc README.rst
%endif

%dir %{pylibdir}
%dir %{dynload_dir}

%license %{pylibdir}/LICENSE.txt

%{pylibdir}/lib2to3
%if %{without flatpackage}
%exclude %{pylibdir}/lib2to3/tests
%endif

%dir %{pylibdir}/unittest/
%dir %{pylibdir}/unittest/__pycache__/
%{pylibdir}/unittest/*.py
%{pylibdir}/unittest/__pycache__/*%{bytecode_suffixes}

%dir %{pylibdir}/asyncio/
%dir %{pylibdir}/asyncio/__pycache__/
%{pylibdir}/asyncio/*.py
%{pylibdir}/asyncio/__pycache__/*%{bytecode_suffixes}

%dir %{pylibdir}/venv/
%dir %{pylibdir}/venv/__pycache__/
%{pylibdir}/venv/*.py
%{pylibdir}/venv/__pycache__/*%{bytecode_suffixes}
%{pylibdir}/venv/scripts

%{pylibdir}/wsgiref
%{pylibdir}/xmlrpc

%dir %{pylibdir}/ensurepip/
%dir %{pylibdir}/ensurepip/__pycache__/
%{pylibdir}/ensurepip/*.py
%{pylibdir}/ensurepip/__pycache__/*%{bytecode_suffixes}

%if %{with rpmwheels}
%exclude %{pylibdir}/ensurepip/_bundled
%else
%dir %{pylibdir}/ensurepip/_bundled
%{pylibdir}/ensurepip/_bundled/*.whl
%{pylibdir}/ensurepip/_bundled/__init__.py
%{pylibdir}/ensurepip/_bundled/__pycache__/*%{bytecode_suffixes}
%endif

%dir %{pylibdir}/concurrent/
%dir %{pylibdir}/concurrent/__pycache__/
%{pylibdir}/concurrent/*.py
%{pylibdir}/concurrent/__pycache__/*%{bytecode_suffixes}

%dir %{pylibdir}/concurrent/futures/
%dir %{pylibdir}/concurrent/futures/__pycache__/
%{pylibdir}/concurrent/futures/*.py
%{pylibdir}/concurrent/futures/__pycache__/*%{bytecode_suffixes}

%{pylibdir}/pydoc_data

%{dynload_dir}/_blake2.%{SOABI_optimized}.so

%{dynload_dir}/_asyncio.%{SOABI_optimized}.so
%{dynload_dir}/_bisect.%{SOABI_optimized}.so
%{dynload_dir}/_bz2.%{SOABI_optimized}.so
%{dynload_dir}/_codecs_cn.%{SOABI_optimized}.so
%{dynload_dir}/_codecs_hk.%{SOABI_optimized}.so
%{dynload_dir}/_codecs_iso2022.%{SOABI_optimized}.so
%{dynload_dir}/_codecs_jp.%{SOABI_optimized}.so
%{dynload_dir}/_codecs_kr.%{SOABI_optimized}.so
%{dynload_dir}/_codecs_tw.%{SOABI_optimized}.so
%{dynload_dir}/_contextvars.%{SOABI_optimized}.so
%{dynload_dir}/_crypt.%{SOABI_optimized}.so
%{dynload_dir}/_csv.%{SOABI_optimized}.so
%{dynload_dir}/_ctypes.%{SOABI_optimized}.so
%{dynload_dir}/_curses.%{SOABI_optimized}.so
%{dynload_dir}/_curses_panel.%{SOABI_optimized}.so
%{dynload_dir}/_dbm.%{SOABI_optimized}.so
%{dynload_dir}/_decimal.%{SOABI_optimized}.so
%{dynload_dir}/_elementtree.%{SOABI_optimized}.so
%if %{with gdbm}
%{dynload_dir}/_gdbm.%{SOABI_optimized}.so
%endif
%{dynload_dir}/_hashlib.%{SOABI_optimized}.so
%{dynload_dir}/_heapq.%{SOABI_optimized}.so
%{dynload_dir}/_json.%{SOABI_optimized}.so
%{dynload_dir}/_lsprof.%{SOABI_optimized}.so
%{dynload_dir}/_lzma.%{SOABI_optimized}.so
%{dynload_dir}/_multibytecodec.%{SOABI_optimized}.so
%{dynload_dir}/_multiprocessing.%{SOABI_optimized}.so
%{dynload_dir}/_opcode.%{SOABI_optimized}.so
%{dynload_dir}/_pickle.%{SOABI_optimized}.so
%{dynload_dir}/_posixsubprocess.%{SOABI_optimized}.so
%{dynload_dir}/_queue.%{SOABI_optimized}.so
%{dynload_dir}/_random.%{SOABI_optimized}.so
%{dynload_dir}/_socket.%{SOABI_optimized}.so
%{dynload_dir}/_sqlite3.%{SOABI_optimized}.so
%{dynload_dir}/_ssl.%{SOABI_optimized}.so
%{dynload_dir}/_statistics.%{SOABI_optimized}.so
%{dynload_dir}/_struct.%{SOABI_optimized}.so
%{dynload_dir}/array.%{SOABI_optimized}.so
%{dynload_dir}/audioop.%{SOABI_optimized}.so
%{dynload_dir}/binascii.%{SOABI_optimized}.so
%{dynload_dir}/cmath.%{SOABI_optimized}.so
%{dynload_dir}/_datetime.%{SOABI_optimized}.so
%{dynload_dir}/fcntl.%{SOABI_optimized}.so
%{dynload_dir}/grp.%{SOABI_optimized}.so
%{dynload_dir}/math.%{SOABI_optimized}.so
%{dynload_dir}/mmap.%{SOABI_optimized}.so
%{dynload_dir}/nis.%{SOABI_optimized}.so
%{dynload_dir}/ossaudiodev.%{SOABI_optimized}.so
%{dynload_dir}/parser.%{SOABI_optimized}.so
%{dynload_dir}/_posixshmem.%{SOABI_optimized}.so
%{dynload_dir}/pyexpat.%{SOABI_optimized}.so
%{dynload_dir}/readline.%{SOABI_optimized}.so
%{dynload_dir}/resource.%{SOABI_optimized}.so
%{dynload_dir}/select.%{SOABI_optimized}.so
%{dynload_dir}/spwd.%{SOABI_optimized}.so
%{dynload_dir}/syslog.%{SOABI_optimized}.so
%{dynload_dir}/termios.%{SOABI_optimized}.so
%{dynload_dir}/unicodedata.%{SOABI_optimized}.so
%{dynload_dir}/_uuid.%{SOABI_optimized}.so
%{dynload_dir}/xxlimited.%{SOABI_optimized}.so
%{dynload_dir}/_xxsubinterpreters.%{SOABI_optimized}.so
%{dynload_dir}/zlib.%{SOABI_optimized}.so
%{dynload_dir}/_zoneinfo.%{SOABI_optimized}.so

%dir %{pylibdir}/site-packages/
%dir %{pylibdir}/site-packages/__pycache__/
%{pylibdir}/site-packages/README.txt
%{pylibdir}/*.py
%dir %{pylibdir}/__pycache__/
%{pylibdir}/__pycache__/*%{bytecode_suffixes}

%dir %{pylibdir}/collections/
%dir %{pylibdir}/collections/__pycache__/
%{pylibdir}/collections/*.py
%{pylibdir}/collections/__pycache__/*%{bytecode_suffixes}

%dir %{pylibdir}/ctypes/
%dir %{pylibdir}/ctypes/__pycache__/
%{pylibdir}/ctypes/*.py
%{pylibdir}/ctypes/__pycache__/*%{bytecode_suffixes}
%{pylibdir}/ctypes/macholib

%{pylibdir}/curses

%dir %{pylibdir}/dbm/
%dir %{pylibdir}/dbm/__pycache__/
%{pylibdir}/dbm/*.py
%{pylibdir}/dbm/__pycache__/*%{bytecode_suffixes}

%dir %{pylibdir}/distutils/
%dir %{pylibdir}/distutils/__pycache__/
%{pylibdir}/distutils/*.py
%{pylibdir}/distutils/__pycache__/*%{bytecode_suffixes}
%{pylibdir}/distutils/README
%{pylibdir}/distutils/command

%dir %{pylibdir}/email/
%dir %{pylibdir}/email/__pycache__/
%{pylibdir}/email/*.py
%{pylibdir}/email/__pycache__/*%{bytecode_suffixes}
%{pylibdir}/email/mime
%doc %{pylibdir}/email/architecture.rst

%{pylibdir}/encodings

%{pylibdir}/html
%{pylibdir}/http

%dir %{pylibdir}/importlib/
%dir %{pylibdir}/importlib/__pycache__/
%{pylibdir}/importlib/*.py
%{pylibdir}/importlib/__pycache__/*%{bytecode_suffixes}

%dir %{pylibdir}/json/
%dir %{pylibdir}/json/__pycache__/
%{pylibdir}/json/*.py
%{pylibdir}/json/__pycache__/*%{bytecode_suffixes}

%{pylibdir}/logging
%{pylibdir}/multiprocessing

%dir %{pylibdir}/sqlite3/
%dir %{pylibdir}/sqlite3/__pycache__/
%{pylibdir}/sqlite3/*.py
%{pylibdir}/sqlite3/__pycache__/*%{bytecode_suffixes}

%if %{without flatpackage}
%exclude %{pylibdir}/turtle.py
%exclude %{pylibdir}/__pycache__/turtle*%{bytecode_suffixes}
%endif

%{pylibdir}/urllib
%{pylibdir}/xml
%{pylibdir}/zoneinfo

%if "%{_lib}" == "lib64"
%attr(0755,root,root) %dir %{_prefix}/lib/python%{pybasever}
%attr(0755,root,root) %dir %{_prefix}/lib/python%{pybasever}/site-packages
%attr(0755,root,root) %dir %{_prefix}/lib/python%{pybasever}/site-packages/__pycache__/
%endif

# "Makefile" and the config-32/64.h file are needed by
# distutils/sysconfig.py:_init_posix(), so we include them in the core
# package, along with their parent directories (bug 531901):
%dir %{pylibdir}/config-%{LDVERSION_optimized}-%{platform_triplet}/
%{pylibdir}/config-%{LDVERSION_optimized}-%{platform_triplet}/Makefile
%dir %{_includedir}/python%{LDVERSION_optimized}/
%{_includedir}/python%{LDVERSION_optimized}/%{_pyconfig_h}

%{_libdir}/%{py_INSTSONAME_optimized}
%if %{with main_python}
%{_libdir}/libpython3.so
%endif


%if %{without flatpackage}
%files -n %{pkgname}-devel
%endif

%{pylibdir}/config-%{LDVERSION_optimized}-%{platform_triplet}/*
%if %{without flatpackage}
%exclude %{pylibdir}/config-%{LDVERSION_optimized}-%{platform_triplet}/Makefile
%exclude %{_includedir}/python%{LDVERSION_optimized}/%{_pyconfig_h}
%endif
%{_includedir}/python%{LDVERSION_optimized}/*.h
%{_includedir}/python%{LDVERSION_optimized}/internal/
%{_includedir}/python%{LDVERSION_optimized}/cpython/
%doc Misc/README.valgrind Misc/valgrind-python.supp Misc/gdbinit

%if %{with main_python}
%{_bindir}/python3-config
%{_bindir}/python-config
%{_libdir}/pkgconfig/python3.pc
%{_libdir}/pkgconfig/python.pc
%{_libdir}/pkgconfig/python3-embed.pc
%{_bindir}/pathfix.py
%{_bindir}/pygettext3.py
%{_bindir}/pygettext.py
%{_bindir}/msgfmt3.py
%{_bindir}/msgfmt.py
%endif

%{_bindir}/2to3-%{pybasever}
%{_bindir}/pathfix%{pybasever}.py
%{_bindir}/pygettext%{pybasever}.py
%{_bindir}/msgfmt%{pybasever}.py

%{_bindir}/python%{pybasever}-config
%{_bindir}/python%{LDVERSION_optimized}-config
%{_bindir}/python%{LDVERSION_optimized}-*-config
# Alternatives
%ghost %{_bindir}/python3-config

%{_libdir}/libpython%{LDVERSION_optimized}.so
%{_libdir}/pkgconfig/python-%{LDVERSION_optimized}.pc
%{_libdir}/pkgconfig/python-%{LDVERSION_optimized}-embed.pc
%{_libdir}/pkgconfig/python-%{pybasever}.pc
%{_libdir}/pkgconfig/python-%{pybasever}-embed.pc

%if %{with rhel8_compat_shims}
%{_libexecdir}/platform-python-config
%{_libexecdir}/platform-python%{pybasever}-config
%{_libexecdir}/platform-python%{LDVERSION_optimized}-config
%{_libexecdir}/platform-python%{pybasever}-*-config
%{_libexecdir}/platform-python%{LDVERSION_optimized}-*-config
%endif


%if %{without flatpackage}
%files -n %{pkgname}-idle
%endif

%if %{with main_python}
%{_bindir}/idle*
%else
%{_bindir}/idle%{pybasever}
# Alternatives
%ghost %{_bindir}/idle3
%endif

%{pylibdir}/idlelib

%if %{with main_python}
%{_metainfodir}/idle3.appdata.xml
%{_datadir}/applications/idle3.desktop
%{_datadir}/icons/hicolor/*/apps/idle3.*
%endif

%if %{without flatpackage}
%files -n %{pkgname}-tkinter
%endif

%{pylibdir}/tkinter
%if %{without flatpackage}
%exclude %{pylibdir}/tkinter/test
%endif
%{dynload_dir}/_tkinter.%{SOABI_optimized}.so
%{pylibdir}/turtle.py
%{pylibdir}/__pycache__/turtle*%{bytecode_suffixes}
%dir %{pylibdir}/turtledemo
%{pylibdir}/turtledemo/*.py
%{pylibdir}/turtledemo/*.cfg
%dir %{pylibdir}/turtledemo/__pycache__/
%{pylibdir}/turtledemo/__pycache__/*%{bytecode_suffixes}


%if %{without flatpackage}
%files -n %{pkgname}-test
%endif

%{pylibdir}/ctypes/test
%{pylibdir}/distutils/tests
%{pylibdir}/sqlite3/test
%{pylibdir}/test
%{dynload_dir}/_ctypes_test.%{SOABI_optimized}.so
%{dynload_dir}/_testbuffer.%{SOABI_optimized}.so
%{dynload_dir}/_testcapi.%{SOABI_optimized}.so
%{dynload_dir}/_testimportmultiple.%{SOABI_optimized}.so
%{dynload_dir}/_testinternalcapi.%{SOABI_optimized}.so
%{dynload_dir}/_testmultiphase.%{SOABI_optimized}.so
%{dynload_dir}/_xxtestfuzz.%{SOABI_optimized}.so
%{pylibdir}/lib2to3/tests
%{pylibdir}/tkinter/test
%{pylibdir}/unittest/test

# We don't bother splitting the debug build out into further subpackages:
# if you need it, you're probably a developer.

# Hence the manifest is the combination of analogous files in the manifests of
# all of the other subpackages

%if %{with debug_build}
%if %{without flatpackage}
%files -n %{pkgname}-debug
%endif

%if %{with main_python}
%{_bindir}/python3-debug
%{_bindir}/python-debug
%endif

# Analog of the core subpackage's files:
%{_bindir}/python%{LDVERSION_debug}
# Alternatives
%ghost %{_bindir}/python3-debug

# Analog of the -libs subpackage's files:
# ...with debug builds of the built-in "extension" modules:

%{dynload_dir}/_blake2.%{SOABI_debug}.so

%{dynload_dir}/_asyncio.%{SOABI_debug}.so
%{dynload_dir}/_bisect.%{SOABI_debug}.so
%{dynload_dir}/_bz2.%{SOABI_debug}.so
%{dynload_dir}/_codecs_cn.%{SOABI_debug}.so
%{dynload_dir}/_codecs_hk.%{SOABI_debug}.so
%{dynload_dir}/_codecs_iso2022.%{SOABI_debug}.so
%{dynload_dir}/_codecs_jp.%{SOABI_debug}.so
%{dynload_dir}/_codecs_kr.%{SOABI_debug}.so
%{dynload_dir}/_codecs_tw.%{SOABI_debug}.so
%{dynload_dir}/_contextvars.%{SOABI_debug}.so
%{dynload_dir}/_crypt.%{SOABI_debug}.so
%{dynload_dir}/_csv.%{SOABI_debug}.so
%{dynload_dir}/_ctypes.%{SOABI_debug}.so
%{dynload_dir}/_curses.%{SOABI_debug}.so
%{dynload_dir}/_curses_panel.%{SOABI_debug}.so
%{dynload_dir}/_dbm.%{SOABI_debug}.so
%{dynload_dir}/_decimal.%{SOABI_debug}.so
%{dynload_dir}/_elementtree.%{SOABI_debug}.so
%if %{with gdbm}
%{dynload_dir}/_gdbm.%{SOABI_debug}.so
%endif
%{dynload_dir}/_hashlib.%{SOABI_debug}.so
%{dynload_dir}/_heapq.%{SOABI_debug}.so
%{dynload_dir}/_json.%{SOABI_debug}.so
%{dynload_dir}/_lsprof.%{SOABI_debug}.so
%{dynload_dir}/_lzma.%{SOABI_debug}.so
%{dynload_dir}/_multibytecodec.%{SOABI_debug}.so
%{dynload_dir}/_multiprocessing.%{SOABI_debug}.so
%{dynload_dir}/_opcode.%{SOABI_debug}.so
%{dynload_dir}/_pickle.%{SOABI_debug}.so
%{dynload_dir}/_posixsubprocess.%{SOABI_debug}.so
%{dynload_dir}/_queue.%{SOABI_debug}.so
%{dynload_dir}/_random.%{SOABI_debug}.so
%{dynload_dir}/_socket.%{SOABI_debug}.so
%{dynload_dir}/_sqlite3.%{SOABI_debug}.so
%{dynload_dir}/_ssl.%{SOABI_debug}.so
%{dynload_dir}/_statistics.%{SOABI_debug}.so
%{dynload_dir}/_struct.%{SOABI_debug}.so
%{dynload_dir}/array.%{SOABI_debug}.so
%{dynload_dir}/audioop.%{SOABI_debug}.so
%{dynload_dir}/binascii.%{SOABI_debug}.so
%{dynload_dir}/cmath.%{SOABI_debug}.so
%{dynload_dir}/_datetime.%{SOABI_debug}.so
%{dynload_dir}/fcntl.%{SOABI_debug}.so
%{dynload_dir}/grp.%{SOABI_debug}.so
%{dynload_dir}/math.%{SOABI_debug}.so
%{dynload_dir}/mmap.%{SOABI_debug}.so
%{dynload_dir}/nis.%{SOABI_debug}.so
%{dynload_dir}/ossaudiodev.%{SOABI_debug}.so
%{dynload_dir}/parser.%{SOABI_debug}.so
%{dynload_dir}/_posixshmem.%{SOABI_debug}.so
%{dynload_dir}/pyexpat.%{SOABI_debug}.so
%{dynload_dir}/readline.%{SOABI_debug}.so
%{dynload_dir}/resource.%{SOABI_debug}.so
%{dynload_dir}/select.%{SOABI_debug}.so
%{dynload_dir}/spwd.%{SOABI_debug}.so
%{dynload_dir}/syslog.%{SOABI_debug}.so
%{dynload_dir}/termios.%{SOABI_debug}.so
%{dynload_dir}/unicodedata.%{SOABI_debug}.so
%{dynload_dir}/_uuid.%{SOABI_debug}.so
%{dynload_dir}/_xxsubinterpreters.%{SOABI_debug}.so
%{dynload_dir}/_xxtestfuzz.%{SOABI_debug}.so
%{dynload_dir}/zlib.%{SOABI_debug}.so
%{dynload_dir}/_zoneinfo.%{SOABI_debug}.so

# No need to split things out the "Makefile" and the config-32/64.h file as we
# do for the regular build above (bug 531901), since they're all in one package
# now; they're listed below, under "-devel":

%{_libdir}/%{py_INSTSONAME_debug}

# Analog of the -devel subpackage's files:
%{pylibdir}/config-%{LDVERSION_debug}-%{platform_triplet}
%{_includedir}/python%{LDVERSION_debug}
%{_bindir}/python%{LDVERSION_debug}-config
%{_bindir}/python%{LDVERSION_debug}-*-config
# Alternatives
%ghost %{_bindir}/python3-debug-config

%{_libdir}/libpython%{LDVERSION_debug}.so
%{_libdir}/libpython%{LDVERSION_debug}.so.%{py_SOVERSION}
%{_libdir}/pkgconfig/python-%{LDVERSION_debug}.pc
%{_libdir}/pkgconfig/python-%{LDVERSION_debug}-embed.pc

%if %{with rhel8_compat_shims}
%{_libexecdir}/platform-python-debug
%{_libexecdir}/platform-python%{LDVERSION_debug}
%{_libexecdir}/platform-python%{LDVERSION_debug}-config
%{_libexecdir}/platform-python%{LDVERSION_debug}-*-config
%endif

# Analog of the -tools subpackage's files:
#  None for now; we could build precanned versions that have the appropriate
# shebang if needed

# Analog  of the tkinter subpackage's files:
%{dynload_dir}/_tkinter.%{SOABI_debug}.so

# Analog  of the -test subpackage's files:
%{dynload_dir}/_ctypes_test.%{SOABI_debug}.so
%{dynload_dir}/_testbuffer.%{SOABI_debug}.so
%{dynload_dir}/_testcapi.%{SOABI_debug}.so
%{dynload_dir}/_testimportmultiple.%{SOABI_debug}.so
%{dynload_dir}/_testinternalcapi.%{SOABI_debug}.so
%{dynload_dir}/_testmultiphase.%{SOABI_debug}.so

%endif # with debug_build

# We put the debug-gdb.py file inside /usr/lib/debug to avoid noise from ldconfig
# See https://bugzilla.redhat.com/show_bug.cgi?id=562980
#
# The /usr/lib/rpm/redhat/macros defines %%__debug_package to use
# debugfiles.list, and it appears that everything below /usr/lib/debug and
# (/usr/src/debug) gets added to this file (via LISTFILES) in
# /usr/lib/rpm/find-debuginfo.sh
#
# Hence by installing it below /usr/lib/debug we ensure it is added to the
# -debuginfo subpackage
# (if it doesn't, then the rpmbuild ought to fail since the debug-gdb.py
# payload file would be unpackaged)

# Workaround for https://bugzilla.redhat.com/show_bug.cgi?id=1476593
%undefine _debuginfo_subpackages

# ======================================================
# Finally, the changelog:
# ======================================================

%changelog
* Wed Sep 20 2023 Charalampos Stratakis <cstratak@redhat.com> - 3.9.16-1.2
- Security fix for CVE-2023-40217
Resolves: RHEL-3237

* Mon May 29 2023 Charalampos Stratakis <cstratak@redhat.com> - 3.9.16-1.1
- Security fix for CVE-2023-24329
Resolves: rhbz#2173917

* Tue Dec 13 2022 Charalampos Stratakis <cstratak@redhat.com> - 3.9.16-1
- Update to 3.9.16
- Security fix for CVE-2022-45061
Resolves: rhbz#2144072

* Mon Nov 07 2022 Lumír Balhar <lbalhar@redhat.com> - 3.9.14-2
- Fix for CVE-2022-42919
Resolves: rhbz#2138705

* Mon Sep 12 2022 Charalampos Stratakis <cstratak@redhat.com> - 3.9.14-1
- Update to 3.9.14
- Security fixes for CVE-2020-10735 and CVE-2021-28861
Resolves: rhbz#1834423, rhbz#2120642

* Tue Jun 14 2022 Charalampos Stratakis <cstratak@redhat.com> - 3.9.13-1
- Update to 3.9.13
- Security fix for CVE-2015-20107
- Fix the test suite support for Expat >= 2.4.5
Resolves: rhbz#2075390

* Tue Sep 07 2021 Charalampos Stratakis <cstratak@redhat.com> - 3.9.7-1
- Update to 3.9.7
Resolves: rhbz#2003102

* Thu Aug 05 2021 Tomas Orsava <torsava@redhat.com> - 3.9.6-2
- Adjusted the postun scriptlets to enable upgrading to RHEL 9
- Resolves: rhbz#1933055

* Tue Jul 27 2021 Charalampos Stratakis <cstratak@redhat.com> - 3.9.6-1
- Update to 3.9.6
- Fix CVE-2021-29921: Improper input validation of octal strings in the ipaddress module
Resolves: rhbz#1957458

* Fri Apr 30 2021 Charalampos Stratakis <cstratak@redhat.com> - 3.9.2-2
- Security fix for CVE-2021-3426: information disclosure via pydoc
Resolves: rhbz#1935913

* Wed Mar 03 2021 Lumír Balhar <lbalhar@redhat.com> - 3.9.2-1
- Update to 3.9.2 to fix CVE-2021-23336
Resolves: rhbz#1928904

* Wed Feb 10 2021 Charalampos Stratakis <cstratak@redhat.com> - 3.9.1-5
- Compile the debug build with -O0 instead of -Og
Resolves: rhbz#1926283

* Fri Feb 05 2021 Charalampos Stratakis <cstratak@redhat.com> - 3.9.1-4
- Add support for FIPS mode
Resolves: rhbz#1877430

* Wed Jan 27 2021 Tomas Orsava <torsava@redhat.com> - 3.9.1-3
- Security fix for CVE-2021-3177
- Resolves: rhbz#1918168, rhbz#1877430

* Wed Jan 06 2021 Tomas Orsava <torsava@redhat.com> - 3.9.1-2
- Convert from Fedora to the python39 module in RHEL8
- Resolves: rhbz#1877430

* Tue Dec 08 2020 Tomas Hrnciar <thrnciar@redhat.com> - 3.9.1-1
- Update to 3.9.1

* Fri Nov 27 2020 Tomas Hrnciar <thrnciar@redhat.com> - 3.9.1~rc1-1
- Update to 3.9.1rc1

* Tue Oct 06 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0-1
- Update to 3.9.0 final

* Fri Sep 25 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~rc2-2
- Use upstream architecture names on Fedora 34+
- https://fedoraproject.org/wiki/Changes/Python_Upstream_Architecture_Names

* Thu Sep 17 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~rc2-1
- Update to 3.9.0rc2

* Wed Aug 12 2020 Petr Viktorin <pviktori@redhat.com> - 3.9.0~rc1-2
- In sys.version and initial REPL message, list the source commit as "default"

* Tue Aug 11 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~rc1-1
- Update to 3.9.0rc1

* Mon Aug 03 2020 Lumír Balhar <lbalhar@redhat.com> - 3.9.0~b5-5
- Add support for upstream architectures' names (patch 353)

* Thu Jul 30 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~b5-4
- Make python3-libs installable without python3
  Resolves: rhbz#1862082

* Wed Jul 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 3.9.0~b5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Fri Jul 24 2020 Lumír Balhar <lbalhar@redhat.com> - 3.9.0~b5-2
- Add versioned pathfix%%{pybasever}.py to main and non-main RPMs

* Mon Jul 20 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~b5-1
- Update to 3.9.0b5

* Thu Jul 16 2020 Marcel Plch <mplch@redhat.com> - 3.9.0~b4-2
- Remove large, autogenerated Python sources and redundant pycache levels to reduce filesystem footprint

* Sat Jul 04 2020 Tomas Hrnciar <thrnciar@redhat.com> - 3.9.0~b4-1
- Update to 3.9.0b4

* Wed Jun 10 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~b3-1
- Update to 3.9.0b3

* Tue Jun 09 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~b2-1
- Update to 3.9.0b2

* Fri May 29 2020 Petr Viktorin <pviktori@redhat.com> - 3.9.0~b1-4
- Add cherry-picks for bugs found in 3.9.0b1

* Thu May 21 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~b1-3
- Rebuilt for https://fedoraproject.org/wiki/Changes/Python3.9

* Thu May 21 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~b1-2
- Bootstrap for https://fedoraproject.org/wiki/Changes/Python3.9

* Tue May 19 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~b1-1
- Update to Python 3.9.0b1

* Thu May 07 2020 Tomas Orsava <torsava@redhat.com> - 3.9.0~a6-2
- Rename from python39 to python3.9

* Tue Apr 28 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~a6-1
- Update to Python 3.9.0a6

* Tue Mar 24 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~a5-1
- Update to Python 3.9.0a5

* Thu Feb 27 2020 Marcel Plch <mplch@redhat.com> - 3.9.0~a4-1
- Update to Python 3.9.0a4

* Tue Feb 11 2020 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~a3-2
- Update the ensurepip module to work with setuptools >= 45

* Mon Jan 27 2020 Victor Stinner <vstinner@python.org> - 3.9.0~a3-1
- Update to Python 3.9.0a3

* Thu Dec 19 2019 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~a2-1
- Rebased to Python 3.9.0a2

* Wed Dec 04 2019 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~a1-3
- Build Python with -fno-semantic-interposition for better performance
- https://fedoraproject.org/wiki/Changes/PythonNoSemanticInterpositionSpeedup

* Thu Nov 28 2019 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~a1-2
- Don't remove the test.test_tools module

* Wed Nov 20 2019 Miro Hrončok <mhroncok@redhat.com> - 3.9.0~a1-1
- Rebased to Python 3.9.0a1

* Mon Oct 14 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0-1
- Update to Python 3.8.0 final

* Tue Oct 01 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~rc1-1
- Rebased to Python 3.8.0rc1

* Sat Aug 31 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~b4-1
- Rebased to Python 3.8.0b4
- Enable Profile-guided optimization for all arches, not just x86 (#1741015)

* Mon Jul 29 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~b3-1
- Update to 3.8.0b3

* Fri Jul 26 2019 Fedora Release Engineering <releng@fedoraproject.org> - 3.8.0~b2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Jul 05 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~b2-1
- Update to 3.8.0b2

* Wed Jun 05 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~b1-1
- Update to 3.8.0b1

* Fri May 17 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~a4-2
- Remove a faulty patch that resulted in invalid value of
  distutils.sysconfig.get_config_var('LIBPL') (#1710767)

* Tue May 07 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~a4-1
- Update to 3.8.0a4

* Tue Mar 26 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~a3-1
- Update to 3.8.0a3

* Mon Feb 25 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~a2-1
- Update to 3.8.0a2

* Mon Feb 18 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~a1-3
- Reduced default build flags used to build extension modules
  https://fedoraproject.org/wiki/Changes/Python_Extension_Flags

* Sun Feb 17 2019 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 3.8.0~a1-2
- Rebuild for readline 8.0

* Tue Feb 05 2019 Miro Hrončok <mhroncok@redhat.com> - 3.8.0~a1-1
- Update to 3.8.0a1

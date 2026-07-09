%global name nwos
%global release 1
%global unmangled_version %{version}
%global __requires_exclude ^.*nwos/addons/mail/static/scripts/nwos-mailgate.py$

Summary: NWOS Server
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{unmangled_version}.tar.gz
License: LGPL-3
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: NWOS, Inc. <info@nwos.com>
Requires: sassc
BuildRequires: python3-devel
BuildRequires: pyproject-rpm-macros
Url: https://www.nwos.com

%description
NWOS is a complete ERP and CRM. The main features are accounting (analytic
and financial), stock management, sales and purchases management, tasks
automation, marketing campaigns, help desk, POS, etc. Technical features include
a distributed server, an object database, a dynamic GUI,
customizable reports, and XML-RPC interfaces.

%generate_buildrequires
%pyproject_buildrequires

%prep
%autosetup

%build
%py3_build

%install
%py3_install

%post
#!/bin/sh

set -e

NWOS_CONFIGURATION_DIR=/etc/nwos
NWOS_CONFIGURATION_FILE=$NWOS_CONFIGURATION_DIR/nwos.conf
NWOS_DATA_DIR=/var/lib/nwos
NWOS_GROUP="nwos"
NWOS_LOG_DIR=/var/log/nwos
NWOS_LOG_FILE=$NWOS_LOG_DIR/nwos-server.log
NWOS_USER="nwos"

if ! getent passwd | grep -q "^nwos:"; then
    groupadd $NWOS_GROUP
    adduser --system --no-create-home $NWOS_USER -g $NWOS_GROUP
fi
# Register "$NWOS_USER" as a postgres user with "Create DB" role attribute
su - postgres -c "createuser -d -R -S $NWOS_USER" 2> /dev/null || true
# Configuration file
mkdir -p $NWOS_CONFIGURATION_DIR
# can't copy debian config-file as addons_path is not the same
if [ ! -f $NWOS_CONFIGURATION_FILE ]
then
    echo "[options]
; This is the password that allows database operations:
; admin_passwd = admin
db_host = False
db_port = False
db_user = $NWOS_USER
db_password = False
addons_path = %{python3_sitelib}/nwos/addons
default_productivity_apps = True
" > $NWOS_CONFIGURATION_FILE
    chown $NWOS_USER:$NWOS_GROUP $NWOS_CONFIGURATION_FILE
    chmod 0640 $NWOS_CONFIGURATION_FILE
fi
# Log
mkdir -p $NWOS_LOG_DIR
chown $NWOS_USER:$NWOS_GROUP $NWOS_LOG_DIR
chmod 0750 $NWOS_LOG_DIR
# Data dir
mkdir -p $NWOS_DATA_DIR
chown $NWOS_USER:$NWOS_GROUP $NWOS_DATA_DIR

INIT_FILE=/lib/systemd/system/nwos.service
touch $INIT_FILE
chmod 0700 $INIT_FILE
cat << EOF > $INIT_FILE
[Unit]
Description=NWOS Open Source ERP and CRM
After=network.target

[Service]
Type=simple
User=nwos
Group=nwos
ExecStart=/usr/bin/nwos --config $NWOS_CONFIGURATION_FILE --logfile $NWOS_LOG_FILE
KillMode=mixed

[Install]
WantedBy=multi-user.target
EOF


%files
%{_bindir}/nwos
%{python3_sitelib}/%{name}-*.egg-info
%{python3_sitelib}/%{name}

.. _manual_install:

=========================
Manual Trove Installation
=========================

Objectives
==========

This document provides a step-by-step guide for manual installation of Trove with an existing OpenStack
environment for development purposes.

This document does not cover:
    - OpenStack setup.

    - All possible configurations for each services.


Requirements
============

Deployment requirements ::

 - Running OpenStack environment that includes at least the following components ::

    - Compute (nova)
    - Image Service (glance)
    - Identity (keystone)
    - A networking component (either neutron or nova-network)
    - If you want to provision datastores on block-storage volumes, you also need Block Storage (cinder)
    - If you want to do backup and restore, you also need Object Storage (swift)
    - Environment with freshly installed Ubuntu 12.04 LTS to run Trove services.
      This will be referred to as "local environment".

 - AMQP service (ZeroMQ, RabbitMQ, QPid)

 - MySQL(sqlite, PostgeSQL) database for Trove's internal needs, accessible from the local environment

 - Certain OpenStack services must be accessible from VMs:
   - Swift

 - VMs must be accessible from local environment for development/debugging purposes


OpenStack services must be accessible directly from the local environment, such as ::

  - Nova
  - Cinder
  - Swift
  - Heat



Installation
============

-----------
Gather info
-----------

The following information about existing environment is required ::

    - Keystone host and port(s)

    - OpenStack administrator's username, tenant and password

    - Nova compute URL

    - Cinder URL

    - Swift URL

    - Heat URL

    - AMPQ connection credentials (RabbitMQ URL: user Id, password; etc.)

    - Trove's backend connection string

--------------------
Install dependencies
--------------------

Install required packages
-------------------------

List of packages to be installed ::


   # apt-get install build-essential libxslt1-dev qemu-utils mysql-client git python-dev python-pexpect python-mysqldb libmysqlclient-dev


Python settings
---------------

To find out which setuptools version is latest please follow link below :

       `setuptools repo`_

.. _setuptools repo: https://pypi.python.org/packages/source/s/setuptools/


To find out which pip version is latest please follow link below :

       `pip repo`_

.. _pip repo: https://pypi.python.org/packages/source/p/pip


Some packages in Ubuntu repo are outdated, so install their latest version from sources ::

    ## Use latest setuptools
    # wget https://pypi.python.org/packages/source/s/setuptools/setuptools-{{latest}}.tar.gz
    # tar xfvz setuptools-{{latest}}.tar.gz
    # cd setuptools-{{latest}}
    # python setup.py install --user


    ## Use latest pip
    # wget https://pypi.python.org/packages/source/p/pip/pip-{{latest}}.tar.gz
    # tar xfvz pip-{{latest}}.tar.gz
    # cd pip-{{latest}}
    # python setup.py install --user


Note '--user' above -- we installed packages in user's home dir, in $HOME/.local/bin, so we need to add it to path::

    # echo PATH="$HOME/.local/bin:$PATH" >> ~/.profile
    # . ~/.profile


Install virtualenv, create environment and activate it ::

    # pip install virtualenv --user
    # virtualenv --system-site-packages env
    # . env/bin/activate


------------
Obtain Trove
------------
Get Trove's sources from git ::

    # git clone https://github.com/openstack/trove.git
    # git clone https://github.com/openstack/python-troveclient.git

-------------
Install Trove
-------------
First install required python packages ::

    # cd ~/trove
    # pip install -r requirements.txt

Install Trove itself::

    # python setup.py develop

Install Python-Troveclient ::

    # cd ~/python-troveclient
    # python setup.py develop
    # cd ~

We'll need several OS clients as well ::

    # pip install python-glanceclient
    # pip install python-keystoneclient
    # pip install python-novaclient

---------------------------
Prepare Trove for OpenStack
---------------------------

You will need to create a tenant 'trove_for_trove_usage' and users 'regular_trove_user'
and 'admin_trove_user' with password 'trove' to be used with Trove service.
Also, you will need to register OpenStack service and its endpoints ::

    # keystone --os-username <OpenStackAdminUsername> --os-password <OpenStackAdminPassword>
        --os-tenant-name <OpenStackAdminTenant> --os-auth-url http://<KeystoneIP>:35357/v2.0
        tenant-create --name trove_for_trove_usage

    # keystone --os-username <OpenStackAdminUsername> --os-password <OpenStackAdminPassword>
        --os-tenant-name <OpenStackAdminTenant> --os-auth-url http://<KeystoneIP>:35357/v2.0
        user-create --name regular_trove_user --pass trove --tenant trove_for_trove_usage

    # keystone --os-username <OpenStackAdminUsername> --os-password <OpenStackAdminPassword>
        --os-tenant-name <OpenStackAdminTenant> --os-auth-url http://<KeystoneIP>:35357/v2.0
        user-create --name admin_trove_user --pass trove --tenant trove_for_trove_usage

    # keystone --os-username <OpenStackAdminUsername> --os-password <OpenStackAdminPassword>
        --os-tenant-name <OpenStackAdminTenant> --os-auth-url http://<KeystoneIP>:35357/v2.0
        user-role-add --name admin_trove_user --tenant trove_for_trove_usage --role admin

    # keystone --os-username <OpenStackAdminUsername> --os-password <OpenStackAdminPassword>
        --os-tenant-name <OpenStackAdminTenant> --os-auth-url http://<KeystoneIP>:35357/v2.0
        service-create --name trove --type database

    # keystone --os-username <OpenStackAdminUsername> --os-password <OpenStackAdminPassword>
        --os-tenant-name <OpenStackAdminTenant> --os-auth-url http://<KeystoneIP>:35357/v2.0
        endpoint-create --service trove --region RegionOne
        --publicurl 'http://<EnvironmentPublicIP>:8779/v1.0/$(tenant_id)s'
        --adminurl 'http://<EnvironmentPublicIP>:8779/v1.0/$(tenant_id)s'
        --internalurl 'http://<EnvironmentPublicIP>:8779/v1.0/$(tenant_id)s'

Where EnvironmentPublicIP - IP address of server where Trove was installed.
This IP should be reachable from any hosts that will be used to communicate with Trove

---------------------------------
Prepare Trove configuration files
---------------------------------

There are several configuration files for Trove ::

    - api-paste.ini and trove.conf -- for trove-api service

    - trove-taskmanager.conf -- for trove-taskmanager service

    - trove-guestagent.conf -- for trove-guestagent service

    - trove-conductor.conf -- for trove-conductor service

    - <datastore_manager>.cloudinit -- userdata for VMs


Cloudinit scripts are userdata that is being used for different datastore types like mysql/percona, cassandra, mongodb, redis, couchbase while provisioning new compute instance

Samples of the above are available in $TROVE/trove/etc/trove/ as *.conf.sample files.

If a vanilla Ubuntu image used as a source image for Trove instances, then it is cloudinit script's responsibility
to install and run Trove guestagent in the instance.

As an alternative one may consider creating a custom image with pre-installed and pre-configured Trove in it.

--------------
Vanilla images
--------------

As the source image for trove instances, we will use a cloudinit-enabled vanilla Ubuntu image ::

    # wget http://cloud-images.ubuntu.com/precise/current/precise-server-cloudimg-amd64-disk1.img

Convert the downloaded image into uncompressed qcow2 ::


    # qemu-img convert -O qcow2 precise-server-cloudimg-amd64-disk1.img precise.qcow2

Upload the converted image into Glance ::


    # glance --os-username admin_trove_user --os-password trove --os-tenant-name trove_for_trove_usage --os-auth-url http://<KeystoneIP>:35357/v2.0
        image-create --name trove-image --public --container-format ovf --disk-format qcow2 --owner trove_for_trove_usage < precise.qcow2

At this step please remember image ID, or ::

    # export IMAGEID=<glance_image_id>


------------------
Cloud-init scripts
------------------

Cloud-init location
-------------------


By the default Trove-taskamanger will look at /etc/trove/cloudinit for <datastore_manager>.cloudinit


Cloud-init content
------------------

Each cloudinit script should contain ::

       - database package installation
       - python installation
       - trove installation
       - adding simple script that will launch trove-guestagent with appropriate
         configuration files that would be injected into the provisioned VM
       - trove-guestagent service registration
       - adding trove-guestagent to operating system upstart script


Note: File injection happens before cloud-init gets executed

------------------------------------
Custom images with Trove code inside
------------------------------------

To be added

----------------
Prepare database
----------------
Create Trove database schema ::

  - Log into backend (MySQL, PostgreSQL, etc.)
  - Create database called `trove` (This database will be used for persisting Trove models)
  - Compose connection string. Example: mysql://<user>:<password>@<backend_host>/<database_name>


-----------------------
Initialize the database
-----------------------

Once database for Trove needs was created you will need to fill database with required tables ::

    # trove-manage --config-file=${TROVE_CONF_PATH}/trove.conf db_recreate ${TROVE_PATH}/db/sqlalchemy/migrate_repo/


---------------------------
Setup Trove with Datastores
---------------------------

Datastore
---------

Datastore - a data structure that describes a set of Datastore Versions, that consists of ::

    - ID -- simple auto-generated UUID
    - Name -- user-defined attribute, actual name of a datastore
    - Datastore Versions

Example::

    mysql, cassandra, redis, etc.

Datastore Version
-----------------

Datastore Versions - a data structure that describes a version of specific database, pinned to Datastore, that consists of ::

    - ID -- simple auto-generated UUID
    - Datastore ID -- reference to Datastore
    - Name -- user-defined attribute, actual name of a database version
    - Datastore Manager -- trove-guestagent manager that is used for datastore management
    - Image ID -- reference to a specific Glance image ID
    - Packages -- operating system specific packages that would be deployed onto datastore VM
    - Active -- boolean flag that defines if version can be used for instance deployment or not


Example ::

  - version “5.5”
  - for “mysql-datastore”
  - with packages “mysql-server=5.5, percona-xtrabackup=2.1”
  - pinned to image “1d73a402-3953-4721-8c99-86fc72e1cb51”
  - “active=True”
  - managed by “mysql” manager


Datastore and Datastore version registration
--------------------------------------------

To register datastore you need to execute ::

    # export DATASTORE_TYPE="mysql" # available options: cassandra, mysql, mongodb, redis, couchbase

    # export DATASTORE_VERSION="5.5" # available options: for cassandra 2.0.x, for mysql: 5.x, for mongodb: 2.x.x, etc.

    # export PACKAGES="mysql-server=5.5" # available options: cassandra=2.0.9, mongodb=2.0.4, etc

    # trove-manage datastore_update "${DATASTORE_TYPE}" ""

    # trove-manage datastore_version_update "${DATASTORE_TYPE}" "${DATSTORE_VERSION}" "${DATASTORE_TYPE}" ${IMAGEID} "${PACKAGES}" 1

    # trove-manage datastore_update "${DATASTORE_TYPE}" "${DATASTORE_VERSION}"



Run Trove
=========

---------------------------------------
Trove services configuration and tuning
---------------------------------------

To be added

-----------------------
Starting Trove services
-----------------------

Run trove-api::

    # trove-api --config-file=${TROVE_CONF_DIR}/trove-api.conf &

Run trove-taskmanager::

    # trove-taskmanager --config-file=${TROVE_CONF_DIR}/trove-taskamanger.conf &

Run trove-conductor::

   # trove-conductor --config-file=${TROVE_CONF_DIR}/trove-conductor.conf &


Trove interaction
=================

------------
Keystonerc::
------------

You need to build `keystonerc` file that contains to simplify auth process while using Trove client::

        export OS_TENANT_NAME=trove # Tenant name

        export OS_USERNAME=regular_trove_user

        export OS_PASSWORD=trove

        export OS_AUTH_URL="http://<KeystoneIP>:5000/v2.0/"

        export OS_AUTH_STRATEGY=keystone

-----------------------------
Trove deployment verification
-----------------------------

First you need to execute::

    # . keystonerc

To see `help` for certain command::

    # trove help <command>

To create instance::

    # trove create <name> <flavor_id>
                    [--size <size>]
                    [--databases <databases> [<databases> ...]]
                    [--users <users> [<users> ...]] [--backup <backup>]
                    [--availability_zone <availability_zone>]
                    [--datastore <datastore>]
                    [--datastore_version <datastore_version>]
                    [--nic <net-id=net-uuid,v4-fixed-ip=ip-addr,port-id=port-uuid>]
                    [--configuration <configuration>] [--slave_of <master_id>]




Troubleshooting
===============

If Trove instance was created properly, and it's in ACTIVE state, and it's known for sure to be working,
but there are no IP addresses for the instance in the output of 'trove show <instance_id>', then make sure
the following lines are added to trove-api.conf::

    add_addresses = True
    network_label_regex = ^NETWORK_NAME$

where NETWORK_NAME should be replaced with real name of the network to which the instance is connected to.

One possible way to find the network name is to execute the 'nova list' command. The output will list
all OpenStack instances for the tenant, including network information. Look for ::

    NETWORK_NAME=IP_ADDRESS

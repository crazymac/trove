.. _confiuration:

========================
Guestagent configuration
========================


Current guest configuration
===========================

* Trove GuestAgent could work with more then one configuration file.
* From the beggining trove-guestagent got launched with two config file:
 - trove-guestagent.conf -> on VM side: guest_config
 - guest_info -> on VM side: guest_info

* Second config delivers instance and tenant IDs.


Future guest configuration
==========================

* Almost the same with previous configuration.
* Difference shows up when trove could support more then one database type provisioning
* New feature:
 - guest_info delivers not only instance and tenant IDs,
   it also delivers database specific parameters, such as:
   - datastore_manager;
   - backup_strategy;
   - mount_point;
   - service_registry_ext;
   - Root configuration.

List of additional parameters could be extended on-the-fly.


WARNINGS
========

* 1. {datastore}/guest_info.config should always exist if {datastore} was registered and ready for use
* 2. All parameters in {datastore}/guest_info.config shold be registered in common/cfg.py

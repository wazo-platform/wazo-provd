Changelog
=========

19.04
-----

* The following endpoints are now multi-tenant.

  This means that created resources will be in the same tenant as the creator or in the tenant
  specified by the Wazo-Tenant HTTP header. Listing resources will also only list the ones in the
  user's tenant unless a sub-tenant is specified using the Wazo-Tenant header. The `recurse=true`
  query string can be used to list from multiple tenants. GET, DELETE and PUT on a resource that is
  not tenant accessible will result in a 404.

  * `/provd/dev_mgr`

  See :ref:`intro-provisioning` for more information on how device tenants are handled.

Changelog
=========

19.12
-----

* `xivo-provisioning` has been renamed to `wazo-provd`.


19.08
-----

* The API version has been added to the URL and the `provd` prefix has been removed. For example,
`/provd/dev_mgr`is now located at `/0.2/dev_mgr` and `/api/api.yml` is now at `/0.2/api/api.yml`.


19.05
-----

* New readonly parameters have been added to the device resource:

  * `is_new`


19.04
-----

* The following endpoints are now multi-tenant.

  This means that created resources will be in the same tenant as the creator or in the tenant
  specified by the Wazo-Tenant HTTP header. Listing resources will also only list the ones in the
  user's tenant unless a sub-tenant is specified using the Wazo-Tenant header. The `recurse=true`
  query string can be used to list from multiple tenants. GET, DELETE and PUT on a resource that is
  not tenant accessible will result in a 404.

  * `/provd/dev_mgr`

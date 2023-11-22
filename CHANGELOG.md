# Changelog

## 23.16

* The following configurations have been renamed:

  * `ip` / `external_ip` --> `advertised_host`
  * `http_port` --> `advertised_http_port`
  * `base_external_url` --> `advertised_http_url`
  * `num_http_proxies` --> `http_proxied_trusted_proxies_count`

## 23.15

* A new API has been added to configure the provisioning key

## 23.12

* New configuration has been added to configure number of HTTP proxies ahead of this
  service to get the right client IP address

  ```
  general:
    num_http_proxies: 0
  ```

## 20.09

* Deprecate SSL configuration

## 20.02

* The `/0.2/status` resource has been added

## 19.12

* `xivo-provisioning` has been renamed to `wazo-provd`.

## 19.08

* The API version has been added to the URL and the `provd` prefix has been removed. For example,
`/provd/dev_mgr`is now located at `/0.2/dev_mgr` and `/api/api.yml` is now at `/0.2/api/api.yml`.

## 19.05

* New readonly parameters have been added to the device resource:

  * `is_new`

## 19.04

* The following endpoints are now multi-tenant.

  This means that created resources will be in the same tenant as the creator or in the tenant
  specified by the Wazo-Tenant HTTP header. Listing resources will also only list the ones in the
  user's tenant unless a sub-tenant is specified using the Wazo-Tenant header. The `recurse=true`
  query string can be used to list from multiple tenants. GET, DELETE and PUT on a resource that is
  not tenant accessible will result in a 404.

  * `/provd/dev_mgr`

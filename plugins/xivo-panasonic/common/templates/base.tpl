# Panasonic SIP Phone Standard Format File #

{# SIP per-line settings -#}
{% for line_no, line in sip_lines.iteritems() %}
PHONE_NUMBER_{{ line_no }}="{{ line['number'] }}"
SIP_URI_{{ line_no }}="sip:{{ line['auth_username'] }}@{{ line['registrar_ip'] }}"
SIP_PRXY_ADDR_{{ line_no }}="{{ line['proxy_ip'] }}"
SIP_2NDPROXY_ADDR_{{ line_no }}="{{ line['backup_proxy_ip'] }}"
SIP_RGSTR_ADDR_{{ line_no }}="{{ line['registrar_ip'] }}"
SIP_2NDRGSTR_ADDR_{{ line_no }}="{{ line['backup_registrar_ip'] }}"
SIP_AUTHID_{{ line_no }}="{{ line['auth_username'] }}"
SIP_PASS_{{ line_no }}="{{ line['password'] }}"
{% endfor -%}

FIRM_UPGRADE_ENABLE="Y"
FIRM_VERSION="01.133"
FIRM_UPGRADE_AUTO="Y"
FIRM_FILE_PATH="http://{{ ip }}:{{ http_port }}/firmware/UT11x12x-01.133_HW1.fw"


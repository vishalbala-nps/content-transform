# CERU Advisory CERU-2026-0412: Critical vulnerabilities in Kestrel Orbital Gateway

Cyber Emergency Response Unit (CERU). Issued: 14 September 2026. Severity: Critical.

## Overview

Two vulnerabilities have been reported in the web management interface of Kestrel Orbital Gateway, a VPN and remote-access appliance widely deployed by government departments, banks and hospitals.

The more severe of the two, CVE-2026-41877, allows an unauthenticated remote attacker to execute arbitrary commands on the appliance with root privileges. It has a CVSS v3.1 base score of 9.8.

The second, CVE-2026-41878, is an authentication bypass in the session handling of the same interface and has a CVSS v3.1 base score of 8.1. Chained together, the two allow an attacker to take full control of an appliance and every VPN session passing through it.

CERU has observed active exploitation of CVE-2026-41877 since 9 September 2026. At least 37 organisations reporting to CERU have confirmed compromised appliances. Exploitation requires only network access to the management interface, which is exposed to the internet on an estimated 4,200 appliances.

## Affected products

- Kestrel Orbital Gateway 4.x, versions 4.0.0 to 4.2.6
- Kestrel Orbital Gateway 3.9 LTS, versions 3.9.0 to 3.9.14
- Kestrel Orbital Cloud Connector, all versions before 2.1.3

## Description

CVE-2026-41877 is an OS command injection flaw in the diagnostics endpoint of the management interface. Input supplied to the hostname field of the network test tool is passed to a shell without sanitisation.

CVE-2026-41878 arises because session tokens issued to the management interface are not bound to the client and do not expire when the administrator logs out. An attacker who obtains any previously issued token can reuse it.

In observed intrusions, attackers dropped a persistent implant, harvested stored VPN credentials and certificates, and used the appliance to move laterally into internal networks.

## Indicators of compromise

Connections to or from the following, or the presence of the listed file, indicate likely compromise:

- 203.0.113.47
- 198.51.100.212
- update-kestrel-cdn.example
- /var/tmp/.ksync with SHA-256 8d1b7aad35df6f4a45e80690b580ef38bba57073f01b7498b847e03e57ea9001

## Recommended actions

- Upgrade Orbital Gateway 4.x to version 4.2.7 and Orbital Gateway 3.9 LTS to version 3.9.15 immediately.
- Upgrade Orbital Cloud Connector to version 2.1.3.
- If you cannot patch within 24 hours, disable the web management interface on all external network interfaces.
- Search logs from 1 September 2026 onwards for connections to the indicators listed above.
- Rotate all credentials and VPN certificates stored on any appliance whose management interface was exposed.
- Report suspected compromise to CERU within 6 hours of detection.

## Timeline

- 2 September 2026: An independent researcher notifies Kestrel Networks.
- 9 September 2026: CERU observes the first exploitation.
- 12 September 2026: Kestrel Networks releases fixed versions 4.2.7 and 3.9.15.
- 14 September 2026: CERU issues this advisory.

## References

Kestrel Networks security bulletin KSB-2026-009.

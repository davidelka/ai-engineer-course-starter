---
id: it-laptop-policy
title: Laptop and Endpoint Policy
department: it_security
doc_type: policy
version: "1.3"
effective_date: 2025-08-01
owner: Yossi Dahan
classification: internal
language: en
---

# Laptop and Endpoint Policy

## Which laptop you get

- Engineers, data analysts and designers receive a MacBook Pro 14-inch with an Apple M-series chip, 32 GB of memory and 1 TB of storage.
- All other employees receive a MacBook Air 13-inch with 16 GB of memory and 512 GB of storage.
- Employees who need Windows for a specific customer-facing task can request a Windows laptop from IT with manager approval.
- Each employee also receives one external monitor for the office desk and one for home, a keyboard, a mouse and a laptop bag.

## Refresh cycle

Laptops are replaced every 3 years. IT contacts the employee one month before the refresh date. Earlier replacement is possible when a laptop fails and cannot be repaired within 5 working days.

## Management and security controls

Every Acme laptop is enrolled in Jamf (for macOS) or Intune (for Windows) before it is handed over. The following controls are mandatory and must not be disabled:

- Full-disk encryption (FileVault on macOS, BitLocker on Windows).
- Automatic OS updates; critical updates must be installed within 7 days of release.
- The endpoint protection agent (EDR).
- Screen lock after 5 minutes of inactivity.
- A firewall, enabled.

Laptops that are not compliant for more than 7 days lose access to Okta-protected applications until they are fixed.

## Acceptable use

- The laptop is for Acme work. Light personal use (browsing, personal email) is allowed; storing large personal media libraries, mining cryptocurrency and installing pirated software are not.
- Do not install browser extensions that can read all website data unless they are on the IT allow list.
- Family members may not use the work laptop.
- On public Wi-Fi, connect to the Acme VPN (Tailscale) before accessing internal systems.

## Lost or stolen laptop

Report a lost or stolen laptop to IT (it@acme.example) and to Security (security@acme.example) within 1 hour of noticing. IT will lock and wipe the device remotely. Reporting quickly is what matters; you will not be blamed for reporting.

## Travel

Laptops travel as carry-on, never in checked luggage. When traveling to countries on the Security team's high-risk list, request a loaner laptop from IT at least 5 working days before the trip.

## Leaving Acme

Return the laptop, chargers, security keys and monitors to IT on your last working day. Berlin employees return equipment to Katrin Vogel, the Berlin office manager.

## Buying out the old laptop

At the end of the 3-year cycle, employees may buy their old laptop for a symbolic 300 NIS after IT wipes it. MacBook Pros used for production access are not sold; they are recycled.

---
id: it-password-policy-2024
title: Password Policy (2024)
department: it_security
doc_type: policy
version: "1.0"
effective_date: 2024-06-01
owner: Tamar Golan
classification: internal
language: en
---

# Password Policy (effective June 2024)

## Scope

This policy applies to every account used for Acme work: the Okta single sign-on account, accounts in SaaS tools that do not use Okta, local laptop accounts, and service accounts.

## Password requirements

- Passwords must be at least 10 characters long and include at least three of the following: uppercase letters, lowercase letters, digits, symbols.
- Passwords must be changed every 90 days. The last 5 passwords cannot be reused.
- Passwords must not contain the employee's name, the word "acme", or the name of the current month or season.

## Multi-factor authentication

- MFA is required for Okta. Employees may use the Okta Verify app or an SMS code.
- MFA is recommended, but not required, for SaaS tools that do not use Okta.

## Account lockout

After 5 failed login attempts, the Okta account is locked for 30 minutes. IT can unlock it earlier after verifying the employee's identity over a video call.

## Storing passwords

- Passwords must not be written down or stored in plain-text files or notes.
- A password manager is recommended. Acme pays for 1Password for employees who request it.

## Service accounts

Service account passwords are stored in the Platform team's vault and rotated every 180 days.

## Reporting

If you suspect that a password was exposed, change it immediately and report it to security@acme.example.

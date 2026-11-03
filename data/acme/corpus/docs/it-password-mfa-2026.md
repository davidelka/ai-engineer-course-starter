---
id: it-password-mfa-2026
title: Password and MFA Policy (2026)
department: it_security
doc_type: policy
version: "2.0"
effective_date: 2026-01-15
owner: Tamar Golan
classification: internal
language: en
supersedes: it-password-policy-2024
---

# Password and MFA Policy (effective January 15, 2026)

This policy replaces the June 2024 Password Policy. It follows current guidance (such as NIST SP 800-63B) that long passphrases and strong MFA protect better than frequent forced password changes.

## Scope

Every account used for Acme work: Okta single sign-on, SaaS tools that do not use Okta, laptop accounts, and service accounts.

## Passwords and passphrases

- Passwords must be at least 14 characters long. We recommend a passphrase of four or more unrelated words.
- There is no forced periodic rotation. Passwords must be changed immediately if there is any suspicion of compromise, and when Okta reports that the password appears in a known breach list.
- Passwords must not be reused across accounts, and must not contain the employee's name or the word "acme".

## Password manager

Using 1Password is mandatory for all employees. Every Acme password that is not the Okta password itself must be stored in the employee's Acme 1Password vault. Shared team credentials are stored in shared vaults, never in Slack, Confluence or documents.

## Multi-factor authentication

- MFA is mandatory for every account that supports it.
- SMS codes and phone calls are no longer accepted as a second factor. Use Okta Verify with push and number matching, or a FIDO2 security key.
- A FIDO2 security key (YubiKey) is mandatory for: anyone with admin rights in any system, anyone with access to production infrastructure, and the Finance team. IT issues two keys per person, one primary and one backup.
- Passkeys on company laptops are accepted for Okta login as an alternative to a security key for employees who are not in the groups above.

## Account lockout

After 10 failed login attempts, the Okta account is locked for 15 minutes. Repeated lockouts within a day are investigated by the Security team.

## Service accounts

Service account credentials are stored in the Platform team's secret manager and rotated automatically every 90 days. Long-lived personal access tokens for GitHub are not allowed; use short-lived tokens issued through Okta.

## Lost security key

Report a lost security key to it@acme.example on the same day. IT revokes it and you continue with the backup key until a replacement is issued.

## Summary of changes from 2024

- Minimum length: from 10 to 14 characters.
- Forced rotation every 90 days: removed.
- SMS as a second factor: no longer allowed.
- 1Password: from recommended to mandatory.
- Lockout: from 5 attempts and 30 minutes to 10 attempts and 15 minutes.

# Privacy Policy Template for a Personal WHOOP Hermes Coach

> This is a starting template, not legal advice. Replace every bracketed field,
> remove sections that do not match your deployment, and publish the finished
> policy at a public HTTPS URL before placing that URL in the WHOOP Developer
> Dashboard.

**Effective date:** [DATE]

**Operator:** [YOUR NAME OR ORGANIZATION]

**Contact:** [YOUR EMAIL]

## Overview

[APP NAME] is a personal AI coaching integration operated by [OPERATOR]. It
connects a user's WHOOP account to a developer-operated Hermes Agent and uses
Inkbox to deliver requested or automated coaching messages.

## Information the integration accesses

After a user grants permission through WHOOP OAuth, the integration may access:

- WHOOP profile information, including name and email;
- body measurements, including height, weight, and maximum heart rate;
- physiological cycles and Strain;
- Recovery metrics, including Recovery score, heart-rate variability, resting
  heart rate, blood-oxygen percentage, and skin temperature when available;
- sleep records, including sleep duration, performance, efficiency,
  consistency, and sleep-stage durations; and
- workout records, including activity type, timestamps, Strain, heart-rate
  summaries, energy, distance, elevation, and heart-rate-zone durations when
  available.

The official WHOOP Developer API does not provide this integration with
continuous heart-rate samples, GPS routes, WHOOP Journal entries, Stress
Monitor data, Healthspan data, or private WHOOP Coach conversations.

## How information is used

The integration uses this information only to:

- answer the user's questions about their WHOOP data;
- create summaries, comparisons, coaching text, and visual report cards;
- react to WHOOP workout, sleep, and Recovery webhook events; and
- deliver user-configured messages through the operator's Inkbox identity.

## Service providers and disclosure

Information is processed by the operator's deployment of Hermes Agent, WHOOP,
Inkbox, and the AI model provider configured by the operator. [DESCRIBE ANY
ADDITIONAL HOSTING, LOGGING, ANALYTICS, OR SERVICE PROVIDERS.] Information is
not sold. It is not disclosed to other parties except as needed to operate the
integration, comply with law, protect security, or when the user directs the
operator to share it.

## Storage, security, and retention

WHOOP OAuth credentials are stored on the operator's Hermes host. The
integration stores access and refresh tokens in a private local file and stores
webhook-deduplication state locally. Messages and operational logs may be
retained by the operator, Inkbox, the configured model provider, or hosting
providers according to their respective settings and policies.

[DESCRIBE YOUR HOST, ACCESS CONTROLS, BACKUPS, LOG RETENTION, MESSAGE RETENTION,
AND DELETION SCHEDULE.]

## User choices and deletion

A user can stop future WHOOP access by revoking the integration in WHOOP or by
contacting [CONTACT EMAIL]. On request, the operator will delete locally held
WHOOP OAuth tokens and personal data controlled by the operator, subject to any
legal or security retention requirements. The operator may also revoke access
through WHOOP's official OAuth revocation endpoint.

## Health information disclaimer

The integration provides informational coaching and is not a medical device or
a substitute for professional medical advice, diagnosis, or treatment. Users
should seek qualified medical care for health concerns.

## Changes

This policy may be updated as the integration changes. The effective date above
will be revised when material changes are published.

## Contact

Questions or requests may be sent to [CONTACT EMAIL].

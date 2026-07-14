# WHOOP Coach for Hermes + Inkbox

Private demo plugin that gives a Hermes agent official WHOOP data tools and
verified WHOOP webhook events, then lets the agent proactively reach its human
over Inkbox iMessage, SMS, email, and voice.

## Architecture

```text
WHOOP OAuth + Developer API
            │
WHOOP v2 webhooks ──▶ https://<agent>.inkboxwire.com/webhook
            │
            ▼
verified external:whoop event ──▶ whoop-coach skill
            │
            ▼
official whoop_* tools ──▶ Inkbox iMessage / SMS / call
```

The plugin uses only the supported WHOOP Developer API. It does not expose
continuous heart-rate samples, workout HR curves, GPS routes, Journal entries,
Stress Monitor, Healthspan, or WHOOP's private Coach API.

## Install

Install the Inkbox Hermes plugin version that supports companion webhook
providers and tunnel callback routes, then:

```bash
hermes plugins install inkbox-ai/whoop-hermes-agent-plugin --enable
hermes gateway restart
hermes whoop setup --import-env /path/to/existing/.env
hermes whoop doctor
```

The WHOOP plugin registers its verifier and OAuth callback in memory when
Hermes starts. It never copies files into the installed Inkbox plugin.

## WHOOP dashboard

Run:

```bash
hermes whoop webhook-url
```

Add the displayed values to the WHOOP Developer Dashboard:

- Redirect URL: `https://<agent>.inkboxwire.com/integrations/whoop/oauth/callback`
- Webhook URL: `https://<agent>.inkboxwire.com/webhook`
- Webhook model: `v2`
- Scopes: `offline read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement`

WHOOP does not expose an API for editing developer-app settings, so adding the
redirect and webhook URLs is a one-time manual dashboard action.

## Commands

- `hermes whoop setup [--import-env PATH]`
- `hermes whoop doctor`
- `hermes whoop status`
- `hermes whoop webhook-url`
- `hermes whoop disconnect`

OAuth tokens live in `~/.hermes/whoop/tokens.json` with mode `0600`. The WHOOP
client secret is also used as `INKBOX_WEBHOOK_SECRET_WHOOP` so the Inkbox
external-event registry can verify WHOOP's signatures.

## Tools

The plugin covers every supported read endpoint for an authenticated member:

- Profile and body measurements
- Cycle list/detail and cycle-linked sleep/recovery
- Recovery list
- Sleep list/detail
- Workout list/detail
- Legacy activity-ID mapping
- Higher-level today, period-summary, workout-comparison, and webhook-processing tools

OAuth revocation is intentionally a confirmed CLI command rather than an
agent-callable tool.

## Event policy

- Scored workout updates may produce one concise recap.
- Sleep updates normally wait for the corresponding Recovery event.
- Recovery updates may produce one combined morning briefing.
- Deleted, duplicate, and unscored records remain silent.
- Webhooks never trigger calls. Voice is reserved for a separately scheduled,
  explicitly configured escalation.

This is an unofficial integration and is not affiliated with WHOOP.


<h1>WHOOP Coach for Hermes + Inkbox</h1>

<img src="assets/whoop_inkbox_agent.png" alt="WHOOP Coach, powered by Inkbox" width="200" align="left">

<p>
  <br><br>
  <b>Turn your WHOOP data into an agent that actually reaches you:</b><br>
  official Recovery, Sleep, Strain, and workout data; event-driven coaching; and visual reports over iMessage.<br>
  Powered by Hermes + Inkbox without relying on WHOOP's private Coach API.
</p>

<p>
  <code>Recovery</code> · <code>Sleep</code> · <code>Workouts</code> · <code>Visual Reports</code> · <code>iMessage</code> · <code>Webhooks</code>
</p>

<br clear="left">

---

An end-to-end Hermes plugin that gives an agent official WHOOP data tools,
verified WHOOP webhook events, polished health-report cards, and proactive
delivery over an Inkbox iMessage identity.

Every developer runs their own Hermes agent, creates their own Inkbox identity,
and registers their own WHOOP developer app. This repository does not provide a
shared WHOOP Client ID, Client Secret, OAuth token, Inkbox API key, or identity.

## Architecture

```text
Developer-owned WHOOP app + OAuth
                 │
WHOOP Developer API + v2 webhooks
                 │
                 ▼
     developer-owned Inkbox tunnel
                 │
                 ▼
       WHOOP plugin + Hermes agent
                 │
                 ▼
        Inkbox iMessage identity
```

The plugin uses only the supported WHOOP Developer API. It does not expose
continuous heart-rate samples, workout HR curves, GPS routes, Journal entries,
Stress Monitor, Healthspan, or WHOOP's private Coach API.

## Prerequisites

Before starting, each developer needs:

- macOS, Linux, or WSL2. Windows PowerShell installation is also supported by
  Hermes, but iMessage connection still requires an iPhone.
- Python and Git as installed/managed by the Hermes installer.
- A model provider configured in Hermes. Webhook coaching wakes a Hermes agent;
  the nightly visual cron itself does not use a model.
- Access to this private GitHub repository. Authenticate Git before installing:

  ```bash
  gh auth login
  gh auth setup-git
  ```

- An Inkbox account/API key, or an email address for the Inkbox setup wizard's
  self-signup flow. No pre-existing Inkbox identity is required.
- A WHOOP membership and WHOOP account. WHOOP requires a membership to create a
  developer app.
- A public HTTPS privacy-policy page for the WHOOP consent screen. A public
  GitHub Gist, public website, or hosted policy page is sufficient for a demo;
  it must not require repository access or authentication.

## Complete installation

Follow these steps in order. The Inkbox identity must exist before the final
WHOOP callback and webhook URLs are known.

### 1. Install and configure Hermes Agent

macOS, Linux, or WSL2:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
hermes setup
```

Windows PowerShell:

```powershell
iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
hermes setup
```

Complete `hermes setup` and select a working model provider before continuing.
Confirm Hermes is available:

```bash
hermes --version
hermes doctor
```

### 2. Install the Inkbox plugin and create an identity

```bash
hermes plugins install inkbox-ai/hermes-agent-plugin --enable
hermes inkbox setup
```

The Inkbox wizard:

1. Installs the Inkbox SDK into the Python environment that actually runs Hermes.
2. Accepts an existing Inkbox API key or creates a new account and identity.
3. Stores the agent-scoped API key, identity handle, and webhook signing key in
   `~/.hermes/.env`.
4. Offers to enable iMessage. Enable it for this demo.
5. Prints an iMessage router number and `connect @your-agent` command.
6. Waits for you to send the first message from your iPhone and confirms the
   new conversation.
7. Optionally provisions a dedicated phone number for SMS and voice calls.

The identity is developer-owned. Do not copy another developer's
`INKBOX_API_KEY`, `INKBOX_IDENTITY`, or signing key.

Verify the identity:

```bash
hermes inkbox doctor
hermes inkbox whoami
```

### 3. Install the WHOOP plugin

```bash
hermes plugins install inkbox-ai/whoop-hermes-agent-plugin --enable
```

The repository is currently private, so GitHub access and Git authentication
must already be configured. `hermes whoop setup` installs the visual renderer's
Pillow dependency into the active Hermes Python environment when necessary.

### 4. Start the gateway and obtain the public URLs

Start Hermes in a terminal and keep it running:

```bash
hermes gateway run
```

The Inkbox plugin creates the public tunnel, and the WHOOP plugin mounts its
OAuth callback and verified webhook handler on that same tunnel. In another
terminal run:

```bash
hermes whoop webhook-url
```

Save the exact `redirect_uri` and `webhook_url` it prints. They look like:

```text
https://<your-inkbox-identity>.inkboxwire.com/integrations/whoop/oauth/callback
https://<your-inkbox-identity>.inkboxwire.com/webhook
```

Do not use the example hostname literally, and do not use another developer's
tunnel. If the gateway is already installed as a service, use
`hermes gateway restart` instead of opening a second gateway process.

### 5. Create your own WHOOP developer app

Open the [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com/),
sign in with your WHOOP account, and create a Team if prompted. A personal demo
can use your own name as the Team name; this does not require incorporating a
business.

Create a new app and fill in:

- **Name:** any user-facing name, such as `My WHOOP Hermes Coach`.
- **Logo:** a square `.png` or `.jpg` you are permitted to use.
- **Contacts:** your own administrative email address.
- **Privacy Policy:** your own public HTTPS policy URL. Do not reuse the
  maintainer's policy. Publish a policy appropriate for your deployment before
  sharing the OAuth flow with anyone else. A customizable starting point is
  available in [`docs/privacy-policy-template.md`](docs/privacy-policy-template.md).
- **Redirect URL:** the exact `redirect_uri` from
  `hermes whoop webhook-url`.
- **Scopes:** enable all six read scopes used by this plugin:
  - `read:recovery`
  - `read:cycles`
  - `read:sleep`
  - `read:workout`
  - `read:profile`
  - `read:body_measurement`
- **Webhook URL:** the exact `webhook_url` from
  `hermes whoop webhook-url`.
- **Webhook model version:** `v2`.

Create/save the app, then copy its **Client ID** and **Client Secret**. Treat the
Client Secret as a password: keep it server-side and never commit it, paste it
into chat, or share it with another developer.

WHOOP apps work immediately in development with a limited number of test
members. Approval is only needed when the developer wants to distribute the app
beyond the dashboard's test-user allowance. Each developer can therefore run
this demo using their own app without receiving credentials from this project.

Official references:

- [WHOOP: Getting Started](https://developer.whoop.com/docs/developing/getting-started/)
- [WHOOP: OAuth 2.0](https://developer.whoop.com/docs/developing/oauth/)
- [WHOOP: Webhooks](https://developer.whoop.com/docs/developing/webhooks/)

### 6. Import credentials and authorize your WHOOP account

Create a temporary local file named `whoop.env` outside the repository:

```dotenv
WHOOP_CLIENT_ID=replace-with-your-client-id
WHOOP_CLIENT_SECRET=replace-with-your-client-secret
WHOOP_TIMEZONE=America/Los_Angeles
```

Do not add quotes around individual values unless your editor requires them,
and do not commit this file. The plugin supplies the API URLs and complete
`offline` + read-scope list by default.

Run:

```bash
hermes whoop setup --import-env /absolute/path/to/whoop.env
```

If exactly one active Inkbox iMessage conversation exists, setup selects it as
the proactive WHOOP home channel automatically. If multiple conversations
exist, setup prints their IDs; rerun with the desired one:

```bash
hermes whoop setup --home-channel <imessage-conversation-id>
```

Setup prints and opens the WHOOP OAuth authorization URL. Log in to WHOOP,
review the requested scopes, and grant access. WHOOP redirects to the running
Inkbox tunnel, where the plugin exchanges the one-time authorization code and
stores rotating OAuth tokens in `~/.hermes/whoop/tokens.json` with mode `0600`.

After authorization, delete the temporary credential file and restart the
gateway so its webhook verifier sees the new app secret:

```bash
rm /absolute/path/to/whoop.env
hermes gateway restart
```

### 7. Verify the complete integration

```bash
hermes inkbox doctor
hermes whoop doctor
hermes whoop status
```

`hermes whoop doctor` should report:

- `configured: true`
- `tokens_present: true`
- `home_channel_configured: true`
- `ok: true`
- matching configured and expected redirect URIs

Send the Inkbox identity an iMessage such as:

```text
What is my Recovery today, and show me the post-sleep report?
```

The reply should contain WHOOP-backed numbers and one native PNG attachment.

### 8. Install proactive recaps

```bash
hermes whoop automations install
hermes whoop automations status
```

The installer is idempotent: rerunning it updates the existing job instead of
creating duplicates. It configures:

- A no-agent daily recap cron at `0 23 * * *` in `WHOOP_TIMEZONE`.
- One workout visual after a scored `workout.updated` webhook.
- One combined post-sleep/recovery visual after a scored
  `recovery.updated` webhook.

The 11 PM job renders directly without a model call, approval prompt, token
spend, progress message, or extra cron-wrapper bubble. Workout and sleep recaps
are webhook-driven; they are not polling cron jobs.

## Test WHOOP webhooks

WHOOP recommends these development tests after OAuth is connected:

1. In the WHOOP app, add a short activity in the past. Once WHOOP scores it,
   the integration should receive `workout.updated` and send one workout card.
2. Edit a previous sleep start or end by one minute. WHOOP should publish both
   `sleep.updated` and `recovery.updated`; this plugin waits for Recovery and
   sends one complete post-sleep card.
3. Revert the edits after verification.

WHOOP may retry or duplicate webhook deliveries. The plugin validates WHOOP's
HMAC signature, deduplicates `trace_id` and resource versions, and durably
claims only one proactive recap per workout or sleep resource.

## Configuration and secrets

The supported WHOOP settings are:

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `WHOOP_CLIENT_ID` | yes | - | Developer-owned WHOOP OAuth client ID. |
| `WHOOP_CLIENT_SECRET` | yes | - | Developer-owned WHOOP OAuth client secret and webhook HMAC key. |
| `WHOOP_REDIRECT_URI` | yes | active Inkbox callback | Must exactly match the WHOOP dashboard. |
| `WHOOP_HOME_CHANNEL` | proactive delivery | - | Inkbox iMessage conversation UUID. |
| `WHOOP_TIMEZONE` | no | `America/Los_Angeles` | Daily recap schedule and local summaries. |
| `WHOOP_QUIET_HOURS_START` | no | `23:00` | Automatic outreach quiet-period start. |
| `WHOOP_QUIET_HOURS_END` | no | `07:00` | Automatic outreach quiet-period end. |
| `WHOOP_RECAPS_RESPECT_QUIET_HOURS` | no | `true` | Delay event-driven recaps during quiet hours. Automation install sets it to `false` for immediate requested recaps. |

Never commit `.env`, OAuth tokens, Client Secrets, Inkbox API keys, signing
keys, phone numbers, or personal WHOOP exports. Every developer should revoke
their own integration with `hermes whoop disconnect` when finished.

## Commands

```bash
hermes whoop setup [--import-env PATH] [--home-channel CONVERSATION_ID]
hermes whoop doctor
hermes whoop status
hermes whoop webhook-url
hermes whoop automations install|status|remove
hermes whoop disconnect
```

Update an existing deployment:

```bash
hermes plugins update inkbox
hermes plugins update whoop
hermes gateway restart
hermes whoop automations install
```

## Available data and reports

The plugin covers every supported read endpoint for an authenticated member:

- Profile and body measurements
- Cycle list/detail and cycle-linked sleep/recovery
- Recovery list
- Sleep list/detail
- Workout list/detail, including accumulated heart-rate-zone durations
- Legacy activity-ID mapping
- Today summaries, period summaries, and workout comparisons
- Four deterministic reports through `whoop_render_report`: sleep phases,
  combined post-sleep recovery, workout/HR-zone summary, and daily recap

OAuth revocation is intentionally a confirmed CLI command rather than an
agent-callable tool.

## Event policy

- Scored `workout.updated` events may produce one workout recap.
- `sleep.updated` normally waits for the corresponding Recovery event.
- Scored `recovery.updated` events may produce one combined post-sleep recap.
- Deleted, duplicate, and unscored records remain silent.
- Webhooks never trigger calls. Voice is reserved for separately scheduled,
  explicitly configured escalation workflows.
- iMessage images are uploaded and delivered as native attachments without
  leaking local paths or double-sending a confirmation bubble.

## Troubleshooting

- **WHOOP OAuth returns 403:** verify that the authorization request's redirect
  URI exactly matches the app dashboard, restart the OAuth flow, and use the
  new one-time code only once.
- **`home_channel_configured` is false:** connect to the Inkbox identity over
  iMessage, send it a message, then rerun `hermes whoop setup`. If setup prints
  multiple conversation IDs, select one with `--home-channel`.
- **No webhook event arrives:** confirm the webhook uses the active HTTPS
  tunnel, model `v2`, and the WHOOP account completed OAuth for this exact app.
- **WHOOP plugin is unavailable:** run `hermes plugins list`, confirm both
  `inkbox` and `whoop` are enabled, then restart the gateway.
- **Private repository clone fails:** authenticate GitHub with an account that
  has repository access, then run `gh auth setup-git`.
- **Images fail to render:** rerun `hermes whoop setup`; it installs Pillow into
  the Hermes runtime rather than an unrelated system Python.

This is an unofficial integration and is not affiliated with WHOOP.

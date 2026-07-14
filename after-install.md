# WHOOP plugin installed

This plugin requires a developer-owned Inkbox identity and WHOOP developer app.
Follow the repository README's **Complete installation** section for the full
zero-to-working-agent flow.

If Inkbox is not configured yet, start there:

```bash
hermes plugins install inkbox-ai/hermes-agent-plugin --enable
hermes inkbox setup
hermes inkbox doctor
```

Then start the gateway, create your own WHOOP app using the URLs printed by the
plugin, and authorize it:

```bash
hermes gateway run
hermes whoop webhook-url
hermes whoop setup --import-env /absolute/path/to/whoop.env
```

Use all six WHOOP read scopes and webhook model **v2**. After OAuth succeeds:

```bash
hermes gateway restart
hermes whoop doctor
hermes whoop automations install
```

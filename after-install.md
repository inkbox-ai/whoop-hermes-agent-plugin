# WHOOP plugin installed

The Inkbox plugin must include companion-provider support. Then run:

```bash
hermes gateway restart
hermes whoop setup --import-env /path/to/existing/.env
hermes whoop doctor
hermes whoop webhook-url
```

Add the printed redirect URI and webhook URL to the WHOOP Developer Dashboard.
Select webhook model version **v2**.


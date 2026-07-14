# WHOOP plugin installed

The Inkbox plugin must include companion-provider support. Then run:

```bash
python -m pip install 'Pillow>=10'
hermes gateway restart
hermes whoop setup --import-env /path/to/existing/.env
hermes whoop doctor
hermes whoop webhook-url
hermes whoop automations install
```

Add the printed redirect URI and webhook URL to the WHOOP Developer Dashboard.
Select webhook model version **v2**.

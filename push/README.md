# Publish notifications — deployment in progress

Deployed on Cloudflare with D1 and encrypted secrets. WordPress publish_post sends ID to the protected receiver URL. Cloud-hosted FCM validation passed without sending a notification. A physical-device, newly-published-post test remains necessary.

The receiver accepts a secret `publish/<WEBHOOK_SECRET>` URL, checks the public WordPress API for the article, ignores articles older than `ACTIVATED_AT`, and records each post ID in D1 before sending a data-only FCM topic message. The Android client also deduplicates IDs.

Required bindings:

- `DB`: D1 database initialized using `schema.sql`.
- `FCM_SERVICE_ACCOUNT`: encrypted secret containing the dedicated Firebase service-account JSON. Never commit it or include it in the APK.
- `WEBHOOK_SECRET`: encrypted, randomly generated secret.
- `ACTIVATED_AT`: UTC timestamp of activation, after all existing posts.

Configure WordPress `publish_post` with only `ID` plus its automatic `hook` field. A published-post edit triggers the hook too, so the activation date and ID ledger are essential.

Failed or uncertain sends remain recorded as `failed` rather than broadcasting a possible duplicate. They require an operator check; this implementation does not guarantee delivery during an external outage. Android permission, Google Play Services, connectivity and device power restrictions also affect delivery.

Run `node --test --test-isolation=none push/worker.test.mjs` from the repository root. Before activation, validate Firebase authorization without broadcasting to the topic, verify the webhook form fields, and test on a phone after installing the new APK.

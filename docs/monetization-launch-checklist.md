# Monetization Launch Checklist

Repository defaults keep Analytics, AdSense, and Skimlinks off. Complete the account-level work below before enabling any of them in production.

## Analytics and Consent

- Analytics is also opt-in. Keep `ENABLE_ANALYTICS=false` until the consent flow is published and verified.
- Set `GA_MEASUREMENT_ID`, then enable Analytics only after the selected CMP can update Google consent signals for the visitor's region.
- Verify that Analytics, AdSense, and Skimlinks do not load before the applicable consent state allows them.

## AdSense

- Publish Google Privacy & Messaging or another Google-certified TCF CMP for the EEA, UK, and Switzerland before enabling Google tags.
- Configure applicable US-state privacy messages.
- Prefer manual ads initially. If Auto ads remain enabled, exclude `/airports`, `/when-should-i-leave`, `/link-graph`, `/wide-link-graph`, `/privacy`, `/terms`, and `/contact`.
- Add Auto ads area exclusions around navigation, airport search, checkpoint controls, charts, and calculator controls.
- Consider disabling anchor and vignette formats for the live utility experience.
- Create a responsive display unit and set `ADSENSE_SLOT_DISPLAY`.
- Create a separate Multiplex unit and set `ADSENSE_SLOT_MULTIPLEX`.
- Set `ADSENSE_CLIENT`, then set `ENABLE_ADSENSE=true` only after the consent message and unit types are verified.
- Verify mobile placement, unfilled behavior, and coverage reports in AdSense.

## Affiliate Links

- Confirm the Skimlinks domain and privacy settings in the Skimlinks dashboard.
- Set `SKIMLINKS_SCRIPT_URL` only if the disclosed commercial guide should use automatic affiliate measurement.
- Keep official TSA links noncommercial.
- Keep potentially compensated provider and card links visibly disclosed and marked `rel="sponsored"`.

## Verification Boundary

Repository tests verify route allowlists, slot formats, labels, disclosures, and disabled defaults. They cannot verify a published CMP, geographic consent behavior, Auto ads settings, auction fill, or third-party dashboard configuration.

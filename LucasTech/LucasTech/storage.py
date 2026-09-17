from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    # Certains packages tiers (ex. django-jazzmin) livrent des fichiers JS
    # référençant un .map absent du package. Sans ça, collectstatic
    # échoue entièrement à cause de ces fichiers qu'on ne contrôle pas.
    manifest_strict = False

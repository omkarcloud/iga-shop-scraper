"""The one network helper the iga_shop module needs: the Accept-Language a
session sends. IGA Shop is an Australian site, so every session announces the
language list Chrome sends on a machine set up in Australia."""

ACCEPT_LANGUAGE_AU = "en-AU,en;q=0.9"


def accept_language(proxy=None, country=None):
    return ACCEPT_LANGUAGE_AU

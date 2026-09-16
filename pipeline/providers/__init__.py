"""M10.1 pipeline providers — one capability per module.

Strict layering (spec §C.1): discovery emits ``DocumentRef[]``, fetch emits
``DocumentEvidence``, parse emits ``ParsedInstrument``, version emits
``VersionClaim``. Providers never cross layers and never branch on
jurisdiction — source peculiarities live in ``*.profile.json``.
"""

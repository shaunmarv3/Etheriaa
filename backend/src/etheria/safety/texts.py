"""Fixed wording the product rules require (spec 4.6). Code emits these; the
model never has to get them right."""

DISCLAIMER = (
    "Etheria is an AI health assistant, not a doctor. This is general information, "
    "not a diagnosis or a prescription. Please see a doctor for advice about your own "
    "health. In an emergency, call 112 (or 108 for an ambulance)."
)

EMERGENCY = (
    "**This may be a medical emergency. Call 112 now, or 108 for an ambulance. Do not wait.**"
)

TELE_MANAS = (
    "You can also talk to someone right now at **Tele-MANAS: 14416 or 1-800-891-4416** "
    "(free, 24x7)."
)

NOT_FOUND_WORDING = (
    "No interaction between these is recorded in the sources I checked, but that does "
    "not mean the combination is safe: please confirm with a pharmacist or doctor."
)

NO_CAUTION_WORDING = (
    "I found no recorded caution for your report values with this medicine, but that "
    "is not a clearance: please check with your doctor or pharmacist."
)

DOSE_REPLACEMENT = "Dosing should come from your doctor or pharmacist."

NO_EVIDENCE_NOTE = (
    "I could not find a verified source for this, so I can only give general guidance."
)


def emergency_block(helpline: bool) -> str:
    """The block that opens a RED reply, before any model token."""
    return EMERGENCY + ("\n\n" + TELE_MANAS if helpline else "") + "\n\n"

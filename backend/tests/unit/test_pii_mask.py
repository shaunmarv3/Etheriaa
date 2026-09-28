from etheria.ingestion.pii_mask import mask_pii, verhoeff_check_digit, verhoeff_valid


def aadhaar(prefix: str = "23456789012") -> str:
    return prefix + verhoeff_check_digit(prefix)


def test_verhoeff_known_values() -> None:
    # Standard Verhoeff test vector: 236 -> check digit 3.
    assert verhoeff_check_digit("236") == "3"
    assert verhoeff_valid("2363")
    assert not verhoeff_valid("2364")


def test_aadhaar_with_valid_checksum_masked() -> None:
    a = aadhaar()
    spaced = f"{a[:4]} {a[4:8]} {a[8:]}"
    for form in (a, spaced):
        out = mask_pii(f"Aadhaar: {form} issued")
        assert form not in out.text
        assert "[AADHAAR]" in out.text
        assert out.counts["aadhaar"] == 1


def test_twelve_digits_bad_checksum_kept() -> None:
    a = aadhaar()
    bad = a[:-1] + str((int(a[-1]) + 1) % 10)
    assert mask_pii(f"Bill number {bad}").text == f"Bill number {bad}"


def test_phone_forms_masked() -> None:
    for form in ("+91 98765 43210", "+91-9876543210", "09876543210", "9876543210", "+919876543210"):
        out = mask_pii(f"Call {form} now")
        assert "[PHONE]" in out.text, form
        assert "43210" not in out.text, form


def test_five_digit_start_not_phone() -> None:
    assert mask_pii("Ref 5876543210").text == "Ref 5876543210"


def test_email_masked() -> None:
    out = mask_pii("Mail rahul.verma@example.com today")
    assert out.text == "Mail [EMAIL] today"


def test_labelled_identifiers_masked() -> None:
    text = (
        "Patient Name: Rahul Verma\n"
        "UHID : APL-12345\n"
        "Referred by: Dr. Anil Kapoor\n"
        "Lab No. 88213\n"
        "MRN - 55-221\n"
        "Patient ID: P00991\n"
        "Name : Priya Nair"
    )
    out = mask_pii(text)
    for secret in (
        "Rahul Verma",
        "APL-12345",
        "Anil Kapoor",
        "88213",
        "55-221",
        "P00991",
        "Priya Nair",
    ):
        assert secret not in out.text, secret
    assert "Patient Name: [NAME]" in out.text
    assert "UHID : [ID]" in out.text


def test_address_line_masked() -> None:
    out = mask_pii("Address: 12, MG Road, Pune 411001\nAge: 34")
    assert "MG Road" not in out.text
    assert "411001" not in out.text
    assert "Age: 34" in out.text


def test_age_and_sex_kept() -> None:
    line = "Age/Sex: 34 Y / Male   Gender: Male"
    assert mask_pii(line).text == line


def test_lab_values_untouched() -> None:
    text = "Haemoglobin 10.9 g/dL 13.0 - 17.0\nPlatelets 2,45,000 /cumm 1,50,000 - 4,10,000"
    assert mask_pii(text).text == text


def test_test_names_with_name_suffix_untouched() -> None:
    # "Name" as a label only at the start of a line.
    text = "Test Name   Result   Unit"
    assert mask_pii(text).text == text


def test_counts_never_hold_values() -> None:
    out = mask_pii("Patient Name: A B\nPhone 9876543210\nx@y.in")
    assert all(isinstance(v, int) for v in out.counts.values())
    assert out.counts == {"name": 1, "phone": 1, "email": 1}

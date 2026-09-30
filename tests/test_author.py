import json

import pytest
from pydantic import ValidationError

from paper_factory.author import AuthorProfile, load_author


def test_author_precedence_and_empty_value_fallback():
    profile = load_author(
        explicit={"display_name": "Explicit Author", "email": "", "country": "  "},
        project_metadata={"display_name": "Project Author", "email": "project@example.org", "country": "Korea", "city": "Project City"},
        environ={
            "PF_AUTHOR_PROFILE_JSON": json.dumps({"display_name": "JSON Author", "email": "json@example.org", "department": "JSON Department"}),
            "PF_AUTHOR_DISPLAY_NAME": "Env Author",
            "PF_AUTHOR_EMAIL": " env@example.org ",
            "PF_AUTHOR_CITY": "",
        },
    )
    assert profile.display_name == "Explicit Author"
    assert profile.email == "env@example.org"
    assert profile.country == "Korea"
    assert profile.city == "Project City"
    assert profile.department == "JSON Department"


def test_json_environment_is_above_project_metadata():
    profile = load_author(project_metadata={"email": "project@example.org"}, environ={
        "PF_AUTHOR_PROFILE_JSON": '{"email": "json@example.org"}',
        "PF_AUTHOR_EMAIL": "",
    })
    assert profile.email == "json@example.org"


def test_supports_every_documented_individual_variable():
    expected = {
        "given_name": "Ada", "family_name": "Lovelace", "display_name": "Ada Lovelace",
        "email": "ada@example.org", "orcid": "0000-0002-1825-0097",
        "affiliation": "Example University", "department": "Computing",
        "city": "London", "country": "UK", "scholar_id": "example-id",
        "github": "https://github.com/example", "homepage": "https://example.org/ada",
    }
    profile = load_author(environ={f"PF_AUTHOR_{field.upper()}": value for field, value in expected.items()}, require=True)
    assert profile.model_dump() == expected


def test_empty_profile_does_not_invent_author_values():
    profile = load_author(environ={})
    assert all(value == "" for value in profile.model_dump().values())


def test_resolves_display_name_from_given_and_family_names():
    profile = load_author(explicit={"given_name": " Ada ", "family_name": " Lovelace "}, environ={})
    assert profile.display_name == "Ada Lovelace"


def test_single_name_does_not_become_a_required_display_name():
    with pytest.raises(ValueError, match="display_name or both given_name and family_name"):
        load_author(explicit={"given_name": "Ada", "email": "ada@example.org", "affiliation": "University"}, environ={}, require=True)


def test_explicit_display_name_is_preserved():
    assert load_author(explicit={"given_name": "Ada", "family_name": "Lovelace", "display_name": "A. Lovelace"}, environ={}).display_name == "A. Lovelace"


def test_required_values_report_all_missing_fields():
    with pytest.raises(ValueError) as caught:
        load_author(environ={}, require=True)
    assert "display_name" in str(caught.value)
    assert "email" in str(caught.value)
    assert "affiliation" in str(caught.value)


@pytest.mark.parametrize("name_fields", [{"display_name": "Example Author"}, {"given_name": "Example", "family_name": "Author"}])
def test_required_author_accepts_complete_profile(name_fields):
    profile = load_author(explicit={**name_fields, "email": "author@example.org", "affiliation": "Example University"}, environ={}, require=True)
    assert profile.display_name == "Example Author"


@pytest.mark.parametrize("raw", ["{", "not JSON", "null", "[]", '"author"', "42"])
def test_rejects_malformed_or_nonobject_json(raw):
    with pytest.raises(ValueError, match="PF_AUTHOR_PROFILE_JSON"):
        load_author(environ={"PF_AUTHOR_PROFILE_JSON": raw})


@pytest.mark.parametrize("source", ["explicit", "project_metadata", "environ"])
def test_unknown_fields_are_rejected(source):
    arguments = {"environ": {}}
    if source == "environ":
        arguments[source] = {"PF_AUTHOR_PROFILE_JSON": '{"unexpected": "value"}'}
    else:
        arguments[source] = {"unexpected": "value"}
    with pytest.raises(ValueError, match="Unknown author fields"):
        load_author(**arguments)


@pytest.mark.parametrize("value", [None, 1, True, [], {}])
def test_json_values_must_be_strings(value):
    with pytest.raises(ValueError, match="must be a string"):
        load_author(environ={"PF_AUTHOR_PROFILE_JSON": json.dumps({"affiliation": value})})


def test_individual_environment_values_must_be_strings():
    with pytest.raises(ValueError, match="PF_AUTHOR_EMAIL must be a string"):
        load_author(environ={"PF_AUTHOR_EMAIL": 42})


@pytest.mark.parametrize("value", [None, 42, True])
def test_profile_rejects_nonstring_fields(value):
    with pytest.raises(ValidationError):
        AuthorProfile(display_name=value)


@pytest.mark.parametrize("orcid", ["0000-0002-1825-0097", "0000-0002-1694-233X"])
def test_valid_orcid_checksum(orcid):
    assert load_author(explicit={"orcid": orcid}, environ={}).orcid == orcid


def test_lowercase_orcid_check_digit_is_normalized():
    assert AuthorProfile(orcid="0000-0002-1694-233x").orcid == "0000-0002-1694-233X"


@pytest.mark.parametrize("orcid", ["0000-0002-1825-0098", "0000-0002-1694-2330"])
def test_invalid_orcid_checksum(orcid):
    with pytest.raises(ValidationError, match="checksum"):
        load_author(explicit={"orcid": orcid}, environ={})


@pytest.mark.parametrize("orcid", ["0000000218250097", "orcid", "https://orcid.org/0000-0002-1825-0097"])
def test_invalid_orcid_format(orcid):
    with pytest.raises(ValidationError, match="format"):
        AuthorProfile(orcid=orcid)


@pytest.mark.parametrize("email", ["name", "name@localhost", "name @example.org", "@example.org", "name@example@org.com"])
def test_invalid_email_shape(email):
    with pytest.raises(ValidationError, match="email"):
        AuthorProfile(email=email)


@pytest.mark.parametrize("field", ["github", "homepage"])
@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///private", "ftp://example.org", "github.com/example", "https://", "https://example.org/a b", "https://example.org:invalid"])
def test_rejects_invalid_author_urls(field, url):
    with pytest.raises(ValidationError, match="URLs"):
        AuthorProfile(**{field: url})


def test_does_not_read_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PF_AUTHOR_DISPLAY_NAME=Unrequested Author\n", encoding="utf-8")
    assert load_author(environ={}).display_name == ""
    assert list(tmp_path.iterdir()) == [tmp_path / ".env"]


def test_default_environment_reads_exported_author(monkeypatch):
    for field in AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    monkeypatch.delenv("PF_AUTHOR_PROFILE_JSON", raising=False)
    monkeypatch.setenv("PF_AUTHOR_DISPLAY_NAME", "Exported Author")
    assert load_author().display_name == "Exported Author"


@pytest.mark.parametrize("field", ["display_name", "affiliation", "email"])
def test_author_metadata_rejects_control_characters(field):
    with pytest.raises(ValidationError, match="control characters"):
        AuthorProfile(**{field: "Example\x00Author"})

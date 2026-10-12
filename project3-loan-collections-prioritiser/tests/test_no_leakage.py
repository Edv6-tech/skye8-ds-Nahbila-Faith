from src.features import FEATURE_COLUMNS, FORBIDDEN_POST_CONTACT


def test_no_post_contact_field_in_features():
    leaked = set(FEATURE_COLUMNS) & set(FORBIDDEN_POST_CONTACT)
    assert not leaked, f"Post-contact fields reached the model: {leaked}"


def test_feature_list_is_a_list():
    assert isinstance(FEATURE_COLUMNS, list)

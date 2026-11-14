from shop.slugs import slugify


def test_slugify_lower_cases_and_joins_words_with_one_hyphen():
    assert slugify("Czerwony   Rower") == "czerwony-rower"


def test_slugify_maps_polish_letters():
    assert slugify("Łąka żółta ślimaka") == "laka-zolta-slimaka"


def test_slugify_keeps_digits_and_drops_punctuation():
    assert slugify('Rower 27", 3 biegi!') == "rower-27-3-biegi"


def test_slugify_has_no_leading_or_trailing_hyphen():
    assert slugify("--Café Latte--") == "cafe-latte"


def test_slugify_of_text_without_ascii_words_is_empty():
    assert slugify("!!!") == ""

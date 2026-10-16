from __future__ import annotations

from scripts.import_purananuru import WORK_TITLE, _parse_page


def _page(content: str, page_range: str) -> dict[str, object]:
    return {
        "title": f"{WORK_TITLE}/பாடல் {page_range}",
        "revisions": [
            {
                "revid": 123,
                "slots": {"main": {"content": content}},
            }
        ],
    }


def test_parse_legacy_hash_stanza_without_trailing_metadata() -> None:
    page = _page(
        "= பாடல்:02 (மண்திணிந்த) =\n"
        "===பாடியவர்: முரஞ்சியூர் முடிநாகராயர்.===\n"
        ";பாடப்பட்டோன்: சேரமான் பெருஞ்சோற்று உதியன் சேரலாதன்.\n"
        "#மண் திணிந்த நிலனும்,<br />\n"
        "நிலம் ஏந்திய விசும்பும்,<br />\n"
        "விசும்பு தைவரு வளியும்<br />\n"
        "வளித் தலைஇய தீயும்,\n"
        ";திணை: பாடாண் திணை;\n"
        ":இந்தக் குறிப்பு பாடியது.\n"
        "= பாடல்:03 (நிறை) =\n",
        "01-10",
    )

    record = next(item for item in _parse_page(page) if item["id"] == 2)

    assert record["lines"] == [
        "மண் திணிந்த நிலனும்,",
        "நிலம் ஏந்திய விசும்பும்,",
        "விசும்பு தைவரு வளியும்",
        "வளித் தலைஇய தீயும்,",
    ]
    assert record["poet"] == "முரஞ்சியூர் முடிநாகராயர்"


def test_parse_line_numbered_poem_and_remove_editorial_markers() -> None:
    page = _page(
        "== பாடல்: 51 (நீர்மிகிற்) ==\n"
        ":நீர்மிகிற் சிறையு மில்லை\n"
        ":மன்னுயிர் நிழற்று நிழலு மில்லை\n"
        ":வளிமிகின் வலியு மில்லை\n"
        ":10 செம்புற் றீயல் போல (10)\n"
        ":(பாடபேதம்.)\n"
        "== பாடல்: 52 ==\n",
        "51-60",
    )

    record = _parse_page(page)[0]

    assert record["id"] == 51
    assert record["lines"] == [
        "நீர்மிகிற் சிறையு மில்லை",
        "மன்னுயிர் நிழற்று நிழலு மில்லை",
        "வளிமிகின் வலியு மில்லை",
        "செம்புற் றீயல் போல",
    ]


def test_wrapped_poem_uses_one_stanza_not_alternate_text_or_commentary() -> None:
    page = _page(
        "</poem> 192\n"
        "=== பெரியோர் சிறியோர்! ===\n"
        "<poem>\n"
        "பாடியவர்: கணியன் பூங்குன்றனார்\n"
        "திணை: பொதுவியல்\n\n"
        "யாதும் ஊரே ; யாவரும் கேளிர் ;<br />\n"
        "தீதும் நன்றும் பிறர்தர வாரா ;<br />\n"
        "நோதலும் தணிதலும் அவற்றோ ரன்ன ;<br />\n\n"
        "யாது மூரே யாவருங் கேளிர்<br />\n"
        "மாற்று உரை\n\n"
        "பொருள் விளக்கம்.\n"
        "</poem> 193\n",
        "191-200",
    )

    record = _parse_page(page)[0]

    assert record["id"] == 192
    assert record["lines"] == [
        "யாதும் ஊரே ; யாவரும் கேளிர் ;",
        "தீதும் நன்றும் பிறர்தர வாரா ;",
        "நோதலும் தணிதலும் அவற்றோ ரன்ன ;",
    ]

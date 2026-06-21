from bot import config


def test_help_text_lists_commands():
    text = config.get_help_text()
    assert "/broadcast" in text
    assert "/cancel_scheduled" in text

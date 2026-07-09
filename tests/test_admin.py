from bot.db import Subscriber
from bot.handlers.admin import _describe


def test_describe_name_and_username():
    sub = Subscriber(user_id=1, username="jdoe", full_name="Jane Doe")
    assert _describe(sub) == "Jane Doe @jdoe"


def test_describe_no_username():
    sub = Subscriber(user_id=1, username=None, full_name="Мария Иванова")
    assert _describe(sub) == "Мария Иванова"


def test_describe_keeps_emoji():
    sub = Subscriber(user_id=1, username=None, full_name="Анна Петрова 🧘‍♀️")
    assert _describe(sub) == "Анна Петрова 🧘‍♀️"


def test_describe_escapes_html_in_name():
    sub = Subscriber(user_id=1, username=None, full_name="<b>Ваня</b> & Co")
    assert _describe(sub) == "&lt;b&gt;Ваня&lt;/b&gt; &amp; Co"


def test_describe_empty():
    assert _describe(Subscriber(user_id=1, username=None, full_name=None)) == "—"

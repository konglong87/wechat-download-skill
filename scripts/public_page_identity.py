"""Visible, source-declared article title and public-account name parser."""

from html import unescape
from html.parser import HTMLParser

PAGE_FIELDS = frozenset(("activity-name", "js_name"))


class PageIdentity(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}
        self.scripts = []
        self.active = None
        self.active_tag = None
        self.depth = 0
        self.parts = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
        if self.active is not None and tag == self.active_tag:
            self.depth += 1
        elif self.active is None:
            field = dict(attrs).get("id")
            if field in PAGE_FIELDS:
                self.active, self.active_tag, self.depth, self.parts = field, tag, 1, []

    def handle_data(self, data):
        if self.in_script:
            self.scripts.append(data)
        if self.active is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False
        if self.active is None or tag != self.active_tag:
            return
        self.depth -= 1
        if self.depth == 0:
            value = " ".join(unescape("".join(self.parts)).split())
            if value:
                self.fields[self.active] = value
            self.active = self.active_tag = None



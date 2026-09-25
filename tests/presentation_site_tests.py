"""Small, dependency-free integrity check for the static presentation site."""

from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.references = []
        self.tags = []
        self.images = []
        self.lang = None
        self.image_without_alt = False

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.tags.append(tag)
        if tag == "html":
            self.lang = attributes.get("lang")
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "img":
            self.images.append(attributes)
            if "alt" not in attributes:
                self.image_without_alt = True
        for attribute in ("href", "src"):
            if attribute in attributes:
                self.references.append(attributes[attribute])


def check(site_root: Path):
    pages = sorted(site_root.glob("*.html"))
    assert {page.name for page in pages} == {
        "index.html", "features.html", "tour.html", "deployment.html", "about.html"
    }
    parsed = {}
    for path in pages:
        page = Page()
        page.feed(path.read_text(encoding="utf-8"))
        assert page.lang == "en", f"{path}: missing English document language"
        assert page.tags.count("title") == 1, f"{path}: expected one title"
        assert page.tags.count("main") == 1, f"{path}: expected one main landmark"
        assert page.tags.count("h1") == 1, f"{path}: expected one h1"
        assert not page.image_without_alt, f"{path}: image without alt"
        parsed[path.resolve()] = page

    for path, page in parsed.items():
        for image in page.images:
            source = (path.parent / image["src"]).resolve()
            if source.suffix == ".png":
                data = source.read_bytes()[:24]
                assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{source}: invalid PNG"
                actual_size = (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))
                declared_size = (int(image["width"]), int(image["height"]))
                assert declared_size == actual_size, f"{path}: incorrect image dimensions for {source}"
        for reference in page.references:
            url = urlsplit(reference)
            if url.scheme or url.netloc:
                continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path.resolve()
            assert target.is_relative_to(site_root.resolve()), f"{path}: path escapes site: {reference}"
            assert target.is_file(), f"{path}: broken local link: {reference}"
            if url.fragment and target.suffix == ".html":
                assert unquote(url.fragment) in parsed[target].ids, (
                    f"{path}: broken page anchor: {reference}"
                )


if __name__ == "__main__":
    check(Path(sys.argv[1]))
    print("presentation site links and landmarks passed")

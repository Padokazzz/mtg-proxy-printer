from pathlib import Path

from mtg_proxy.cache.image_cache import ImageCache, _PNG_SIGNATURE
from mtg_proxy.models import CardRequest, ResolvedCard


class FakeClient:
    def __init__(self, data=b"fakepng"):
        self.data = data
        self.calls = 0

    def download_image(self, url):
        self.calls += 1
        return self.data


def _make_rc(name="Sol Ring", lang="en", set_="cmm", cn="337"):
    return ResolvedCard(
        request=CardRequest(name=name),
        scryfall_id="id1",
        name=name,
        language=lang,
        set_code=set_,
        set_name=set_.upper(),
        collector_number=cn,
        released_at="2020-01-01",
        image_url=f"http://img/{set_}/{cn}.png",
    )


def _fake_config(tmp_path):
    class Out:
        cache_directory = str(tmp_path / "cartas")

    class Cfg:
        output = Out()

        @property
        def cache_dir(self):
            from pathlib import Path
            return Path(self.output.cache_directory)

    return Cfg()


def test_cache_miss_downloads(tmp_path):
    client = FakeClient(_PNG_SIGNATURE + b"data")
    cache = ImageCache(_fake_config(tmp_path), client)
    rc = _make_rc()
    path = cache.get(rc)
    assert path.exists()
    assert client.calls == 1
    assert path.read_bytes().startswith(_PNG_SIGNATURE)


def test_cache_hit_reuses(tmp_path):
    client = FakeClient(_PNG_SIGNATURE + b"data")
    cfg = _fake_config(tmp_path)
    cache = ImageCache(cfg, client)
    rc = _make_rc()
    p1 = cache.get(rc)
    # segunda chamada: nem deve tocar o cliente
    cache2 = ImageCache(cfg, client)
    p2 = cache2.get(rc)
    assert p1 == p2
    assert client.calls == 1


def test_cache_corrupt_recovers(tmp_path):
    client = FakeClient(_PNG_SIGNATURE + b"data")
    cfg = _fake_config(tmp_path)
    cache = ImageCache(cfg, client)
    rc = _make_rc()
    path = cache.get(rc)
    # corrompe o arquivo
    path.write_bytes(b"not-a-png")
    # nova instância deve detectar e re-download
    client2 = FakeClient(_PNG_SIGNATURE + b"data")
    cache2 = ImageCache(cfg, client2)
    path2 = cache2.get(rc)
    assert path2.read_bytes().startswith(_PNG_SIGNATURE)
    assert client2.calls == 1

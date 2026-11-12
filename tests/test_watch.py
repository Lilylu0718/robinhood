from watch_check import find_moves


def test_moves_threshold_and_retrigger():
    st = {}
    m = find_moves({"NVDA": 95.0, "MU": 98.0}, {"NVDA": 100.0, "MU": 100.0}, st, "2026-11-12")
    assert [s for s, *_ in m] == ["NVDA"]
    # 同日同方向没再扩大 2 个点 → 不重复报
    assert find_moves({"NVDA": 94.0}, {"NVDA": 100.0}, st, "2026-11-12") == []
    assert [s for s, *_ in find_moves({"NVDA": 92.5}, {"NVDA": 100.0}, st, "2026-11-12")] == ["NVDA"]
    # 反向大涨要报；新的一天重置
    assert find_moves({"NVDA": 105.0}, {"NVDA": 100.0}, st, "2026-11-12")
    assert find_moves({"NVDA": 95.5}, {"NVDA": 100.0}, st, "2026-11-13")


def test_zone_hits():
    from watch_check import find_zone_hits
    st = {"date": "2026-11-12", "triggered": {}}
    zones = {"NVDA": {"buy_below": 150}, "MSFT": {"buy_below": 600, "paused": True}, "BAD": {}}
    assert find_zone_hits({"NVDA": 151.0, "MSFT": 500.0}, zones, st) == []
    assert [s for s, *_ in find_zone_hits({"NVDA": 149.0}, zones, st)] == ["NVDA"]
    assert find_zone_hits({"NVDA": 147.0}, zones, st) == []          # 没再跌 2%
    assert find_zone_hits({"NVDA": 145.0}, zones, st)


def test_extra_satellites_from_pool(tmp_path, monkeypatch):
    import json
    import config
    f = tmp_path / "pool.json"
    f.write_text(json.dumps({"satellites": [{"symbol": "crm"}, {"symbol": "NVDA"}, {"symbol": "bad sym"},
                                            {"symbol": "CRM"}, {"symbol": "BRK.B"}]}))
    monkeypatch.setattr(config, "POOL_FILE", f)
    assert config._load_extra_satellites() == ("CRM", "BRK.B")
    monkeypatch.setattr(config, "POOL_FILE", tmp_path / "missing.json")
    assert config._load_extra_satellites() == ()

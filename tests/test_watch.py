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

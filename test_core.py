from datetime import date
from connectors.mock import MockConnector
from sampling import filter_by_date, select, to_dataframe

s, e = date(2026, 10, 1), date(2026, 10, 31)
pool = MockConnector().fetch("girldate", s, e, 300)
assert len(pool) == 300
inr = filter_by_date(pool, s, e)
assert 0 < len(inr) <= 300
assert not filter_by_date(pool, date(2020, 1, 1), date(2020, 1, 2))

pop = select(inr, "popular", 10)
scores = [p.likes + p.comments for p in pop]
assert scores == sorted(scores, reverse=True) and len(pop) == 10

r1 = [p.post_id for p in select(inr, "random", 10, 7)]
r2 = [p.post_id for p in select(inr, "random", 10, 7)]
r3 = [p.post_id for p in select(inr, "random", 10, 8)]
assert r1 == r2 and r1 != r3

assert len(select(inr, "random", 10**6, 1)) == len(inr)
assert to_dataframe([]).empty
df = to_dataframe(pop)
assert "author_hash" in df.columns and "username" not in df.columns
print("TESTLER GECTI")

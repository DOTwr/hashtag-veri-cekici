"""Testler icin sahte Apify sunucusu: calistir -> durum -> veri seti."""
from unittest.mock import MagicMock


def resp(code, js):
    m = MagicMock()
    m.status_code = code
    m.json.return_value = js
    m.text = str(js)
    return m


class FakeApify:
    """actor adina gore veri seti dondurur; gelen girdileri kaydeder."""

    def __init__(self, datasets: dict, start_code=201, final_status="SUCCEEDED", runs=None, inputs=None):
        self.datasets = datasets          # actor -> list
        self.start_code = start_code
        self.final_status = final_status
        self.calls = []                   # (actor, input)
        self.runs = runs or []            # gecmis calistirmalar
        self.inputs = inputs or {}        # kvs -> INPUT
        self.items = {}                   # dataset id -> list
        self.limits = (0.2, 5.0)          # (kullanilan, limit) USD; None = okunamaz

    def post(self, url, headers=None, json=None, timeout=0, params=None):
        actor = url.split("/acts/")[1].split("/")[0]
        self.calls.append((actor, json, headers))
        if self.start_code not in (200, 201):
            return resp(self.start_code, {"error": "x"})
        ds = f"ds_{len(self.calls)}"
        self.items[ds] = self.datasets.get(actor, [])
        return resp(201, {"data": {"id": f"run_{len(self.calls)}", "status": "RUNNING", "defaultDatasetId": ds}})

    def get(self, url, headers=None, params=None, timeout=0):
        if "/actor-runs/" in url:
            rid = url.rsplit("/", 1)[1]
            n = rid.split("_")[1]
            return resp(200, {"data": {"id": rid, "status": self.final_status, "defaultDatasetId": f"ds_{n}"}})
        if "/datasets/" in url:
            ds = url.split("/datasets/")[1].split("/")[0]
            return resp(200, self.items.get(ds, []))
        if url.endswith("/runs"):
            return resp(200, {"data": {"items": self.runs}})
        if url.endswith("/users/me/limits"):
            if self.limits is None:
                return resp(500, {"error": "x"})
            used, limit = self.limits
            return resp(200, {"data": {"current": {"monthlyUsageUsd": used}, "limits": {"maxMonthlyUsageUsd": limit}}})
        if "/key-value-stores/" in url:
            kvs = url.split("/key-value-stores/")[1].split("/")[0]
            if kvs in self.inputs:
                return resp(200, self.inputs[kvs])
            return resp(404, {"error": "yok"})
        return resp(404, {})

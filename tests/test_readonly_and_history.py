import json

import pytest

from tradelab.broker import ReadOnlyGroww, ReadOnlyViolation, redact
from tradelab.cli import main


class FakeClient:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*a, **k):
            self.calls.append(name)
            return {"ok": True}
        return call


@pytest.mark.parametrize("method", ["place_order", "modify_order", "cancel_order",
                                    "create_smart_order", "modify_smart_order", "cancel_smart_order"])
def test_write_methods_are_blocked(method):
    fake = FakeClient()
    api = ReadOnlyGroww(fake)
    with pytest.raises(ReadOnlyViolation):
        getattr(api, method)
    assert fake.calls == []


def test_unknown_methods_are_blocked_and_reads_pass():
    fake = FakeClient()
    api = ReadOnlyGroww(fake)
    with pytest.raises(ReadOnlyViolation):
        api.something_new
    assert api.get_positions_for_user() == {"ok": True}
    assert "client hidden" in repr(api)


def test_redact_masks_tokens_and_totp_secrets():
    text = "token eyJabc.def-ghi.jkl_mno secret ABCDEFGHIJKLMNOPQRSTUVWXYZ234567 done"
    out = redact(text)
    assert "eyJ" not in out and "ABCDEFGH" not in out and out.endswith("done")


def test_history_end_to_end(ledger_xlsx, orders_xlsx, tmp_path):
    out, data = tmp_path / "reports", tmp_path / "data"
    assert main(["history", "--ledger", str(ledger_xlsx), "--orders", str(orders_xlsx),
                 "--out", str(out), "--data", str(data)]) == 0
    r = json.loads((out / "history.json").read_text())
    assert r["fno"]["summary"]["n"]["value"] == 3
    assert r["fno"]["summary"]["total"]["value"] == pytest.approx(-700)
    assert r["fno"]["summary"]["total"]["label"] == "derived"
    assert r["money"]["deposits_on_or_day_after_fno_loss"]["value"]["count"] == 2
    assert r["fno"]["hypothetical_caps"]["label"] == "hypothetical"
    assert r["fno"]["intraday_sequence"]["label"] == "unavailable"
    # stock: ABC +100 gross, XYZ short +10 gross
    assert r["stocks"]["summary_gross"]["total"]["value"] == pytest.approx(110)
    recon = r["stocks"]["charges_reconciliation"]["value"]
    assert sum(w["implied_charges"] for w in recon) == pytest.approx(0.90 + 10, abs=0.01)  # XYZ has no ledger bill in fixture
    assert (data / "tradelab.db").exists()
    md = (out / "history.md").read_text()
    assert "hypothetical" in md and "no edge demonstrated" in md


def test_history_is_reproducible(ledger_xlsx, orders_xlsx, tmp_path):
    outs = []
    for i in range(2):
        out = tmp_path / f"r{i}"
        main(["history", "--ledger", str(ledger_xlsx), "--orders", str(orders_xlsx), "--out", str(out), "--data", str(tmp_path / f"d{i}")])
        outs.append((out / "history.json").read_text())
    assert outs[0] == outs[1]

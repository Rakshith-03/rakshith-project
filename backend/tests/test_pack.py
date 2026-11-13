from bp.model import load_model
from bp.pack import make_cells, run

M = load_model()
Z0 = [0.50, 0.58, 0.62, 0.53]; DQ = [0.0, -0.03, 0.02, 0.01]; DR = [0.0, 0.10, -0.05, 0.2]


def scenario(mode, I=0.0, t=4 * 3600, **kw):
    return run(make_cells(M, 4, DQ, DR, Z0), I, t, mode=mode, **kw)


def test_balancing_at_rest_reduces_soc_spread():
    off, pas, act = scenario("off"), scenario("passive", threshold=0.002), scenario("active")
    assert abs(off["dSOC_final"] - off["dSOC_initial"]) < 0.005
    assert pas["dSOC_final"] < off["dSOC_final"] / 2 and act["dSOC_final"] < off["dSOC_final"] / 2
    assert pas["balancing_energy_Wh"] > act["balancing_energy_Wh"] > 0   # passive burns more energy


def test_active_balancing_during_charge_lets_pack_accept_more_charge():
    off = scenario("off", I=-1.0, t=3 * 3600)
    act = scenario("active", I=-1.0, t=3 * 3600, I_bal=0.5)
    assert off["stopped_at_s"] is not None and act["charge_in_Ah"] > off["charge_in_Ah"]

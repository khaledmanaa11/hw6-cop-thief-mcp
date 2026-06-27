"""
Offline deception simulation for HW6 Step 5 (NO LLM / NO API).

Models each agent as moving toward/away from a BELIEVED opponent cell.
The belief is set by the opponent's free-text "claim" each ply, filtered by a
trust policy. This lets us measure -- against the real engine geometry -- whether
lying actually degrades the victim's belief and changes the outcome, and whether
skepticism defends. The real Step-5 LLM drops into the same belief/claim seam.

Run: python decep_sim.py
"""
import random
import sys

GRID_TESTS = [("official 5x5 / 25", 5, 5, 25), ("open 9x9 / 40", 9, 9, 40)]
N_GAMES = 4000
DIRS8 = [(-1,0),(1,0),(0,1),(0,-1),(-1,1),(-1,-1),(1,1),(1,-1)]


def cheb(a, b):
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))


def in_bounds(p, R, C):
    return 0 <= p[0] < R and 0 <= p[1] < C


def legal_targets(pos, R, C):
    return [(pos[0]+dr, pos[1]+dc) for dr, dc in DIRS8
            if in_bounds((pos[0]+dr, pos[1]+dc), R, C)]


def step_toward(pos, target, R, C):
    cands = legal_targets(pos, R, C)
    return min(cands, key=lambda p: cheb(p, target))


def step_away(pos, target, R, C, sealed=None):
    cands = legal_targets(pos, R, C)
    if sealed is not None:                       # believer avoids the bluffed 'sealed' half
        open_cands = [p for p in cands if not sealed(p)]
        if open_cands:
            cands = open_cands
    return max(cands, key=lambda p: cheb(p, target))


def sealed_far_half(cop_pos, R, C):
    """Cop bluffs: 'the half of the board farther from me is walled — you're trapped on my side.'
    Returns a predicate that is True for cells in that far (claimed-sealed) half."""
    cr, cc = cop_pos
    # split on whichever axis the cop is more off-center -> a believable 'wall'
    if abs(cr - (R-1)/2) >= abs(cc - (C-1)/2):
        mid = (R-1)/2
        return lambda p: (p[0] > mid) if cr <= mid else (p[0] < mid)
    mid = (C-1)/2
    return lambda p: (p[1] > mid) if cc <= mid else (p[1] < mid)


def farthest_corner(p, R, C):
    corners = [(0,0),(0,C-1),(R-1,0),(R-1,C-1)]
    return max(corners, key=lambda c: cheb(c, p))


def clamp(p, R, C):
    return (max(0, min(R-1, p[0])), max(0, min(C-1, p[1])))


def claim(policy, true_self, true_opp_known, R, C):
    """What the agent BROADCASTS about its own position this ply."""
    if policy == "honest":
        return true_self
    if policy == "decoy":                         # consistent believable lie
        return farthest_corner(true_self, R, C)
    if policy == "herd":                          # cop only: push a believer-thief into a trap
        # claim a position so that "flee away from claim" points toward the true cop
        return clamp((2*true_opp_known[0]-true_self[0], 2*true_opp_known[1]-true_self[1]), R, C)
    raise ValueError(policy)


def believe(trust, last_claim, true_self, true_opp, prev_belief, R, C, radius=2):
    """How the agent SETS its belief of the opponent from the incoming claim."""
    if trust == "believer":
        return last_claim
    if trust == "skeptic":                        # ignore text; noisy partial sensor (radius)
        if cheb(true_self, true_opp) <= radius:
            return true_opp
        return prev_belief                        # stale otherwise
    raise ValueError(trust)


def play(R, C, max_moves, cop_pol, thief_pol, rng):
    """
    cop_pol/thief_pol: dict(claim=, trust=, omniscient_move=bool)
    omniscient_move=True means that side MOVES on true opponent pos (control side),
    isolating the messaging effect on the OTHER side's belief.
    Returns (captured, plies, mean_belief_err_of_studied_side).
    The 'studied' side is whichever is NOT omniscient.
    """
    while True:
        cop = (rng.randrange(R), rng.randrange(C))
        thief = (rng.randrange(R), rng.randrange(C))
        if cop != thief:
            break
    center = (R//2, C//2)
    bel_cop_of_thief = center      # cop's belief about thief
    bel_thief_of_cop = center      # thief's belief about cop
    cl_cop = cop                   # last claim broadcast by cop
    cl_thief = thief
    errs, captured, plies = [], False, 0
    to_move = "THIEF"

    for ply in range(max_moves):
        plies = ply + 1
        if to_move == "THIEF":
            bel_thief_of_cop = (cop if thief_pol["omniscient_move"]
                                else believe(thief_pol["trust"], cl_cop, thief, cop, bel_thief_of_cop, R, C))
            if not thief_pol["omniscient_move"]:
                errs.append(cheb(bel_thief_of_cop, cop))
            sealed = sealed_far_half(cop, R, C) if cop_pol.get("region_bluff") and thief_pol["trust"] == "believer" else None
            thief = step_away(thief, bel_thief_of_cop, R, C, sealed=sealed)
            cl_thief = claim(thief_pol["claim"], thief, cop, R, C)
            to_move = "COP"
        else:
            bel_cop_of_thief = (thief if cop_pol["omniscient_move"]
                                else believe(cop_pol["trust"], cl_thief, cop, thief, bel_cop_of_thief, R, C))
            if not cop_pol["omniscient_move"]:
                errs.append(cheb(bel_cop_of_thief, thief))
            cop = step_toward(cop, bel_cop_of_thief, R, C)
            cl_cop = claim(cop_pol["claim"], cop, thief, R, C)
            to_move = "THIEF"
            if cop == thief:
                captured = True
                break

    return captured, plies, (sum(errs)/len(errs) if errs else 0.0)


def run(label, R, C, mm, cop_pol, thief_pol, seed=7):
    rng = random.Random(seed)
    caps = pl = err = 0.0
    for _ in range(N_GAMES):
        c, p, e = play(R, C, mm, cop_pol, thief_pol, rng)
        caps += c; pl += p; err += e
    n = N_GAMES
    print(f"  {label:<46} capture={caps/n*100:5.1f}%  plies={pl/n:5.2f}  belief_err={err/n:4.2f}")


def cop(claim_, trust, omni=False, region_bluff=False):
    return {"claim": claim_, "trust": trust, "omniscient_move": omni, "region_bluff": region_bluff}
def thf(claim_, trust, omni=False):
    return {"claim": claim_, "trust": trust, "omniscient_move": omni}


for name, R, C, mm in GRID_TESTS:
    print(f"\n=== {name}  ({N_GAMES} random-start games) ===")
    print("\n EXPERIMENT A -- does the THIEF lying break the COP? (Thief moves omniscient; we study Cop's belief)")
    run("A1 honest-Thief  vs believer-Cop",  R, C, mm, cop("honest","believer"), thf("honest","believer",omni=True))
    run("A2 LIAR-Thief     vs believer-Cop",  R, C, mm, cop("honest","believer"), thf("decoy","believer",omni=True))
    run("A3 LIAR-Thief     vs skeptic-Cop",   R, C, mm, cop("honest","skeptic"),  thf("decoy","believer",omni=True))

    print("\n EXPERIMENT B -- does the COP lying break the THIEF? (Cop moves omniscient; we study Thief's belief)")
    run("B1 honest-Cop    vs believer-Thief", R, C, mm, cop("honest","believer",omni=True), thf("honest","believer"))
    run("B2 HERDER-Cop    vs believer-Thief", R, C, mm, cop("herd","believer",omni=True),   thf("honest","believer"))
    run("B3 HERDER-Cop    vs skeptic-Thief",  R, C, mm, cop("herd","believer",omni=True),   thf("honest","skeptic"))

    print("\n EXPERIMENT C -- realistic blind game, NEITHER omniscient (tournament matrix)")
    run("C1 naive-Cop(honest/believe) vs naive-Thief(honest/believe)", R, C, mm, cop("honest","believer"), thf("honest","believer"))
    run("C2 ROBUST-Cop(herd/skeptic)  vs ROBUST-Thief(decoy/skeptic)", R, C, mm, cop("herd","skeptic"),    thf("decoy","skeptic"))
    run("C3 ROBUST-Cop(herd/skeptic)  vs naive-Thief(honest/believe)", R, C, mm, cop("herd","skeptic"),    thf("honest","believer"))
    run("C4 naive-Cop(honest/believe) vs ROBUST-Thief(decoy/skeptic)", R, C, mm, cop("honest","believer"), thf("decoy","skeptic"))

    print("\n EXPERIMENT D -- COP BARRIER/REGION BLUFF ('the far half is sealed, you're trapped on my side')")
    run("D1 honest-Cop          vs believer-Thief (no bluff)", R, C, mm, cop("honest","believer",omni=True), thf("honest","believer"))
    run("D2 REGION-BLUFF-Cop    vs believer-Thief (trapped)",  R, C, mm, cop("honest","believer",omni=True,region_bluff=True), thf("honest","believer"))
    run("D3 REGION-BLUFF-Cop    vs skeptic-Thief  (immune)",   R, C, mm, cop("honest","believer",omni=True,region_bluff=True), thf("honest","skeptic"))

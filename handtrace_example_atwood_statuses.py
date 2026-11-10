"""Checked statuses for the Atwood answers p and mount (generated from reviewed drafts; see
handtrace_example_atwood.py). Each row: name -> [status, countermodel, note, check], where check is
the spec passed to Trace.annotate(..., check=). Every number a check reports is computed by the
recorder from the recorded premises."""

# fmt: off
P_STATUSES = {'pp1': ['REQUIRED',
         '',
         'W1: precondition for E7-E10 to apply at all (an identity failure: the thing tracked is not the body '
         'computed). Check: drop everything resting on pp1.',
         {'drop_dependents': True}],
 'pp2': ['REQUIRED', '', 'W1, as for pp1.', {'drop_dependents': True}],
 'transl1': ['NEEDS',
             'W2: B1 rocks about a horizontal axis with its centre of mass offset from the attachment, so the '
             "representative's acceleration a1 differs from the attachment point's y1'' by a rotational term rot1 "
             '(free; the source gives no number). M-KIN still constrains the attachment points.',
             'W2. The READING rd1 (a1 = y1dd) is the relation translation licenses; it rests on transl1.',
             {'replace': {'rd1': 'a1 = y1dd + rot1'}}],
 'transl2': ['NEEDS',
             "W2, for B2: a rotational term rot2 (free) between B2's representative and its attachment point.",
             'W2. rd2 (a2 = y2dd) rests on transl2.',
             {'replace': {'rd2': 'a2 = y2dd + rot2'}}],
 'm1': ['NEEDS',
        'CM1 (W3): m(B1) = 4 kg; the source gives 9a = 49/5, a = 49/45.',
        'W3, CM1.',
        {'replace': {'m1': 4}}],
 'm2': ['NEEDS',
        'W3, computed in the example (not in the source): m(B2) = 6 kg; the example gives a = 49/15.',
        "W3; the m2 countermodel is the example's, not the source's.",
        {'replace': {'m2': 6}}],
 'rin': ['NEEDS',
         'CM2 (W4): the support (and R) in a lift accelerating upward at 1 m/s²; relative to R each E8 '
         'acceleration loses 1; the source gives 8a = 2·(49/5 + 1), a = 27/10.',
         'W4, CM2. e8rel1 and e8rel2 rest on rin.',
         {'replace': {'e8rel1': 'a1 = Fnet1/m1 - 1', 'e8rel2': 'a2 = Fnet2/m2 - 1'}}],
 'admG1': ['NEEDS',
           "W5 ('drop either interaction and a changes'): i_G1 not admitted; B1's sum has only the string member, "
           'and the weight relation and P-EQV for B1 lapse.',
           'W5. sum1, w1 and peqv1 all rest on admG1.',
           {'replace': {'sum1': 'Fnet1 = T1'}, 'remove': ['w1', 'ff1', 'peqv1']}],
 'admG2': ['NEEDS',
           "W5: i_G2 not admitted; B2's sum has only the string member, and w2, peqv2 lapse.",
           'W5. sum2, w2 and peqv2 all rest on admG2.',
           {'replace': {'sum2': 'Fnet2 = T2'}, 'remove': ['w2', 'ff2', 'peqv2']}],
 'w1': ['NEEDS',
        "W5 ('a g that differs between the blocks changes a'), new numbers here: the field at B1 is g + 1/10 m/s² "
        'while g = 49/5 stays the value at B2.',
        "W5. Caveat: g's INPUT text also says g is 'uniform over the region of motion', which this world "
        "falsifies; the checker cannot see text. Provisional (10 November 2026, P1): the 'same g / uniform field' "
        'clause is owned by w1, so this world breaks only w1. The free-fall reading ff1 rests on that clause and '
        'changes with it.',
        {'replace': {'w1': 'fG1 = -mu1*(g + 1/10)', 'ff1': 'fG1 = -m1*(g + 1/10)'}}],
 'w2': ['NEEDS',
        'W5, new numbers here: the field at B2 is g + 1/10 m/s² while g = 49/5 stays the value at B1.',
        "W5. Same caveat as w1 (g's text says uniform). Provisional (10 November 2026, P1): the 'same g / uniform "
        "field' clause is owned by w2, so this world breaks only w2. The free-fall reading ff2 rests on that "
        'clause and changes with it.',
        {'replace': {'w2': 'fG2 = -mu2*(g + 1/10)', 'ff2': 'fG2 = -m2*(g + 1/10)'}}],
 'g': ['NEEDS',
       "W6 ('changing g scales a'), new number here: g = 10 m/s².",
       'W6. Provisional (10 November 2026, P1): g is the number and its free-fall reading. The reading clause has '
       'its own countermodel, CM3: g read as a field strength with μ(B2) = 6 kg (ff2 and peqv2, which rest on g, '
       'changed) gives a = 147/40, checked in the tests.',
       {'replace': {'g': 10}}],
 'peqv1': ['ENTAILED',
           '',
           'W7: μ(B1) = m(B1) follows from the uniform-field weight w1 and g read as the local free-fall '
           'acceleration. Provisional (10 November 2026, P2): that reading is now recorded as the READING ff1 (fG1 '
           '= -m1*g), so the entailment is confirmed. Under a field-strength reading of g, P-EQV fails; that world '
           "is a countermodel to g's reading clause (see g).",
           {'entailed_by': ['w1', 'g', 'ff1']}],
 'peqv2': ['ENTAILED',
           '',
           'W7: μ(B2) = m(B2) follows from the uniform-field weight w2 and g read as the local free-fall '
           'acceleration. Provisional (10 November 2026, P2): that reading is now recorded as the READING ff2 (fG2 '
           '= -m2*g), so the entailment is confirmed. Under a field-strength reading of g, P-EQV fails; that world '
           "is a countermodel to g's reading clause (see g).",
           {'entailed_by': ['w2', 'g', 'ff2']}],
 'admS1': ['REQUIRED',
           '',
           'W8: without admission there is a different account. Check: drop everything resting on admS1.',
           {'drop_dependents': True}],
 'admS2': ['REQUIRED', '', 'W8, as for admS1.', {'drop_dependents': True}],
 'pull1': ['NEEDS',
           "W9 ('angled segments change the ŷ-components'), new number here: the segment above B1 at an angle with "
           "cos θ = 4/5, so the string's ŷ-component on B1 is (4/5)·T1.",
           'W9 (verticality); T ≥ 0 is used only at [25]. Only sum1 is changed; dkin also rests on pull1 and an '
           'angled segment would change it too. Provisional (10 November 2026, P1): verticality is owned by pull1; '
           'the string admission no longer states it.',
           {'replace': {'sum1': 'Fnet1 = fG1 + 4/5*T1'}}],
 'pull2': ['NEEDS',
           'W9, new number here: cos θ = 4/5 above B2, ŷ-component (4/5)·T2.',
           'W9 (verticality). Only sum2 is changed. Provisional (10 November 2026, P1): verticality is owned by '
           'pull2; the string admission no longer states it.',
           {'replace': {'sum2': 'Fnet2 = fG2 + 4/5*T2'}}],
 'Ea': ['NEEDS',
        "W10 ('a heavy chain: the two end forces differ'), new numbers here: hanging chain portions of 1/10 kg "
        "above B1 and 1/5 kg above B2, frictionless contact (E-b kept), negligible arc mass; each segment's top "
        'tension is its end force plus its mass times (g + its acceleration), and the two top tensions are equal.',
        "W10 (via M-EQ). meq rests on Ea. Provisional (10 November 2026, P2): the countermodel is written on E-a's "
        'own relation, with M-EQ, which rests on it, dropped.',
        {'replace': {'Ea': 'T2 + 1/5*(g + a2) - T1 - 1/10*(g + a1) + Ft = 0'}, 'remove': ['meq']}],
 'Eb': ['NEEDS',
        'CM4 (W11): pulley inertia I/r² = 1 kg, so T2 − T1 = 1·a1; the source gives 9a = 2·49/5, a = 98/45. (CM5, '
        'axle friction 0.8 N at the rim, is checked as an extra: 47/20 descending, 51/20 ascending.)',
        'W11, CM4 (CM5 in the extras). meq rests on Eb. Provisional (10 November 2026, P2): the countermodel is '
        "written on E-b's own relation (F_t = −(I/r²)·a1), with M-EQ, which rests on it, dropped.",
        {'replace': {'Eb': 'Ft = -1*a1'}, 'remove': ['meq']}],
 'meq': ['ENTAILED',
         '',
         'No T§10(b) row: M-EQ is replaced by its premise set E-a ∧ E-b (W10, W11). Provisional (10 November 2026, '
         'P2): E-a (T2 − T1 + F_t = 0) and E-b (F_t = 0) now carry relations, so the entailment is confirmed; E-a '
         'alone does not entail it.',
         {'entailed_by': ['Ea', 'Eb']}],
 'Ka': ['NEEDS',
        "W12 ('an elastic cord at a changing stretch: in general a1 + a2 ≠ 0'): the length L accelerates, L'' = "
        "Ldd free, so y1'' + y2'' = −L''.",
        'W12 (via M-KIN). dkin rests on Ka.',
        {'replace': {'dkin': 'y1dd + y2dd = -Ldd'}}],
 'Kb': ['REQUIRED',
        '',
        'W13: slack near t0 gives only an inequality; no countermodel keeping the other rows was found. Check: '
        'drop everything resting on Kb (dkin).',
        {'drop_dependents': True}],
 'Kc': ['NEEDS',
        "W14 ('an axle accelerating at A_P gives a1 + a2 = 2A_P'), A_P free.",
        'W14 (via M-KIN). dkin rests on Kc.',
        {'replace': {'dkin': 'y1dd + y2dd = 2*AP'}}],
 'Kde': ['NEEDS',
         "W15 ('an elastic hook at a changing stretch breaks the coupling'): the hook length h1 above B1's "
         "attachment accelerates, h1'' = h1dd free, so y1'' + y2'' = −h1''.",
         'W15 (rigid attachments). dkin rests on Kde.',
         {'replace': {'dkin': 'y1dd + y2dd = -h1dd'}}],
 'diff': ['REQUIRED',
          '',
          'W15 (differentiability): without it the derivative step cannot run. Check: drop dkin.',
          {'drop_dependents': True}],
 'mkin': ['ENTAILED',
          '',
          'No T§10(b) row: M-KIN is replaced by K-a to K-e (W12-W15) with the vertical segments (W9). mkin is a '
          'relation between functions, recorded as text, so the check cannot be made and the ledger warns.',
          {'entailed_by': []}],
 'comp1': ['NEEDS',
           'CM6 (W16): an unlisted 1 N downward push on B1; the source gives 8a = 98/5 − 1, a = 93/40.',
           'W16, CM6. sum1 rests on comp1.',
           {'replace': {'sum1': 'Fnet1 = fG1 + T1 - 1'}}],
 'haze1': ['NEEDS',
           "CM6 numbers (W16) as an unkeyed omitted aggregate: H(B1) = −1 N, entered in B1's sum.",
           "W16. The recorded sum1 has no haze term (C-FS 'exact, no haze term'), so haze1's value enters no "
           'relation; the check adds the term to sum1 (which rests on haze1) and changes the value.',
           {'replace': {'sum1': 'Fnet1 = fG1 + T1 + haze1', 'haze1': -1}}],
 'comp2': ['NEEDS',
           'W16, computed in the example (not in the source): an unlisted 1 N downward push on B2; the example '
           'gives 8a = 98/5 + 1, a = 103/40.',
           'W16. sum2 rests on comp2.',
           {'replace': {'sum2': 'Fnet2 = fG2 + T2 - 1'}}],
 'haze2': ['NEEDS',
           "W16, as comp2 but as an unkeyed aggregate: H(B2) = −1 N, entered in B2's sum.",
           'W16. As for haze1: the recorded sum2 has no haze term.',
           {'replace': {'sum2': 'Fnet2 = fG2 + T2 + haze2', 'haze2': -1}}],
 'persist': ['NEEDS',
             "W17, written within the recorded provenance: persistence fails at [15], B2's gravity member is "
             "re-identified with i_G1 (the merge C-ID guards against), so B2's sum reads Fnet2 = fG1 + T2.",
             "W17. The source's own countermodel (B2's mass put into B1's account) changes e8rel1 and peqv1, which "
             'the recorded provenance does not link to persist: the re-deliveries of m(Bk) cannot cite persist, '
             'because a DELIVER takes no uses. A recording gap, not a physics one.',
             {'replace': {'sum2': 'Fnet2 = fG1 + T2'}}],
 'axis': ['USES',
          '',
          'W18: reversing the axis and the signs together leaves p physically unchanged. Check: the trajectory '
          "coordinates y1, y2 measured downward, with the readings translated (a_k = −y_k''). The check exercises "
          "the orientation of the trajectory coordinates (J's y_k), not W18 itself: p's numerals are written in "
          'the axis, so a full reversal changes the components. axis is pruned by kind (convention) whatever its '
          'status.',
          {'replace': {'rd1': 'a1 = -y1dd', 'rd2': 'a2 = -y2dd'}}],
 'd3bind': ['USES',
            '',
            'No T§10(b) row ([7] D3 := |f(i_S1 → B1)|). Proposed: USES, a recorded choice of end: binding D3 at '
            "B2's end (T = T2) leaves p unchanged under M-EQ. Provisional (10 November 2026, P3): a normalization "
            'states the question, so it is pruned by kind whatever its status.',
            {'replace': {'t9': 'T = T2'}}],
 'J': ['REQUIRED',
       '',
       "No T§10(b) row of its own; its content ('an open J ∋ t0', trajectories over J) is inside W13 and W15. "
       'Proposed: REQUIRED, the interval premise under the instant result: without trajectories on an open J '
       "around t0 the K12/E7 value y_k''(t0) and the differentiated M-KIN do not apply.",
       {'drop_dependents': True}]}

MOUNT_STATUSES = {'persist': ['NEEDS',
             "Persistence fails at [15]: B2's gravity member is re-identified with i_G1 (the merge C-ID guards "
             "against), so B2's sum reads f(i_G1 → B1): Fnet2 = fG1 + T2. W17 (structural). The source's own W17 "
             "countermodel (B2's mass put into B1's account) gives refutes p: fUm = -98 (was -147/2) but changes "
             'relations (peqv1, e8rel1) that the recorded provenance does not link to persist.',
             'W17; T§10(b) status for p: NEEDS (structural)',
             {'replace': {'sum2': 'Fnet2 = fG1 + T2'}}],
 'pp1': ['REQUIRED',
         'W1: B1 is not a material object represented by a point-particle, so E8, the [22] reading and the '
         'attachment coupling do not apply to it (e8rel1, dkin, rd1 dropped).',
         'W1; T§10(b) status for p: REQUIRED',
         {'drop_dependents': True}],
 'transl1': ['NEEDS',
             'W2: B1 rocks about a horizontal axis with its centre of mass offset from the attachment, so its '
             "representative's ŷ-acceleration exceeds the attachment point's by 1/2 m/s² at t0 (rd1: a1 = y1dd + "
             '1/2); M-KIN still constrains the attachment points.',
             'W2; T§10(b) status for p: NEEDS',
             {'replace': {'rd1': 'a1 = y1dd + 1/2'}}],
 'm1': ['NEEDS',
        'CM1 (W3) carried to mount: m(B1) = 4 kg.',
        'W3; T§10(b) status for p: NEEDS',
        {'replace': {'m1': 4}}],
 'rin': ['NEEDS',
         'CM2 (W4) carried to mount: the support, and R with it, is in a lift accelerating upward at 1 m/s², so '
         "each block's E8 acceleration is its R-acceleration plus 1 m/s²; the pulley, at rest in R, then "
         'accelerates at 1 m/s², so with mass mP = 1 kg (Q4 gives it mass; the value is chosen here) its net force '
         'is 1 N (Q5 rests on rin). Keeping Q5 unchanged (as if the pulley were massless) gives refutes p: fUm = '
         '-81 (was -147/2).',
         'W4; T§10(b) status for p: NEEDS',
         {'replace': {'e8rel1': 'a1 = Fnet1/m1 - 1', 'e8rel2': 'a2 = Fnet2/m2 - 1', 'Q5': 'fPp + fU = mP*1'},
          'values': {'mP': 1}}],
 'admG1': ['NEEDS',
           "W5 ('drop either interaction'): gravity on B1 is not admitted, so B1's sum has only its string member, "
           'Fnet1 = T1.',
           'W5; T§10(b) status for p: NEEDS',
           {'replace': {'sum1': 'Fnet1 = T1'}}],
 'admS1': ['REQUIRED',
           'W8: without the string admission at B1 there is a different account: sum1, sum2, meq, t9, dkin, rd1, '
           'pairS1, pairS2, Q1 dropped.',
           'W8; T§10(b) status for p: REQUIRED; taut clause ENTAILED by W13',
           {'drop_dependents': True}],
 'comp1': ['NEEDS',
           'CM6 (W16) carried to mount: an unlisted 1 N downward push on B1.',
           'W16; T§10(b) status for p: NEEDS',
           {'replace': {'sum1': 'Fnet1 = fG1 + T1 - 1'}}],
 'haze1': ['NEEDS',
           "W16: the unkeyed omitted aggregate on B1 is H(B1) = -1 N, and B1's sum carries it. Changing the value "
           'alone gives p still follows: no recorded relation mentions haze1.',
           'W16; T§10(b) status for p: NEEDS',
           {'replace': {'haze1': -1, 'sum1': 'Fnet1 = fG1 + T1 + haze1'}}],
 'd3bind': ['USES',
            "D3 := |f(i_S1 → B1)| fixes which end 'the tension' names; mount uses T1 and T2, not T. Dropping what "
            'rests on it (t9) leaves the mount load: p still follows. New here (no T§10(b) row).',
            'no T§10(b) row Provisional (10 November 2026, P3): a normalization states the question, so it is '
            'pruned by kind whatever its status.',
            {'drop_dependents': True}],
 'g': ['NEEDS',
       'W6 carried to mount: g = 10 m/s² scales the tensions.',
       'W6; T§10(b) status for p: NEEDS Provisional (10 November 2026, P1): g is the number and its free-fall '
       'reading. The reading clause has its own countermodel, CM3: g read as a field strength with μ(B2) = 6 kg '
       '(ff2 and peqv2, which rest on g, changed) gives a = 147/40, checked in the tests.',
       {'replace': {'g': 10}}],
 'w1': ['NEEDS',
        "W5 ('a g that differs between the blocks'): the field at B1 is g + 1/5 m/s².",
        "W5; T§10(b) status for p: NEEDS Provisional (10 November 2026, P1): the 'same g / uniform field' clause "
        'is owned by w1, so this world breaks only w1. The free-fall reading ff1 rests on that clause and changes '
        'with it.',
        {'replace': {'w1': 'fG1 = -mu1*(g + 1/5)', 'ff1': 'fG1 = -m1*(g + 1/5)'}}],
 'peqv1': ['ENTAILED',
           '',
           'W7: μ(B1) = m(B1) follows from the uniform-field weight w1 and g read as the local free-fall '
           'acceleration. Provisional (10 November 2026, P2): that reading is now recorded as the READING ff1 (fG1 '
           '= -m1*g), so the entailment is confirmed. Under a field-strength reading of g, P-EQV fails; that world '
           "is a countermodel to g's reading clause (see g).",
           {'entailed_by': ['w1', 'g', 'ff1']}],
 'pull1': ['NEEDS',
           'W9 written out: the segment above B1 makes angle θ with the vertical (cos θ = 4/5), the string runs '
           "over a smooth peg (E-b's frictionless-contact option, so no wrap term), B1 is momentarily at rest at "
           "t0. B1's ŷ sum is Fnet1 = fG1 + (4/5)T1; E8 on x̂ gives 3·a1x = (3/5)T1; inextensibility gives "
           "(3/5)a1x + (4/5)y1'' + y2'' = 0; σ's counterpart at end 1 has ŷ-component -(4/5)T1 (T1 is the tension, "
           'as M-EQ and D3 use it).',
           'W9; T§10(b) status for p: NEEDS (verticality) Provisional (10 November 2026, P1): verticality is owned '
           'by pull1; the string admission no longer states it.',
           {'replace': {'sum1': 'Fnet1 = fG1 + 4/5*T1',
                        'dkin': '3/5*a1x + 4/5*y1dd + y2dd = 0',
                        'pairS1': 'cS1 = -4/5*T1'},
            'add': ['3*a1x = 3/5*T1']}],
 'pp2': ['REQUIRED',
         'W1: B2 is not a material object represented by a point-particle (e8rel2, dkin, rd2 dropped).',
         'W1; T§10(b) status for p: REQUIRED',
         {'drop_dependents': True}],
 'transl2': ['NEEDS',
             "W2 for B2: a rocking B2 whose representative's ŷ-acceleration exceeds the attachment point's by 1/2 "
             'm/s².',
             'W2; T§10(b) status for p: NEEDS',
             {'replace': {'rd2': 'a2 = y2dd + 1/2'}}],
 'm2': ['NEEDS',
        'W3 (computed for p in the example, not in the source) carried to mount: m(B2) = 6 kg.',
        'W3; T§10(b) status for p: NEEDS',
        {'replace': {'m2': 6}}],
 'admG2': ['NEEDS',
           'W5: gravity on B2 is not admitted; Fnet2 = T2.',
           'W5; T§10(b) status for p: NEEDS',
           {'replace': {'sum2': 'Fnet2 = T2'}}],
 'admS2': ['REQUIRED',
           'W8: without the string admission at B2: sum2, meq, t9, dkin, rd2, pairS1, pairS2, Q1 dropped.',
           'W8; T§10(b) status for p: REQUIRED; taut clause ENTAILED by W13',
           {'drop_dependents': True}],
 'comp2': ['NEEDS',
           'W16 (computed for p in the example) carried to mount: an unlisted 1 N downward push on B2.',
           'W16; T§10(b) status for p: NEEDS',
           {'replace': {'sum2': 'Fnet2 = fG2 + T2 - 1'}}],
 'haze2': ['NEEDS',
           "W16: H(B2) = -1 N and B2's sum carries it.",
           'W16; T§10(b) status for p: NEEDS',
           {'replace': {'haze2': -1, 'sum2': 'Fnet2 = fG2 + T2 + haze2'}}],
 'w2': ['NEEDS',
        "W5 ('a g that differs between the blocks'): the field at B2 is g + 1/5 m/s².",
        "W5; T§10(b) status for p: NEEDS Provisional (10 November 2026, P1): the 'same g / uniform field' clause "
        'is owned by w2, so this world breaks only w2. The free-fall reading ff2 rests on that clause and changes '
        'with it.',
        {'replace': {'w2': 'fG2 = -mu2*(g + 1/5)', 'ff2': 'fG2 = -m2*(g + 1/5)'}}],
 'peqv2': ['ENTAILED',
           '',
           'W7: μ(B2) = m(B2) follows from the uniform-field weight w2 and g read as the local free-fall '
           'acceleration. Provisional (10 November 2026, P2): that reading is now recorded as the READING ff2 (fG2 '
           '= -m2*g), so the entailment is confirmed. Under a field-strength reading of g, P-EQV fails; that world '
           "is a countermodel to g's reading clause (see g).",
           {'entailed_by': ['w2', 'g', 'ff2']}],
 'pull2': ['NEEDS',
           'W9 for B2, as pull1 (segment above B2 at cos θ = 4/5, smooth peg, B2 momentarily at rest).',
           'W9; T§10(b) status for p: NEEDS (verticality) Provisional (10 November 2026, P1): verticality is owned '
           'by pull2; the string admission no longer states it.',
           {'replace': {'sum2': 'Fnet2 = fG2 + 4/5*T2',
                        'dkin': 'y1dd + 4/5*y2dd = 3/5*a2x',
                        'pairS2': 'cS2 = -4/5*T2'},
            'add': ['5*a2x = -3/5*T2']}],
 'Ea': ['NEEDS',
        'W10 carried to mount: a string whose inertia is not negligible (λL = 1/2 kg) but whose weight is '
        'neglected, as Q4 does for the pulley, hanging with equal segments and released from rest at t0: the end '
        "forces differ, T2 = T1 + (1/2 kg)·a1, while σ's ŷ momentum change is zero at that instant, so Q1 and Q6 "
        'still hold.',
        'W10; T§10(b) status for p: NEEDS (via M-EQ) Provisional (10 November 2026, P2): the countermodel is '
        "written on E-a's own relation, with M-EQ, which rests on it, dropped.",
        {'replace': {'Ea': 'T2 - T1 - 1/2*a1 + Ft = 0'}, 'remove': ['meq']}],
 'Eb': ['NEEDS',
        'CM4 (W11) carried to mount: I/r² = 1 kg gives T2 = T1 + 1·a1; the balanced pulley turns about its fixed '
        'axle, so Q5 still holds. CM5 (descending) gives refutes p: fUm = -737/10 (was -147/2).',
        'W11; T§10(b) status for p: NEEDS (via M-EQ) Provisional (10 November 2026, P2): the countermodel is '
        "written on E-b's own relation (F_t = −(I/r²)·a1), with M-EQ, which rests on it, dropped.",
        {'replace': {'Eb': 'Ft = -1*a1'}, 'remove': ['meq']}],
 'meq': ['ENTAILED',
         '',
         'No T§10(b) row: M-EQ is replaced by its premise set E-a ∧ E-b (W10, W11). Provisional (10 November 2026, '
         'P2): E-a (T2 − T1 + F_t = 0) and E-b (F_t = 0) now carry relations, so the entailment is confirmed; E-a '
         'alone does not entail it.',
         {'entailed_by': ['Ea', 'Eb']}],
 'J': ['REQUIRED',
       'Without an open interval J ∋ t0 carrying the trajectories, K12 and E7 have nothing to differentiate (dkin, '
       'rd1, rd2 dropped). New here (no T§10(b) row).',
       'no T§10(b) row',
       {'drop_dependents': True}],
 'Ka': ['NEEDS',
        "W12 carried to mount: an elastic cord whose stretch accelerates at L'' = 1/2 m/s² at t0, so y1'' + y2'' = "
        '-1/2.',
        'W12; T§10(b) status for p: NEEDS (via M-KIN)',
        {'replace': {'dkin': 'y1dd + y2dd = -1/2'}}],
 'Kb': ['REQUIRED',
        'W13: slack near t0 gives only an inequality (dkin dropped).',
        'W13; T§10(b) status for p: REQUIRED (via M-KIN)',
        {'drop_dependents': True}],
 'Kc': ['NEEDS',
        'W14 carried to mount: the axle accelerates upward at A_P = 1/2 m/s² (the pulley rides a carriage; the '
        "support and R stay as in [5]), so M-KIN gives y1'' + y2'' = 2A_P = 1, and the pulley (mass mP = 1 kg, "
        'chosen here) has net force mP·A_P (Q5 rests on Kc).',
        'W14; T§10(b) status for p: NEEDS (via M-KIN)',
        {'replace': {'dkin': 'y1dd + y2dd = 1', 'Q5': 'fPp + fU = mP*1/2'}, 'values': {'mP': 1}}],
 'Kde': ['NEEDS',
         "W15 (rigid attachments) carried to mount: an elastic hook between σ's end 2 and B2 whose stretch "
         "accelerates at 1/5 m/s², so y1'' + y2'' = -1/5.",
         'W15; T§10(b) status for p: NEEDS (rigid attachments)',
         {'replace': {'dkin': 'y1dd + y2dd = -1/5'}}],
 'mkin': ['ENTAILED',
          'M-KIN is replaced by K-a, K-b, K-c, K-d/K-e, J and the vertical segments (W9), as for p. mkin carries '
          'no relation (a relation between functions, recorded as text): cannot check: mkin carries no relation or '
          'value.',
          'no T§10(b) row: replaced by W12-W15 with W9',
          {'entailed_by': []}],
 'diff': ['REQUIRED',
          'W15 (differentiability): without twice-differentiable y1, y2 the differentiation at [21] cannot run '
          '(dkin dropped).',
          'W15; T§10(b) status for p: REQUIRED (differentiability)',
          {'drop_dependents': True}],
 'bn': ['NEEDS',
        'Both string attachments are non-Newtonian by the same amount: each counterpart on σ falls 1/2 N short of '
        "the negation of the force on its block (e.g. momentum carried off by a third party). The string's own end "
        'pulls stay equal, so M-EQ still holds and the block accounts are unchanged; Q1 then gives a smaller push '
        'from the pulley. New here (W19 is USES for p).',
        'W19; T§10(b) status for p: USES (matters only in T§7)',
        {'replace': {'pairS1': 'cS1 = -T1 + 1/2', 'pairS2': 'cS2 = -T2 + 1/2'}}],
 'sigma1': ['USES',
            'σ is two participants, the end-1 piece and the end-2 piece, each a massless link on the pulley: each '
            'piece balances separately (cS1 + fP1s = 0, cS2 + fP2s = 0) and the pulley receives their sum (fPs = '
            'fP1s + fP2s). New here (W19 is USES for p).',
            'W19; T§10(b) status for p: USES (matters only in T§7)',
            {'replace': {'Q1': 'cS1 + fP1s = 0'}, 'add': ['cS2 + fP2s = 0', 'fPs = fP1s + fP2s']}],
 'Q2': ['REQUIRED',
        "No addressed string–pulley interaction i_P: σ's and the pulley's balances have no member for the contact "
        '(Q1, Q5, pairP, pairU dropped). New here (W20 gives no countermodel).',
        'W20; T§10(b) status for p: Not used for p',
        {'drop_dependents': True}],
 'Q3': ['REQUIRED',
        'No addressed pulley–mount interaction i_U: nothing carries the load to the mount (Q1, Q5, pairP, pairU '
        'dropped). New here.',
        'W20; T§10(b) status for p: Not used for p',
        {'drop_dependents': True}],
 'Q4': ['NEEDS',
        "Without Q4 the pulley's weight counts: its set gains a gravity member fGP = -mP·g, so its balance reads "
        'fPp + fU + fGP = 0. For mP = 1 kg the checker gives refutes p: fUm = -833/10 (was -147/2): at mP = 1 kg '
        'the load exceeds 147/2 N by 49/5 N = mP·g: True; at mP = 2 kg the load exceeds 147/2 N by 98/5 N = mP·g: '
        "True. Reproduces T§7.3 'Without Q4, the mount load is 147/2 N plus the pulley's weight'. With mP left "
        'open: p does not follow: fUm left open. The mass values are new here.',
        'W20; T§10(b) status for p: Not used for p',
        {'replace': {'Q5': 'fPp + fU + fGP = 0'}, 'add': ['fGP = -mP*g'], 'values': {'mP': 1}}],
 'Q6': ['NEEDS',
        "A light rod presses σ onto the top of the pulley with 1 N: a third, normal contact on σ, so σ's set is "
        "not exactly {i_S1, i_S2, i_P}; it is normal to σ, so M-EQ holds. σ's balance over its true set reads cS1 "
        '+ cS2 + fPs - 1 = 0. New here.',
        'W20; T§10(b) status for p: Not used for p',
        {'replace': {'Q1': 'cS1 + cS2 + fPs - 1 = 0'}}],
 'Q7': ['NEEDS',
        "i_U is not Newtonian: the mount's counterpart is 1/2 N short of the negation of f(i_U → pulley). If "
        'instead i_P or i_U is not binary, C-PAIR gives no counterpart: p does not follow: fUm left open. New '
        'here.',
        'W20; T§10(b) status for p: Not used for p',
        {'replace': {'pairU': 'fUm = -fU + 1/2'}}],
 'Q1': ['ENTAILED',
        '',
        'T§7.3 (Q1), the massless-link rule. Provisional (10 November 2026, P4): ENTAILED by E-a, like M-EQ: '
        "negligible mass makes σ's net force zero. The check cannot confirm it, and the ledger warns: E-a's "
        'recorded relation is the along-string form of that rule (T2 − T1 + F_t = 0), and Q1 is its ŷ form over '
        "Q6's set; one premise carries one relation. D has no force-balance entry for σ (E10 excludes it, T§7.3 "
        "OPEN). Written as a world, σ's ŷ net force of −1 N gives a mount load of −145/2.",
        {'entailed_by': []}],
 'Q5': ['ENTAILED',
        "Q5 is the source's own consequence of K-c (axle at rest, in W4's inertial R), Q4 (positive mass) and Q6 "
        "(the pulley's set) through E9 (T§7.3). The recorder cannot check it: Kc, rin, Q4, Q6 and E9 carry no "
        'relation, so the other relations leave fU open: not entailed by the other premises. Its relation is where '
        'the Kc, rin and Q4 countermodels act; replacing it alone (net force 1 N) gives refutes p: fUm = -149/2 '
        '(was -147/2).',
        'W20; T§10(b) status for p: Not used for p',
        {'entailed_by': []}],
 'axis': ['USES',
          'W18: a convention; the check keeps it: p still follows. Reversing ŷ (weights become +μg; every other '
          'recorded relation is homogeneous in the components) gives refutes p: fUm = 147/2 (was -147/2): the same '
          'downward load quoted on the reversed axis, which the checker reads as a refutation because it compares '
          'components.',
          'W18; T§10(b) status for p: USES',
          {}],
 'cquote': ['USES',
            "W18: quote each interaction's vector on its other participant instead (σ for i_S1, i_S2; the pulley "
            'for i_P; the mount for i_U), the first participant receiving the negation. The pair relations are the '
            'same equations.',
            'W18; T§10(b) status for p: USES',
            {'replace': {'pairS1': 'T1 = -cS1',
                         'pairS2': 'T2 = -cS2',
                         'pairP': 'fPs = -fPp',
                         'pairU': 'fU = -fUm'}}]}

# fmt: on

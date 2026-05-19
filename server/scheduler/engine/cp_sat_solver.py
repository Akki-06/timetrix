"""
CP-SAT timetable solver — Google OR-Tools CP-SAT backend.

Replaces the multi-phase greedy engine with a globally-optimal constraint
satisfaction model.  The greedy engine in runner.py is kept as a fallback
for the (rare) case where CP-SAT times out or encounters an error.

Model summary
─────────────
Variables
  t_var[(o_id, day, slot, room_id)]    theory offering → (day, slot, room)
  l_var[(o_id, day, s1, room_id)]      lab offering    → (day, pair_start, room)
                                        (implies both s1 and s2 are occupied)

Hard constraints
  C1  Coverage         each offering scheduled exactly weekly_load times
  C2  Room uniqueness  ≤ 1 offering per (room, day, slot)
  C3  Faculty clash    ≤ 1 offering per (faculty, day, slot)
  C4  Group clash      ≤ 1 offering per (group, day, slot)
                       — PE options in the same elective group are allowed
                         to all land on the same slot (students choose one)
  C5  Faculty daily    faculty daily load ≤ max_daily
  C6  Faculty weekly   faculty weekly load ≤ max_weekly
  C7  PE same slot     all options in an elective group share one (day, slot)
  C8  Combined same    all offerings with same combined_token share (day,slot,room)
  C9  One course/day   a section has ≤ 1 session of the same course per day

Objective
  Maximise sum of ML suitability scores for every scheduled (offering, slot, room).
  Scores are integer-scaled (×1000) because CP-SAT requires integer coefficients.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Optional

log = logging.getLogger(__name__)

SCORE_SCALE = 1000   # float → integer scaling for CP-SAT objective


class CPSATScheduler:
    """
    Wraps the OR-Tools CP-SAT model.  Call solve() once per scheduling run.
    """

    def __init__(self, time_limit_seconds: int = 120):
        self.time_limit = time_limit_seconds

    # ─────────────────────────────────────────────────────────────────────────

    def solve(
        self,
        offerings,          # list[CourseOffering]  (faculty pre-assigned)
        slot_map: dict,     # {(day, slot_number): TimeSlot}
        theory_rooms: list, # [Room] sorted by program-affinity
        lab_rooms: list,    # [Room]
        faculty_meta: dict, # {fac_id: {max_weekly, max_daily, avail_days, avail_slots}}
        ml_scorer,          # MLScorer instance
        pre_blocked: dict,  # {(day, slot): set[room_id]} from cross-term allocations
        valid_pairs: list,  # [(s1, s2)] valid consecutive slot pairs for labs
        days: list,         # active day strings e.g. ["MON",.."FRI"]
        config,             # SchedulerConfig
        combined_to_ind: dict,  # {combined_group_id: [individual_group_ids]}
    ):
        """
        Returns
        -------
        (pending_saves, unscheduled_offerings)
          pending_saves            list[dict]   ready for runner._save()
          unscheduled_offerings    list[CourseOffering]

        Returns (None, None) when no feasible solution is found — caller must
        fall back to the greedy engine.
        """
        try:
            from ortools.sat.python import cp_model
        except ImportError:
            log.warning("CP-SAT: ortools not installed — greedy fallback.")
            return None, None

        model = cp_model.CpModel()

        # ── categorise ───────────────────────────────────────────────────────
        def _is_lab(o):
            return bool(o.course.requires_lab_room or o.course.requires_consecutive_slots)

        lab_offs    = [o for o in offerings if     _is_lab(o)
                       and (o.weekly_load or o.course.min_weekly_lectures) > 0]
        theory_offs = [o for o in offerings if not _is_lab(o)
                       and (o.weekly_load or o.course.min_weekly_lectures) > 0]

        all_ds = list(slot_map.keys())      # [(day, slot_number), ...]
        theory_room_ids = {r.id for r in theory_rooms}

        # ── ROOM METADATA LOOKUP ─────────────────────────────────────────────
        # Maps room_id → (room_number, room_type, capacity) so the objective
        # scoring uses the real room number (e.g. "1010") that GNN embeddings
        # are keyed on, not the integer primary key.
        room_meta_map: dict[int, tuple] = {
            r.id: (r.room_number, r.room_type, r.capacity)
            for r in theory_rooms + lab_rooms
        }

        # ── BUILD THEORY VARIABLES ────────────────────────────────────────────
        t_var: dict = {}
        # index structures (populated while building variables)
        t_by_off  = defaultdict(list)   # o_id  → [(day,slot,rid,var)]
        t_by_rds  = defaultdict(list)   # (rid,day,slot) → [(o_id,var)]
        t_by_fds  = defaultdict(list)   # (fac_id,day,slot) → [(o_id,var)]
        t_by_gds  = defaultdict(list)   # (grp_id,day,slot) → [(o_id,var)]

        for o in theory_offs:
            sg     = o.student_group
            fac_id = o.assigned_faculty_id if o.assigned_faculty else None
            meta   = faculty_meta.get(fac_id, {}) if fac_id else {}

            for day, slot in all_ds:
                # Section working-days filter
                if sg.working_days and day not in sg.working_days:
                    continue
                # Faculty availability filter
                if fac_id:
                    if day not in meta.get("avail_days", set(days)):
                        continue
                    if slot not in meta.get("avail_slots", {}).get(day, set(range(1, 10))):
                        continue

                for r in theory_rooms:
                    if config.enforce_room_type and r.room_type != "THEORY":
                        continue
                    if r.capacity < sg.strength:
                        continue
                    if r.id in pre_blocked.get((day, slot), set()):
                        continue

                    v = model.NewBoolVar(f"t_{o.id}_{day}_{slot}_{r.id}")
                    t_var[(o.id, day, slot, r.id)] = v
                    t_by_off[o.id].append((day, slot, r.id, v))
                    t_by_rds[(r.id, day, slot)].append((o.id, v))
                    if fac_id:
                        t_by_fds[(fac_id, day, slot)].append((o.id, v))
                    t_by_gds[(sg.id, day, slot)].append((o.id, v))

        # ── BUILD LAB VARIABLES ───────────────────────────────────────────────
        l_var: dict = {}
        l_by_off  = defaultdict(list)   # o_id → [(day,s1,s2,rid,var)]
        l_by_rds  = defaultdict(list)   # (rid,day,slot) → [(o_id,s1,var)]
        l_by_fds  = defaultdict(list)   # (fac_id,day,slot) → [(o_id,s1,var)]
        l_by_gds  = defaultdict(list)   # (grp_id,day,slot) → [(o_id,s1,var)]

        for o in lab_offs:
            use_lab = o.course.requires_lab_room
            pool    = lab_rooms if use_lab else theory_rooms
            sg      = o.student_group
            fac_id  = o.assigned_faculty_id if o.assigned_faculty else None
            meta    = faculty_meta.get(fac_id, {}) if fac_id else {}

            for day in days:
                if sg.working_days and day not in sg.working_days:
                    continue
                if fac_id and day not in meta.get("avail_days", set(days)):
                    continue

                for s1, s2 in valid_pairs:
                    if (day, s1) not in slot_map or (day, s2) not in slot_map:
                        continue
                    if fac_id:
                        avail = meta.get("avail_slots", {}).get(day, set(range(1, 10)))
                        if s1 not in avail or s2 not in avail:
                            continue

                    for r in pool:
                        if config.enforce_room_type:
                            exp = "LAB" if use_lab else "THEORY"
                            if r.room_type != exp:
                                continue
                        if r.capacity < sg.strength:
                            continue
                        if (r.id in pre_blocked.get((day, s1), set()) or
                                r.id in pre_blocked.get((day, s2), set())):
                            continue

                        v = model.NewBoolVar(f"l_{o.id}_{day}_{s1}_{r.id}")
                        l_var[(o.id, day, s1, r.id)] = v
                        l_by_off[o.id].append((day, s1, s2, r.id, v))
                        for sl in (s1, s2):
                            l_by_rds[(r.id, day, sl)].append((o.id, s1, v))
                            if fac_id:
                                l_by_fds[(fac_id, day, sl)].append((o.id, s1, v))
                            l_by_gds[(sg.id, day, sl)].append((o.id, s1, v))

        log.info(
            f"CP-SAT model: {len(t_var)} theory vars, {len(l_var)} lab vars, "
            f"{len(theory_offs)} theory offs, {len(lab_offs)} lab offs"
        )

        if not t_var and not l_var:
            log.warning("CP-SAT: no valid variables — greedy fallback.")
            return None, None

        # ── HARD CONSTRAINTS ──────────────────────────────────────────────────

        # C1: Coverage
        unplaceable = []
        for o in theory_offs:
            weekly = o.weekly_load or o.course.min_weekly_lectures
            vs = [v for _, _, _, v in t_by_off[o.id]]
            if not vs:
                log.warning(f"  CP-SAT C1: no variables for {o.course.code} ({o.student_group.name})")
                unplaceable.append(o)
                continue
            model.Add(sum(vs) == weekly)

        for o in lab_offs:
            weekly = o.weekly_load or o.course.min_weekly_lectures
            vs = [v for _, _, _, _, v in l_by_off[o.id]]
            if not vs:
                log.warning(f"  CP-SAT C1: no lab variables for {o.course.code}")
                unplaceable.append(o)
                continue
            model.Add(sum(vs) == weekly)

        # C2: Room uniqueness — ≤ 1 offering per (room, day, slot)
        all_rds = set(t_by_rds.keys()) | set(l_by_rds.keys())
        for key in all_rds:
            t_vs = [v for _, v in t_by_rds.get(key, [])]
            l_vs = [v for _, _, v in l_by_rds.get(key, [])]
            combined = t_vs + l_vs
            if len(combined) > 1:
                model.Add(sum(combined) <= 1)

        # C3: Faculty clash — ≤ 1 offering per (faculty, day, slot)
        all_fds = set(t_by_fds.keys()) | set(l_by_fds.keys())
        for key in all_fds:
            t_vs = [v for _, v in t_by_fds.get(key, [])]
            l_vs = [v for _, _, v in l_by_fds.get(key, [])]
            combined = t_vs + l_vs
            if len(combined) > 1:
                model.Add(sum(combined) <= 1)

        # C4: Group clash — ≤ 1 offering per (group, day, slot)
        # PE options sharing a slot for the same group are handled via C7 (PE same slot):
        # those options are excluded from the standard group clash check.
        pe_offering_ids = set()
        pe_groups_raw: dict = defaultdict(list)   # elective_slot_group → [offering]
        for o in theory_offs:
            if o.elective_slot_group and o.course.course_type == "PE":
                pe_groups_raw[o.elective_slot_group].append(o)
                pe_offering_ids.add(o.id)
        # Ungrouped PE offerings: auto-group by student_group
        pe_by_sg: dict = defaultdict(list)
        for o in theory_offs:
            if o.course.course_type == "PE" and o.id not in pe_offering_ids:
                pe_by_sg[o.student_group_id].append(o)
        for sg_id, offs in pe_by_sg.items():
            if len(offs) > 1:
                auto_key = f"PE_AUTO_{sg_id}"
                pe_groups_raw[auto_key].extend(offs)
                for o in offs:
                    pe_offering_ids.add(o.id)

        all_gds = set(t_by_gds.keys()) | set(l_by_gds.keys())
        for (grp_id, day, slot) in all_gds:
            t_entries = t_by_gds.get((grp_id, day, slot), [])
            l_entries = l_by_gds.get((grp_id, day, slot), [])
            # Separate PE and non-PE
            non_pe = [v for o_id, v in t_entries if o_id not in pe_offering_ids]
            non_pe += [v for o_id, _, v in l_entries]
            pe_vs  = [v for o_id, v in t_entries if o_id in pe_offering_ids]

            # Non-PE: ≤ 1
            if len(non_pe) > 1:
                model.Add(sum(non_pe) <= 1)

            # For PE options at this slot we add an indicator; the coupling
            # between PE options and group-busy is enforced in C7 below.
            # We only need: non_pe + (1 if any PE option active here) ≤ 1
            if non_pe and pe_vs:
                # If any PE option is active at this slot, non_pe must be 0
                pe_active_here = model.NewBoolVar(f"pe_active_{grp_id}_{day}_{slot}")
                model.AddMaxEquality(pe_active_here, pe_vs)
                model.Add(sum(non_pe) + pe_active_here <= 1)

        # C5 & C6: Faculty daily / weekly load
        fac_ids_in_model = {
            o.assigned_faculty_id
            for o in theory_offs + lab_offs
            if o.assigned_faculty_id
        }
        for fac_id in fac_ids_in_model:
            meta       = faculty_meta.get(fac_id, {})
            max_daily  = meta.get("max_daily", 4)
            max_weekly = meta.get("max_weekly", 18)

            week_vs = []
            for day in days:
                day_vs = []
                for slot in range(1, 10):
                    t_vs = [v for _, v in t_by_fds.get((fac_id, day, slot), [])]
                    l_vs = [v for _, _, v in l_by_fds.get((fac_id, day, slot), [])]
                    day_vs.extend(t_vs + l_vs)
                week_vs.extend(day_vs)
                if day_vs:
                    model.Add(sum(day_vs) <= max_daily)
            if week_vs:
                model.Add(sum(week_vs) <= max_weekly)

        # C7: PE same slot — all options in a group share one (day, slot)
        for gkey, pe_offs in pe_groups_raw.items():
            if len(pe_offs) <= 1:
                continue
            weekly = max(o.weekly_load or o.course.min_weekly_lectures for o in pe_offs)

            # shared active variable per (day, slot)
            pe_slot_active: dict = {}
            for day, slot in all_ds:
                sv = model.NewBoolVar(f"pe_{gkey}_{day}_{slot}")
                pe_slot_active[(day, slot)] = sv

            # Total sessions == weekly
            model.Add(sum(pe_slot_active.values()) == weekly)

            # Each option is scheduled iff the shared slot is active
            for o in pe_offs:
                for day, slot in all_ds:
                    vs_here = [v for d, s, rid, v in t_by_off[o.id] if d == day and s == slot]
                    sv = pe_slot_active[(day, slot)]
                    if vs_here:
                        model.Add(sum(vs_here) == sv)
                    else:
                        # This option has no variables here — force sv=0 for it
                        # (other options in the group may still have variables here;
                        #  if they can't be scheduled here, the model handles it)
                        model.Add(sv == 0)

            # All options need DISTINCT rooms at the chosen slot
            # Ensured automatically by C2 (room uniqueness).

        # C8: Combined sections — same (day, slot, room)
        combined_groups: dict = defaultdict(list)
        for o in theory_offs:
            if o.combined_token:
                combined_groups[(o.course_id, o.combined_token)].append(o)

        for (_, token), unit in combined_groups.items():
            if len(unit) <= 1:
                continue
            # For every (day, slot, room) triple the first offering's variable
            # must equal every other offering's variable.
            all_dsrid = {
                (d, s, rid)
                for o in unit
                for d, s, rid, _ in t_by_off[o.id]
            }
            for d, s, rid in all_dsrid:
                vs = [t_var.get((o.id, d, s, rid)) for o in unit]
                vs = [v for v in vs if v is not None]
                if len(vs) > 1:
                    for other_v in vs[1:]:
                        model.Add(vs[0] == other_v)

        # C9: ≤ 1 session of the same course per (group, day)
        for o in theory_offs:
            for day in days:
                vs_day = [v for d, s, rid, v in t_by_off[o.id] if d == day]
                if len(vs_day) > 1:
                    model.Add(sum(vs_day) <= 1)

        # ── OBJECTIVE: maximise ML suitability scores ─────────────────────────
        score_keys  = []   # list of BoolVar
        score_vals  = []   # list of int (scaled)

        # Batch-score all theory (offering, day, slot) → room combinations
        batch_params = []
        batch_vars   = []

        for o in theory_offs:
            if not o.assigned_faculty:
                continue
            fac  = o.assigned_faculty
            meta = faculty_meta.get(fac.id, {})
            sg   = o.student_group

            for d, s, rid, v in t_by_off[o.id]:
                r_num, r_type, r_cap = room_meta_map.get(rid, (str(rid), "THEORY", 60))
                batch_params.append(dict(
                    faculty_name               = fac.name,
                    room_number                = r_num,
                    day                        = d,
                    slot                       = s,
                    is_lab                     = False,
                    contact_hours              = o.weekly_load or o.course.min_weekly_lectures,
                    semester                   = getattr(sg, "term", None) and sg.term.semester or 4,
                    current_load               = 0,
                    course_name                = o.course.name,
                    room_type                  = r_type,
                    room_capacity              = r_cap,
                    requires_consecutive_slots = False,
                    is_elective                = o.course.course_type in {"OE", "PE"},
                    section_name               = sg.name,
                    program_code               = (getattr(getattr(sg, "term", None), "program", None)
                                                  and sg.term.program.code),
                    current_load_today         = 0,
                    max_daily                  = meta.get("max_daily", 4),
                    is_combined                = bool(o.combined_token),
                    working_days               = sg.working_days,
                ))
                batch_vars.append(v)

        if batch_params:
            try:
                raw_scores = ml_scorer.score_batch(batch_params)
                for v, sc in zip(batch_vars, raw_scores):
                    score_keys.append(v)
                    score_vals.append(max(0, int(sc * SCORE_SCALE)))
            except Exception as e:
                log.warning(f"CP-SAT: ML scoring failed ({e}), using uniform scores.")
                for v in batch_vars:
                    score_keys.append(v)
                    score_vals.append(500)   # 0.5 × SCORE_SCALE

        # Lab offerings: ML-score at the pair's first slot
        lab_batch_params = []
        lab_batch_vars   = []
        for o in lab_offs:
            if not o.assigned_faculty:
                continue
            fac  = o.assigned_faculty
            meta = faculty_meta.get(fac.id, {})
            sg   = o.student_group

            for day, s1, s2, rid, v in l_by_off[o.id]:
                r_num, r_type, r_cap = room_meta_map.get(rid, (str(rid), "LAB", 40))
                lab_batch_params.append(dict(
                    faculty_name               = fac.name,
                    room_number                = r_num,
                    day                        = day,
                    slot                       = s1,
                    is_lab                     = True,
                    contact_hours              = o.weekly_load or o.course.min_weekly_lectures,
                    semester                   = getattr(sg, "term", None) and sg.term.semester or 4,
                    current_load               = 0,
                    course_name                = o.course.name,
                    room_type                  = r_type,
                    room_capacity              = r_cap,
                    requires_consecutive_slots = True,
                    is_elective                = o.course.course_type in {"OE", "PE"},
                    section_name               = sg.name,
                    program_code               = (getattr(getattr(sg, "term", None), "program", None)
                                                  and sg.term.program.code),
                    current_load_today         = 0,
                    max_daily                  = meta.get("max_daily", 4),
                    is_combined                = bool(o.combined_token),
                    working_days               = sg.working_days,
                ))
                lab_batch_vars.append(v)

        if lab_batch_params:
            try:
                lab_scores = ml_scorer.score_batch(lab_batch_params)
                for v, sc in zip(lab_batch_vars, lab_scores):
                    score_keys.append(v)
                    score_vals.append(max(0, int(sc * SCORE_SCALE)))
            except Exception as e:
                log.warning(f"CP-SAT: lab ML scoring failed ({e}), using fixed 0.7.")
                for v in lab_batch_vars:
                    score_keys.append(v)
                    score_vals.append(700)

        if score_keys:
            model.Maximize(
                sum(coef * var for coef, var in zip(score_vals, score_keys))
            )

        # ── SOLVE ─────────────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds   = self.time_limit
        solver.parameters.num_search_workers    = 4
        solver.parameters.log_search_progress   = False

        log.info(f"CP-SAT: solving (time_limit={self.time_limit}s)…")
        status     = solver.Solve(model)
        status_name = solver.StatusName(status)

        log.info(
            f"CP-SAT: {status_name} | "
            f"obj={solver.ObjectiveValue():.0f} | "
            f"wall={solver.WallTime():.2f}s"
        )

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            log.warning(f"CP-SAT: no feasible solution ({status_name}). Greedy fallback.")
            return None, None

        # ── EXTRACT SOLUTION ──────────────────────────────────────────────────
        off_by_id = {o.id: o for o in theory_offs + lab_offs}
        pending_saves: list  = []
        scheduled_ids: set   = set()

        for (o_id, day, slot, room_id), var in t_var.items():
            if solver.Value(var) == 1:
                o  = off_by_id[o_id]
                ts = slot_map[(day, slot)]
                pending_saves.append({
                    "offering_id"      : o_id,
                    "student_group_id" : o.student_group_id,
                    "faculty_id"       : o.assigned_faculty_id if o.assigned_faculty else None,
                    "room_id"          : room_id,
                    "timeslot_id"      : ts.id,
                    "score"            : round(
                        solver.ObjectiveValue() / SCORE_SCALE / max(len(batch_vars), 1), 4
                    ),
                    "is_pe"            : o.course.course_type == "PE",
                })
                scheduled_ids.add(o_id)

        for (o_id, day, s1, room_id), var in l_var.items():
            if solver.Value(var) == 1:
                o  = off_by_id[o_id]
                s2 = next((b for a, b in valid_pairs if a == s1), None)
                if not s2:
                    continue
                for slot in [s1, s2]:
                    if (day, slot) not in slot_map:
                        continue
                    ts = slot_map[(day, slot)]
                    pending_saves.append({
                        "offering_id"      : o_id,
                        "student_group_id" : o.student_group_id,
                        "faculty_id"       : o.assigned_faculty_id if o.assigned_faculty else None,
                        "room_id"          : room_id,
                        "timeslot_id"      : ts.id,
                        "score"            : 0.75,
                        "is_pe"            : False,
                    })
                scheduled_ids.add(o_id)

        all_scheduled_offerings = theory_offs + lab_offs
        unscheduled = [o for o in all_scheduled_offerings if o.id not in scheduled_ids]
        unscheduled += unplaceable  # offerings that had no variables at all

        log.info(
            f"CP-SAT solution extracted: {len(pending_saves)} allocation records, "
            f"{len(unscheduled)} unscheduled offerings."
        )
        return pending_saves, unscheduled

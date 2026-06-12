"""
Editor API — copy-on-edit timetable editing with real-time DB sync.

Architecture:
  1. POST /editor/start/   → clone base timetable into a draft
  2. POST /editor/move/    → atomic move + full constraint check (all 6 rules)
  3. POST /editor/delete/  → remove allocation(s) from draft
  4. POST /editor/save/    → promote draft → real version
  5. POST /editor/discard/ → delete draft
  6. GET  /editor/palette/ → section's offerings with scheduled counts
  7. GET  /editor/rooms/   → list rooms free at a given slot

Constraint rules enforced in /editor/move/:
  R1 — Lab weekly limit: max 1 lab session (2 consecutive slots) per lab course per week
  R2 — Adjacent slot:    same course_code can't be in slot ±1 on same day
  R3 — PE stacking:      all PE siblings (same elective_slot_group) move together
  R4 — Room handling:    faculty/SG busy → BLOCK; room busy → WARN (pick later)
  R5 — PE all-or-nothing: if any PE sibling faculty/SG conflict → block ALL
  R6 — DB sync:          mutations applied to draft timetable immediately
"""

from django.db import transaction  # type: ignore
from django.db.models import Max  # type: ignore
from django.shortcuts import get_object_or_404  # type: ignore
from rest_framework import status  # type: ignore
from rest_framework.response import Response  # type: ignore
from rest_framework.views import APIView  # type: ignore

from academics.models import CourseOffering, StudentGroup
from infrastructure.models import Room

from .models import LectureAllocation, TimeSlot, Timetable


# ─────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────

def _expand_section_set(sg):
    """Return [sg.pk, ...combined-group pks that include sg]."""
    ids = [sg.pk]
    combined = StudentGroup.objects.filter(term=sg.term, name__contains=sg.name).exclude(pk=sg.pk)
    for c in combined:
        if sg.name in c.name.split("+"):
            ids.append(c.pk)
    return ids


def _get_timeslot(day, slot_number):
    """Get or raise 404 for a TimeSlot."""
    return get_object_or_404(TimeSlot, day=day, slot_number=int(slot_number))


def _alloc_to_dict(alloc):
    """Serialize a LectureAllocation to a dict for the frontend."""
    co = alloc.course_offering
    course = co.course
    sg = co.student_group
    return {
        "id":                  alloc.id,
        "day":                 alloc.timeslot.day,
        "slot_number":         alloc.timeslot.slot_number,
        "course_offering_id":  co.id,
        "course_code":         course.display_code,
        "course_name":         course.name,
        "course_type":         course.course_type,
        "faculty_id":          alloc.faculty_id,
        "faculty_name":        alloc.faculty.name if alloc.faculty else None,
        "room_id":             alloc.room_id,
        "room_number":         alloc.room.room_number if alloc.room_id else None,
        "building_code":       alloc.room.building.code if alloc.room_id and alloc.room.building else "",
        "room_type":           alloc.room.room_type if alloc.room_id else None,
        "student_group_id":    sg.id,
        "student_group_name":  sg.name,
        "is_combined":         "+" in sg.name,
        "is_lab":              course.requires_lab_room or course.course_type == "PR",
        "is_pe":               course.course_type == "PE",
        "requires_consecutive": course.requires_consecutive_slots,
        "elective_slot_group": co.elective_slot_group,
        "combined_token":      co.combined_token,
        "status":              "ok",
    }


def _section_allocs(tt, sg_ids):
    """Return all allocs for the given section IDs in a timetable."""
    return (
        LectureAllocation.objects
        .filter(timetable=tt, course_offering__student_group_id__in=sg_ids)
        .select_related(
            "course_offering__course",
            "course_offering__student_group",
            "faculty",
            "room__building",
            "timeslot",
        )
    )


def _all_allocs_as_dicts(tt, sg_ids):
    """Return all section allocs as frontend-friendly dicts."""
    return [_alloc_to_dict(a) for a in _section_allocs(tt, sg_ids)]


# Valid lab pairs (slot, slot+1) — lunch breaks the (4,5) chain
_LAB_PAIRS = {(1, 2), (2, 3), (3, 4), (5, 6)}


# ─────────────────────────────────────────────────────────────────────────
# 1) START — clone base timetable into a draft
# ─────────────────────────────────────────────────────────────────────────

class EditorStartView(APIView):
    """POST /api/scheduler/editor/start/

    Body: { "base_timetable_id": int, "student_group_id": int }

    Creates a draft copy of the base timetable for editing.
    If an existing draft for this base+section already exists, returns it.
    """

    @transaction.atomic
    def post(self, request):
        try:
            base_id = int(request.data["base_timetable_id"])
            sg_id   = int(request.data["student_group_id"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"error": "base_timetable_id and student_group_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_tt = get_object_or_404(Timetable, pk=base_id)

        # Reuse existing draft if one exists for this base
        existing = Timetable.objects.filter(
            is_draft=True, draft_base_id=base_id
        ).first()
        if existing:
            sg = get_object_or_404(StudentGroup, pk=sg_id)
            sg_ids = _expand_section_set(sg)
            return Response({
                "draft_timetable_id": existing.id,
                "base_timetable_id":  base_id,
                "allocations":        _all_allocs_as_dicts(existing, sg_ids),
            })

        # Use version 0 for drafts (avoids unique constraint conflicts)
        # Find next available draft version
        draft_v = (
            Timetable.objects.filter(term=base_tt.term, is_draft=True)
            .aggregate(Max("version"))["version__max"]
        )
        draft_v = (draft_v or 0) + 1
        # Use very high version numbers for drafts to avoid clashing with real versions
        max_real = (
            Timetable.objects.filter(term=base_tt.term, is_draft=False)
            .aggregate(Max("version"))["version__max"]
        ) or 0
        draft_version = max(max_real + 1000, 9000 + draft_v)

        draft = Timetable.objects.create(
            term=base_tt.term,
            version=draft_version,
            is_draft=True,
            draft_base_id=base_id,
        )

        # Clone ALL allocations from base (all sections, not just the edited one)
        base_allocs = (
            LectureAllocation.objects
            .filter(timetable=base_tt)
            .select_related("course_offering", "faculty", "room", "timeslot")
        )
        cloned = []
        for a in base_allocs:
            cloned.append(LectureAllocation(
                timetable=draft,
                course_offering=a.course_offering,
                student_group_id=a.student_group_id,
                faculty=a.faculty,
                room=a.room,
                timeslot=a.timeslot,
                hard_constraint_violated=a.hard_constraint_violated,
                soft_constraint_score=a.soft_constraint_score,
            ))
        LectureAllocation.objects.bulk_create(cloned)

        sg = get_object_or_404(StudentGroup, pk=sg_id)
        sg_ids = _expand_section_set(sg)

        return Response({
            "draft_timetable_id": draft.id,
            "base_timetable_id":  base_id,
            "allocations":        _all_allocs_as_dicts(draft, sg_ids),
        }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────
# 2) MOVE — atomic move + full constraint check
# ─────────────────────────────────────────────────────────────────────────

class EditorMoveView(APIView):
    """POST /api/scheduler/editor/move/

    Body:
      {
        "draft_timetable_id":  int,
        "student_group_id":    int,
        "course_offering_id":  int,
        "source": {"day": "TUE", "slot": 4} | null,   // null for palette drops
        "target": {"day": "MON", "slot": 3},
        "room_id": int | null,                          // for room assignment
        "action": "move" | "assign_room"
      }

    Returns:
      {
        "ok": true/false,
        "errors": [...],     // only if ok=false
        "warnings": [...],   // room_busy etc.
        "allocations": [...]  // full updated state
      }
    """

    @transaction.atomic
    def post(self, request):
        d = request.data
        try:
            draft_id = int(d["draft_timetable_id"])
            sg_id    = int(d["student_group_id"])
            co_id    = int(d["course_offering_id"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"error": "draft_timetable_id, student_group_id, course_offering_id required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action  = d.get("action", "move")
        source  = d.get("source")      # {"day", "slot"} or null
        target  = d.get("target")      # {"day", "slot"}

        if not target:
            return Response({"error": "target is required."}, status=status.HTTP_400_BAD_REQUEST)

        draft = get_object_or_404(Timetable, pk=draft_id, is_draft=True)
        co    = get_object_or_404(
            CourseOffering.objects.select_related("course", "student_group", "assigned_faculty"),
            pk=co_id,
        )
        sg    = get_object_or_404(StudentGroup, pk=sg_id)
        sg_ids = _expand_section_set(sg)

        course = co.course
        target_day  = target["day"]
        target_slot = int(target["slot"])

        is_lab = course.requires_lab_room or course.course_type == "PR"
        is_pe  = course.course_type == "PE"
        target_slots = [target_slot, target_slot + 1] if is_lab else [target_slot]

        errors = []
        warnings = []

        # ── ACTION: assign_room ──
        if action == "assign_room":
            room_id = d.get("room_id")
            if not room_id:
                return Response({"error": "room_id required for assign_room."}, status=status.HTTP_400_BAD_REQUEST)

            # Find the allocs at target for this offering and update their room
            # Also include PE siblings if applicable
            offerings_to_update = [co]
            if is_pe and co.elective_slot_group:
                pe_siblings = list(
                    CourseOffering.objects
                    .filter(elective_slot_group=co.elective_slot_group)
                    .exclude(pk=co.pk)
                )
                offerings_to_update.extend(pe_siblings)

            allocs_to_update = LectureAllocation.objects.filter(
                timetable=draft,
                course_offering__in=offerings_to_update,
                timeslot__day=target_day,
                timeslot__slot_number__in=target_slots,
            )
            room = get_object_or_404(Room, pk=room_id)
            allocs_to_update.update(room=room)

            return Response({
                "ok": True,
                "errors": [],
                "warnings": [],
                "allocations": _all_allocs_as_dicts(draft, sg_ids),
            })

        # ── ACTION: move ──

        # Resolve faculty
        faculty_id = co.assigned_faculty_id
        if source:
            # If moving from existing cell, get the faculty from that alloc
            src_alloc = LectureAllocation.objects.filter(
                timetable=draft,
                course_offering=co,
                timeslot__day=source["day"],
                timeslot__slot_number=int(source["slot"]),
            ).first()
            if src_alloc and src_alloc.faculty_id:
                faculty_id = src_alloc.faculty_id

        # Collect PE siblings (Rule 3: all PE in same elective_slot_group move together)
        pe_siblings = []
        if is_pe and co.elective_slot_group:
            pe_siblings = list(
                CourseOffering.objects
                .filter(elective_slot_group=co.elective_slot_group)
                .exclude(pk=co.pk)
                .select_related("course", "student_group", "assigned_faculty")
            )

        all_offerings = [co] + pe_siblings  # all offerings that must move

        # ── R1: Lab weekly limit ──
        if is_lab:
            # Count existing lab allocs for this course_code in the draft (excluding source)
            existing_lab_q = LectureAllocation.objects.filter(
                timetable=draft,
                course_offering__course__code=course.code,
                course_offering__student_group_id__in=sg_ids,
            )
            if source:
                source_ts_ids = list(
                    TimeSlot.objects.filter(
                        day=source["day"],
                        slot_number__in=[int(source["slot"]), int(source["slot"]) + 1],
                    ).values_list("id", flat=True)
                )
                existing_lab_q = existing_lab_q.exclude(timeslot_id__in=source_ts_ids)
            lab_count = existing_lab_q.count()
            if lab_count >= 2:  # 2 slots = 1 lab session
                errors.append({
                    "type": "lab_weekly_limit",
                    "message": f"{course.display_code} Lab is already scheduled this week. Max 1 lab session (2 slots) per week.",
                })

        # ── Lab pair validity ──
        if is_lab and (target_slot, target_slot + 1) not in _LAB_PAIRS:
            errors.append({
                "type": "lab_pair_invalid",
                "message": f"Lab needs 2 consecutive slots — S{target_slot}+S{target_slot+1} is not a valid pair (lunch break or end of day).",
            })

        # ── R2: Adjacent slot check ──
        if not is_lab:
            adj_slots = [target_slot - 1, target_slot + 1]
            # Remove slots that cross lunch (4→5 is not adjacent for theory)
            adj_slots = [s for s in adj_slots if 1 <= s <= 6]

            adj_conflict = LectureAllocation.objects.filter(
                timetable=draft,
                course_offering__course__code=course.code,
                course_offering__student_group_id__in=sg_ids,
                timeslot__day=target_day,
                timeslot__slot_number__in=adj_slots,
            )
            if source and source["day"] == target_day:
                src_ts = TimeSlot.objects.filter(
                    day=source["day"], slot_number=int(source["slot"])
                ).values_list("id", flat=True)
                adj_conflict = adj_conflict.exclude(timeslot_id__in=src_ts)
            if adj_conflict.exists():
                hit = adj_conflict.first()
                errors.append({
                    "type": "adjacent_slot",
                    "message": f"{course.display_code} is in S{hit.timeslot.slot_number} on {target_day}. Same course can't be in consecutive slots.",
                })

        # ── Occupied slot check ──
        for ts_num in target_slots:
            ts_obj = TimeSlot.objects.filter(day=target_day, slot_number=ts_num).first()
            if not ts_obj:
                continue
            occupied = LectureAllocation.objects.filter(
                timetable=draft,
                timeslot=ts_obj,
                course_offering__student_group_id__in=sg_ids,
            )
            # Exclude source allocs (they'll be removed)
            if source and source["day"] == target_day and int(source["slot"]) == ts_num:
                occupied = occupied.exclude(course_offering=co)
            # Exclude PE siblings at same slot (they stack)
            if is_pe and co.elective_slot_group:
                occupied = occupied.exclude(
                    course_offering__elective_slot_group=co.elective_slot_group
                )
            if occupied.exists():
                hit = occupied.first()
                errors.append({
                    "type": "occupied_slot",
                    "message": f"{target_day} S{ts_num} is occupied by {hit.course_offering.course.display_code}. Remove it first.",
                })

        # If hard errors so far, return early
        if errors:
            return Response({
                "ok": False,
                "errors": errors,
                "warnings": [],
                "allocations": _all_allocs_as_dicts(draft, sg_ids),
            })

        # ── R4 + R5: Faculty/Room checks for ALL offerings (PE all-or-nothing) ──
        room_warnings = []
        for off in all_offerings:
            off_faculty_id = off.assigned_faculty_id
            off_room_id = None

            # Get room from source if moving
            if source:
                src = LectureAllocation.objects.filter(
                    timetable=draft,
                    course_offering=off,
                    timeslot__day=source["day"],
                    timeslot__slot_number=int(source["slot"]),
                ).first()
                if src:
                    off_faculty_id = src.faculty_id or off_faculty_id
                    off_room_id = src.room_id

            for ts_num in target_slots:
                ts_obj = TimeSlot.objects.filter(day=target_day, slot_number=ts_num).first()
                if not ts_obj:
                    continue

                # Faculty check (across ALL sections in entire timetable)
                if off_faculty_id:
                    fac_clash = (
                        LectureAllocation.objects
                        .filter(timetable=draft, timeslot=ts_obj, faculty_id=off_faculty_id)
                        .exclude(course_offering=off)
                        .select_related(
                            "course_offering__course",
                            "course_offering__student_group",
                            "room__building",
                        )
                        .first()
                    )
                    if fac_clash:
                        # PE siblings sharing faculty is OK
                        if not (
                            is_pe and co.elective_slot_group and
                            fac_clash.course_offering.elective_slot_group == co.elective_slot_group
                        ):
                            # Also exclude source allocs
                            is_source = (
                                source and
                                fac_clash.timeslot.day == source["day"] and
                                fac_clash.timeslot.slot_number == int(source["slot"]) and
                                fac_clash.course_offering_id == off.id
                            )
                            if not is_source:
                                fc = fac_clash
                                errors.append({
                                    "type": "faculty_busy",
                                    "message": (
                                        f"Faculty {off.assigned_faculty.name if off.assigned_faculty else ''} "
                                        f"is busy at S{ts_num}: {fc.course_offering.course.display_code} "
                                        f"Sec {fc.course_offering.student_group.name}"
                                    ),
                                    "offering_id": off.id,
                                })

                # Student group check (section busy at this slot)
                sg_clash = (
                    LectureAllocation.objects
                    .filter(
                        timetable=draft, timeslot=ts_obj,
                        course_offering__student_group_id__in=_expand_section_set(off.student_group),
                    )
                    .exclude(course_offering=off)
                )
                if is_pe and co.elective_slot_group:
                    sg_clash = sg_clash.exclude(
                        course_offering__elective_slot_group=co.elective_slot_group
                    )
                if source:
                    src_ts_ids = list(
                        TimeSlot.objects.filter(
                            day=source["day"],
                            slot_number__in=[int(source["slot"])] + ([int(source["slot"]) + 1] if is_lab else []),
                        ).values_list("id", flat=True)
                    )
                    sg_clash = sg_clash.exclude(
                        timeslot_id__in=src_ts_ids,
                        course_offering__student_group_id__in=_expand_section_set(off.student_group),
                    )
                # This is already checked by occupied_slot above for the primary offering,
                # but for PE siblings we need to check their student groups too
                if off.id != co.id and sg_clash.exists():
                    hit = sg_clash.first()
                    errors.append({
                        "type": "section_busy",
                        "message": (
                            f"Section {off.student_group.name} is busy at {target_day} S{ts_num}: "
                            f"{hit.course_offering.course.display_code}"
                        ),
                        "offering_id": off.id,
                    })

                # Room check (warn only, don't block)
                if off_room_id:
                    room_clash = (
                        LectureAllocation.objects
                        .filter(timetable=draft, timeslot=ts_obj, room_id=off_room_id)
                        .exclude(course_offering=off)
                    )
                    if source:
                        room_clash = room_clash.exclude(
                            timeslot_id__in=src_ts_ids if source else [],
                            course_offering=off,
                        )
                    if room_clash.exists():
                        room_warnings.append({
                            "type": "room_busy",
                            "slot": ts_num,
                            "offering_id": off.id,
                            "course_code": off.course.display_code,
                        })

        # ── R5: PE all-or-nothing — if any faculty/SG error, block ALL ──
        if errors:
            return Response({
                "ok": False,
                "errors": errors,
                "warnings": [],
                "allocations": _all_allocs_as_dicts(draft, sg_ids),
            })

        # ── All checks passed — apply the move in DB ──

        for off in all_offerings:
            off_faculty_id = off.assigned_faculty_id
            off_room_id = None
            off_room = None

            # Get room+faculty from source
            if source:
                src_allocs = LectureAllocation.objects.filter(
                    timetable=draft,
                    course_offering=off,
                    timeslot__day=source["day"],
                )
                src_slot_nums = [int(source["slot"])]
                if is_lab:
                    src_slot_nums.append(int(source["slot"]) + 1)
                src_allocs = src_allocs.filter(timeslot__slot_number__in=src_slot_nums)

                first_src = src_allocs.first()
                if first_src:
                    off_faculty_id = first_src.faculty_id or off_faculty_id
                    off_room_id = first_src.room_id
                    off_room = first_src.room

                # Delete source allocs
                src_allocs.delete()

            # Check if room is blocked for any target slot
            has_room_warning = any(
                w["offering_id"] == off.id for w in room_warnings
            )

            # Create new allocs at target
            for ts_num in target_slots:
                ts_obj = _get_timeslot(target_day, ts_num)

                # Determine room: if room warning, set to null (user picks later)
                effective_room_id = off_room_id if not has_room_warning else None
                effective_room = off_room if not has_room_warning else None

                # For palette drops (no source), room is null
                if not source:
                    effective_room_id = None
                    effective_room = None

                alloc = LectureAllocation(
                    timetable=draft,
                    course_offering=off,
                    student_group_id=off.student_group_id,
                    faculty_id=off_faculty_id,
                    room_id=effective_room_id,
                    timeslot=ts_obj,
                )
                alloc.save()

        # Build response
        all_allocs = _all_allocs_as_dicts(draft, sg_ids)

        # Mark allocs with room warnings
        warning_offering_ids = {w["offering_id"] for w in room_warnings}
        no_room_ids = set()
        for a in all_allocs:
            if a["course_offering_id"] in warning_offering_ids and a["day"] == target_day and a["slot_number"] in target_slots:
                a["status"] = "yellow"
            elif a["room_id"] is None and a["day"] == target_day and a["slot_number"] in target_slots:
                a["status"] = "red"
                no_room_ids.add(a["course_offering_id"])

        # Also mark palette drops as red (no room)
        if not source:
            for a in all_allocs:
                if a["course_offering_id"] == co.id and a["day"] == target_day and a["slot_number"] in target_slots:
                    if a["room_id"] is None:
                        a["status"] = "red"

        return Response({
            "ok": True,
            "errors": [],
            "warnings": room_warnings,
            "allocations": all_allocs,
        })


# ─────────────────────────────────────────────────────────────────────────
# 3) DELETE — remove allocation(s) from draft
# ─────────────────────────────────────────────────────────────────────────

class EditorDeleteView(APIView):
    """POST /api/scheduler/editor/delete/

    Body:
      {
        "draft_timetable_id": int,
        "student_group_id":   int,
        "course_offering_id": int,
        "day": "MON",
        "slot": 3
      }

    Removes allocation(s) for the given offering at the given slot.
    For labs, removes both consecutive slots. For PE, removes the whole
    elective_slot_group at that slot.
    """

    @transaction.atomic
    def post(self, request):
        d = request.data
        try:
            draft_id = int(d["draft_timetable_id"])
            sg_id    = int(d["student_group_id"])
            co_id    = int(d["course_offering_id"])
            day      = d["day"]
            slot     = int(d["slot"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"error": "draft_timetable_id, student_group_id, course_offering_id, day, slot required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        draft = get_object_or_404(Timetable, pk=draft_id, is_draft=True)
        co    = get_object_or_404(CourseOffering.objects.select_related("course"), pk=co_id)
        sg    = get_object_or_404(StudentGroup, pk=sg_id)
        sg_ids = _expand_section_set(sg)

        course = co.course
        is_lab = course.requires_lab_room or course.course_type == "PR"
        is_pe  = course.course_type == "PE"

        # Build delete query
        del_q = LectureAllocation.objects.filter(timetable=draft)

        if is_lab:
            # Delete both consecutive slots
            slots_to_del = [slot, slot + 1] if (slot, slot + 1) in _LAB_PAIRS else [slot - 1, slot] if (slot - 1, slot) in _LAB_PAIRS else [slot]
            ts_ids = list(
                TimeSlot.objects.filter(day=day, slot_number__in=slots_to_del)
                .values_list("id", flat=True)
            )
            del_q = del_q.filter(course_offering=co, timeslot_id__in=ts_ids)
        elif is_pe and co.elective_slot_group:
            # Delete all PE siblings at this slot
            ts_obj = _get_timeslot(day, slot)
            del_q = del_q.filter(
                timeslot=ts_obj,
                course_offering__elective_slot_group=co.elective_slot_group,
            )
        else:
            ts_obj = _get_timeslot(day, slot)
            del_q = del_q.filter(course_offering=co, timeslot=ts_obj)

        del_q.delete()

        return Response({
            "ok": True,
            "allocations": _all_allocs_as_dicts(draft, sg_ids),
        })


# ─────────────────────────────────────────────────────────────────────────
# 4) SAVE — promote draft to real version
# ─────────────────────────────────────────────────────────────────────────

class EditorSaveView(APIView):
    """POST /api/scheduler/editor/save/

    Body: { "draft_timetable_id": int, "student_group_id": int }

    Validates the draft, then promotes it to a real timetable version.
    """

    @transaction.atomic
    def post(self, request):
        try:
            draft_id = int(request.data["draft_timetable_id"])
            sg_id    = int(request.data["student_group_id"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"error": "draft_timetable_id and student_group_id required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        draft = get_object_or_404(Timetable, pk=draft_id, is_draft=True)
        sg    = get_object_or_404(StudentGroup, pk=sg_id)
        sg_ids = _expand_section_set(sg)

        # Validate: no allocs without rooms for the edited section
        missing_room = LectureAllocation.objects.filter(
            timetable=draft,
            course_offering__student_group_id__in=sg_ids,
            room__isnull=True,
        )
        if missing_room.exists():
            codes = set(a.course_offering.course.display_code for a in missing_room[:5])
            return Response({
                "ok": False,
                "error": f"{missing_room.count()} allocation(s) missing rooms: {', '.join(codes)}. Assign rooms before saving.",
            }, status=status.HTTP_400_BAD_REQUEST)

        # Promote: change draft to real version
        base_id = draft.draft_base_id

        # Next version number for this term
        last_v = (
            Timetable.objects.filter(term=draft.term, is_draft=False)
            .aggregate(Max("version"))["version__max"]
        ) or 0

        draft.version = last_v + 1
        draft.is_draft = False
        draft.draft_base_id = None
        draft.save()

        return Response({
            "ok": True,
            "timetable_id": draft.id,
            "version": draft.version,
        }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────
# 5) DISCARD — delete draft timetable
# ─────────────────────────────────────────────────────────────────────────

class EditorDiscardView(APIView):
    """POST /api/scheduler/editor/discard/

    Body: { "draft_timetable_id": int }

    Deletes the draft timetable and all its allocations.
    """

    @transaction.atomic
    def post(self, request):
        try:
            draft_id = int(request.data["draft_timetable_id"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"error": "draft_timetable_id required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        draft = get_object_or_404(Timetable, pk=draft_id, is_draft=True)
        # CASCADE deletes all LectureAllocations
        draft.delete()

        return Response({"ok": True})


# ─────────────────────────────────────────────────────────────────────────
# 6) PALETTE — offerings for a section
# ─────────────────────────────────────────────────────────────────────────

class EditorPaletteView(APIView):
    """GET /api/scheduler/editor/palette/?student_group_id=X&timetable_id=Y

    Returns every CourseOffering for the section. Accepts either a real
    timetable_id or a draft timetable_id for count accuracy.
    """

    def get(self, request):
        sg_id = request.query_params.get("student_group_id")
        tt_id = request.query_params.get("timetable_id")
        if not sg_id:
            return Response(
                {"error": "student_group_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sg = get_object_or_404(StudentGroup, pk=sg_id)
        tt = get_object_or_404(Timetable, pk=tt_id) if tt_id else None

        sg_ids = _expand_section_set(sg)
        offerings = (
            CourseOffering.objects
            .filter(student_group_id__in=sg_ids)
            .select_related("course", "assigned_faculty", "student_group")
            .order_by("course__code")
        )

        # Pre-count scheduled allocations per offering in this timetable
        scheduled_map = {}
        if tt:
            counts = (
                LectureAllocation.objects
                .filter(timetable=tt, course_offering_id__in=[o.id for o in offerings])
                .values_list("course_offering_id")
            )
            for (oid,) in counts:
                scheduled_map[oid] = scheduled_map.get(oid, 0) + 1

        data = []
        for o in offerings:
            scheduled = scheduled_map.get(o.id, 0)
            ct = o.course.course_type
            data.append({
                "id":                   o.id,
                "course_id":            o.course.id,
                "course_code":          o.course.display_code,
                "course_code_internal": o.course.code,
                "course_name":          o.course.name,
                "course_type":          ct,
                "credits":              o.course.credits,
                "faculty_id":           o.assigned_faculty.id if o.assigned_faculty else None,
                "faculty_name":         o.assigned_faculty.name if o.assigned_faculty else None,
                "weekly_load":          o.weekly_load,
                "scheduled_count":      scheduled,
                "remaining":            max(0, o.weekly_load - scheduled),
                "student_group_id":     o.student_group.id,
                "student_group_name":   o.student_group.name,
                "elective_slot_group":  o.elective_slot_group,
                "combined_token":       o.combined_token,
                "is_pe":                ct == "PE",
                "is_lab":               o.course.requires_lab_room or ct == "PR",
                "is_combined":          "+" in o.student_group.name,
                "requires_consecutive": o.course.requires_consecutive_slots,
                "room_type_hint":       "LAB" if (o.course.requires_lab_room or ct == "PR") else "THEORY",
            })

        return Response({
            "offerings": data,
            "student_group": {"id": sg.id, "name": sg.name, "strength": sg.strength},
        })


# ─────────────────────────────────────────────────────────────────────────
# 7) ROOMS — list free rooms at a given slot
# ─────────────────────────────────────────────────────────────────────────

class EditorFreeRoomsView(APIView):
    """GET /api/scheduler/editor/rooms/
        ?day=MON&slot=2&timetable_id=5
        &room_type=THEORY
        &min_capacity=30
    """

    def get(self, request):
        day   = request.query_params.get("day")
        slot  = request.query_params.get("slot")
        tt_id = request.query_params.get("timetable_id")
        if not (day and slot and tt_id):
            return Response(
                {"error": "day, slot, timetable_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room_type = request.query_params.get("room_type")
        min_cap   = request.query_params.get("min_capacity")

        timeslot = get_object_or_404(TimeSlot, day=day, slot_number=slot)

        occupied = set(
            LectureAllocation.objects
            .filter(timetable_id=tt_id, timeslot=timeslot)
            .values_list("room_id", flat=True)
        )

        rooms = Room.objects.filter(is_active=True).exclude(pk__in=occupied)
        if room_type:
            rooms = rooms.filter(room_type=room_type)
        if min_cap and str(min_cap).isdigit():
            rooms = rooms.filter(capacity__gte=int(min_cap))

        rooms = rooms.select_related("building").order_by("room_number")

        return Response({
            "rooms": [
                {
                    "id":            r.id,
                    "room_number":   r.room_number,
                    "building_code": r.building.code if r.building else "",
                    "building_name": r.building.name if r.building else "",
                    "room_type":     r.room_type,
                    "capacity":      r.capacity,
                }
                for r in rooms
            ],
        })

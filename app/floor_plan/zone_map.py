"""Zone -> sail.db location mapping for the floor plan.

This is the single source of truth for "which physical inventory location
backs each zone on the schematic". The 4 bookable rooms also live in
floor_plan.db's bookable_rooms table (for the booking flow); this dict
covers the broader case where we want any zone to surface its real
assets without making it bookable yet.

Best-effort matches based on the existing locations in sail.db. The user
should review and adjust — unmapped zones simply show "No inventory
linked" in the side panel. Adjusting a mapping requires no migration;
just change the value here.
"""

# zone_key -> sail.db locations.id (or None if intentionally unlinked)
ZONE_TO_LOCATION = {
    # Bookable rooms (also in bookable_rooms table — kept here for completeness)
    "boardroom-1":          38,   # WORKSHOP-1
    "boardroom-2":          39,   # WORKSHOP-2
    "conference-long":      40,   # WORKSHOP-3
    "global-theater":       11,   # DIGITAL-THEATER

    # Likely matches by name
    "open-workshop":        22,   # OPEN-WORKSHOP-AREA
    "metaverse-xr":         29,   # TECH-LAB-METAVERS
    "it-infrastructure":     8,   # DATA-CENTER
    "ux-test-small":        36,   # UX-TESTING
    "ux-test-zone":         36,   # UX-TESTING (same physical room)
    "ux-obs":               34,   # UX-OBSERVATION
    "main-boardroom":       12,   # DIVISION-HEAD
    "corporate-innovation": 30,   # TECHNOLOGY-AND-INNOVATION-DIRECTOR
    "academia":             26,   # TECH-LAB-ARAMCO-AI

    # Incubator zones
    "remote-incubation":    14,   # INCUBATOR-2
    "east-cluster-b":       17,   # INCUBATOR-3
    "east-cluster-c":       18,   # INCUBATOR-4
    "east-cluster-d":       19,   # INCUBATOR-5

    # Less obvious — left unmapped for now (set explicitly to None to be loud)
    "east-cluster-a":       None,
    "west-cluster":         None,
    "west-lounge":          None,
    "pod-1":                None,
    "pod-2":                None,
    "pod-3":                None,
    "mid-pavilion":         None,
    "lobby":                None,
    "restrooms":            None,
}


def location_for(zone_key):
    """Return the sail.db location_id for a zone, or None if unmapped."""
    return ZONE_TO_LOCATION.get(zone_key)

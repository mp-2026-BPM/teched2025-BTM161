import re
from dataclasses import dataclass, field

import pandas as pd


TOOL_EVENT_TYPES = { #TODO: unknown and extract them
    "prepare_order", "remake_order_item", "estimate_prep_time",
    "transfer_to_customer_service", "offer_refund", "offer_partial_refund",
    "transfer_to_order_agent", "transfer_to_barista", "transfer_to_inventory",
    "check_inventory", "update_stock", "get_alternatives",
    "process_order", "calculate_total"}

KNOWN_AGENTS = {"order_agent", "barista_agent", "inventory_agent", "customer_service_agent"} #TODO: unknown and extract them

_ORDER_ID_RE = re.compile(r"\*?\*?ORD\d+\*?\*?") # e.g. ORD9867

_ITEM_LINE_RE = re.compile(
    r"-\s+\*?\*?(\d+\s+)?([A-Za-z][A-Za-z0-9 \-]+?)\*?\*?\s*[–\-]?\s*\$[\d.]+",
    re.MULTILINE,
)

@dataclass
class ObjectCentricEventlog:
    """
    Minimal OCEL 2.0 container (OCEL-spec §3).

    Attributes
    ----------
    events : pd.DataFrame
        Columns: ocel:eid, ocel:type, ocel:timestamp, + type-specific attributes.
    objects : pd.DataFrame
        Columns: ocel:oid, ocel:type, + type-specific attributes.
    e2o : pd.DataFrame
        Event-to-object relations.
        Columns: ocel:eid, ocel:oid, ocel:qualifier.
    """

    events: pd.DataFrame
    objects: pd.DataFrame
    events_to_objects: pd.DataFrame

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def events_of_type(self, event_type: str) -> pd.DataFrame:
        return self.events[self.events["ocel:type"] == event_type]

    def objects_of_type(self, object_type: str) -> pd.DataFrame:
        return self.objects[self.objects["ocel:type"] == object_type]

    def objects_for_event(self, eid: str) -> pd.DataFrame:
        oids = self.events_to_objects[self.events_to_objects["ocel:eid"] == eid]["ocel:oid"]
        return self.objects[self.objects["ocel:oid"].isin(oids)]

    def events_for_object(self, oid: str) -> pd.DataFrame:
        eids = self.events_to_objects[self.events_to_objects["ocel:oid"] == oid]["ocel:eid"]
        return self.events[self.events["ocel:eid"].isin(eids)]

    def summary(self) -> str:
        lines = [
            "=== OCEL 2.0 Summary ===",
            f"  Events  : {len(self.events)} total  |  types: {sorted(self.events['ocel:type'].unique())}",
            f"  Objects : {len(self.objects)} total  |  types: {sorted(self.objects['ocel:type'].unique())}",
            f"  E2O     : {len(self.events_to_objects)} relations",
        ]
        return "\n".join(lines)


def _extract_order_id(text: str) -> str | None:
    """Return the first ORDxxxx found in *text*, or None."""
    m = _ORDER_ID_RE.search(text)
    if m:
        return re.sub(r"\*", "", m.group(0))
    return None


def _extract_order_items(text: str) -> list[str]:
    """
    Return a list of item description strings parsed from a markdown message.
    Example line: '- **Large Latte** – $4.75'  →  'Large Latte'
    """
    items = []
    for m in _ITEM_LINE_RE.finditer(text):
        qty_prefix = (m.group(1) or "").strip()
        item_name = m.group(2).strip().rstrip("-").strip()
        if qty_prefix:
            # "2 Large Lattes" → emit two separate items
            try:
                qty = int(qty_prefix)
                items.extend([item_name] * qty)
            except ValueError:
                items.append(item_name)
        else:
            items.append(item_name)
    return items


def convert_to_ocel(el: pd.DataFrame) -> ObjectCentricEventlog:
    """
    Transform a flat event log DataFrame into an OCEL 2.0 object.

    Parameters
    ----------
    df_raw : pd.DataFrame
        Raw event log as loaded directly from the CSV.

    Returns
    -------
    OCEL
        Populated OCEL 2.0 container.
    """

    # -----------------------------------------------------------------------
    # 1.  Normalise timestamps
    # -----------------------------------------------------------------------
    df = el.copy()
    df["time_finished"] = pd.to_datetime(df["time_finished"])
    df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])

    # -----------------------------------------------------------------------
    # 2.  Build OBJECTS
    # -----------------------------------------------------------------------

    objects = (
        el[["org:resource", "case_id"]]
        .copy()
        .assign(
            ocel_type=lambda d: d["org:resource"].str.contains("agent").map({True: "agent", False: "user"}),
            ocel_id=lambda d: d["case_id"].where(~d["org:resource"].str.contains("agent"),d["org:resource"])
        )
        .drop(columns=["org:resource", "case_id"])
        .drop_duplicates()
    )


    object_rows: list[dict] = []
    seen_oids: set[str] = set()

    def _add_object(oid: str, otype: str, **attrs):
        if oid not in seen_oids:
            seen_oids.add(oid)
            object_rows.append({"ocel:oid": oid, "ocel:type": otype, **attrs})

    # 2a. Agent objects  (one per distinct resource that is an agent)
    for resource in df["org:resource"].dropna().unique():
        if resource in KNOWN_AGENTS:
            _add_object(oid=resource, otype="Agent")

    # 2b. Customer objects  (one per case_id)
    for case_id in df["case_id"].dropna().unique():
        _add_object(oid=f"customer_{case_id}", otype="Customer")

    # 2c. Prompt objects  (one per row whose concept:name == 'user_prompt')
    #     identity:id is used as the raw id; prefixed with 'prompt_'
    for _, row in df[df["concept:name"] == "user_prompt"].iterrows():
        oid = f"prompt_{row['identity:id']}"
        _add_object(
            oid=oid,
            otype="Prompt",
            message=row.get("message"),
        )

    # 2d. Order & OrderItem objects  (parsed from LLM messages)
    #
    # Strategy:
    #   - First pass: collect all (order_id, case_id, items) tuples we can
    #     observe in call_llm messages.  The first message that mentions an
    #     ORD id AND lists items is taken as the canonical order description.
    #
    order_case: dict[str, str] = {}          # order_id → case_id
    order_items: dict[str, list[str]] = {}   # order_id → [item descriptions]

    for _, row in df[df["concept:name"] == "call_llm"].iterrows():
        msg = row.get("message")
        if not isinstance(msg, str):
            continue
        oid = _extract_order_id(msg)
        if oid is None:
            continue
        if oid not in order_case:
            order_case[oid] = row["case_id"]
        if oid not in order_items:
            items = _extract_order_items(msg)
            if items:
                order_items[oid] = items

    # If no explicit ORD id was found for a case, synthesise one from case_id
    # (covers the first case in the sample log where process_order runs but no
    # ORD id is ever surfaced in the messages that we have)
    cases_with_process_order = set(
        df[df["tool"] == "process_order"]["case_id"].dropna()
    )
    for case_id in cases_with_process_order:
        already_has_order = any(v == case_id for v in order_case.values())
        if not already_has_order:
            synthetic_oid = f"ORD_case_{case_id[:8]}"
            order_case[synthetic_oid] = case_id

    for order_id, case_id in order_case.items():
        _add_object(oid=order_id, otype="Order", case_id=case_id)

    for order_id, items in order_items.items():
        for idx, item_name in enumerate(items, start=1):
            item_oid = f"{order_id}_item_{idx}"
            _add_object(oid=item_oid, otype="OrderItem",
                        order_id=order_id, item_name=item_name)

    objects_df = pd.DataFrame(object_rows)

    # -----------------------------------------------------------------------
    # 3.  Build EVENTS
    # -----------------------------------------------------------------------

    event_rows: list[dict] = []

    for _, row in df.iterrows():
        eid = row["identity:id"]
        etype_raw = row["concept:name"]   # user_prompt | call_llm | execute_tool
        ts = row["time_finished"]

        # Map concept:name + tool column → OCEL event type
        if etype_raw == "user_prompt":
            etype = "user_prompt"
            ev = {
                "ocel:eid": eid,
                "ocel:type": etype,
                "ocel:timestamp": ts,
                "message": row.get("message"),
            }

        elif etype_raw == "call_llm":
            etype = "call_llm"
            ev = {
                "ocel:eid": eid,
                "ocel:type": etype,
                "ocel:timestamp": ts,
                "message": row.get("message"),
                "model": row.get("model"),
                "input_tokens": row.get("input_tokens"),
                "response_tokens": row.get("response_tokens"),
                "duration": row.get("duration"),
            }

        elif etype_raw == "execute_tool":
            # tool column tells us which specific tool
            tool_name = row.get("tool") if pd.notna(row.get("tool")) else "unknown_tool"
            etype = str(tool_name)
            ev = {
                "ocel:eid": eid,
                "ocel:type": etype,
                "ocel:timestamp": ts,
                "duration": row.get("duration"),
            }

        else:
            # Fallback: keep as-is
            etype = etype_raw
            ev = {
                "ocel:eid": eid,
                "ocel:type": etype,
                "ocel:timestamp": ts,
            }

        ev["_case_id"] = row["case_id"]          # helper for e2o; dropped later
        ev["_resource"] = row.get("org:resource") # helper for e2o; dropped later
        ev["_raw_message"] = row.get("message")   # helper for order linking
        event_rows.append(ev)

    events_df = pd.DataFrame(event_rows)

    # -----------------------------------------------------------------------
    # 4.  Build E2O relations
    # -----------------------------------------------------------------------

    e2o_rows: list[dict] = []

    def _link(eid: str, oid: str, qualifier: str):
        if oid in seen_oids:
            e2o_rows.append({
                "ocel:eid": eid,
                "ocel:oid": oid,
                "ocel:qualifier": qualifier,
            })

    # Pre-compute a mapping: case_id → order_id (for quick lookup)
    case_to_order: dict[str, str] = {v: k for k, v in order_case.items()}
    # case_id → [item_oids]
    case_to_items: dict[str, list[str]] = {}
    for order_id, items in order_items.items():
        c = order_case.get(order_id)
        if c:
            case_to_items.setdefault(c, [])
            for idx in range(1, len(items) + 1):
                case_to_items[c].append(f"{order_id}_item_{idx}")

    for _, ev in events_df.iterrows():
        eid = ev["ocel:eid"]
        case_id = ev["_case_id"]
        resource = ev["_resource"]
        etype = ev["ocel:type"]

        # Every event → Customer
        _link(eid, f"customer_{case_id}", "involves_customer")

        # Agent events
        if resource in KNOWN_AGENTS:
            _link(eid, resource, "executed_by")

        # user_prompt → Prompt object
        if etype == "user_prompt":
            _link(eid, f"prompt_{eid}", "is_prompt")

        # call_llm messages that mention an ORD id → link Order
        raw_msg = ev.get("_raw_message")
        if isinstance(raw_msg, str):
            mentioned_order = _extract_order_id(raw_msg)
            if mentioned_order:
                _link(eid, mentioned_order, "references_order")
                # Also link items
                for item_oid in [
                    o for o in seen_oids
                    if o.startswith(f"{mentioned_order}_item_")
                ]:
                    _link(eid, item_oid, "references_order_item")

        # Tool events → link Order and OrderItems of the case
        if etype in TOOL_EVENT_TYPES or etype in {
            "process_order", "check_inventory",
            "estimate_prep_time", "prepare_order",
        }:
            order_id = case_to_order.get(case_id)
            if order_id:
                _link(eid, order_id, "acts_on_order")
                for item_oid in case_to_items.get(case_id, []):
                    _link(eid, item_oid, "acts_on_order_item")

    e2o_df = pd.DataFrame(e2o_rows, columns=["ocel:eid", "ocel:oid", "ocel:qualifier"])

    # -----------------------------------------------------------------------
    # 5.  Clean up helper columns from events_df
    # -----------------------------------------------------------------------
    events_df = events_df.drop(
        columns=["_case_id", "_resource", "_raw_message"], errors="ignore"
    )

    return ObjectCentricEventlog(events=events_df, objects=objects, events_to_objects=e2o_df)


def load_and_convert(csv_path: str) -> ObjectCentricEventlog:
    """Load a CSV file and return an OCEL object."""
    df = pd.read_csv(csv_path)
    return convert_to_ocel(df)

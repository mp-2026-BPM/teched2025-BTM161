from dataclasses import dataclass

import polars as pl


EVENT_ATTRIBUTES = {
    "agent_response": ["ocel_time", "duration", "input_tokens", "response_tokens"],
    "call_llm": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "user_prompt": ["ocel_time"],
    "prepare_order": ["ocel_time", "duration"],
    "estimate_prep_time": ["ocel_time", "duration"],
    "process_order": ["ocel_time", "duration"],
    "check_inventory": ["ocel_time", "duration"],
    "update_stock": ["ocel_time", "duration"],
    "get_order": ["ocel_time", "duration"],
    "remake_order_item": ["ocel_time", "duration"],
    "transfer_to_customer_service": ["ocel_time", "duration"],
    "offer_refund": ["ocel_time", "duration"],
    "offer_partial_refund": ["ocel_time", "duration"],
    "transfer_to_order_agent": ["ocel_time", "duration"],
    "transfer_to_barista": ["ocel_time", "duration"],
    "transfer_to_inventory": ["ocel_time", "duration"],
    "get_alternatives": ["ocel_time", "duration"],
    "calculate_total": ["ocel_time", "duration"],
    "order_agent_handover_inventory_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "order_agent_handover_barista_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "order_agent_handover_customer_service_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "barista_agent_handover_order_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "barista_agent_handover_inventory_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "barista_agent_handover_customer_service_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "inventory_agent_handover_order_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "inventory_agent_handover_barista_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "inventory_agent_handover_customer_service_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "customer_service_agent_handover_order_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "customer_servicey_agent_handover_barista_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],
    "customer_service_agent_handover_inventory_agent": ["ocel_time", "model", "duration", "input_tokens", "response_tokens"],

}

OBJECT_ATTRIBUTES = {
    "agent": [],
    "user": [],
    "prompt": ["message"],
    "response": ["message"],
    "order_agent": [],
    "barista_agent": [],
    "inventory_agent": [],
    "customer_service_agent": [],
}


@dataclass
class ObjectCentricEventlog:
    """
    Minimal OCEL 2.0 container
    """

    events: pl.DataFrame
    objects: pl.DataFrame
    event_object: pl.DataFrame
    object_object: pl.DataFrame
    event_map_type: pl.DataFrame
    object_map_type: pl.DataFrame
    event_tables: dict[str, pl.DataFrame]
    object_tables: dict[str, pl.DataFrame]

    @classmethod
    def from_eventlog(cls, eventlog: str | pl.DataFrame) -> "ObjectCentricEventlog":
        """
        Crate an ObjectCentricEventlog according to the OCEL 2.0 standard from a flat event log.
        The input is either a path to the eventlog or the eventlog a as a polars DataFrame

        Input:
            el : pl.DataFrame holding the raw event log as loaded directly from the CSV.

        """
        if type(eventlog) == str:
            eventlog = pl.read_csv(eventlog)

        el_enriched = preprocess_eventlog(eventlog)

        objects = (
            el_enriched.select(
                pl.concat_list(
                    [
                        pl.struct(
                            pl.col("object_id_agent").alias("ocel_id"),
                            pl.col("object_type_agent").alias("ocel_type"),
                        ),
                        pl.struct(
                            pl.col("object_id_message").alias("ocel_id"),
                            pl.col("object_type_message").alias("ocel_type"),
                        ),
                    ]
                )
            )
            .explode("ocel_id")
            .select(pl.col("ocel_id").struct.unnest())
            .drop_nulls()
            .unique()
        )

        events = el_enriched.select(
            ocel_id=pl.col("event_id"), ocel_type=pl.col("event_type")
        )

        event_object = (
            el_enriched.select(
                ocel_event_id=pl.col("event_id"),
                ocel_object_id=pl.concat_list(
                    [pl.col("object_id_agent"), pl.col("object_id_message")]
                ),
                ocel_qualifier=pl.concat_list(
                    [pl.col("object_type_agent"), pl.col("object_type_message")]
                ),
            )
            .explode("ocel_object_id", "ocel_qualifier")
            .drop_nulls()
        )

        object_object = pl.DataFrame(
            schema={
                "ocel_source_id": str,
                "ocel_target_id": str,
                "ocel_qualifier": str,
            }
        )

        event_map_type = (
            events.select("ocel_type")
            .unique()
            .with_columns(ocel_type_map=pl.col("ocel_type"))
        )

        object_map_type = (
            objects.select("ocel_type")
            .unique()
            .with_columns(ocel_type_map=pl.col("ocel_type"))
        )

        event_tables = {}
        for evt_type in event_map_type["ocel_type"].to_list():
            attrs = EVENT_ATTRIBUTES[evt_type]
            evt_type_tbl = (
                events.filter(pl.col("ocel_type") == evt_type)
                .join(
                    el_enriched.select(["event_id", *attrs]),
                    left_on="ocel_id",
                    right_on="event_id",
                    how="left",
                )
                .drop("ocel_type")
            )
            event_tables[f"event_{evt_type}"] = evt_type_tbl

        object_tables = {}
        for obj_type in object_map_type["ocel_type"].to_list():
            attrs = OBJECT_ATTRIBUTES[obj_type]
            column_id = (
                "object_id_message"
                if (obj_type == "prompt" or obj_type == "response")
                else "object_id_agent"
            )
            obj_type_tbl = (
                objects.filter(pl.col("ocel_type") == obj_type)
                .join(
                    el_enriched.select([column_id, *attrs]),
                    left_on="ocel_id",
                    right_on=column_id,
                    how="left",
                )
                .drop("ocel_type")
                .unique()
            )
            object_tables[f"object_{obj_type}"] = obj_type_tbl

        return cls(
            events=events,
            objects=objects,
            event_object=event_object,
            object_object=object_object,
            event_map_type=event_map_type,
            object_map_type=object_map_type,
            event_tables=event_tables,
            object_tables=object_tables,
        )


def preprocess_eventlog(eventlog: pl.DataFrame) -> pl.DataFrame:
    el_enriched = (
        eventlog.with_columns(
            object_type_message=(
                pl.when(pl.col("concept:instance") == "prompt").then(pl.col("concept:instance"))
                .when((pl.col("concept:name") == "call_llm") & (pl.col("message").is_not_null())).then(pl.lit("response"))
                .otherwise(pl.lit(None))),
            object_id_agent=pl.when(pl.col("org:resource").str.contains("agent")).then(pl.col("case_id") + pl.lit("_") + pl.col("org:resource")).otherwise(pl.col("case_id")),
            object_type_agent=pl.col("org:resource"),
            event_id=pl.col("identity:id"),
            event_type=(
                pl.when((pl.col("concept:name") == "execute_tool") & pl.col("tool").is_not_null()).then(pl.col("tool"))
                .when((pl.col("concept:name") == "call_llm") & (pl.col("message").is_not_null())).then(pl.lit("agent_response"))
                .otherwise(pl.col("concept:name"))),
            ocel_time=pl.col("time_finished").str.to_datetime()
        )
        .with_columns(
            object_id_message=(
                pl.when(pl.col("object_type_message") == "prompt").then(pl.lit("prompt_") + pl.col("identity:id"))
                .when(pl.col("object_type_message") == "response").then(pl.lit("response_") + pl.col("identity:id"))
                .otherwise(pl.lit(None))),
        )
    )

    el_enriched = (
        el_enriched
        .with_row_index()
        .with_columns(
            index=pl.col("index").cast(pl.Float64),
            next_event_type=pl.col("event_type").shift(-1),
            next_agent=pl.col("object_type_agent").shift(-1),
            next_agent_id=pl.col("object_id_agent").shift(-1)
        ).with_columns(
            handover_flag=
            (
                (pl.col("event_type") == "call_llm") &
                (pl.col("next_event_type") == "call_llm") &
                (pl.col("object_type_agent") != pl.col("next_agent"))
            )
        )
    )

    cols_to_keep = ["index", "case_id", "ocel_time", "event_id", "event_type", "object_type_agent", "object_id_agent", "duration", "model", "input_tokens", "response_tokens"]

    rows_to_insert_one_direction = (
        el_enriched
        .filter(pl.col("handover_flag"))
        .with_columns(
            index=(pl.col("index") + 0.5),
            ocel_time=pl.col("ocel_time")+ pl.duration(nanoseconds=1),
            event_type=pl.col("object_type_agent")+"_handover_"+pl.col("next_agent"),
            object_type_agent=pl.col("object_type_agent"),
            object_id_agent=pl.col("object_id_agent"),
        )
        .with_columns(
            pl.all().exclude(cols_to_keep).map_elements(lambda _: None)
        )
    )

    rows_to_insert_second_direction = (
        el_enriched
        .filter(pl.col("handover_flag"))
        .with_columns(
            index=(pl.col("index") + 0.5),
            ocel_time=pl.col("ocel_time")+ pl.duration(nanoseconds=1),
            event_type=pl.col("object_type_agent")+"_handover_"+pl.col("next_agent"),
            object_type_agent=pl.col("next_agent"),
            object_id_agent=pl.col("next_agent_id"),
        )
        .with_columns(
            pl.all().exclude(cols_to_keep).map_elements(lambda _: None)
        )
    )

    el_enriched = (
        pl.concat([
            el_enriched.filter(pl.col("handover_flag") == False),
            rows_to_insert_one_direction,
            rows_to_insert_second_direction
        ])
        .sort("index")
    )

    return el_enriched
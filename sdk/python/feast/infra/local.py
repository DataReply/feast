import os
import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd
import pytz

from feast import FeatureTable, utils
from feast.feature_view import FeatureView
from feast.infra.key_encoding_utils import serialize_entity_key
from feast.infra.offline_stores.helpers import get_offline_store_from_sources
from feast.infra.provider import (
    Provider,
    RetrievalJob,
    _convert_arrow_to_proto,
    _get_column_names,
    _run_field_mapping,
)
from feast.protos.feast.types.EntityKey_pb2 import EntityKey as EntityKeyProto
from feast.protos.feast.types.Value_pb2 import Value as ValueProto
from feast.registry import Registry
from feast.repo_config import LocalOnlineStoreConfig, RepoConfig


class LocalProvider(Provider):
    _db_path: str

    def __init__(self, config: LocalOnlineStoreConfig):
        self._db_path = config.path

    def _get_conn(self):
        return sqlite3.connect(
            self._db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )

    def update_infra(
        self,
        project: str,
        tables_to_delete: Sequence[Union[FeatureTable, FeatureView]],
        tables_to_keep: Sequence[Union[FeatureTable, FeatureView]],
        partial: bool,
    ):
        conn = self._get_conn()
        for table in tables_to_keep:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {_table_id(project, table)} (entity_key BLOB, feature_name TEXT, value BLOB, event_ts timestamp, created_ts timestamp,  PRIMARY KEY(entity_key, feature_name))"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {_table_id(project, table)}_ek ON {_table_id(project, table)} (entity_key);"
            )

        for table in tables_to_delete:
            conn.execute(f"DROP TABLE IF EXISTS {_table_id(project, table)}")

    def teardown_infra(
        self, project: str, tables: Sequence[Union[FeatureTable, FeatureView]]
    ) -> None:
        os.unlink(self._db_path)

    def online_write_batch(
        self,
        project: str,
        table: Union[FeatureTable, FeatureView],
        data: List[
            Tuple[EntityKeyProto, Dict[str, ValueProto], datetime, Optional[datetime]]
        ],
        progress: Optional[Callable[[int], Any]],
    ) -> None:
        conn = self._get_conn()

        with conn:
            for entity_key, values, timestamp, created_ts in data:
                entity_key_bin = serialize_entity_key(entity_key)
                timestamp = _to_naive_utc(timestamp)
                if created_ts is not None:
                    created_ts = _to_naive_utc(created_ts)

                for feature_name, val in values.items():
                    conn.execute(
                        f"""
                            UPDATE {_table_id(project, table)}
                            SET value = ?, event_ts = ?, created_ts = ?
                            WHERE (event_ts < ? OR (event_ts = ? AND (created_ts IS NULL OR ? IS NULL OR created_ts < ?)))
                            AND (entity_key = ? AND feature_name = ?)
                        """,
                        (
                            # SET
                            val.SerializeToString(),
                            timestamp,
                            created_ts,
                            # WHERE
                            timestamp,
                            timestamp,
                            created_ts,
                            created_ts,
                            entity_key_bin,
                            feature_name,
                        ),
                    )

                    conn.execute(
                        f"""INSERT OR IGNORE INTO {_table_id(project, table)}
                            (entity_key, feature_name, value, event_ts, created_ts)
                            VALUES (?, ?, ?, ?, ?)""",
                        (
                            entity_key_bin,
                            feature_name,
                            val.SerializeToString(),
                            timestamp,
                            created_ts,
                        ),
                    )

    def online_read(
        self,
        project: str,
        table: Union[FeatureTable, FeatureView],
        entity_keys: List[EntityKeyProto],
    ) -> List[Tuple[Optional[datetime], Optional[Dict[str, ValueProto]]]]:

        conn = self._get_conn()
        cur = conn.cursor()

        result: List[Tuple[Optional[datetime], Optional[Dict[str, ValueProto]]]] = []

        for entity_key in entity_keys:
            entity_key_bin = serialize_entity_key(entity_key)

            cur.execute(
                f"SELECT feature_name, value, event_ts FROM {_table_id(project, table)} WHERE entity_key = ?",
                (entity_key_bin,),
            )

            res = {}
            res_ts = None
            for feature_name, val_bin, ts in cur.fetchall():
                val = ValueProto()
                val.ParseFromString(val_bin)
                res[feature_name] = val
                res_ts = ts

            if not res:
                result.append((None, None))
            else:
                result.append((res_ts, res))
        return result

    def materialize_single_feature_view(
        self,
        feature_view: FeatureView,
        start_date: datetime,
        end_date: datetime,
        registry: Registry,
        project: str,
    ) -> None:
        entities = []
        for entity_name in feature_view.entities:
            entities.append(registry.get_entity(entity_name, project))

        (
            join_key_columns,
            feature_name_columns,
            event_timestamp_column,
            created_timestamp_column,
        ) = _get_column_names(feature_view, entities)

        start_date = utils.make_tzaware(start_date)
        end_date = utils.make_tzaware(end_date)

        offline_store = get_offline_store_from_sources([feature_view.input])
        table = offline_store.pull_latest_from_table_or_query(
            data_source=feature_view.input,
            join_key_columns=join_key_columns,
            feature_name_columns=feature_name_columns,
            event_timestamp_column=event_timestamp_column,
            created_timestamp_column=created_timestamp_column,
            start_date=start_date,
            end_date=end_date,
        )

        if feature_view.input.field_mapping is not None:
            table = _run_field_mapping(table, feature_view.input.field_mapping)

        join_keys = [entity.join_key for entity in entities]
        rows_to_write = _convert_arrow_to_proto(table, feature_view, join_keys)

        self.online_write_batch(project, feature_view, rows_to_write, None)

        feature_view.materialization_intervals.append((start_date, end_date))
        registry.apply_feature_view(feature_view, project)

    @staticmethod
    def get_historical_features(
        config: RepoConfig,
        feature_views: List[FeatureView],
        feature_refs: List[str],
        entity_df: Union[pd.DataFrame, str],
        registry: Registry,
        project: str,
    ) -> RetrievalJob:
        offline_store = get_offline_store_from_sources(
            [feature_view.input for feature_view in feature_views]
        )
        return offline_store.get_historical_features(
            config=config,
            feature_views=feature_views,
            feature_refs=feature_refs,
            entity_df=entity_df,
            registry=registry,
            project=project,
        )


def _table_id(project: str, table: Union[FeatureTable, FeatureView]) -> str:
    return f"{project}_{table.name}"


def _to_naive_utc(ts: datetime):
    if ts.tzinfo is None:
        return ts
    else:
        return ts.astimezone(pytz.utc).replace(tzinfo=None)

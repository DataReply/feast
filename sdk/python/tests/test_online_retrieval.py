import os
import time
from datetime import datetime

import pytest

from feast import FeatureStore, RepoConfig
from feast.protos.feast.types.EntityKey_pb2 import EntityKey as EntityKeyProto
from feast.protos.feast.types.Value_pb2 import Value as ValueProto
from feast.repo_config import RegistryConfig
from tests.cli_utils import CliRunner, get_example_repo


def test_online() -> None:
    """
    Test reading from the online store in local mode.
    """
    runner = CliRunner()
    with runner.local_repo(get_example_repo("example_feature_repo_1.py")) as store:
        # Write some data to two tables

        driver_locations_fv = store.get_feature_view(name="driver_locations")
        customer_profile_fv = store.get_feature_view(name="customer_profile")
        customer_driver_combined_fv = store.get_feature_view(
            name="customer_driver_combined"
        )

        provider = store._get_provider()

        driver_key = EntityKeyProto(
            join_keys=["driver"], entity_values=[ValueProto(int64_val=1)]
        )
        provider.online_write_batch(
            project=store.config.project,
            table=driver_locations_fv,
            data=[
                (
                    driver_key,
                    {
                        "lat": ValueProto(double_val=0.1),
                        "lon": ValueProto(string_val="1.0"),
                    },
                    datetime.utcnow(),
                    datetime.utcnow(),
                )
            ],
            progress=None,
        )

        customer_key = EntityKeyProto(
            join_keys=["customer"], entity_values=[ValueProto(int64_val=5)]
        )
        provider.online_write_batch(
            project=store.config.project,
            table=customer_profile_fv,
            data=[
                (
                    customer_key,
                    {
                        "avg_orders_day": ValueProto(float_val=1.0),
                        "name": ValueProto(string_val="John"),
                        "age": ValueProto(int64_val=3),
                    },
                    datetime.utcnow(),
                    datetime.utcnow(),
                )
            ],
            progress=None,
        )

        customer_key = EntityKeyProto(
            join_keys=["customer", "driver"],
            entity_values=[ValueProto(int64_val=5), ValueProto(int64_val=1)],
        )
        provider.online_write_batch(
            project=store.config.project,
            table=customer_driver_combined_fv,
            data=[
                (
                    customer_key,
                    {"trips": ValueProto(int64_val=7)},
                    datetime.utcnow(),
                    datetime.utcnow(),
                )
            ],
            progress=None,
        )

        # Retrieve two features using two keys, one valid one non-existing
        result = store.get_online_features(
            feature_refs=[
                "driver_locations:lon",
                "customer_profile:avg_orders_day",
                "customer_profile:name",
                "customer_driver_combined:trips",
            ],
            entity_rows=[{"driver": 1, "customer": 5}, {"driver": 1, "customer": 5}],
        ).to_dict()

        assert "driver_locations__lon" in result
        assert "customer_profile__avg_orders_day" in result
        assert "customer_profile__name" in result
        assert result["driver"] == [1, 1]
        assert result["customer"] == [5, 5]
        assert result["driver_locations__lon"] == ["1.0", "1.0"]
        assert result["customer_profile__avg_orders_day"] == [1.0, 1.0]
        assert result["customer_profile__name"] == ["John", "John"]
        assert result["customer_driver_combined__trips"] == [7, 7]

        # invalid table reference
        with pytest.raises(ValueError):
            store.get_online_features(
                feature_refs=["driver_locations_bad:lon"], entity_rows=[{"driver": 1}],
            )

        # Create new FeatureStore object with fast cache invalidation
        cache_ttl = 1
        fs_fast_ttl = FeatureStore(
            config=RepoConfig(
                registry=RegistryConfig(
                    path=store.config.registry, cache_ttl_seconds=cache_ttl
                ),
                online_store=store.config.online_store,
                project=store.config.project,
                provider=store.config.provider,
            )
        )

        # Should download the registry and cache it permanently (or until manually refreshed)
        result = fs_fast_ttl.get_online_features(
            feature_refs=[
                "driver_locations:lon",
                "customer_profile:avg_orders_day",
                "customer_profile:name",
                "customer_driver_combined:trips",
            ],
            entity_rows=[{"driver": 1, "customer": 5}],
        ).to_dict()
        assert result["driver_locations__lon"] == ["1.0"]
        assert result["customer_driver_combined__trips"] == [7]

        # Rename the registry.db so that it cant be used for refreshes
        os.rename(store.config.registry, store.config.registry + "_fake")

        # Wait for registry to expire
        time.sleep(cache_ttl)

        # Will try to reload registry because it has expired (it will fail because we deleted the actual registry file)
        with pytest.raises(FileNotFoundError):
            fs_fast_ttl.get_online_features(
                feature_refs=[
                    "driver_locations:lon",
                    "customer_profile:avg_orders_day",
                    "customer_profile:name",
                    "customer_driver_combined:trips",
                ],
                entity_rows=[{"driver": 1, "customer": 5}],
            ).to_dict()

        # Restore registry.db so that we can see if it actually reloads registry
        os.rename(store.config.registry + "_fake", store.config.registry)

        # Test if registry is actually reloaded and whether results return
        result = fs_fast_ttl.get_online_features(
            feature_refs=[
                "driver_locations:lon",
                "customer_profile:avg_orders_day",
                "customer_profile:name",
                "customer_driver_combined:trips",
            ],
            entity_rows=[{"driver": 1, "customer": 5}],
        ).to_dict()
        assert result["driver_locations__lon"] == ["1.0"]
        assert result["customer_driver_combined__trips"] == [7]

        # Create a registry with infinite cache (for users that want to manually refresh the registry)
        fs_infinite_ttl = FeatureStore(
            config=RepoConfig(
                registry=RegistryConfig(
                    path=store.config.registry, cache_ttl_seconds=0
                ),
                online_store=store.config.online_store,
                project=store.config.project,
                provider=store.config.provider,
            )
        )

        # Should return results (and fill the registry cache)
        result = fs_infinite_ttl.get_online_features(
            feature_refs=[
                "driver_locations:lon",
                "customer_profile:avg_orders_day",
                "customer_profile:name",
                "customer_driver_combined:trips",
            ],
            entity_rows=[{"driver": 1, "customer": 5}],
        ).to_dict()
        assert result["driver_locations__lon"] == ["1.0"]
        assert result["customer_driver_combined__trips"] == [7]

        # Wait a bit so that an arbitrary TTL would take effect
        time.sleep(2)

        # Rename the registry.db so that it cant be used for refreshes
        os.rename(store.config.registry, store.config.registry + "_fake")

        # TTL is infinite so this method should use registry cache
        result = fs_infinite_ttl.get_online_features(
            feature_refs=[
                "driver_locations:lon",
                "customer_profile:avg_orders_day",
                "customer_profile:name",
                "customer_driver_combined:trips",
            ],
            entity_rows=[{"driver": 1, "customer": 5}],
        ).to_dict()
        assert result["driver_locations__lon"] == ["1.0"]
        assert result["customer_driver_combined__trips"] == [7]

        # Force registry reload (should fail because file is missing)
        with pytest.raises(FileNotFoundError):
            fs_infinite_ttl.refresh_registry()

        # Restore registry.db so that teardown works
        os.rename(store.config.registry + "_fake", store.config.registry)

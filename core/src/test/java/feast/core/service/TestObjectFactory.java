/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright 2018-2020 The Feast Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package feast.core.service;

import feast.core.model.*;
import feast.proto.core.FeatureSetProto;
import feast.proto.core.SourceProto;
import feast.proto.types.ValueProto;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public class TestObjectFactory {

  public static Source defaultSource =
      new Source(
          SourceProto.SourceType.KAFKA,
          SourceProto.KafkaSourceConfig.newBuilder()
              .setBootstrapServers("kafka:9092")
              .setTopic("my-topic")
              .build(),
          true);

  public static FeatureSet CreateFeatureSet(
      String name, String project, List<Entity> entities, List<Feature> features) {
    FeatureSet fs =
        new FeatureSet(
            name,
            project,
            100L,
            entities,
            features,
            defaultSource,
            new HashMap<>(),
            FeatureSetProto.FeatureSetStatus.STATUS_READY);
    fs.setVersion(1);
    return fs;
  }

  public static Feature CreateFeature(
      String name, ValueProto.ValueType.Enum valueType, Map<String, String> labels) {
    return Feature.fromProto(
        FeatureSetProto.FeatureSpec.newBuilder()
            .setName(name)
            .setValueType(valueType)
            .putAllLabels(labels)
            .build());
  }

  public static Feature CreateFeature(String name, ValueProto.ValueType.Enum valueType) {
    return Feature.fromProto(
        FeatureSetProto.FeatureSpec.newBuilder().setName(name).setValueType(valueType).build());
  }

  public static Entity CreateEntity(String name, ValueProto.ValueType.Enum valueType) {
    return Entity.fromProto(
        FeatureSetProto.EntitySpec.newBuilder().setName(name).setValueType(valueType).build());
  }

  public static FeatureSetJobStatus CreateFeatureSetJobStatusWithJob(
      JobStatus status, FeatureSetProto.FeatureSetJobDeliveryStatus deliveryStatus, int version) {
    Job job = new Job();
    job.setStatus(status);
    job.setId(UUID.randomUUID().toString());

    FeatureSetJobStatus featureSetJobStatus = new FeatureSetJobStatus();
    featureSetJobStatus.setJob(job);

    featureSetJobStatus.setDeliveryStatus(deliveryStatus);
    featureSetJobStatus.setVersion(version);

    return featureSetJobStatus;
  }
}

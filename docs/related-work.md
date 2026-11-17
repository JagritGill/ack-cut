# Research and provenance

Researched 2026-11-17, before application implementation. Searches included:

- `Kafka consumer out of order processing commit offsets gap audit offline simulator tool github`
- `Kafka parallel consumer offset commit watermark unprocessed messages visualizer`
- `"Kafka" "offline" "commit" "audit" offsets tool`
- `github Kafka "offset" "simulator" "commit" audit`
- `"Kafka" "commit" "crash" "trace" checker offline`
- `"ack-cut" github`

The local project catalog and public personal repository names were checked.
Search is not proof of worldwide novelty or repository-name availability.

## Closest documented alternatives

| Primary source | Material overlap | Deliberate scope here |
| --- | --- | --- |
| [Confluent Parallel Consumer](https://github.com/confluentinc/parallel-consumer) | Concurrent processing, acknowledgments and safe commit management. Its offset-map metadata can preserve out-of-order completion information across recovery. | Inspect a supplied trace using an ordinary scalar committed offset, with no client, concurrency engine or offset-map metadata support. The replay counts would not model that library's enhanced recovery. |
| [SmallRye receiving Kafka records](https://smallrye.io/smallrye-reactive-messaging/4.28.0/kafka/receiving-kafka-records/) | Documents throttled/ordered acknowledgment commits, latest acknowledgment behavior and crash replay tradeoffs. | Explain each supplied commit and selected hypothetical crash cut, rather than implement a live connector strategy. These are established safety concepts. |
| [Smart Commit Kafka Consumer](https://github.com/sahabpardaz/smart-commit-kafka-consumer) | Tracks record acknowledgments and commits completed consecutive pages. | Offline record-level evidence and a CLI gate; no wrapper or actual commits. No implementation or GPL-licensed code is reused. |
| [Monedula Kafka Simulator](https://monedula.dev/kafka-simulator/) | Browser-based deterministic educational scenarios, including consumers, restarts and many broker behaviors. | A narrow JSON trace audit of one partition/assignment, suitable for checked-in regression fixtures; no cluster simulation or browser UI. We did not test feature completeness. |

These tools substantially overlap in explaining or managing commit safety. This
project's value is its small explicit input contract and reviewable evidence:
distinguish unfinished records below the restart offset from completed records
that would replay, retain historical unsafe commits, and handle sparse delivered
offsets using an explicit next consumer position. This is not a novel commit
algorithm or a claim that no other tool offers this analysis.

## Semantic references

[Apache Kafka 4.1.2 KafkaConsumer API](https://kafka.apache.org/41/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html)
documents separate consumer and committed positions, nonconsecutive record offsets,
and using the next record/nextOffsets for commits. These facts motivate the model;
we do not emulate the Kafka protocol or certify a Kafka configuration. The
[awesome-kafka directory](https://github.com/conduktor/awesome-kafka) helped discover
the simulator; its own official page was then read.

Only primary documentation/READMEs were consulted. No comparator implementation,
fixture, test or prose was copied or translated. Original runtime code, synthetic
traces and tests are written from scratch with AI assistance. Python's standard
library supplies parsing and containers. Previously verified portfolio CI pins
and release conventions are reused with [attribution](../NOTICE.md).

The key demonstration delivers offsets 100, 104 and 105, completes only 105, then
stores 106. A crash cut exposes two unfinished skipped records, not six imagined
missing integer offsets. Later completions repair the current cut but cannot erase
the earlier unsafe commit. See [architecture](architecture.md) for assumptions.

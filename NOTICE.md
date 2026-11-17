# Attribution

Original project files use [MIT](LICENSE). The implementation, synthetic traces,
tests and documentation were created from scratch with AI assistance. There is
no claim of sole human authorship, novel commit algorithms or worldwide uniqueness.

Runtime uses Python's standard library under the
[Python license](https://docs.python.org/3/license.html); Python is not vendored
or relicensed. No third-party runtime packages or assets are included. Related
tools and semantic sources are credited in [research](docs/related-work.md).
In particular, no code from the GPL-licensed Smart Commit Kafka Consumer is used.

CI references [actions/checkout](https://github.com/actions/checkout) and
[actions/setup-python](https://github.com/actions/setup-python), each MIT-licensed
upstream. Full commit pins come from previously verified portfolio workflows;
actions are not vendored or relicensed. Routine release-check conventions follow
the existing portfolio workflow, independently written here. No earlier project's
substantive application implementation was reused.

Apache Kafka is a trademark of the Apache Software Foundation. This project is
independent and not endorsed by it. The project performs no Kafka integration.
Workflow configuration is not a CI result; verify the actual run and commit.

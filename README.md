# AppWren

**Know every application, and what to do with it.**

AppWren is an open system of record for application portfolio management: one living record of every application an organization runs, who answers for it, what it is for, what it is built on, what it costs, and how healthy it is, turned into an explainable recommendation for each one: invest, maintain, tolerate, modernize, replace, consolidate, or retire.

It is built with particular care for research and health organizations that are not large corporations: research institutes, academic medical centers, universities, and the nonprofits around them, where software comes from vendors, central IT, and labs alike. Within them it is built first for the product, application, and engineering teams who own the software. Nothing in it is specific to either, and any organization that wants a lightweight, self-hosted portfolio system can adopt it.

- **The reasoning is on the screen.** Every score opens to its factors, levels, weights, and sources, and every recommendation to the rule that produced it.
- **People decide.** The system recommends; a named person records the disposition and why. Where they differ, both are shown.
- **Unknown is not zero.** Missing data is counted against confidence, never assumed, and too little of it means *Assess*, not a guess.
- **One definition of an application.** Applications, their components, and their deployments are separate records, so the portfolio compares like with like.
- **Judged by the right rubric.** A pilot is not judged like a system of record, nor research software like a commercial product.
- **Research-ready.** Grant funding and end dates, research continuity, research data classes, and single-maintainer risk are built in.
- **A history that cannot be quietly changed.** Every change is in an append-only, hash-chained log.
- **Quiet by default.** No scanners or agents; connectors to other tools only when an administrator turns them on.
- **Open and yours.** Apache 2.0, no paid edition, SQLite on a laptop or PostgreSQL on a server, and your own name and colors.

## Status

AppWren is at the start of its build. The plan is public:

- [What it is and who it is for](spec/vision.md)
- [How the scores and recommendations work](spec/engine.md)
- [The roadmap](spec/roadmap.md), in waves that each end in a release
- [Everything else in the specification](spec/README.md)

Installation instructions arrive with the first release.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

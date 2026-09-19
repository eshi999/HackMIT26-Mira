"""python -m mira.evaluation"""

from __future__ import annotations

from mira.core.db import create_schema, get_engine, get_sessionmaker, reset_engine
from mira.evaluation.harness import print_report, run_precedent_evaluation
from mira.seed.northstar import AS_OF, seed_northstar


def main() -> None:
    reset_engine()
    url = "sqlite:///./data/mira-eval.db"
    engine = get_engine(url)
    create_schema(engine)
    Session = get_sessionmaker(url)
    session = Session()
    try:
        seed_northstar(session)
        session.commit()
        report = run_precedent_evaluation(session, AS_OF.date())
        session.commit()
        print_report(report)
    finally:
        session.close()
        reset_engine()


if __name__ == "__main__":
    main()
